from typing import Optional, List
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func

from src.models.statistic import Statistic
from src.logs import debug_logger


class StatisticService:
    """Сервис для работы с агрегированной статистикой системы"""

    @staticmethod
    async def create(
        db: AsyncSession,
        stat_date: date,
        cards_created: int = 0,
        cards_completed: int = 0,
        comments_posted: int = 0,
        active_users: int = 0,
        notes: Optional[str] = None
    ) -> Statistic:
        statistic = Statistic(
            stat_date=stat_date,
            cards_created=cards_created,
            cards_completed=cards_completed,
            comments_posted=comments_posted,
            active_users=active_users,
            notes=notes
        )
        db.add(statistic)
        await db.commit()
        await db.refresh(statistic)
        return statistic

    @staticmethod
    async def get_by_id(db: AsyncSession, stat_id: int) -> Optional[Statistic]:
        query = select(Statistic).where(Statistic.id == stat_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_date(db: AsyncSession, stat_date: date) -> Optional[Statistic]:
        query = select(Statistic).where(Statistic.stat_date == stat_date)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_range(db: AsyncSession, date_from: date, date_to: date) -> List[Statistic]:
        query = select(Statistic).where(and_(Statistic.stat_date >= date_from, Statistic.stat_date <= date_to)).order_by(Statistic.stat_date)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        stat_id: int,
        cards_created: Optional[int] = None,
        cards_completed: Optional[int] = None,
        comments_posted: Optional[int] = None,
        active_users: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Optional[Statistic]:
        update_data = {}
        if cards_created is not None:
            update_data["cards_created"] = cards_created
        if cards_completed is not None:
            update_data["cards_completed"] = cards_completed
        if comments_posted is not None:
            update_data["comments_posted"] = comments_posted
        if active_users is not None:
            update_data["active_users"] = active_users
        if notes is not None:
            update_data["notes"] = notes
        if not update_data:
            return await StatisticService.get_by_id(db, stat_id)
        stmt = update(Statistic).where(Statistic.id == stat_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await StatisticService.get_by_id(db, stat_id)

    @staticmethod
    async def delete(db: AsyncSession, stat_id: int) -> bool:
        stmt = delete(Statistic).where(Statistic.id == stat_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    # --- Новые методы для автоматического сбора статистики ---

    @staticmethod
    async def get_or_create_current_stat(db: AsyncSession) -> Statistic:
        """Получить запись статистики за текущий день или создать новую"""
        today = date.today()
        stat = await StatisticService.get_by_date(db, today)
        
        if not stat:
            # Создаем новую запись за текущий день
            stat = await StatisticService.create(db, today)
            
        return stat

    @staticmethod
    async def increment_cards_created(db: AsyncSession) -> None:
        """Увеличить счетчик созданных карточек за текущий день"""
        today = date.today()
        stat = await StatisticService.get_by_date(db, today)
        
        if stat:
            # Обновляем существующую запись
            stmt = update(Statistic).where(Statistic.stat_date == today).values(
                cards_created=Statistic.cards_created + 1
            )
            await db.execute(stmt)
            await db.commit()
            debug_logger.debug(f"Обновлен счетчик созданных карточек за {today}")
        else:
            # Создаем новую запись
            await StatisticService.create(db, today, cards_created=1)

    @staticmethod
    async def increment_cards_completed(db: AsyncSession) -> None:
        """Увеличить счетчик завершенных карточек за текущий день"""
        today = date.today()
        stat = await StatisticService.get_by_date(db, today)
        
        if stat:
            # Обновляем существующую запись
            stmt = update(Statistic).where(Statistic.stat_date == today).values(
                cards_completed=Statistic.cards_completed + 1
            )
            await db.execute(stmt)
            await db.commit()
            debug_logger.debug(f"Обновлен счетчик завершенных карточек за {today}")
        else:
            # Создаем новую запись
            await StatisticService.create(db, today, cards_completed=1)

    @staticmethod
    async def increment_comments_posted(db: AsyncSession) -> None:
        """Увеличить счетчик опубликованных комментариев за текущий день"""
        today = date.today()
        stat = await StatisticService.get_by_date(db, today)
        
        if stat:
            # Обновляем существующую запись
            stmt = update(Statistic).where(Statistic.stat_date == today).values(
                comments_posted=Statistic.comments_posted + 1
            )
            await db.execute(stmt)
            await db.commit()
            debug_logger.debug(f"Обновлен счетчик комментариев за {today}")
        else:
            # Создаем новую запись
            await StatisticService.create(db, today, comments_posted=1)

    @staticmethod
    async def track_active_user(db: AsyncSession, user_id: int) -> None:
        """Отслеживание активного пользователя за текущий день"""
        today = date.today()
        
        # Получаем или создаем запись статистики за текущий день
        stat = await StatisticService.get_by_date(db, today)
        
        if not stat:
            # Если записи нет, создаем новую с одним активным пользователем
            await StatisticService.create(db, today, active_users=1)
            return
            
        # Подсчет активных пользователей должен вестись на уровне отдельной таблицы
        # для точности. Но для примера просто увеличиваем счетчик здесь
        await db.execute(
            update(Statistic)
            .where(Statistic.stat_date == today)
            .values(active_users=Statistic.active_users + 1)
        )
        await db.commit()
        debug_logger.debug(f"Отмечена активность пользователя {user_id} за {today}")

    @staticmethod
    async def update_stats_for_card_completion(db: AsyncSession, card_completed: bool) -> None:
        """Обновить статистику при изменении статуса завершения карточки"""
        if card_completed:
            await StatisticService.increment_cards_completed(db)
            debug_logger.debug("Статистика обновлена: карточка завершена") 