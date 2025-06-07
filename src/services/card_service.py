from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from src.models.card import Card, card_users
from src.logs import debug_logger, log_function, api_logger
from src.services.statistic_service import StatisticService


def _prepare_assigned_users(card: Card) -> Card:
    """
    Вспомогательная функция для преобразования объектов User в список ID
    """
    if hasattr(card, "assigned_users") and card.assigned_users:
        card.__dict__["assigned_users"] = [
            user.id if hasattr(user, "id") else user 
            for user in card.assigned_users
        ]
    return card


class CardService:
    """CRUD operations service for Card model"""

    @staticmethod
    @log_function()
    async def create(
        db: AsyncSession,
        title: str,
        column_id: int,
        description: Optional[str] = None,
        color: Optional[str] = None,
        order: Optional[int] = None,
        completed: Optional[bool] = False,
        deadline: Optional[datetime] = None,
        assigned_users: Optional[List[int]] = None
    ) -> Card:
        """Create a new card in a column"""
        # If order not provided, place it at the end
        if order is None:
            query = select(func.max(Card.order)).where(Card.column_id == column_id)
            result = await db.execute(query)
            max_order = result.scalar()
            order = (max_order or 0) + 1
            
        card = Card(
            title=title,
            description=description,
            column_id=column_id,
            color=color,
            order=order,
            completed=completed,
            deadline=deadline
        )
        
        db.add(card)
        await db.flush()  # Получаем ID карточки
        
        # Добавляем назначенных пользователей
        if assigned_users:
            for user_id in assigned_users:
                stmt = card_users.insert().values(
                    user_id=user_id,
                    card_id=card.id
                )
                await db.execute(stmt)
        
        await db.commit()
        
        # Загружаем карточку со всеми связями
        query = select(Card).options(
            selectinload(Card.assigned_users)
        ).where(Card.id == card.id)
        result = await db.execute(query)
        card = result.scalar_one()
        
        debug_logger.info(f"Создана новая карточка: ID {card.id}, в колонке {column_id}")
        
        # Обновляем статистику созданных карточек
        await StatisticService.increment_cards_created(db)
        
        return card

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        card_id: int,
        load_relations: bool = False
    ) -> Optional[Card]:
        """Get a card by ID with optional relation loading"""
        query = select(Card).where(Card.id == card_id)
        
        if load_relations:
            query = query.options(
                selectinload(Card.assigned_users),
                selectinload(Card.comments),
                selectinload(Card.tags)
            )
            
        result = await db.execute(query)
        card = result.scalars().first()
        
        # Преобразуем объекты User в список ID при загрузке отношений
        if card and load_relations:
            _prepare_assigned_users(card)
            
        return card

    @staticmethod
    async def get_by_column_id(
        db: AsyncSession,
        column_id: int,
        load_relations: bool = False
    ) -> List[Card]:
        """Get all cards for a column with optional relation loading"""
        query = select(Card).where(Card.column_id == column_id).order_by(Card.order)
        
        if load_relations:
            query = query.options(
                selectinload(Card.assigned_users),
                selectinload(Card.comments),
                selectinload(Card.tags)
            )
            
        result = await db.execute(query)
        cards = list(result.scalars().all())
        
        # Преобразуем объекты User в список ID при загрузке отношений
        if load_relations:
            for card in cards:
                _prepare_assigned_users(card)
                
        return cards

    @staticmethod
    @log_function()
    async def update(
        db: AsyncSession,
        card_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        column_id: Optional[int] = None,
        color: Optional[str] = None,
        order: Optional[int] = None,
        completed: Optional[bool] = None,
        deadline: Optional[datetime] = None,
        assigned_users: Optional[List[int]] = None
    ) -> Optional[Card]:
        """Update a card's details"""
        debug_logger.debug(f"Обновление карточки ID: {card_id}")
        
        # Получаем текущее состояние карточки для логирования изменений
        current_card = await CardService.get_by_id(db, card_id)
        if not current_card:
            debug_logger.warning(f"Карточка с ID {card_id} не найдена при попытке обновления")
            return None
            
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if column_id is not None:
            update_data["column_id"] = column_id
        if color is not None:
            update_data["color"] = color
        if order is not None:
            update_data["order"] = order
        if completed is not None:
            update_data["completed"] = completed
        if deadline is not None:
            update_data["deadline"] = deadline
            
        if update_data:
            # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
            update_data["updated_at"] = datetime.utcnow().replace(tzinfo=None)
            
            debug_logger.debug(f"Обновляемые поля карточки {card_id}: {update_data}")
            stmt = update(Card).where(Card.id == card_id).values(**update_data)
            await db.execute(stmt)
            
        # Обновляем назначенных пользователей
        if assigned_users is not None:
            debug_logger.debug(f"Обновление назначенных пользователей для карточки {card_id}: {assigned_users}")
            # Удаляем текущих назначенных пользователей
            stmt = delete(card_users).where(card_users.c.card_id == card_id)
            await db.execute(stmt)
            
            # Добавляем новых назначенных пользователей
            for user_id in assigned_users:
                stmt = card_users.insert().values(
                    user_id=user_id,
                    card_id=card_id
                )
                await db.execute(stmt)
        
        await db.commit()
        updated_card = await CardService.get_by_id(db, card_id, load_relations=True)
        debug_logger.info(f"Карточка {card_id} успешно обновлена")
        return updated_card

    @staticmethod
    async def delete(
        db: AsyncSession,
        card_id: int
    ) -> bool:
        """Delete a card"""
        debug_logger.debug(f"Удаление карточки ID: {card_id}")
        
        # Проверяем существование карточки
        card = await CardService.get_by_id(db, card_id)
        if not card:
            debug_logger.warning(f"Карточка с ID {card_id} не найдена при попытке удаления")
            return False
            
        try:
            stmt = delete(Card).where(Card.id == card_id)
            result = await db.execute(stmt)
            await db.commit()
            success = result.rowcount > 0
            if success:
                debug_logger.info(f"Карточка {card_id} успешно удалена")
            else:
                debug_logger.warning(f"Не удалось удалить карточку {card_id}")
            return success
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при удалении карточки {card_id}: {str(e)}")
            return False

    @staticmethod
    @log_function()
    async def reorder_cards(
        db: AsyncSession,
        column_id: int,
        card_order: List[int]
    ) -> bool:
        """Reorder cards in a column"""
        debug_logger.debug(f"Изменение порядка карточек в колонке {column_id}: {card_order}")
        try:
            # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
            current_time = datetime.utcnow().replace(tzinfo=None)
            
            for new_order, card_id in enumerate(card_order):
                stmt = update(Card).where(
                    Card.id == card_id, 
                    Card.column_id == column_id
                ).values(order=new_order, updated_at=current_time)
                await db.execute(stmt)
            
            await db.commit()
            debug_logger.info(f"Порядок карточек в колонке {column_id} успешно обновлен")
            return True
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при изменении порядка карточек в колонке {column_id}: {str(e)}")
            return False

    @staticmethod
    @log_function()
    async def move_card(
        db: AsyncSession,
        card_id: int,
        new_column_id: int,
        new_order: int
    ) -> Optional[Card]:
        """Move a card to a different column with specified order"""
        debug_logger.debug(f"Перемещение карточки {card_id} в колонку {new_column_id} на позицию {new_order}")
        
        # Получаем текущую колонку карточки
        card = await CardService.get_by_id(db, card_id)
        if not card:
            debug_logger.warning(f"Карточка {card_id} не найдена при попытке перемещения")
            return None
            
        old_column_id = card.column_id
        
        try:
            # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
            current_time = datetime.utcnow().replace(tzinfo=None)
            
            # Смещаем карточки в новой колонке
            shift_stmt = update(Card).where(
                Card.column_id == new_column_id,
                Card.order >= new_order
            ).values(order=Card.order + 1, updated_at=current_time)
            await db.execute(shift_stmt)
            
            # Перемещаем карточку
            stmt = update(Card).where(Card.id == card_id).values(
                column_id=new_column_id,
                order=new_order,
                updated_at=current_time
            )
            await db.execute(stmt)
            
            # Сжимаем позиции в старой колонке
            compress_stmt = update(Card).where(
                Card.column_id == old_column_id,
                Card.order > card.order
            ).values(order=Card.order - 1, updated_at=current_time)
            await db.execute(compress_stmt)
            
            await db.commit()
            # Используем load_relations=True для загрузки связей
            moved_card = await CardService.get_by_id(db, card_id, load_relations=True)
            debug_logger.info(f"Карточка {card_id} успешно перемещена из колонки {old_column_id} в колонку {new_column_id}")
            return moved_card
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при перемещении карточки {card_id}: {str(e)}")
            api_logger.error(f"Failed to move card {card_id} to column {new_column_id}: {str(e)}")
            return None

    @staticmethod
    async def assign_user(
        db: AsyncSession,
        card_id: int,
        user_id: int
    ) -> bool:
        """Assign a user to a card"""
        debug_logger.debug(f"Назначение пользователя {user_id} на карточку {card_id}")
        stmt = card_users.insert().values(
            user_id=user_id,
            card_id=card_id
        )
        try:
            await db.execute(stmt)
            await db.commit()
            debug_logger.info(f"Пользователь {user_id} успешно назначен на карточку {card_id}")
            return True
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при назначении пользователя {user_id} на карточку {card_id}: {str(e)}")
            return False

    @staticmethod
    async def unassign_user(
        db: AsyncSession,
        card_id: int,
        user_id: int
    ) -> bool:
        """Unassign a user from a card"""
        debug_logger.debug(f"Снятие назначения пользователя {user_id} с карточки {card_id}")
        stmt = delete(card_users).where(
            card_users.c.user_id == user_id,
            card_users.c.card_id == card_id
        )
        try:
            result = await db.execute(stmt)
            await db.commit()
            success = result.rowcount > 0
            if success:
                debug_logger.info(f"Пользователь {user_id} успешно снят с карточки {card_id}")
            else:
                debug_logger.warning(f"Пользователь {user_id} не был назначен на карточку {card_id}")
            return success
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при снятии пользователя {user_id} с карточки {card_id}: {str(e)}")
            return False

    @staticmethod
    @log_function()
    async def toggle_completed(
        db: AsyncSession,
        card_id: int
    ) -> Optional[Card]:
        """Toggle the completed status of a card"""
        debug_logger.debug(f"Изменение статуса выполнения карточки {card_id}")
        
        # Get the current card with its completed status
        card = await CardService.get_by_id(db, card_id)
        if not card:
            debug_logger.warning(f"Карточка с ID {card_id} не найдена при изменении статуса")
            return None
            
        try:
            # Toggle the completed status
            new_status = not card.completed
            stmt = update(Card).where(Card.id == card_id).values(
                completed=new_status
            )
            await db.execute(stmt)
            await db.commit()
            
            # Обновляем статистику, если карточка была завершена
            if new_status:
                await StatisticService.update_stats_for_card_completion(db, True)
            
            # Загружаем обновленную карточку со всеми связями
            updated_card = await CardService.get_by_id(db, card_id, load_relations=True)
            debug_logger.info(f"Статус выполнения карточки {card_id} изменен на {new_status}")
            return updated_card
        except Exception as e:
            await db.rollback()
            debug_logger.error(f"Ошибка при изменении статуса карточки {card_id}: {str(e)}")
            return None

    @staticmethod
    async def get_archived(
        db: AsyncSession,
        column_id: Optional[int] = None
    ) -> List[Card]:
        """Получить архивные карточки (все или для конкретной колонки)"""
        query = select(Card).where(Card.is_archived == True)
        
        if column_id:
            query = query.where(Card.column_id == column_id)
            
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def archive(
        db: AsyncSession,
        card_id: int
    ) -> bool:
        """Архивировать карточку"""
        # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
        current_time = datetime.utcnow().replace(tzinfo=None)
        
        stmt = update(Card).where(Card.id == card_id).values(
            is_archived=True,
            updated_at=current_time
        )
        await db.execute(stmt)
        await db.commit()
        return True

    @staticmethod
    async def restore(
        db: AsyncSession,
        card_id: int
    ) -> bool:
        """Восстановить из архива"""
        # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
        current_time = datetime.utcnow().replace(tzinfo=None)
        
        stmt = update(Card).where(Card.id == card_id).values(
            is_archived=False,
            updated_at=current_time
        )
        await db.execute(stmt)
        await db.commit()
        return True 