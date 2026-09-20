"""Unit tests: no database, no HTTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.enums import CaseStatus
from app.services.pdf import simple_pdf
from app.services.sla import sla_state
from app.services.storage import LocalStorage, safe_filename


class TestPasswords:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("Wathiq!Demo2026")
        assert hashed != "Wathiq!Demo2026"
        assert verify_password("Wathiq!Demo2026", hashed)
        assert not verify_password("wrong", hashed)

    def test_rejects_overlong_password(self) -> None:
        with pytest.raises(ValueError):
            hash_password("x" * 80)

    def test_verify_survives_a_malformed_hash(self) -> None:
        assert not verify_password("anything", "not-a-bcrypt-hash")


class TestTokens:
    def test_round_trip(self) -> None:
        user_id = uuid4()
        token = create_access_token(user_id=user_id, email="a@b.demo", role="reviewer")
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "reviewer"
        assert payload["iss"] == "wathiq"

    def test_rejects_tampered_token(self) -> None:
        import jwt

        token = create_access_token(user_id=uuid4(), email="a@b.demo", role="admin")
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb"))


class TestSla:
    def test_no_due_date_is_none(self) -> None:
        assert sla_state(None) == "none"

    def test_terminal_case_has_no_sla(self) -> None:
        past = datetime.now(UTC) - timedelta(hours=1)
        assert sla_state(past, status=CaseStatus.completed) == "none"

    def test_past_due_is_breached(self) -> None:
        assert sla_state(datetime.now(UTC) - timedelta(minutes=1)) == "breached"

    def test_close_to_due_is_at_risk(self) -> None:
        assert sla_state(datetime.now(UTC) + timedelta(minutes=10)) == "at_risk"

    def test_far_from_due_is_on_track(self) -> None:
        assert sla_state(datetime.now(UTC) + timedelta(hours=10)) == "on_track"


class TestStorage:
    def test_round_trip(self, tmp_path) -> None:
        storage = LocalStorage(tmp_path)
        case_id = uuid4()
        path = storage.save(case_id, "trade licence.pdf", b"hello")
        assert storage.exists(path)
        assert storage.read(path) == b"hello"

    def test_filename_is_sanitised(self) -> None:
        assert safe_filename("../../etc/passwd") == ".._.._etc_passwd"
        assert safe_filename("   ") == "document"

    def test_path_traversal_is_refused(self, tmp_path) -> None:
        storage = LocalStorage(tmp_path)
        assert storage.exists("../../etc/passwd") is False
        with pytest.raises(ValueError):
            storage.read("../../etc/passwd")


class TestPdf:
    def test_produces_a_valid_looking_pdf(self) -> None:
        data = simple_pdf("Trade licence", [("Licence number", "CN-1234567")], "synthetic")
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")
        assert b"CN-1234567" in data

    def test_escapes_parentheses(self) -> None:
        data = simple_pdf("T", [("Name", "Falcon (Holdings) LLC")], "f")
        assert rb"Falcon \(Holdings\) LLC" in data

    def test_non_latin_text_does_not_break_the_file(self) -> None:
        data = simple_pdf("الرخصة التجارية", [("اسم", "شركة")], "synthetic")
        assert data.startswith(b"%PDF-1.4")
