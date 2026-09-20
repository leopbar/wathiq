"""Uniform error shape: {"detail": "<human message>", "code": "<MACHINE_CODE>"}."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


class NotFoundError(AppError):
    def __init__(self, what: str = "Resource") -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"{what} not found", "NOT_FOUND")


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Your role cannot perform this action") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, detail, "FORBIDDEN")


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Sign in to continue") -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, "UNAUTHORIZED")


class ConflictError(AppError):
    def __init__(self, detail: str, code: str = "CONFLICT") -> None:
        super().__init__(status.HTTP_409_CONFLICT, detail, code)


class ValidationError(AppError):
    # 422 spelled numerically: Starlette renamed the constant and deprecated the old name.
    def __init__(self, detail: str, code: str = "INVALID_INPUT") -> None:
        super().__init__(422, detail, code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": code},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
        return JSONResponse(
            status_code=422,
            content={
                "detail": f"{where}: {first.get('msg', 'invalid input')}",
                "code": "INVALID_INPUT",
            },
        )
