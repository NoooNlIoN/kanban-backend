from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.permissions import check_board_permissions
from src.models.user import User
from src.models.board import BoardUserRole
from src.schemas.board import (
    BoardCreate, 
    BoardResponse, 
    BoardUpdate, 
    BoardList, 
    BoardByEmailRequest, 
    BoardCompleteResponse,
    BoardStatistics,
    BoardFullStatsResponse,
    UserBoardsStatsResponse
)
from src.services.board_service import BoardService
from src.services.user_service import UserService
from src.services.websocket_service import notify_board_updated, notify_board_deleted
from src.api.v1.cards import prepare_card_for_response

router = APIRouter(
    prefix="/boards",
    tags=["boards"],
)


@router.post("", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
async def create_board(
    board_create: BoardCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new board"""
    board = await BoardService.create(
        db=db,
        title=board_create.title,
        description=board_create.description,
        owner_id=current_user.id,
    )
    
    # No need to notify about creation since the board has only one user initially
    
    return board


@router.get("", response_model=BoardList)
async def get_boards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all boards available to the current user"""
    # Если пользователь суперпользователь - показываем все доски в системе
    if current_user.is_superuser:
        boards = await BoardService.get_all_boards(
            db=db,
            skip=skip,
            limit=limit,
        )
    else:
        boards = await BoardService.get_boards_by_user(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
    return {
        "boards": boards,
        "total": len(boards)  # For simple pagination. In production, use a count query
    }


@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific board by ID"""
    board = await BoardService.get_by_id(db=db, board_id=board_id, load_relations=True)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Суперпользователи могут видеть любые доски
    if not current_user.is_superuser:
        # Check if the user has access to this board (all roles can view)
        await check_board_permissions(
            db=db,
            board_id=board_id,
            user_id=current_user.id,
            required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
            user=current_user
        )
    
    return board


@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int,
    board_update: BoardUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Update a board (only owner and admin can update)"""
    # First, check if the board exists
    board = await BoardService.get_by_id(db=db, board_id=board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Суперпользователи могут изменять любые доски
    if not current_user.is_superuser:
        # Check if user has update permissions (owner or admin)
        await check_board_permissions(
            db=db,
            board_id=board_id,
            user_id=current_user.id,
            required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN],
            user=current_user
        )
    
    # Update the board
    updated_board = await BoardService.update(
        db=db,
        board_id=board_id,
        title=board_update.title,
        description=board_update.description
    )
    
    # Notify subscribers about the update
    board_data = {
        "id": updated_board.id,
        "title": updated_board.title,
        "description": updated_board.description,
        "owner_id": updated_board.owner_id
    }
    await notify_board_updated(board_id, board_data)
    
    return updated_board


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a board (only owner can delete)"""
    # First, check if the board exists
    board = await BoardService.get_by_id(db=db, board_id=board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Суперпользователи могут удалять любые доски
    if not current_user.is_superuser:
        # Check if user is the owner of the board
        if board.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the board owner can delete it"
            )
    
    # Delete the board
    deleted = await BoardService.delete(db=db, board_id=board_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete board"
        )
    
    # Notify subscribers about the deletion
    await notify_board_deleted(board_id)


@router.post("/by-email", response_model=BoardResponse)
async def get_board_by_email(
    request: BoardByEmailRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific board by accessing it with a user's email"""
    # First, find the user by email
    target_user = await UserService.get_by_email(db, request.email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found"
        )
    
    # Now get the board
    board = await BoardService.get_by_id(db=db, board_id=request.board_id, load_relations=True)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if the target user has access to this board (all roles can view)
    target_role = await BoardService.get_user_role(db, request.board_id, target_user.id, target_user)
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user with this email does not have access to the board"
        )
    
    # Check if the current user has access to the board as well
    await check_board_permissions(
        db=db,
        board_id=request.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    return board


@router.get("/{board_id}/by-email/{email}", response_model=BoardResponse)
async def get_board_by_email_path(
    board_id: int,
    email: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific board by accessing it with a user's email through path parameters"""
    # First, find the user by email
    target_user = await UserService.get_by_email(db, email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found"
        )
    
    # Now get the board
    board = await BoardService.get_by_id(db=db, board_id=board_id, load_relations=True)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if the target user has access to this board (all roles can view)
    target_role = await BoardService.get_user_role(db, board_id, target_user.id, target_user)
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user with this email does not have access to the board"
        )
    
    # Check if the current user has access to the board as well
    await check_board_permissions(
        db=db,
        board_id=board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    return board


@router.get("/{board_id}/complete", response_model=BoardCompleteResponse)
async def get_complete_board(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a complete board with all its columns and cards in a single request"""
    # Check if the board exists and user has access to it
    board = await BoardService.get_complete_board(db=db, board_id=board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if the user has access to this board (all roles can view)
    await check_board_permissions(
        db=db,
        board_id=board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    # Преобразование объектов User в списке assigned_users карточек в список их ID
    for column in board.columns:
        for card in column.cards:
            prepare_card_for_response(card)
    
    return board


@router.get("/stats/full", response_model=UserBoardsStatsResponse)
async def get_user_boards_full_statistics(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all boards with complete statistics for current user"""
    
    if current_user.is_superuser:
        # Суперпользователи видят статистику всех досок в системе
        boards, global_stats = await BoardService.get_all_boards_with_full_stats(db)
    else:
        # Обычные пользователи видят только свои доски
        boards, global_stats = await BoardService.get_user_boards_with_full_stats(db, current_user.id)
    
    # Формируем ответ с полной статистикой для каждой доски
    boards_with_stats = []
    for board in boards:
        # Вычисляем статистику для каждой доски
        board_stats = await BoardService.calculate_board_statistics(db, board.id)
        
        board_response = BoardFullStatsResponse(
            id=board.id,
            title=board.title,
            description=board.description,
            owner_id=board.owner_id,
            created_at=board.created_at,
            updated_at=board.updated_at,
            columns=board.columns if hasattr(board, 'columns') else [],
            statistics=BoardStatistics(**board_stats)
        )
        boards_with_stats.append(board_response)
    
    return UserBoardsStatsResponse(
        boards=boards_with_stats,
        total_boards=len(boards),
        global_statistics=BoardStatistics(**global_stats)
    ) 