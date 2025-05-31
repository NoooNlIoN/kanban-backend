from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.permissions import check_board_permissions
from src.models.user import User
from src.models.board import BoardUserRole, board_users
from src.services.board_service import BoardService
from src.services.user_service import UserService
from src.services.websocket_service import notify_user_added, notify_user_removed, notify_user_role_changed
from src.schemas.board_permissions import (
    TransferOwnershipRequest,
    ChangeUserRoleRequest,
    AddUserRequest,
    AddUserByEmailRequest,
    RemoveUserRequest
)

router = APIRouter(
    prefix="/boards/{board_id}/permissions",
    tags=["board permissions"],
)


@router.post("/transfer-ownership", status_code=status.HTTP_200_OK)
async def transfer_board_ownership(
    board_id: int,
    request: TransferOwnershipRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Transfer ownership of a board to another user (only owner can transfer ownership)"""
    # Check if board exists and user is owner
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Board not found"
        )
    
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the board owner can transfer ownership"
        )
    
    success, message = await BoardService.transfer_ownership(
        db=db,
        board_id=board_id,
        current_owner_id=current_user.id,
        new_owner_id=request.new_owner_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Notify subscribers about the ownership transfer
    await notify_user_role_changed(board_id, request.new_owner_id, BoardUserRole.OWNER.value)
    await notify_user_role_changed(board_id, current_user.id, BoardUserRole.ADMIN.value)
    
    return {"message": message}


@router.post("/change-role", status_code=status.HTTP_200_OK)
async def change_user_role(
    board_id: int,
    request: ChangeUserRoleRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Change a user's role on a board (only owner can change roles)"""
    # Only owner can change roles
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the board owner can change user roles"
        )
    
    success, message = await BoardService.escalate_user_permission(
        db=db,
        board_id=board_id,
        target_user_id=request.user_id,
        acting_user_id=current_user.id,
        new_role=request.role
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Notify subscribers about the role change
    await notify_user_role_changed(board_id, request.user_id, request.role.value)
    
    return {"message": message}


@router.post("/add-user", status_code=status.HTTP_200_OK)
async def add_user_to_board(
    board_id: int,
    request: AddUserRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Add a user to the board (only owner can add users)"""
    # Check if user is the owner
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the board owner can add users to the board"
        )
    
    success = await BoardService.add_user_to_board(
        db=db,
        board_id=board_id,
        user_id=request.user_id,
        role=request.role
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to board"
        )
    
    # Get user info for notification
    from sqlalchemy import select
    from src.models.user import User
    
    user_query = select(User).where(User.id == request.user_id)
    result = await db.execute(user_query)
    user = result.scalars().first()
    
    if user:
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": request.role.value
        }
        # Notify subscribers about the new user
        await notify_user_added(board_id, user_data)
    
    return {"message": "User added to board successfully"}


@router.post("/add-user-by-email", status_code=status.HTTP_200_OK)
async def add_user_to_board_by_email(
    board_id: int,
    request: AddUserByEmailRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Add a user to the board by email (only owner can add users)"""
    # Check if user is the owner
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )

    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the board owner can add users to the board"
        )

    # Find the user by email
    target_user = await UserService.get_by_email(db, request.email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found"
        )

    # Check if user is already a member
    user_role = await BoardService.get_user_role(db, board_id, target_user.id, target_user)
    if user_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this board"
        )

    # Add the user to the board
    success = await BoardService.add_user_to_board(
        db=db,
        board_id=board_id,
        user_id=target_user.id,
        role=request.role
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to board"
        )

    # Prepare user data for notification
    user_data = {
        "id": target_user.id,
        "username": target_user.username,
        "email": target_user.email,
        "role": request.role.value
    }

    # Notify subscribers about the new user
    await notify_user_added(board_id, user_data)

    return {"message": "User added to board successfully"}


