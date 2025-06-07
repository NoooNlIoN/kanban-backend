from typing import List, Union, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.models.user import User
from src.models.board import BoardUserRole
from src.services.column_service import ColumnService
from src.services.card_service import CardService
from src.api.v1.columns import check_board_access
from src.services.websocket_service import (
    notify_card_created,
    notify_card_updated,
    notify_card_deleted,
    notify_card_moved
)
from src.schemas.card import (
    CardCreate, 
    CardResponse, 
    CardUpdate, 
    CardList,
    CardOrderUpdate,
    CardMove,
    CardUserAssignment
)
from src.logs import debug_logger, api_logger
from src.models.card import Card
from src.services.user_statistic_service import UserStatisticService


def prepare_card_for_response(card: Union[Card, Dict[str, Any]]) -> Union[Card, Dict[str, Any]]:
    """
    Подготовка карточки для отправки в ответе API
    Преобразует объекты User в списке assigned_users в список их ID
    Оставляет теги как есть (они уже в правильном формате)
    
    Args:
        card: Карточка (объект модели или словарь)
        
    Returns:
        Карточка с преобразованными данными
    """
    if isinstance(card, dict):
        # Если карточка - словарь (например, при ручном создании ответа)
        if "assigned_users" in card and card["assigned_users"] and not all(isinstance(u, int) for u in card["assigned_users"]):
            card["assigned_users"] = [getattr(user, "id", user) for user in card["assigned_users"]]
        # Теги оставляем как есть - они уже в правильном формате для API
        return card
    else:
        # Если карточка - объект модели
        if hasattr(card, "assigned_users") and card.assigned_users:
            # Обработка каждого элемента - если это объект с атрибутом id, берем его id, иначе используем сам элемент
            card.__dict__["assigned_users"] = [
                user.id if hasattr(user, "id") else user 
                for user in card.assigned_users
            ]
        # Теги уже загружены правильно через selectinload и будут автоматически сериализованы
        return card


router = APIRouter(
    prefix="/boards/{board_id}/columns/{column_id}/cards",
    tags=["cards"],
)

# Define a new router for board-level card operations
board_cards_router = APIRouter(
    prefix="/boards/{board_id}/cards",
    tags=["cards"],
)


async def check_column_access(
    board_id: int,
    column_id: int,
    db: AsyncSession,
    current_user: User,
    require_modify: bool = False
):
    """
    Check if user has access to the column and if it belongs to the specified board
    
    Args:
        board_id: ID of the board
        column_id: ID of the column
        db: Database session
        current_user: Current authenticated user
        require_modify: If True, checks if user has modify permissions (Owner/Admin),
                        otherwise checks if user has read access (Owner/Admin/Member)
    """
    # First check if user has access to the board
    await check_board_access(board_id, db, current_user, require_modify)
    
    # Then check if column exists and belongs to the board
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
    
    return column


