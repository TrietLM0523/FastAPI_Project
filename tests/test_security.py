from app.core.security import hash_password, verify_password


def test_hash_password_does_not_store_plaintext() -> None:
    plain_password = "StrongPassword123!"

    hashed_password = hash_password(plain_password)

    assert hashed_password != plain_password
    assert verify_password(
        plain_password,
        hashed_password,
    )


def test_verify_password_rejects_wrong_password() -> None:
    hashed_password = hash_password(
        "CorrectPassword123!",
    )

    assert not verify_password(
        "WrongPassword123!",
        hashed_password,
    )
