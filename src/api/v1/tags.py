from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.permissions import check_board_permissions
from src.models.user import User
from src.models.board import BoardUserRole
from src.schemas.tag import TagCreate, TagResponse, TagUpdate, TagAssignment
from src.services.tag_service import TagService
from src.services.board_service import BoardService
from src.services.card_service import CardService
from src.models.column import Column

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_create: TagCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Создание нового тега для доски"""
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=tag_create.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN],
        user=current_user
    )
    
    # Проверяем существование доски
    board = await BoardService.get_by_id(db=db, board_id=tag_create.board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Доска не найдена"
        )
    
    tag = await TagService.create(
        db=db,
        board_id=tag_create.board_id,
        name=tag_create.name,
        color=tag_create.color,
    )
    
    return tag


@router.get("/board/{board_id}", response_model=List[TagResponse])
async def get_board_tags(
    board_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Получение всех тегов доски"""
    # Проверка прав доступа к доске для просмотра (любая роль)
    await check_board_permissions(
        db=db,
        board_id=board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    tags = await TagService.get_by_board_id(db=db, board_id=board_id)
    return tags


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Получение тега по ID"""
    tag = await TagService.get_by_id(db=db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не найден"
        )
    
    # Проверка прав доступа к доске, к которой относится тег
    await check_board_permissions(
        db=db,
        board_id=tag.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: int,
    tag_update: TagUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Обновление тега (только owner и admin)"""
    # Проверяем существование тега
    tag = await TagService.get_by_id(db=db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не найден"
        )
    
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=tag.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN],
        user=current_user
    )
    
    # Обновляем тег
    updated_tag = await TagService.update(
        db=db,
        tag_id=tag_id,
        name=tag_update.name,
        color=tag_update.color
    )
    
    return updated_tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Удаление тега (только owner и admin)"""
    # Проверяем существование тега
    tag = await TagService.get_by_id(db=db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не найден"
        )
    
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=tag.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN],
        user=current_user
    )
    
    # Удаляем тег
    deleted = await TagService.delete(db=db, tag_id=tag_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось удалить тег"
        )


@router.get("/card/{card_id}", response_model=List[TagResponse])
async def get_card_tags(
    card_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Получение всех тегов карточки"""
    # Получаем карточку
    card = await CardService.get_by_id(db=db, card_id=card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карточка не найдена"
        )
    
    # Получаем колонку напрямую через ID
    column = await db.get(Column, card.column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Колонка не найдена"
        )
    
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=column.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    # Получаем теги карточки
    tags = await TagService.get_card_tags(db=db, card_id=card_id)
    return tags


@router.post("/assign", status_code=status.HTTP_200_OK)
async def assign_tag_to_card(
    assignment: TagAssignment,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Назначение тега карточке"""
    # Проверяем существование тега
    tag = await TagService.get_by_id(db=db, tag_id=assignment.tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не найден"
        )
    
    # Проверяем существование карточки
    card = await CardService.get_by_id(db=db, card_id=assignment.card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карточка не найдена"
        )
    
    # Получаем колонку напрямую через ID
    column = await db.get(Column, card.column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Колонка не найдена"
        )
    
    # Проверяем, что тег относится к той же доске, что и карточка
    if tag.board_id != column.board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тег и карточка должны относиться к одной доске"
        )
    
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=column.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    # Проверяем, не назначен ли уже этот тег данной карточке
    existing_tags = await TagService.get_card_tags(db=db, card_id=assignment.card_id)
    if any(existing_tag.id == assignment.tag_id for existing_tag in existing_tags):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тег уже назначен этой карточке"
        )
    
    # Назначаем тег карточке
    success = await TagService.assign_to_card(
        db=db, 
        tag_id=assignment.tag_id, 
        card_id=assignment.card_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось назначить тег карточке"
        )
    
    return {"status": "success", "message": "Тег успешно назначен карточке"}


@router.post("/unassign", status_code=status.HTTP_200_OK)
async def remove_tag_from_card(
    assignment: TagAssignment,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Удаление тега с карточки"""
    # Проверяем существование тега
    tag = await TagService.get_by_id(db=db, tag_id=assignment.tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не найден"
        )
    
    # Проверяем существование карточки
    card = await CardService.get_by_id(db=db, card_id=assignment.card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карточка не найдена"
        )
    
    # Получаем колонку напрямую через ID
    column = await db.get(Column, card.column_id)
    if not column:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Колонка не найдена"
        )
    
    # Проверка прав доступа к доске
    await check_board_permissions(
        db=db,
        board_id=column.board_id,
        user_id=current_user.id,
        required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
        user=current_user
    )
    
    # Удаляем тег с карточки
    success = await TagService.remove_from_card(
        db=db, 
        tag_id=assignment.tag_id, 
        card_id=assignment.card_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тег не был назначен этой карточке"
        )
    
    return {"status": "success", "message": "Тег успешно удален с карточки"} 