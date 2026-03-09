import re
from fastapi import HTTPException

COMMON_PASSWORDS = {"password", "password1", "123456789", "qwerty123", "iloveyou", "admin123"}

def validate_password(password: str) -> str:
    password = password.strip()
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters.")
    if not re.search(r"[A-Za-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one letter.")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if password.lower() in COMMON_PASSWORDS:
        raise HTTPException(status_code=400, detail="Password is too common. Choose a stronger one.")
    return password
