from fastapi import WebSocket
from typing import Dict, List, Set, Optional, Any
import json
from pydantic import BaseModel

from src.schemas.websocket import WebSocketEventType, WebSocketMessage
from src.logs.server_log import api_logger


class WebSocketMessage(BaseModel):
    """Model for WebSocket messages"""
    event: str
    data: dict


class ConnectionManager:
    """WebSocket connection manager for real-time updates"""
    
    def __init__(self):
        # {user_id: set(connections)}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # {board_id: set(user_ids)}
        self.board_subscribers: Dict[int, Set[int]] = {}
        # {board_id: set(user_ids with access)}
        self.board_access: Dict[int, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a new WebSocket client"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Log connection
        client_host = websocket.client.host if hasattr(websocket, 'client') and websocket.client else "unknown"
        api_logger.info(f"WebSocket: User {user_id} connected from {client_host}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Disconnect a WebSocket client"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            
            # Log disconnection
            client_host = websocket.client.host if hasattr(websocket, 'client') and websocket.client else "unknown"
            api_logger.info(f"WebSocket: User {user_id} disconnected from {client_host}")
    
    def set_user_board_access(self, user_id: int, board_id: int, has_access: bool = True):
        """Set whether a user has access to a board"""
        if has_access:
            if board_id not in self.board_access:
                self.board_access[board_id] = set()
            self.board_access[board_id].add(user_id)
        else:
            if board_id in self.board_access:
                self.board_access[board_id].discard(user_id)
                if not self.board_access[board_id]:
                    del self.board_access[board_id]
    
    def check_board_access(self, user_id: int, board_id: int) -> bool:
        """Check if a user has access to a board"""
        if board_id not in self.board_access:
            return False
        return user_id in self.board_access[board_id]
    
    def subscribe_to_board(self, user_id: int, board_id: int) -> bool:
        """Subscribe a user to updates for a specific board, if they have access"""
        # Check access first
        if not self.check_board_access(user_id, board_id):
            api_logger.warning(f"WebSocket: Access denied for user {user_id} to subscribe to board {board_id}")
            return False
            
        if board_id not in self.board_subscribers:
            self.board_subscribers[board_id] = set()
        self.board_subscribers[board_id].add(user_id)
        
        # Log subscription
        api_logger.info(f"WebSocket: User {user_id} subscribed to board {board_id}")
        return True
    
    def unsubscribe_from_board(self, user_id: int, board_id: int):
        """Unsubscribe a user from updates for a specific board"""
        if board_id in self.board_subscribers:
            self.board_subscribers[board_id].discard(user_id)
            if not self.board_subscribers[board_id]:
                del self.board_subscribers[board_id]
            
            # Log unsubscription
            api_logger.info(f"WebSocket: User {user_id} unsubscribed from board {board_id}")
    
    async def broadcast_to_board(self, board_id: int, message: WebSocketMessage):
        """Broadcast a message to all users subscribed to a board"""
        if board_id not in self.board_subscribers:
            return
            
        # Validate message data structure based on event type
        try:
            self._validate_message_data(message)
        except ValueError as e:
            api_logger.error(f"WebSocket: Invalid message data for event {message.event}: {str(e)}")
            return
            
        json_message = message.model_dump_json()
        subscriber_count = len(self.board_subscribers[board_id])
        
        # Log broadcast
        api_logger.info(f"WebSocket: Broadcasting event '{message.event}' to {subscriber_count} subscribers of board {board_id}")
        
        for user_id in self.board_subscribers[board_id]:
            await self.send_to_user(user_id, json_message)
    
    def _validate_message_data(self, message: WebSocketMessage):
        """Validate message data structure based on event type"""
        event = message.event
        data = message.data
        
        required_fields = {
            WebSocketEventType.BOARD_UPDATED: ["board_id", "board"],
            WebSocketEventType.BOARD_DELETED: ["board_id"],
            WebSocketEventType.COLUMN_CREATED: ["board_id", "column"],
            WebSocketEventType.COLUMN_UPDATED: ["board_id", "column"],
            WebSocketEventType.COLUMN_DELETED: ["board_id", "column_id"],
            WebSocketEventType.CARD_CREATED: ["board_id", "card"],
            WebSocketEventType.CARD_UPDATED: ["board_id", "card"],
            WebSocketEventType.CARD_DELETED: ["board_id", "card_id"],
            WebSocketEventType.CARD_MOVED: ["board_id", "card", "from_column_id", "to_column_id"],
            WebSocketEventType.COLUMNS_REORDERED: ["columns"],
            WebSocketEventType.CARD_DEADLINE_UPDATED: ["board_id", "card_id", "deadline"],
            WebSocketEventType.USER_ROLE_CHANGED: ["board_id", "user_id", "role"],
            WebSocketEventType.USER_ADDED: ["board_id", "user"],
            WebSocketEventType.USER_REMOVED: ["board_id", "user_id"],
            WebSocketEventType.COMMENT_ADDED: ["board_id", "card_id", "comment"],
            WebSocketEventType.COMMENT_UPDATED: ["board_id", "card_id", "comment"],
            WebSocketEventType.COMMENT_DELETED: ["board_id", "card_id", "comment_id"],
            WebSocketEventType.REACTION_ADDED: ["board_id", "card_id", "comment_id", "reaction"],
            WebSocketEventType.REACTION_REMOVED: ["board_id", "card_id", "comment_id", "reaction_id"],
        }
        
        if event in required_fields:
            for field in required_fields[event]:
                if field not in data:
                    raise ValueError(f"Missing required field '{field}' for event '{event}'")
    
    async def send_to_user(self, user_id: int, message: str):
        """Send a message to a specific user on all their connections"""
        if user_id not in self.active_connections:
            return
        
        # Parse message for logging purposes
        try:
            message_data = json.loads(message)
            event_type = message_data.get("event", "unknown")
            api_logger.info(f"WebSocket: Sending event '{event_type}' to user {user_id}")
        except:
            api_logger.info(f"WebSocket: Sending message to user {user_id}")
            
        disconnected_websockets = set()
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                api_logger.error(f"WebSocket: Failed to send message to user {user_id}: {str(e)}")
                disconnected_websockets.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected_websockets:
            self.active_connections[user_id].discard(websocket)
        
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]


# Create global connection manager
manager = ConnectionManager()


# Basic notification function
async def notify(board_id: int, event_type: str, data: dict, log_details: str = None):
    """Universal notification function for board events"""
    message = WebSocketMessage(event=event_type, data=data)
    await manager.broadcast_to_board(board_id, message)
    
    # Create log message
    log_msg = f"WebSocket: Notified {event_type} for board {board_id}"
    if log_details:
        log_msg += f", {log_details}"
    api_logger.info(log_msg)


# WebSocket notification functions
async def notify_board_updated(board_id: int, board_data: dict):
    """Notify all board subscribers that a board has been updated"""
    data = {"board_id": board_id, "board": board_data}
    await notify(board_id, WebSocketEventType.BOARD_UPDATED, data)


async def notify_board_deleted(board_id: int):
    """Notify all board subscribers that a board has been deleted"""
    data = {"board_id": board_id}
    await notify(board_id, WebSocketEventType.BOARD_DELETED, data)


async def notify_column_created(board_id: int, column_data: dict):
    """Notify all board subscribers that a column has been created"""
    data = {"board_id": board_id, "column": column_data}
    await notify(board_id, WebSocketEventType.COLUMN_CREATED, data)


async def notify_column_updated(board_id: int, column_data: dict):
    """Notify all board subscribers that a column has been updated"""
    data = {"board_id": board_id, "column": column_data}
    await notify(board_id, WebSocketEventType.COLUMN_UPDATED, data)


async def notify_column_deleted(board_id: int, column_id: int):
    """Notify all board subscribers that a column has been deleted"""
    data = {"board_id": board_id, "column_id": column_id}
    log_details = f"column {column_id}"
    await notify(board_id, WebSocketEventType.COLUMN_DELETED, data, log_details)


async def notify_card_created(board_id: int, card_data: dict):
    """Notify all board subscribers that a card has been created"""
    data = {"board_id": board_id, "card": card_data}
    await notify(board_id, WebSocketEventType.CARD_CREATED, data)


async def notify_card_updated(board_id: int, card_data: dict):
    """Notify all board subscribers that a card has been updated"""
    data = {"board_id": board_id, "card": card_data}
    await notify(board_id, WebSocketEventType.CARD_UPDATED, data)


async def notify_card_deleted(board_id: int, card_id: int):
    """Notify all board subscribers that a card has been deleted"""
    data = {"board_id": board_id, "card_id": card_id}
    log_details = f"card {card_id}"
    await notify(board_id, WebSocketEventType.CARD_DELETED, data, log_details)


async def notify_card_moved(board_id: int, card_data: dict, from_column_id: int, to_column_id: int):
    """Notify all board subscribers that a card has been moved"""
    data = {
        "board_id": board_id, 
        "card": card_data,
        "from_column_id": from_column_id,
        "to_column_id": to_column_id
    }
    log_details = f"from column {from_column_id} to column {to_column_id}"
    await notify(board_id, WebSocketEventType.CARD_MOVED, data, log_details)


async def notify_columns_reordered(board_id: int, columns_data: List[Dict[str, Any]]):
    """Notify all board subscribers that columns have been reordered"""
    data = {"columns": columns_data}
    await notify(board_id, WebSocketEventType.COLUMNS_REORDERED, data)


async def notify_card_deadline_updated(board_id: int, card_id: int, deadline_data: Dict[str, Any]):
    """Notify all board subscribers that a card's deadline has been updated"""
    data = {"board_id": board_id, "card_id": card_id, "deadline": deadline_data}
    log_details = f"card {card_id}"
    await notify(board_id, WebSocketEventType.CARD_DEADLINE_UPDATED, data, log_details)


async def notify_user_role_changed(board_id: int, user_id: int, new_role: str):
    """Notify all board subscribers that a user's role has been changed"""
    data = {"board_id": board_id, "user_id": user_id, "role": new_role}
    log_details = f"user {user_id}, new role {new_role}"
    await notify(board_id, WebSocketEventType.USER_ROLE_CHANGED, data, log_details)


async def notify_user_added(board_id: int, user_data: Dict[str, Any]):
    """Notify all board subscribers that a user has been added to the board"""
    data = {"board_id": board_id, "user": user_data}
    user_id = user_data.get("id", "unknown")
    log_details = f"user {user_id}"
    await notify(board_id, WebSocketEventType.USER_ADDED, data, log_details)


async def notify_user_removed(board_id: int, user_id: int):
    """Notify all board subscribers that a user has been removed from the board"""
    data = {"board_id": board_id, "user_id": user_id}
    log_details = f"user {user_id}"
    await notify(board_id, WebSocketEventType.USER_REMOVED, data, log_details)


async def notify_comment_added(board_id: int, card_id: int, comment_data: Dict[str, Any]):
    """Notify all board subscribers that a comment has been added to a card"""
    data = {"board_id": board_id, "card_id": card_id, "comment": comment_data}
    log_details = f"card {card_id}"
    await notify(board_id, WebSocketEventType.COMMENT_ADDED, data, log_details)


async def notify_comment_updated(board_id: int, card_id: int, comment_data: Dict[str, Any]):
    """Notify all board subscribers that a comment has been updated"""
    data = {"board_id": board_id, "card_id": card_id, "comment": comment_data}
    log_details = f"card {card_id}"
    await notify(board_id, WebSocketEventType.COMMENT_UPDATED, data, log_details)


async def notify_comment_deleted(board_id: int, card_id: int, comment_id: int):
    """Notify all board subscribers that a comment has been deleted"""
    data = {"board_id": board_id, "card_id": card_id, "comment_id": comment_id}
    log_details = f"card {card_id}, comment {comment_id}"
    await notify(board_id, WebSocketEventType.COMMENT_DELETED, data, log_details)


async def notify_reaction_added(board_id: int, card_id: int, comment_id: int, reaction_data: Dict[str, Any]):
    """Notify all board subscribers that a reaction has been added to a comment"""
    data = {
        "board_id": board_id, 
        "card_id": card_id, 
        "comment_id": comment_id, 
        "reaction": reaction_data
    }
    log_details = f"card {card_id}, comment {comment_id}"
    await notify(board_id, WebSocketEventType.REACTION_ADDED, data, log_details)


async def notify_reaction_removed(board_id: int, card_id: int, comment_id: int, reaction_id: int):
    """Notify all board subscribers that a reaction has been removed from a comment"""
    data = {
        "board_id": board_id, 
        "card_id": card_id, 
        "comment_id": comment_id, 
        "reaction_id": reaction_id
    }
    log_details = f"card {card_id}, comment {comment_id}, reaction {reaction_id}"
    await notify(board_id, WebSocketEventType.REACTION_REMOVED, data, log_details) 