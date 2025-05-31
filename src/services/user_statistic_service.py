from typing import Optional, List
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func

from src.models.user_statistic import UserStatistic
from src.logs import debug_logger


class UserStatisticService:
    """Сервис для работы со статистикой пользователя"""

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int
    ) -> UserStatistic:
        """Создать запись статистики для пользователя"""
        statistic = UserStatistic(
            user_id=user_id,
            completed_tasks=0,
            active_days_streak=0,
            total_completed_tasks=0,
            total_created_tasks=0,
            total_comments=0
        )
        db.add(statistic)
        await db.commit()
        await db.refresh(statistic)
        return statistic

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Получить статистику пользователя по ID пользователя"""
        query = select(UserStatistic).where(UserStatistic.user_id == user_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_or_create(db: AsyncSession, user_id: int) -> UserStatistic:
        """Получить или создать запись статистики пользователя"""
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        if not stat:
            stat = await UserStatisticService.create(db, user_id)
        return stat

    @staticmethod
    async def increment_completed_tasks(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Увеличить счетчик выполненных задач пользователя"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Увеличиваем счетчики
        stmt = update(UserStatistic).where(UserStatistic.user_id == user_id).values(
            completed_tasks=UserStatistic.completed_tasks + 1,
            total_completed_tasks=UserStatistic.total_completed_tasks + 1
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Обновлен счетчик завершенных задач для пользователя {user_id}")
        return stat

    @staticmethod
    async def decrement_completed_tasks(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Уменьшить счетчик выполненных задач пользователя (когда задача снова становится невыполненной)"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Уменьшаем текущий счетчик, но не трогаем общую статистику
        stmt = update(UserStatistic).where(
            UserStatistic.user_id == user_id,
            UserStatistic.completed_tasks > 0  # Проверка, чтобы не уйти в отрицательные значения
        ).values(
            completed_tasks=UserStatistic.completed_tasks - 1
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Уменьшен счетчик активных завершенных задач для пользователя {user_id}")
        return stat

    @staticmethod
    async def increment_created_tasks(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Увеличить счетчик созданных задач пользователя"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Увеличиваем счетчик
        stmt = update(UserStatistic).where(UserStatistic.user_id == user_id).values(
            total_created_tasks=UserStatistic.total_created_tasks + 1
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Обновлен счетчик созданных задач для пользователя {user_id}")
        return stat

    @staticmethod
    async def increment_comments(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Увеличить счетчик комментариев пользователя"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Увеличиваем счетчик
        stmt = update(UserStatistic).where(UserStatistic.user_id == user_id).values(
            total_comments=UserStatistic.total_comments + 1
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Обновлен счетчик комментариев для пользователя {user_id}")
        return stat

    @staticmethod
    async def update_active_streak(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Обновить счетчик активных дней пользователя"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Увеличиваем счетчик
        stmt = update(UserStatistic).where(UserStatistic.user_id == user_id).values(
            active_days_streak=UserStatistic.active_days_streak + 1
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Обновлен счетчик активных дней для пользователя {user_id}")
        return stat

    @staticmethod
    async def reset_active_streak(db: AsyncSession, user_id: int) -> Optional[UserStatistic]:
        """Сбросить счетчик активных дней пользователя"""
        # Получаем или создаем запись статистики
        stat = await UserStatisticService.get_or_create(db, user_id)
        
        # Сбрасываем счетчик
        stmt = update(UserStatistic).where(UserStatistic.user_id == user_id).values(
            active_days_streak=0
        )
        await db.execute(stmt)
        await db.commit()
        
        # Обновляем объект статистики
        stat = await UserStatisticService.get_by_user_id(db, user_id)
        debug_logger.debug(f"Сброшен счетчик активных дней для пользователя {user_id}")
        return stat

    @staticmethod
    async def get_top_users_by_completed_tasks(db: AsyncSession, limit: int = 10) -> List[UserStatistic]:
        """Получить топ пользователей по количеству выполненных задач"""
        query = select(UserStatistic).order_by(UserStatistic.total_completed_tasks.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all()) 