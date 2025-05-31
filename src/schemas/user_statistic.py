from typing import Optional, List
from pydantic import BaseModel


class UserStatisticBase(BaseModel):
    """Базовая схема пользовательской статистики"""
    completed_tasks: int
    active_days_streak: int
    total_completed_tasks: int
    total_created_tasks: int
    total_comments: int


class UserStatisticCreate(UserStatisticBase):
    """Схема создания пользовательской статистики"""
    user_id: int


class UserStatisticResponse(UserStatisticBase):
    """Схема ответа с пользовательской статистикой"""
    id: int
    user_id: int
    
    class Config:
        orm_mode = True


class UserStatisticShortResponse(BaseModel):
    """Краткая схема для ответа с пользовательской статистикой (для рейтингов)"""
    user_id: int
    username: str
    total_completed_tasks: int
    position: int
    
    class Config:
        orm_mode = True


class UserStatisticList(BaseModel):
    """Схема для списка статистики пользователей"""
    items: List[UserStatisticShortResponse]
    
    class Config:
        orm_mode = True 