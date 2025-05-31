from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from src.models.user import User
from src.services.security_service import SecurityService
from src.services.statistic_service import StatisticService


class UserService:
    """CRUD operations service for User model"""

    @staticmethod
    async def create(
        db: AsyncSession,
        email: str,
        username: str,
        password: str,
        is_active: bool = True,
        is_superuser: bool = False
    ) -> User:
        """Create a new user"""
        # Hash the password
        hashed_password = SecurityService.create_password_hash(password)
        
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            is_active=is_active,
            is_superuser=is_superuser
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """Get user by id"""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_email(
        db: AsyncSession,
        email: str
    ) -> Optional[User]:
        """Get user by email"""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_username(
        db: AsyncSession,
        username: str
    ) -> Optional[User]:
        """Get user by username"""
        query = select(User).where(User.username == username)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get all users with pagination"""
        query = select(User).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        user_id: int,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None
    ) -> Optional[User]:
        """Update a user's details"""
        update_data = {}
        if email is not None:
            update_data["email"] = email
        if username is not None:
            update_data["username"] = username
        if password is not None:
            update_data["hashed_password"] = SecurityService.create_password_hash(password)
        if is_active is not None:
            update_data["is_active"] = is_active
        if is_superuser is not None:
            update_data["is_superuser"] = is_superuser
            
        if not update_data:
            return await UserService.get_by_id(db, user_id)
            
        stmt = update(User).where(User.id == user_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        return await UserService.get_by_id(db, user_id)

    @staticmethod
    async def delete(
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """Delete a user"""
        stmt = delete(User).where(User.id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def track_user_activity(db: AsyncSession, user_id: int) -> None:
        """Отслеживание активности пользователя для статистики"""
        # Убедимся, что пользователь существует
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return
            
        # Обновляем статистику активных пользователей
        await StatisticService.track_active_user(db, user_id) 