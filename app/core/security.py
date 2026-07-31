from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Convert a plaintext password into a secure hash."""
    return password_hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Check whether a plaintext password matches a stored hash."""
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )
