import hashlib
import re
from typing import List

from src.core.config import ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip().lower()))


def valid_password_strength(password: str) -> bool:
    return len(password) >= 8 and any(c.isupper() for c in password) and any(c.isdigit() for c in password)


def validate_files(uploaded_files: List):
    for f in uploaded_files or []:
        if f.type and f.type not in ALLOWED_MIME_TYPES:
            return False, f"Tipo de arquivo não permitido: {f.name}"
        if len(f.getvalue()) > MAX_FILE_SIZE_BYTES:
            return False, f"Arquivo excede 5MB: {f.name}"
    return True, ""
