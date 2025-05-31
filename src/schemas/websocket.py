from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from enum import Enum


class WebSocketEventType(str, Enum):
    """Types of WebSocket events"""
    BOARD_UPDATED = "board_updated"
    BOARD_DELETED = "board_deleted"
    COLUMN_CREATED = "column_created"
    COLUMN_UPDATED = "column_updated"
    COLUMN_DELETED = "column_deleted"
    COLUMNS_REORDERED = "columns_reordered"
    CARD_CREATED = "card_created"
    CARD_UPDATED = "card_updated"
    CARD_DELETED = "card_deleted"
    CARD_MOVED = "card_moved"
    CARD_DEADLINE_UPDATED = "card_deadline_updated"
    CARD_ASSIGNMENT_UPDATED = "card_assignment_updated"
    USER_ADDED = "user_added"
    USER_REMOVED = "user_removed"
    USER_ROLE_CHANGED = "user_role_changed"
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WebSocketMessage(BaseModel):
    """Base message for WebSocket communication"""
    event: WebSocketEventType
    data: Dict[str, Any]


class WebSocketCommand(BaseModel):
    """Commands from client to server"""
    command: str
    data: Dict[str, Any]


class WebSocketSubscription(BaseModel):
    """Subscription request from client"""
    board_id: int


class WebSocketErrorMessage(BaseModel):
    """Error message for WebSocket communication"""
    message: str
    code: Optional[int] = None 