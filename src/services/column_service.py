from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from src.models.column import Column
from src.models.card import Card


class ColumnService:
    """CRUD operations service for Column model"""

    @staticmethod
    async def create(
        db: AsyncSession,
        title: str,
        board_id: int,
        order: Optional[int] = None
    ) -> Column:
        """Create a new column in a board"""
        # If order not provided, place it at the end
        if order is None:
            query = select(func.max(Column.order)).where(Column.board_id == board_id)
            result = await db.execute(query)
            max_order = result.scalar()
            order = (max_order or 0) + 1
            
        column = Column(
            title=title,
            board_id=board_id,
            order=order
        )
        
        db.add(column)
        await db.commit()
        await db.refresh(column)
        
        # Загружаем связи для предотвращения ошибки при сериализации
        column_with_cards = await ColumnService.get_by_id(db, column.id, load_cards=True)
        return column_with_cards

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        column_id: int,
        load_cards: bool = False
    ) -> Optional[Column]:
        """Get column by id with optional cards loading"""
        query = select(Column).where(Column.id == column_id)
        
        if load_cards:
            query = query.options(
                selectinload(Column.cards).selectinload(Card.assigned_users),
                selectinload(Column.cards).selectinload(Card.comments)
            )
            
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_board_id(
        db: AsyncSession,
        board_id: int,
        load_cards: bool = False
    ) -> List[Column]:
        """Get all columns for a board"""
        query = select(Column).where(Column.board_id == board_id).order_by(Column.order)
        
        if load_cards:
            query = query.options(
                selectinload(Column.cards).selectinload(Card.assigned_users),
                selectinload(Column.cards).selectinload(Card.comments)
            )
            
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        column_id: int,
        title: Optional[str] = None,
        order: Optional[int] = None
    ) -> Optional[Column]:
        """Update a column's details"""
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if order is not None:
            update_data["order"] = order
            
        if not update_data:
            return await ColumnService.get_by_id(db, column_id, load_cards=True)
        
        # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
        update_data["updated_at"] = datetime.utcnow().replace(tzinfo=None)
            
        stmt = update(Column).where(Column.id == column_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        return await ColumnService.get_by_id(db, column_id, load_cards=True)

    @staticmethod
    async def delete(
        db: AsyncSession,
        column_id: int
    ) -> bool:
        """Delete a column"""
        stmt = delete(Column).where(Column.id == column_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def reorder_columns(
        db: AsyncSession,
        board_id: int,
        column_order: List[int]
    ) -> bool:
        """Reorder columns in a board
        
        Args:
            db: Database session
            board_id: ID of the board
            column_order: List of column IDs in the desired order
        
        Returns:
            True if reordering was successful
        """
        try:
            # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
            current_time = datetime.utcnow().replace(tzinfo=None)
            
            for new_order, column_id in enumerate(column_order):
                stmt = update(Column).where(
                    Column.id == column_id, 
                    Column.board_id == board_id
                ).values(order=new_order, updated_at=current_time)
                await db.execute(stmt)
            
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False 