from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from src.models.board import Board, BoardUserRole, board_users
from src.models.column import Column  # Added import for Column
from src.models.card import Card, Comment
from src.models.tag import Tag
from src.models.user import User


def _prepare_assigned_users_in_cards(board: Board) -> Board:
    """
    Преобразование объектов User в список ID для всех карточек на доске
    """
    if hasattr(board, "columns") and board.columns:
        for column in board.columns:
            if hasattr(column, "cards") and column.cards:
                for card in column.cards:
                    if hasattr(card, "assigned_users") and card.assigned_users:
                        card.__dict__["assigned_users"] = [
                            user.id if hasattr(user, "id") else user 
                            for user in card.assigned_users
                        ]
    return board


class BoardService:
    """CRUD operations service for Board model"""

    @staticmethod
    async def create(
        db: AsyncSession,
        title: str,
        owner_id: int,
        description: Optional[str] = None
    ) -> Board:
        """Create a new board"""
        board = Board(
            title=title,
            description=description,
            owner_id=owner_id
        )
        db.add(board)
        await db.flush()

        # Add owner to board_users with OWNER role
        stmt = board_users.insert().values(
            user_id=owner_id,
            board_id=board.id,
            role=BoardUserRole.OWNER
        )
        await db.execute(stmt)
        
        await db.commit()
        await db.refresh(board)
        return board

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        board_id: int,
        load_relations: bool = False
    ) -> Optional[Board]:
        """Get board by id with optional relations loading"""
        query = select(Board).where(Board.id == board_id)
        
        if load_relations:
            query = query.options(
                selectinload(Board.columns),
                selectinload(Board.users)
            )
            
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Board]:
        """Get all boards with pagination"""
        query = select(Board).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_all_boards(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Board]:
        """Get all boards with pagination (alias for get_all)"""
        return await BoardService.get_all(db, skip, limit)

    @staticmethod
    async def get_boards_by_user(
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Board]:
        """Get all boards that a user has access to"""
        query = select(Board).join(board_users).where(
            board_users.c.user_id == user_id
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        board_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Board]:
        """Update a board's details"""
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
            
        if not update_data:
            return await BoardService.get_by_id(db, board_id)
        
        # Явно устанавливаем updated_at для предотвращения проблем с часовыми поясами
        update_data["updated_at"] = datetime.utcnow().replace(tzinfo=None)
            
        stmt = update(Board).where(Board.id == board_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        return await BoardService.get_by_id(db, board_id)

    @staticmethod
    async def delete(
        db: AsyncSession,
        board_id: int
    ) -> bool:
        """Delete a board"""
        stmt = delete(Board).where(Board.id == board_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def add_user_to_board(
        db: AsyncSession,
        board_id: int,
        user_id: int,
        role: BoardUserRole = BoardUserRole.MEMBER
    ) -> bool:
        """Add a user to a board with specified role"""
        stmt = board_users.insert().values(
            user_id=user_id,
            board_id=board_id,
            role=role
        )
        try:
            await db.execute(stmt)
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    @staticmethod
    async def remove_user_from_board(
        db: AsyncSession,
        board_id: int,
        user_id: int
    ) -> bool:
        """Remove a user from a board"""
        stmt = delete(board_users).where(
            board_users.c.user_id == user_id,
            board_users.c.board_id == board_id
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def change_user_role(
        db: AsyncSession,
        board_id: int,
        user_id: int,
        new_role: BoardUserRole
    ) -> bool:
        """Change a user's role on a board"""
        stmt = update(board_users).where(
            board_users.c.user_id == user_id,
            board_users.c.board_id == board_id
        ).values(role=new_role)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def get_user_role(
        db: AsyncSession,
        board_id: int,
        user_id: int,
        user: Optional['User'] = None  # Добавляем параметр для объекта пользователя
    ) -> Optional[BoardUserRole]:
        """Get a user's role on a board
        
        Args:
            db: Database session
            board_id: Board ID
            user_id: User ID
            user: User object for superuser check (optional)
        
        Returns:
            BoardUserRole if user is on the board, None otherwise
            For superusers, always returns OWNER regardless of actual board membership
        """
        # Если передан объект пользователя и он суперпользователь - возвращаем роль OWNER
        if user and getattr(user, 'is_superuser', False):
            return BoardUserRole.OWNER
        
        query = select(board_users.c.role).where(
            board_users.c.user_id == user_id,
            board_users.c.board_id == board_id
        )
        result = await db.execute(query)
        row = result.first()
        return row.role if row else None
    
    @staticmethod
    async def transfer_ownership(
        db: AsyncSession,
        board_id: int,
        current_owner_id: int,
        new_owner_id: int
    ) -> Tuple[bool, str]:
        """Transfer board ownership from current owner to new owner
        
        Args:
            db: Database session
            board_id: ID of the board
            current_owner_id: ID of the current owner
            new_owner_id: ID of the user to become the new owner
            
        Returns:
            Tuple of (success, message)
        """
        # Verify board exists
        board = await BoardService.get_by_id(db, board_id)
        if not board:
            return False, "Board not found"
        
        # Verify current_owner is actually the owner
        if board.owner_id != current_owner_id:
            return False, "Only the board owner can transfer ownership"
        
        # Check if new_owner is already on the board
        new_owner_role = await BoardService.get_user_role(db, board_id, new_owner_id)
        
        try:
            # Start transaction
            async with db.begin():
                # Update the board's owner_id
                board_stmt = update(Board).where(
                    Board.id == board_id
                ).values(owner_id=new_owner_id)
                await db.execute(board_stmt)
                
                # If new owner is already on the board, update their role to OWNER
                if new_owner_role is not None:
                    await BoardService.change_user_role(
                        db, board_id, new_owner_id, BoardUserRole.OWNER
                    )
                else:
                    # Add new owner to board_users with OWNER role
                    await BoardService.add_user_to_board(
                        db, board_id, new_owner_id, BoardUserRole.OWNER
                    )
                
                # Demote the current owner to ADMIN
                await BoardService.change_user_role(
                    db, board_id, current_owner_id, BoardUserRole.ADMIN
                )
                
            return True, "Ownership transferred successfully"
        
        except Exception as e:
            await db.rollback()
            return False, f"Failed to transfer ownership: {str(e)}"
    
    @staticmethod
    async def escalate_user_permission(
        db: AsyncSession,
        board_id: int,
        target_user_id: int,
        acting_user_id: int,
        new_role: BoardUserRole
    ) -> Tuple[bool, str]:
        """Escalate a user's permission level on a board
        
        Args:
            db: Database session
            board_id: ID of the board
            target_user_id: ID of the user whose permissions will be changed
            acting_user_id: ID of the user performing the action
            new_role: The new role to assign
            
        Returns:
            Tuple of (success, message)
        """
        # Get the acting user's role
        acting_user_role = await BoardService.get_user_role(db, board_id, acting_user_id)
        if not acting_user_role:
            return False, "You don't have access to this board"
        
        # Get the target user's current role
        target_user_role = await BoardService.get_user_role(db, board_id, target_user_id)
        if not target_user_role:
            return False, "Target user is not a member of this board"
        
        # Check permissions based on role hierarchy
        if acting_user_role == BoardUserRole.MEMBER:
            return False, "Members cannot change user roles"
        
        if acting_user_role == BoardUserRole.ADMIN:
            # Admins can't promote to owner or change other admins
            if new_role == BoardUserRole.OWNER:
                return False, "Admins can't promote users to Owner"
            
            if target_user_role == BoardUserRole.ADMIN or target_user_role == BoardUserRole.OWNER:
                return False, "Admins can't change the role of other admins or the owner"
        
        if acting_user_role == BoardUserRole.OWNER:
            # Owners can do anything except change their own role
            if target_user_id == acting_user_id and new_role != BoardUserRole.OWNER:
                return False, "Owners can't demote themselves"
        
        # Apply the role change
        success = await BoardService.change_user_role(db, board_id, target_user_id, new_role)
        
        if success:
            return True, f"User role updated to {new_role.value}"
        else:
            return False, "Failed to update user role"

    @staticmethod
    async def get_complete_board(
        db: AsyncSession,
        board_id: int
    ) -> Optional[Board]:
        """Get a complete board with all its columns and cards"""
        query = select(Board).where(Board.id == board_id).options(
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.assigned_users),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.comments),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.tags),
        )
        
        result = await db.execute(query)
        board = result.scalars().first()
        
        if board:
            # Преобразование assigned_users в ID
            board = _prepare_assigned_users_in_cards(board)
        
        return board

    @staticmethod
    async def calculate_board_statistics(
        db: AsyncSession,
        board_id: int
    ) -> dict:
        """Calculate statistics for a specific board"""
        # Получаем все карточки доски
        cards_query = select(Card).join(Column).where(Column.board_id == board_id)
        cards_result = await db.execute(cards_query)
        cards = list(cards_result.scalars().all())
        
        # Получаем количество колонок
        columns_query = select(func.count(Column.id)).where(Column.board_id == board_id)
        columns_result = await db.execute(columns_query)
        total_columns = columns_result.scalar() or 0
        
        # Получаем количество комментариев
        comments_query = select(func.count(Comment.id)).join(Card).join(Column).where(Column.board_id == board_id)
        comments_result = await db.execute(comments_query)
        total_comments = comments_result.scalar() or 0
        
        # Подсчитываем статистику по карточкам
        total_cards = len(cards)
        completed_cards = sum(1 for card in cards if card.completed)
        archived_cards = sum(1 for card in cards if card.is_archived)
        cards_with_deadline = sum(1 for card in cards if card.deadline)
        
        # Подсчитываем просроченные карточки
        current_time = datetime.utcnow()
        overdue_cards = sum(
            1 for card in cards 
            if card.deadline and card.deadline < current_time and not card.completed
        )
        
        return {
            "total_cards": total_cards,
            "completed_cards": completed_cards,
            "archived_cards": archived_cards,
            "total_columns": total_columns,
            "total_comments": total_comments,
            "cards_with_deadline": cards_with_deadline,
            "overdue_cards": overdue_cards
        }

    @staticmethod
    async def get_user_boards_with_full_stats(
        db: AsyncSession,
        user_id: int
    ) -> Tuple[List[Board], dict]:
        """Get all user boards with complete statistics"""
        # Получаем все доски пользователя с полной информацией
        query = select(Board).join(board_users).where(
            board_users.c.user_id == user_id
        ).options(
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.assigned_users),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.comments),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.tags),
        )
        
        result = await db.execute(query)
        boards = list(result.scalars().all())
        
        # Подготавливаем доски
        for board in boards:
            board = _prepare_assigned_users_in_cards(board)
        
        # Подсчитываем глобальную статистику
        global_stats = {
            "total_cards": 0,
            "completed_cards": 0,
            "archived_cards": 0,
            "total_columns": 0,
            "total_comments": 0,
            "cards_with_deadline": 0,
            "overdue_cards": 0
        }
        
        # Суммируем статистику по всем доскам
        for board in boards:
            board_stats = await BoardService.calculate_board_statistics(db, board.id)
            for key in global_stats:
                global_stats[key] += board_stats[key]
        
        return boards, global_stats

    @staticmethod
    async def get_all_boards_with_full_stats(
        db: AsyncSession
    ) -> Tuple[List[Board], dict]:
        """Get all boards in system with complete statistics (for superuser)"""
        # Получаем все доски с полной информацией
        query = select(Board).options(
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.assigned_users),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.comments),
            selectinload(Board.columns).selectinload(Column.cards).selectinload(Card.tags),
        )
        
        result = await db.execute(query)
        boards = list(result.scalars().all())
        
        # Подготавливаем доски
        for board in boards:
            board = _prepare_assigned_users_in_cards(board)
        
        # Подсчитываем глобальную статистику
        global_stats = {
            "total_cards": 0,
            "completed_cards": 0,
            "archived_cards": 0,
            "total_columns": 0,
            "total_comments": 0,
            "cards_with_deadline": 0,
            "overdue_cards": 0
        }
        
        # Суммируем статистику по всем доскам
        for board in boards:
            board_stats = await BoardService.calculate_board_statistics(db, board.id)
            for key in global_stats:
                global_stats[key] += board_stats[key]
        
        return boards, global_stats 