from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.db.database import get_async_session
from src.schemas.auth import UserResponse, UserUpdate
from src.schemas.user_statistic import UserStatisticResponse, UserStatisticShortResponse
from src.services.user_service import UserService
from src.api.dependencies.auth import get_current_active_user, get_current_superuser
from src.models.user import User
from src.services.user_statistic_service import UserStatisticService

# Create router
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(get_current_superuser)  # Only superusers can access
):
    """
    Get all users
    """
    users = await UserService.get_all(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific user
    """
    # Only allow superusers or the user themselves to access their info
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
        
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a user
    """
    # Only allow superusers or the user themselves to update their info
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
        
    # Check if user exists
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if new email already exists
    if user_data.email and user_data.email != user.email:
        existing_user = await UserService.get_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Check if new username already exists
    if user_data.username and user_data.username != user.username:
        existing_user = await UserService.get_by_username(db, user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Update user
    updated_user = await UserService.update(
        db, 
        user_id, 
        email=user_data.email,
        username=user_data.username,
        password=user_data.password
    )
    
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a user
    """
    # Only allow superusers or the user themselves to delete their account
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
        
    # Check if user exists
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user
    result = await UserService.delete(db, user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.get("/{user_id}/statistics", response_model=UserStatisticResponse)
async def get_user_statistics(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить статистику пользователя
    """
    # Только суперпользователь или сам пользователь могут просматривать статистику
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
        
    # Проверяем существование пользователя
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Получаем или создаем статистику пользователя
    user_stats = await UserStatisticService.get_or_create(db, user_id)
    return user_stats


@router.get("/top/completed-tasks", response_model=List[UserStatisticShortResponse])
async def get_top_users_completed_tasks(
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(get_current_active_user)
):
    """
    Получить рейтинг пользователей по количеству выполненных задач
    """
    top_stats = await UserStatisticService.get_top_users_by_completed_tasks(db, limit)
    
    # Получаем имена пользователей для статистики
    result = []
    for stat in top_stats:
        user = await UserService.get_by_id(db, stat.user_id)
        if user:
            result.append({
                "user_id": stat.user_id,
                "username": user.username,
                "total_completed_tasks": stat.total_completed_tasks,
                "position": len(result) + 1  # Позиция в рейтинге
            })
    
    return result 