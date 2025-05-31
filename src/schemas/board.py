from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from src.schemas.column import ColumnResponse
from src.models.board import BoardUserRole


class BoardBase(BaseModel):
    """Base schema for board data"""
    title: str
    description: Optional[str] = None


class BoardCreate(BoardBase):
    """Schema for board creation"""
    pass


class BoardUpdate(BaseModel):
    """Schema for board update"""
    title: Optional[str] = None
    description: Optional[str] = None


class BoardInDB(BoardBase):
    """Schema for board representation in the database"""
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BoardResponse(BoardInDB):
    """Schema for board response"""
    pass


class BoardList(BaseModel):
    """Schema for list of boards"""
    boards: List[BoardResponse]
    total: int = 0


class BoardUserRoleDTO(BaseModel):
    """Schema for board user role"""
    role: BoardUserRole


class BoardByEmailRequest(BaseModel):
    """Schema for requesting board by email"""
    board_id: int
    email: str


class BoardCompleteResponse(BoardInDB):
    """Schema for complete board response with columns and their cards"""
    columns: List[ColumnResponse] = []


class BoardStatistics(BaseModel):
    """Schema for board statistics"""
    total_cards: int = 0
    completed_cards: int = 0
    archived_cards: int = 0
    total_columns: int = 0
    total_comments: int = 0
    cards_with_deadline: int = 0
    overdue_cards: int = 0


class BoardFullStatsResponse(BoardInDB):
    """Schema for full board statistics with all details"""
    columns: List[ColumnResponse] = []
    statistics: BoardStatistics
    
    
class UserBoardsStatsResponse(BaseModel):
    """Schema for all user boards with full statistics"""
    boards: List[BoardFullStatsResponse]
    total_boards: int = 0
    global_statistics: BoardStatistics 