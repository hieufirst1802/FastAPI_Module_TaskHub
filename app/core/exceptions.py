from fastapi import Request, status
from fastapi.responses import JSONResponse


class NotFoundException(Exception):
    pass


async def handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
