"""Reject oversized bodies before multipart parsing consumes an unbounded upload."""

from fastapi import HTTPException
from starlette.responses import JSONResponse

from .config import get_settings


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        maximum = (
            get_settings().max_upload_bytes + 65536
            if scope.get("path") == "/datasets/ingest"
            else 65536
        )
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid content length"}, 400)(
                scope, receive, send
            )
        if length > maximum:
            return await JSONResponse({"detail": "Request body exceeds configured limit"}, 413)(
                scope, receive, send
            )
        used = 0

        async def limited_receive():
            nonlocal used
            message = await receive()
            if message["type"] == "http.request":
                used += len(message.get("body", b""))
                if used > maximum:
                    raise HTTPException(413, "Request body exceeds configured limit")
            return message

        await self.app(scope, limited_receive, send)
