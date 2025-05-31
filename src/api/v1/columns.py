from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.permissions import check_board_permissions
from src.models.user import User
from src.models.board import BoardUserRole
from src.services.board_service import BoardService
from src.services.column_service import ColumnService
from src.services.websocket_service import notify_column_created, notify_column_updated, notify_column_deleted
from src.schemas.column import (
    ColumnCreate, 
    ColumnResponse, 
    ColumnUpdate, 
    ColumnList,
    ColumnOrderUpdate
)

router = APIRouter(
    prefix="/boards/{board_id}/columns",
    tags=["columns"],
)


@router.put("/reorder", status_code=status.HTTP_200_OK)
async def reorder_columns(
    board_id: int,
    column_order: ColumnOrderUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Reorder columns in a board (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_board_access(board_id, db, current_user, require_modify=True)
    
    column_order.column_order = [int(column_id) for column_id in column_order.column_order]

    success = await ColumnService.reorder_columns(
        db=db,
        board_id=board_id,
        column_order=column_order.column_order
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder columns"
        )
    
    # Get updated columns to notify subscribers
    columns = await ColumnService.get_by_board_id(db=db, board_id=board_id)
    for column in columns:
        column_data = {
            "id": column.id,
            "title": column.title,
            "board_id": column.board_id,
            "order": column.order
        }
        await notify_column_updated(board_id, column_data)
    
    return {"message": "Columns reordered successfully"} 

async def check_board_access(
    board_id: int,
    db: AsyncSession,
    current_user: User,
    require_modify: bool = False
):
    """
    Check if user has access to the board
    
    Args:
        board_id: ID of the board to check
        db: Database session
        current_user: Current authenticated user
        require_modify: If True, checks if user has modify permissions (Owner/Admin),
                        otherwise checks if user has read access (Owner/Admin/Member)
    """
    # Если пользователь суперпользователь - разрешаем все операции
    if current_user.is_superuser:
        # Все равно проверяем, что доска существует
        board = await BoardService.get_by_id(db=db, board_id=board_id)
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found"
            )
        return board
    
    board = await BoardService.get_by_id(db=db, board_id=board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    required_roles = [BoardUserRole.OWNER, BoardUserRole.ADMIN] if require_modify else [
        BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER
    ]
    
    await check_board_permissions(
        db=db,
        board_id=board_id,
        user_id=current_user.id,
        required_roles=required_roles,
        user=current_user  # Передаем объект пользователя для проверки суперпользователя
    )
    
    return board


@router.post("", response_model=ColumnResponse, status_code=status.HTTP_201_CREATED)
async def create_column(
    board_id: int,
    column_create: ColumnCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new column in a board (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_board_access(board_id, db, current_user, require_modify=True)
    
    column = await ColumnService.create(
        db=db,
        title=column_create.title,
        board_id=board_id,
        order=column_create.order
    )
    
    # Notify subscribers about the new column
    column_data = {
        "id": column.id,
        "title": column.title,
        "board_id": column.board_id,
        "order": column.order
    }
    await notify_column_created(board_id, column_data)
    
    return column


@router.get("", response_model=ColumnList)
async def get_columns(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all columns for a board (All board members)"""
    # Check if user has read access
    await check_board_access(board_id, db, current_user, require_modify=False)
    
    columns = await ColumnService.get_by_board_id(
        db=db,
        board_id=board_id,
        load_cards=True
    )
    return {"columns": columns}


@router.get("/{column_id}", response_model=ColumnResponse)
async def get_column(
    board_id: int,
    column_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific column by ID (All board members)"""
    # Check if user has read access
    await check_board_access(board_id, db, current_user, require_modify=False)
    
    column = await ColumnService.get_by_id(db=db, column_id=column_id, load_cards=True)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column not found"
        )
    
    # Check if the column belongs to the specified board
    if column.board_id != board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column does not belong to the specified board"
        )
    
    return column


@router.put("/{column_id}", response_model=ColumnResponse)
async def update_column(
    board_id: int,
    column_id: int,
    column_update: ColumnUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Update a column (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_board_access(board_id, db, current_user, require_modify=True)
    
    # Check if the column exists and belongs to the specified board
    column = await ColumnService.get_by_id(db=db, column_id=column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column not found"
        )
    
    if column.board_id != board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column does not belong to the specified board"
        )
    
    # Update the column
    updated_column = await ColumnService.update(
        db=db,
        column_id=column_id,
        title=column_update.title,
        order=column_update.order
    )
    
    # Notify subscribers about the column update
    column_data = {
        "id": updated_column.id,
        "title": updated_column.title,
        "board_id": updated_column.board_id,
        "order": updated_column.order
    }
    await notify_column_updated(board_id, column_data)
    
    return updated_column


@router.delete("/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    board_id: int,
    column_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a column (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_board_access(board_id, db, current_user, require_modify=True)
    
    # Check if the column exists and belongs to the specified board
    column = await ColumnService.get_by_id(db=db, column_id=column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column not found"
        )
    
    if column.board_id != board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column does not belong to the specified board"
        )
    
    # Delete the column
    deleted = await ColumnService.delete(db=db, column_id=column_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete column"
        )
    
    # Notify subscribers about the column deletion
    await notify_column_deleted(board_id, column_id)


