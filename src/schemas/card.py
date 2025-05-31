from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class CardBase(BaseModel):
    """Base schema for card data"""
    title: str
    description: Optional[str] = None
    color: Optional[str] = None
    completed: Optional[bool] = False
    deadline: Optional[datetime] = None
    
    @validator('deadline', pre=True)
    def parse_deadline(cls, value):
        if isinstance(value, str) and value.endswith('Z'):
            # Заменяем 'Z' на '+00:00' для правильной обработки UTC
            fixed_value = value.replace('Z', '+00:00')
            # Преобразуем в datetime и удаляем информацию о часовом поясе
            return datetime.fromisoformat(fixed_value).replace(tzinfo=None)
        elif isinstance(value, datetime) and value.tzinfo is not None:
            # Если уже datetime с часовым поясом, удаляем часовой пояс
            return value.replace(tzinfo=None)
        return value


class CardCreate(CardBase):
    """Schema for card creation"""
    order: Optional[int] = None
    assigned_users: Optional[List[int]] = None


class CardUpdate(BaseModel):
    """Schema for card update"""
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    order: Optional[int] = None
    completed: Optional[bool] = None
    deadline: Optional[datetime] = None
    assigned_users: Optional[List[int]] = None
    
    @validator('deadline', pre=True)
    def parse_deadline(cls, value):
        if isinstance(value, str) and value.endswith('Z'):
            # Заменяем 'Z' на '+00:00' для правильной обработки UTC
            fixed_value = value.replace('Z', '+00:00')
            # Преобразуем в datetime и удаляем информацию о часовом поясе
            return datetime.fromisoformat(fixed_value).replace(tzinfo=None)
        elif isinstance(value, datetime) and value.tzinfo is not None:
            # Если уже datetime с часовым поясом, удаляем часовой пояс
            return value.replace(tzinfo=None)
        return value


class CardInDB(CardBase):
    """Schema for card representation in the database"""
    id: int
    column_id: int
    order: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CardResponse(CardInDB):
    """Schema for card response"""
    assigned_users: List[int] = []


class CardList(BaseModel):
    """Schema for list of cards"""
    cards: List[CardResponse]


class CardOrderUpdate(BaseModel):
    """Schema for updating card order"""
    card_order: List[int]


class CardMove(BaseModel):
    """Schema for moving a card to a different column"""
    column_id: int
    order: int


class CardUserAssignment(BaseModel):
    """Schema for assigning a user to a card"""
    user_id: int 