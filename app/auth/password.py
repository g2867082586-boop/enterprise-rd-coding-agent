import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)


def validate_password_strength(password: str) -> None:
    if not 8 <= len(password) <= 128:
        raise ValueError("密码长度必须为 8 到 128 位")
    if not password.strip():
        raise ValueError("密码不能仅包含空格")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("密码必须同时包含字母和数字")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

