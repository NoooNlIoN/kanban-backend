from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.models.user import User
from src.services.comment_service import CommentService
from src.api.v1.cards import check_column_access
from src.services.card_service import CardService
from src.services.websocket_service import notify_comment_added, notify_comment_updated, notify_comment_deleted
from src.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    CommentList
)
from src.services.user_statistic_service import UserStatisticService
from src.logs import debug_logger

router = APIRouter(
    prefix="/boards/{board_id}/columns/{column_id}/cards/{card_id}/comments",
    tags=["comments"],
)


async def check_card_exists(
    board_id: int,
    column_id: int,
    card_id: int,
    db: AsyncSession,
    current_user: User,
    require_modify: bool = False
):
    """Check if card exists and user has access to it"""
    # First check if user has access to the column
    await check_column_access(board_id, column_id, db, current_user, require_modify)
    
    # Then check if card exists and belongs to the column
    card = await CardService.get_by_id(db=db, card_id=card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    if card.column_id != column_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card does not belong to the specified column"
        )
    
    return card


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    board_id: int,
    column_id: int,
    card_id: int,
    comment_data: CommentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a card (all roles can comment)"""
    # Check if user has read access to the card
    await check_card_exists(board_id, column_id, card_id, db, current_user, require_modify=False)
    
    # Create comment
    comment = await CommentService.create(
        db=db,
        text=comment_data.text,
        card_id=card_id,
        user_id=current_user.id
    )
    
    # Обновляем статистику комментариев пользователя
    await UserStatisticService.increment_comments(db=db, user_id=current_user.id)
    debug_logger.debug(f"Пользователь {current_user.id} добавил комментарий {comment.id}")
    
    # Add username to response
    setattr(comment, 'username', current_user.username)
    
    # Notify subscribers about the new comment
    comment_data = {
        "id": comment.id,
        "text": comment.text,
        "user_id": comment.user_id,
        "username": current_user.username,
        "card_id": comment.card_id,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None
    }
    await notify_comment_added(board_id, card_id, comment_data)
    
    return comment


@router.get("", response_model=CommentList)
async def get_comments(
    board_id: int,
    column_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all comments for a card (all roles can view)"""
    # Check if user has read access to the card
    await check_card_exists(board_id, column_id, card_id, db, current_user, require_modify=False)
    
    # Get comments
    comments = await CommentService.get_by_card_id(db=db, card_id=card_id)
    return {"comments": comments}


@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    board_id: int,
    column_id: int,
    card_id: int,
    comment_id: int,
    comment_update: CommentUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Update a comment (only comment author can edit)"""
    # Check if user has read access to the card
    await check_card_exists(board_id, column_id, card_id, db, current_user, require_modify=False)
    
    # Get comment
    comment = await CommentService.get_by_id(db=db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Check if comment belongs to the card
    if comment.card_id != card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment does not belong to the specified card"
        )
    
    # Check if user is the author of the comment
    if comment.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments"
        )
    
    # Update comment
    updated_comment = await CommentService.update(
        db=db,
        comment_id=comment_id,
        text=comment_update.text
    )
    
    # Add username to response
    setattr(updated_comment, 'username', current_user.username)
    
    # Notify subscribers about the comment update
    comment_data = {
        "id": updated_comment.id,
        "text": updated_comment.text,
        "user_id": updated_comment.user_id,
        "username": current_user.username,
        "card_id": updated_comment.card_id,
        "created_at": updated_comment.created_at.isoformat(),
        "updated_at": updated_comment.updated_at.isoformat() if updated_comment.updated_at else None
    }
    await notify_comment_updated(board_id, card_id, comment_data)
    
    return updated_comment


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    board_id: int,
    column_id: int,
    card_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment (author or board owner/admin can delete)"""
    # Check if card exists
    card = await check_card_exists(board_id, column_id, card_id, db, current_user, require_modify=False)
    
    # Get comment
    comment = await CommentService.get_by_id(db=db, comment_id=comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Check if comment belongs to the card
    if comment.card_id != card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment does not belong to the specified card"
        )
    
    # Check if user is the author or has board admin/owner permissions
    is_comment_owner = comment.user_id == current_user.id
    
    # Суперпользователи могут удалять любые комментарии
    if not current_user.is_superuser:
        # If not comment owner, check if user has admin/owner role (handled by check_column_access with require_modify=True)
        if not is_comment_owner:
            await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Delete comment
    deleted = await CommentService.delete(db=db, comment_id=comment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment"
        )
    
    # Notify subscribers about the comment deletion
    await notify_comment_deleted(board_id, card_id, comment_id) 