@router.put("/reorder", status_code=status.HTTP_200_OK)
async def reorder_cards(
    board_id: int,
    column_id: int,
    card_order: CardOrderUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Reorder cards in a column (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    card_order.card_order = [int(card_id) for card_id in card_order.card_order]

    success = await CardService.reorder_cards(
        db=db,
        column_id=column_id,
        card_order=card_order.card_order
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder cards"
        )
    
    # Get updated cards to notify subscribers
    cards = await CardService.get_by_column_id(db=db, column_id=column_id)
    for card in cards:
        card_data = {
            "id": card.id,
            "title": card.title,
            "description": card.description,
            "column_id": card.column_id,
            "color": card.color,
            "order": card.order
        }
        await notify_card_updated(board_id, card_data)
    
    return {"message": "Cards reordered successfully"}

@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    board_id: int,
    column_id: int,
    card_create: CardCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new card in a column (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    card = await CardService.create(
        db=db,
        title=card_create.title,
        description=card_create.description,
        column_id=column_id,
        color=card_create.color,
        order=card_create.order,
        assigned_users=card_create.assigned_users
    )
    
    # Обновляем статистику созданных задач пользователя
    await UserStatisticService.increment_created_tasks(db=db, user_id=current_user.id)
    debug_logger.debug(f"Пользователь {current_user.id} создал задачу {card.id}")
    
    # Преобразование объектов User в список ID
    card = prepare_card_for_response(card)
    
    # Notify subscribers about the new card
    card_data = {
        "id": card.id,
        "title": card.title,
        "description": card.description,
        "column_id": card.column_id,
        "color": card.color,
        "order": card.order,
        "assigned_users": getattr(card, "assigned_users", [])
    }
    await notify_card_created(board_id, card_data)
    
    return card


@router.get("", response_model=CardList)
async def get_cards(
    board_id: int,
    column_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get all cards in a column (All board members)"""
    # Check if user has read access
    await check_column_access(board_id, column_id, db, current_user, require_modify=False)
    
    cards = await CardService.get_by_column_id(
        db=db,
        column_id=column_id,
        load_relations=True
    )
    
    # Преобразование списка объектов User в список ID для всех карточек
    for card in cards:
        prepare_card_for_response(card)
        
    return {"cards": cards}


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    board_id: int,
    column_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific card by ID (All board members)"""
    # Check if user has read access
    await check_column_access(board_id, column_id, db, current_user, require_modify=False)
    
    card = await CardService.get_by_id(db=db, card_id=card_id, load_relations=True)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if the card belongs to the specified column
    if card.column_id != column_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card does not belong to the specified column"
        )
    
    # Преобразование списка объектов User в список ID
    card = prepare_card_for_response(card)
    
    return card


@router.put("/{card_id}", response_model=CardResponse)
async def update_card(
    board_id: int,
    column_id: int,
    card_id: int,
    card_update: CardUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Update a card (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the card exists and belongs to the specified column
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
    
    # Update the card
    updated_card = await CardService.update(
        db=db,
        card_id=card_id,
        title=card_update.title,
        description=card_update.description,
        color=card_update.color,
        order=card_update.order,
        completed=card_update.completed,
        deadline=card_update.deadline,
        assigned_users=card_update.assigned_users
    )
    
    # Преобразование объектов User в список ID
    updated_card = prepare_card_for_response(updated_card)
    
    # Notify subscribers about the card update
    card_data = {
        "id": updated_card.id,
        "title": updated_card.title,
        "description": updated_card.description,
        "column_id": updated_card.column_id,
        "color": updated_card.color,
        "order": updated_card.order,
        "assigned_users": updated_card.assigned_users
    }
    await notify_card_updated(board_id, card_data)
    
    return updated_card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    board_id: int,
    column_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a card (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the card exists and belongs to the specified column
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
    
    # Delete the card
    deleted = await CardService.delete(db=db, card_id=card_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete card"
        )
    
    # Notify subscribers about the card deletion
    await notify_card_deleted(board_id, card_id)





@router.put("/{card_id}/move", response_model=CardResponse)
async def move_card(
    board_id: int,
    column_id: int,
    card_id: int,
    card_move: CardMove,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Move a card to a different column (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the target column exists and belongs to the same board
    target_column = await ColumnService.get_by_id(db=db, column_id=card_move.column_id)
    if not target_column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target column not found"
        )
    
    if target_column.board_id != board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target column does not belong to the specified board"
        )
    
    # Check if the card exists and belongs to the specified column
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
    
    # Store original column for notification
    from_column_id = card.column_id
    
    # Move the card
    moved_card = await CardService.move_card(
        db=db,
        card_id=card_id,
        new_column_id=card_move.column_id,
        new_order=card_move.order
    )
    
    # Преобразование объектов User в список ID
    moved_card = prepare_card_for_response(moved_card)
    
    # Notify subscribers about the card move
    card_data = {
        "id": moved_card.id,
        "title": moved_card.title,
        "description": moved_card.description,
        "column_id": moved_card.column_id,
        "color": moved_card.color,
        "order": moved_card.order,
        "assigned_users": moved_card.assigned_users
    }
    await notify_card_moved(
        board_id=board_id,
        card_data=card_data,
        from_column_id=from_column_id,
        to_column_id=moved_card.column_id
    )
    
    return moved_card


@router.post("/{card_id}/assign", status_code=status.HTTP_200_OK)
async def assign_user_to_card(
    board_id: int,
    column_id: int,
    card_id: int,
    assignment: CardUserAssignment,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Assign a user to a card (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the card exists and belongs to the specified column
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
    
    # Assign user to card
    success = await CardService.assign_user(
        db=db,
        card_id=card_id,
        user_id=assignment.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign user to card"
        )
    
    # Get updated card to notify subscribers
    updated_card = await CardService.get_by_id(db=db, card_id=card_id, load_relations=True)
    card_data = {
        "id": updated_card.id,
        "title": updated_card.title,
        "description": updated_card.description,
        "column_id": updated_card.column_id,
        "color": updated_card.color,
        "order": updated_card.order,
        "assigned_users": [user.id for user in updated_card.assigned_users]
    }
    await notify_card_updated(board_id, card_data)
    
    return {"message": "User assigned to card successfully"}


@router.delete("/{card_id}/unassign/{user_id}", status_code=status.HTTP_200_OK)
async def unassign_user_from_card(
    board_id: int,
    column_id: int,
    card_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Unassign a user from a card (Owner/Admin only)"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the card exists and belongs to the specified column
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
    
    # Unassign user from card
    success = await CardService.unassign_user(
        db=db,
        card_id=card_id,
        user_id=user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unassign user from card"
        )
    
    # Get updated card to notify subscribers
    updated_card = await CardService.get_by_id(db=db, card_id=card_id, load_relations=True)
    card_data = {
        "id": updated_card.id,
        "title": updated_card.title,
        "description": updated_card.description,
        "column_id": updated_card.column_id,
        "color": updated_card.color,
        "order": updated_card.order,
        "assigned_users": [user.id for user in updated_card.assigned_users]
    }
    await notify_card_updated(board_id, card_data)
    
    return {"message": "User unassigned from card successfully"}


@board_cards_router.put("/{card_id}/move", response_model=CardResponse)
async def move_card_between_columns(
    request: Request,
    board_id: int,
    card_id: int,
    card_move: CardMove,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Move a card to a different column without requiring source column ID (Owner/Admin only)"""
    debug_logger.log_data("Move card request", {
        "board_id": board_id,
        "card_id": card_id,
        "target_column": card_move.column_id,
        "new_order": card_move.order,
        "user_id": current_user.id
    })
    
    try:
        # Check if user has board access with modify permissions
        await check_board_access(board_id, db, current_user, require_modify=True)
        
        # Check if the target column exists and belongs to the board
        target_column = await ColumnService.get_by_id(db=db, column_id=card_move.column_id)
        if not target_column:
            debug_logger.warning(f"Целевая колонка {card_move.column_id} не найдена при перемещении карточки {card_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target column not found"
            )
        
        if target_column.board_id != board_id:
            debug_logger.warning(
                f"Целевая колонка {card_move.column_id} принадлежит доске {target_column.board_id}, "
                f"а не запрошенной доске {board_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target column does not belong to the specified board"
            )
        
        # Check if the card exists
        card = await CardService.get_by_id(db=db, card_id=card_id)
        if not card:
            debug_logger.warning(f"Карточка {card_id} не найдена при попытке перемещения")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found"
            )
        
        # Check if card belongs to the board (by checking if its column belongs to the board)
        card_column = await ColumnService.get_by_id(db=db, column_id=card.column_id)
        if not card_column or card_column.board_id != board_id:
            debug_logger.warning(
                f"Карточка {card_id} находится в колонке {card.column_id}, которая "
                f"не принадлежит доске {board_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Card does not belong to the specified board"
            )
        
        # Store original column for notification
        from_column_id = card.column_id
        
        # Move the card
        moved_card = await CardService.move_card(
            db=db,
            card_id=card_id,
            new_column_id=card_move.column_id,
            new_order=card_move.order
        )
        
        if not moved_card:
            debug_logger.error(f"Ошибка при перемещении карточки {card_id} в колонку {card_move.column_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to move card"
            )
        
        # Преобразование объектов User в список ID
        moved_card = prepare_card_for_response(moved_card)
        
        # Notify subscribers about the card move
        card_data = {
            "id": moved_card.id,
            "title": moved_card.title,
            "description": moved_card.description,
            "column_id": moved_card.column_id,
            "color": moved_card.color,
            "order": moved_card.order,
            "assigned_users": moved_card.assigned_users
        }
        await notify_card_moved(
            board_id=board_id,
            card_data=card_data,
            from_column_id=from_column_id,
            to_column_id=moved_card.column_id
        )
        
        debug_logger.info(f"Карточка {card_id} успешно перемещена из колонки {from_column_id} в колонку {moved_card.column_id}")
        return moved_card
    except HTTPException:
        # Перебрасываем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем неожиданные ошибки
        error_message = f"Непредвиденная ошибка при перемещении карточки {card_id}: {str(e)}"
        debug_logger.log_exception(error_message)
        api_logger.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred when moving card"
        )


@router.post("/{card_id}/toggle-completed", response_model=CardResponse)
async def toggle_card_completed(
    board_id: int,
    column_id: int,
    card_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Toggle the completed status of a card"""
    # Check if user has modify permissions
    await check_column_access(board_id, column_id, db, current_user, require_modify=True)
    
    # Check if the card exists and belongs to the specified column
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
    
    # Сохраняем предыдущий статус для сравнения
    previous_completed_status = card.completed
    
    # Toggle the completed status
    updated_card = await CardService.toggle_completed(db=db, card_id=card_id)
    
    # Обновляем статистику пользователя
    if updated_card.completed != previous_completed_status:
        if updated_card.completed:
            # Если задача стала выполненной, увеличиваем счетчик
            await UserStatisticService.increment_completed_tasks(db=db, user_id=current_user.id)
            debug_logger.debug(f"Пользователь {current_user.id} завершил задачу {card_id}")
        else:
            # Если задача стала невыполненной, уменьшаем счетчик
            await UserStatisticService.decrement_completed_tasks(db=db, user_id=current_user.id)
            debug_logger.debug(f"Пользователь {current_user.id} отменил завершение задачи {card_id}")
            
    # Преобразование объектов User в список ID
    updated_card = prepare_card_for_response(updated_card)
    
    # Notify subscribers about the card update
    card_data = {
        "id": updated_card.id,
        "title": updated_card.title,
        "description": updated_card.description,
        "column_id": updated_card.column_id,
        "color": updated_card.color,
        "order": updated_card.order,
        "completed": updated_card.completed,
        "assigned_users": updated_card.assigned_users
    }
    await notify_card_updated(board_id, card_data)
    
    return updated_card 