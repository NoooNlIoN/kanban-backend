from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class CommentBase(BaseModel):
    """Base schema for comment data"""
    text: str


class CommentCreate(CommentBase):
    """Schema for comment creation"""
    card_id: int


class CommentUpdate(BaseModel):
    """Schema for comment update"""
    text: str


class CommentInDB(CommentBase):
    """Schema for comment representation in the database"""
    id: int
    card_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CommentResponse(CommentInDB):
    """Schema for comment response, includes username"""
    username: str


class CommentList(BaseModel):
    """Schema for list of comments"""
    comments: List[CommentResponse] 