@router.get("/users", status_code=status.HTTP_200_OK)
async def get_board_users(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all users with their roles on a board (all board members can view users)"""
    # Check if user has access to the board
    await check_board_permissions(
        db=db,
        board_id=board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    # Get board with its users
    board = await BoardService.get_by_id(db, board_id, load_relations=True)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Get roles for each user
    from sqlalchemy import select
    result = await db.execute(
        select(board_users).where(board_users.c.board_id == board_id)
    )
    user_roles = {row.user_id: row.role for row in result.fetchall()}
    
    # Format response
    users_with_roles = []
    for user in board.users:
        users_with_roles.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user_roles.get(user.id, BoardUserRole.MEMBER).value,
            "is_owner": user.id == board.owner_id
        })
    
    return {"users": users_with_roles}


@router.delete("/remove-user", status_code=status.HTTP_200_OK)
async def remove_user_from_board(
    board_id: int,
    request: RemoveUserRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a user from the board (only owner and admins can remove users)"""
    # Check if board exists
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Get current user's role
    current_user_role = await BoardService.get_user_role(db, board_id, current_user.id, current_user)
    if not current_user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this board"
        )
    
    # Check if the user has permission to remove users
    if current_user_role not in [BoardUserRole.OWNER, BoardUserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can remove users from the board"
        )
    
    # Get the target user - нужно получить объект пользователя для корректной проверки роли
    target_user = await UserService.get_by_id(db, request.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )
    
    # Get the target user's role
    target_user_role = await BoardService.get_user_role(db, board_id, request.user_id, target_user)
    if not target_user_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a member of this board"
        )
    
    # Additional permission checks
    # Owners can remove anyone except themselves
    if current_user_role == BoardUserRole.OWNER:
        if current_user.id == request.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owners cannot remove themselves. Transfer ownership first."
            )
    # Admins can only remove regular members
    elif current_user_role == BoardUserRole.ADMIN:
        if target_user_role in [BoardUserRole.OWNER, BoardUserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins can only remove regular members, not other admins or the owner"
            )
    
    # Remove the user
    success = await BoardService.remove_user_from_board(
        db=db,
        board_id=board_id,
        user_id=request.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove user from board"
        )
    
    # Send WebSocket notification to all board subscribers
    await notify_user_removed(board_id, request.user_id)
    
    return {"message": "User removed from board successfully"} 


@router.post("/add-by-email/{email}", status_code=status.HTTP_200_OK)
async def add_user_to_board_by_email_path(
    board_id: int,
    email: str,
    role: BoardUserRole = BoardUserRole.MEMBER,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Add a user to the board by email using path parameters (only owner can add users)"""
    # Check if user is the owner
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the board owner can add users to the board"
        )
    
    # Find the user by email
    target_user = await UserService.get_by_email(db, email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found"
        )
    
    # Check if user is already a member
    user_role = await BoardService.get_user_role(db, board_id, target_user.id, target_user)
    if user_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this board"
        )
    
    # Add the user to the board
    success = await BoardService.add_user_to_board(
        db=db,
        board_id=board_id,
        user_id=target_user.id,
        role=role
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to board"
        )
    
    # Prepare user data for notification
    user_data = {
        "id": target_user.id,
        "username": target_user.username,
        "email": target_user.email,
        "role": role.value
    }
    
    # Notify subscribers about the new user
    await notify_user_added(board_id, user_data)
    
    return {"message": "User added to board successfully"}


@router.post("/leave", status_code=status.HTTP_200_OK)
async def leave_board(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Leave a board voluntarily (for members and admins)"""
    # Check if board exists
    board = await BoardService.get_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Get user's role on the board
    user_role = await BoardService.get_user_role(db, board_id, current_user.id, current_user)
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this board"
        )
    
    # Owners can't leave directly - they need to transfer ownership first
    if user_role == BoardUserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board owners cannot leave directly. Transfer ownership first."
        )
    
    # Remove the user from the board
    success = await BoardService.remove_user_from_board(
        db=db,
        board_id=board_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to leave the board"
        )
    
    # Send WebSocket notification to all board subscribers
    await notify_user_removed(board_id, current_user.id)
    
    return {"message": "You have successfully left the board"} 