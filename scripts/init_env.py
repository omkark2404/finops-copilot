"""Create local secrets without shell-sourcing environment files or printing credentials."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env already exists; preserving it. Check required values against .env.example.")
else:
    content = (root / ".env.example").read_text()
    for key in ["JWT_SECRET_KEY", "ADMIN_PASSWORD", "POSTGRES_PASSWORD"]:
        content = content.replace(key + "=\n", key + "=" + secrets.token_urlsafe(32) + "\n")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)
    print("Created private .env. Read ADMIN_EMAIL and ADMIN_PASSWORD locally to sign in.")
