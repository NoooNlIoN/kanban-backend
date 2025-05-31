from typing import Optional
from pydantic import BaseModel, Field


class TagBase(BaseModel):
    """Базовая схема тега"""
    name: str = Field(..., max_length=50, description="Название тега")
    color: Optional[str] = Field(None, max_length=7, description="Цвет тега (HEX формат)")


class TagCreate(TagBase):
    """Схема для создания тега"""
    board_id: int = Field(..., description="ID доски, к которой относится тег")


class TagUpdate(BaseModel):
    """Схема для обновления тега"""
    name: Optional[str] = Field(None, max_length=50, description="Название тега")
    color: Optional[str] = Field(None, max_length=7, description="Цвет тега (HEX формат)")


class TagResponse(TagBase):
    """Схема для ответа с информацией о теге"""
    id: int = Field(..., description="Уникальный идентификатор тега")
    board_id: int = Field(..., description="ID доски, к которой относится тег")
    
    class Config:
        orm_mode = True


class TagAssignment(BaseModel):
    """Схема для назначения или удаления тега с карточки"""
    tag_id: int = Field(..., description="ID тега")
    card_id: int = Field(..., description="ID карточки") 