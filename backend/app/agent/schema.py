"""Building a Pydantic model from a document type's field schema, at runtime.

The document types are configuration (rows in `document_types`), so the model that validates an
extraction cannot be written by hand — it has to be built from the schema. `pydantic.create_model`
does that, and the result is a real Pydantic model: the same validation that guards the API
guards the extractor's output.

This is the contract that makes self-correction possible. The worker does not ask "does this
look right?"; it validates against the model, and each `ValidationError` names a field and says
what was wrong with it. That error is what the repair pass acts on, which is why a repair can
be targeted at one field instead of re-reading the whole document.

In Azure mode (M6) the same model is handed to the Foundry deployment as a structured-output
schema, so the model is asked to produce exactly this shape and the validation below is the
second line of defence rather than the first.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model, field_validator

from app.agent.extractor import parse_date

_NUMBER = re.compile(r"^-?[\d,]+(\.\d+)?$")
_CURRENCY = re.compile(r"\b(aed|usd|dhs|dirhams?)\b", re.IGNORECASE)


class FieldError(BaseModel):
    """One validation failure, in the form the repair pass consumes."""

    field: str
    kind: str
    message: str


def _clean_number(value: str) -> str | None:
    stripped = _CURRENCY.sub("", value).replace(",", "").strip()
    return stripped if _NUMBER.match(stripped) else None


def build_model(doc_type: str, field_schema: list[dict[str, Any]]) -> type[BaseModel]:
    """A Pydantic model for one document type's fields.

    Every field is optional at the type level: a document that does not contain a value must
    produce `None`, not a made-up value. "Required" is checked separately, as a rule, so the
    reviewer sees "licence number missing" as a finding rather than as a crash.
    """
    definitions: dict[str, Any] = {}
    validators: dict[str, Any] = {}

    for spec in field_schema:
        name = str(spec["name"])
        kind = str(spec.get("type", "string"))
        definitions[name] = (str | None, None)

        if kind == "date":
            validators[f"_check_{name}"] = field_validator(name)(_date_validator)
        elif kind == "number":
            validators[f"_check_{name}"] = field_validator(name)(_number_validator)

    model = create_model(
        f"{doc_type.title().replace('_', '')}Extraction",
        __config__=ConfigDict(extra="forbid", str_strip_whitespace=True),
        __validators__=validators,
        **definitions,
    )
    return model


def _date_validator(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if parse_date(value) is None:
        raise ValueError("not a recognisable date (expected YYYY-MM-DD or DD/MM/YYYY)")
    return value


def _number_validator(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if _clean_number(value) is None:
        raise ValueError("not a number (digits, optional thousands separators and currency)")
    return value


def validate(
    model: type[BaseModel], values: dict[str, str | None]
) -> tuple[bool, list[FieldError]]:
    """Validate an extraction. Returns (ok, errors), never raises."""
    try:
        model(**values)
    except ValidationError as exc:
        errors = [
            FieldError(
                field=str(error["loc"][0]) if error["loc"] else "?",
                kind=str(error["type"]),
                message=str(error.get("msg", "")).removeprefix("Value error, "),
            )
            for error in exc.errors()
        ]
        return False, errors
    return True, []


def expected_types(field_schema: list[dict[str, Any]]) -> dict[str, str]:
    return {str(spec["name"]): str(spec.get("type", "string")) for spec in field_schema}


def required_fields(field_schema: list[dict[str, Any]]) -> set[str]:
    return {str(spec["name"]) for spec in field_schema if spec.get("required", True)}


def json_schema(doc_type: str, field_schema: list[dict[str, Any]]) -> dict[str, Any]:
    """The JSON schema a structured-output call would send. Shown in the UI and the docs."""
    return build_model(doc_type, field_schema).model_json_schema()


__all__ = [
    "FieldError",
    "build_model",
    "expected_types",
    "json_schema",
    "required_fields",
    "validate",
]
