from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import joinedload

from src.models.card import Comment
from src.models.user import User
from src.services.statistic_service import StatisticService


class CommentService:
    """CRUD operations service for Comment model"""

    @staticmethod
    async def create(
        db: AsyncSession,
        text: str,
        card_id: int,
        user_id: int
    ) -> Comment:
        """Create a new comment"""
        comment = Comment(
            text=text,
            card_id=card_id,
            user_id=user_id
        )
        
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        
        # Обновляем статистику комментариев
        await StatisticService.increment_comments_posted(db)
        
        return comment

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        comment_id: int
    ) -> Optional[Comment]:
        """Get comment by id"""
        query = select(Comment).where(Comment.id == comment_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_by_card_id(
        db: AsyncSession,
        card_id: int
    ) -> List[Comment]:
        """Get all comments for a card with user information"""
        query = select(Comment, User.username).join(
            User, Comment.user_id == User.id
        ).where(
            Comment.card_id == card_id
        ).order_by(Comment.created_at)
        
        result = await db.execute(query)
        
        # Combine comment and username
        comments_with_username = []
        for comment, username in result.fetchall():
            # Associate username with comment
            setattr(comment, 'username', username)
            comments_with_username.append(comment)
            
        return comments_with_username

    @staticmethod
    async def update(
        db: AsyncSession,
        comment_id: int,
        text: str
    ) -> Optional[Comment]:
        """Update a comment's text"""
        stmt = update(Comment).where(Comment.id == comment_id).values(text=text)
        await db.execute(stmt)
        await db.commit()
        
        return await CommentService.get_by_id(db, comment_id)

    @staticmethod
    async def delete(
        db: AsyncSession,
        comment_id: int
    ) -> bool:
        """Delete a comment"""
        stmt = delete(Comment).where(Comment.id == comment_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def is_comment_owner(
        db: AsyncSession,
        comment_id: int,
        user_id: int
    ) -> bool:
        """Check if a user is the owner of a comment"""
        comment = await CommentService.get_by_id(db, comment_id)
        if not comment:
            return False
        
        return comment.user_id == user_id 