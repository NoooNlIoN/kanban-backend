from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, insert
from sqlalchemy.orm import selectinload

from src.models.tag import Tag, card_tags


class TagService:
    """Сервис для работы с тегами карточек"""

    @staticmethod
    async def create(
        db: AsyncSession,
        board_id: int,
        name: str,
        color: Optional[str] = None
    ) -> Tag:
        """Создание нового тега для доски"""
        tag = Tag(
            board_id=board_id,
            name=name,
            color=color
        )
        
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tag_id: int
    ) -> Optional[Tag]:
        """Получение тега по ID"""
        query = select(Tag).where(Tag.id == tag_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_board_id(
        db: AsyncSession,
        board_id: int
    ) -> List[Tag]:
        """Получение всех тегов для доски"""
        query = select(Tag).where(Tag.board_id == board_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        tag_id: int,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> Optional[Tag]:
        """Обновление тега"""
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if color is not None:
            update_data["color"] = color
            
        if not update_data:
            return await TagService.get_by_id(db, tag_id)
            
        stmt = update(Tag).where(Tag.id == tag_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        return await TagService.get_by_id(db, tag_id)

    @staticmethod
    async def delete(
        db: AsyncSession,
        tag_id: int
    ) -> bool:
        """Удаление тега"""
        stmt = delete(Tag).where(Tag.id == tag_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def assign_to_card(
        db: AsyncSession,
        tag_id: int,
        card_id: int
    ) -> bool:
        """Назначение тега карточке"""
        stmt = insert(card_tags).values(
            tag_id=tag_id,
            card_id=card_id
        )
        try:
            await db.execute(stmt)
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    @staticmethod
    async def remove_from_card(
        db: AsyncSession,
        tag_id: int,
        card_id: int
    ) -> bool:
        """Удаление тега с карточки"""
        stmt = delete(card_tags).where(
            card_tags.c.tag_id == tag_id,
            card_tags.c.card_id == card_id
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_card_tags(
        db: AsyncSession,
        card_id: int
    ) -> List[Tag]:
        """Получение всех тегов карточки"""
        # Используем selectinload для загрузки тегов через отношение
        query = select(Tag).join(
            card_tags, Tag.id == card_tags.c.tag_id
        ).where(card_tags.c.card_id == card_id)
        
        result = await db.execute(query)
        return list(result.scalars().all()) 