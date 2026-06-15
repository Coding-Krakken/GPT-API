from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_code_for_status(status_code: int, detail: Any = None) -> str:
    detail_text = str(detail or "").lower()
    if status_code == 403:
        if "missing" in detail_text and "api key" in detail_text:
            return "missing_api_key"
        return "invalid_api_key"
    if status_code == 404:
        return "route_not_found"
    if status_code == 405:
        return "method_not_allowed"
    if status_code == 422:
        return "validation_error"
    if status_code == 408:
        return "timeout"
    if status_code >= 500:
        return "execution_error"
    return "http_error"


def error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    hint: str | None = None,
    extra_error_fields: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        },
        "status": status_code,
    }
    if details is not None:
        body["error"]["details"] = details
    if hint:
        body["error"]["hint"] = hint
    if extra_error_fields:
        body["error"].update(extra_error_fields)
    return JSONResponse(status_code=status_code, content=body)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = getattr(exc, "detail", None)
    status_code = getattr(exc, "status_code", 500)
    message = detail if isinstance(detail, str) else "HTTP error"
    code = error_code_for_status(status_code, detail)
    hint = "Include x-api-key header." if code == "missing_api_key" else None
    return error_response(request=request, status_code=status_code, code=code, message=message, details=None if isinstance(detail, str) else detail, hint=hint)


async def fastapi_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return await http_exception_handler(request, exc)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request=request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        request=request,
        status_code=500,
        code="execution_error",
        message="Internal server error",
    )
