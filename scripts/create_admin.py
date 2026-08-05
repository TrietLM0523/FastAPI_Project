import argparse
import asyncio
import getpass

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import UserRole
from app.repositories.user import UserRepository


async def create_admin(email: str, full_name: str, password: str) -> None:
    async with async_session_factory() as session:
        repository = UserRepository(session)

        if await repository.get_by_email(email) is not None:
            raise ValueError("A user with this email already exists")

        await repository.create(
            {
                "email": email,
                "full_name": full_name,
                "hashed_password": hash_password(password),
                "role": UserRole.ADMIN,
                "is_active": True,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an administrator account")
    parser.add_argument("email")
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        raise ValueError("Passwords do not match")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")

    asyncio.run(create_admin(args.email, args.full_name, password))
    print(f"Administrator created: {args.email}")


if __name__ == "__main__":
    main()
