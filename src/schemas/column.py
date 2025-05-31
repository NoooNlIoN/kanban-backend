from datetime import datetime
from typing import List, Optional, ForwardRef
from pydantic import BaseModel, Field

# Create a forward reference for CardResponse
CardResponse = ForwardRef('CardResponse')


class ColumnBase(BaseModel):
    """Base schema for column data"""
    title: str
    

class ColumnCreate(ColumnBase):
    """Schema for column creation"""
    order: Optional[int] = None


class ColumnUpdate(BaseModel):
    """Schema for column update"""
    title: Optional[str] = None
    order: Optional[int] = None


class ColumnInDB(ColumnBase):
    """Schema for column representation in the database"""
    id: int
    board_id: int
    order: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ColumnResponse(ColumnInDB):
    """Schema for column response"""
    cards: List[CardResponse] = []
    
    class Config:
        from_attributes = True


class ColumnList(BaseModel):
    """Schema for list of columns"""
    columns: List[ColumnResponse]


class ColumnOrderUpdate(BaseModel):
    """Schema for updating column order"""
    column_order: List[int]


# Resolve the forward reference after the CardResponse is imported
from src.schemas.card import CardResponse
ColumnResponse.model_rebuild()