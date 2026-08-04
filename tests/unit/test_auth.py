import pytest

from app.auth.password import hash_password, validate_password_strength, verify_password


def test_argon2_password_hash_and_verify() -> None:
    encoded = hash_password("Example123")
    assert encoded.startswith("$argon2")
    assert "Example123" not in encoded
    assert verify_password(encoded, "Example123")
    assert not verify_password(encoded, "Wrong123")


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678", "        "])
def test_password_strength_rejects_weak_values(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_strength(password)

