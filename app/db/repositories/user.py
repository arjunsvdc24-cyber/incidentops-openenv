"""
IncidentOps - User Repository
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.schemas import UserCreate


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: UserCreate) -> User:
        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            api_key=generate_api_key(),
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_api_key(self, api_key: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.get_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def update_last_seen(self, user_id: int) -> None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.last_seen = datetime.now(timezone.utc)

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self.session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
