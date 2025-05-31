from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.board import BoardUserRole
from src.services.board_service import BoardService


async def check_board_permissions(
    db: AsyncSession, 
    board_id: int, 
    user_id: int,
    required_roles: list[BoardUserRole],
    user: User = None  # Добавляем параметр user для проверки суперпользователя
) -> bool:
    """
    Check if a user has the required permission (role) for a board
    
    Args:
        db: Database session
        board_id: Board ID
        user_id: User ID
        required_roles: List of roles that have permission for the operation
        user: User object for superuser check (optional)
        
    Returns:
        True if the user has permission, otherwise raises HTTPException
    """
    # Если передан объект пользователя и он суперпользователь - разрешаем все операции
    if user and user.is_superuser:
        return True
    
    # Get the user's role on the board (передаем объект пользователя)
    user_role = await BoardService.get_user_role(db, board_id, user_id, user)
    
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this board"
        )
    
    # Owner always has all permissions
    if user_role == BoardUserRole.OWNER:
        return True
    
    # Check if the user's role is in the required roles
    if user_role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not allowed with your role: {user_role.value}"
        )
    
    return True 