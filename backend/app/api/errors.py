from typing import Any

from fastapi import HTTPException


def api_error(status: int, code: str, message: str, details: Any = None) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, "details": details}})

