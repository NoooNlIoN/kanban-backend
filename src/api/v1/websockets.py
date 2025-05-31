from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import json
from typing import Optional, Dict, Any

from src.db.database import get_async_session
from src.api.dependencies.auth import get_current_user_from_token
from src.models.user import User
from src.models.board import BoardUserRole
from src.services.board_service import BoardService
from src.services.websocket_service import manager
from src.logs.server_log import api_logger
from src.schemas.websocket import (
    WebSocketEventType,
    WebSocketMessage,
    WebSocketCommand,
    WebSocketErrorMessage,
    WebSocketSubscription
)

router = APIRouter(tags=["websockets"])


async def get_token_from_query(query_token: str) -> str:
    """Extract token from query parameters"""
    if not query_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return query_token


@router.websocket("/ws/updates")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    """
    WebSocket endpoint for real-time updates.
    
    Authentication is done via token query parameter:
    ws://example.com/api/v1/ws/updates?token=your_access_token
    
    Commands from client:
    - {"command": "subscribe", "data": {"board_id": 123}}
    - {"command": "unsubscribe", "data": {"board_id": 123}}
    - {"command": "ping", "data": {}}
    """
    client_host = websocket.client.host if hasattr(websocket, 'client') and websocket.client else "unknown"
    
    try:
        # Get token from query parameter
        if not token:
            token = websocket.query_params.get("token")
        
        api_logger.info(f"WebSocket: New connection attempt from {client_host}")
        
        # Authenticate user
        user = await get_current_user_from_token(token=token, db=db)
        
        api_logger.info(f"WebSocket: User {user.id} ({user.username}) authenticated successfully from {client_host}")
        
        # Accept connection
        await manager.connect(websocket, user.id)
        
        # Send welcome message
        welcome_message = WebSocketMessage(
            event=WebSocketEventType.PING,
            data={"message": "Connected to the updates stream"}
        )
        await websocket.send_text(welcome_message.model_dump_json())
        
        try:
            # Main message loop
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Проверяем формат сообщения
                if "command" in message_data:
                    # Обработка команд
                    command = message_data.get("command")
                    api_logger.info(f"WebSocket: Received command '{command}' from user {user.id}")
                    
                    if command == "ping":
                        # Respond to ping
                        pong_message = WebSocketMessage(
                            event=WebSocketEventType.PONG,
                            data={}
                        )
                        await websocket.send_text(pong_message.model_dump_json())
                        api_logger.info(f"WebSocket: Sent pong response to user {user.id}")
                    
                    elif command == "subscribe":
                        # Handle board subscription
                        board_id = message_data.get("data", {}).get("board_id")
                        if not board_id:
                            error_message = WebSocketMessage(
                                event=WebSocketEventType.ERROR,
                                data={"message": "Missing board_id", "code": 400}
                            )
                            await websocket.send_text(error_message.model_dump_json())
                            api_logger.warning(f"WebSocket: User {user.id} tried to subscribe without board_id")
                            continue
                        
                        api_logger.info(f"WebSocket: User {user.id} attempting to subscribe to board {board_id}")
                        
                        # Check if user has access to the board
                        user_role = await BoardService.get_user_role(db, board_id, user.id, user)
                        if not user_role:
                            error_message = WebSocketMessage(
                                event=WebSocketEventType.ERROR,
                                data={"message": "Access denied to this board", "code": 403}
                            )
                            await websocket.send_text(error_message.model_dump_json())
                            api_logger.warning(f"WebSocket: User {user.id} denied access to board {board_id}")
                            continue
                        
                        # Subscribe user to board updates
                        manager.subscribe_to_board(user.id, board_id)
                        
                        success_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": f"Subscribed to board {board_id}"}
                        )
                        await websocket.send_text(success_message.model_dump_json())
                        api_logger.info(f"WebSocket: User {user.id} successfully subscribed to board {board_id}")
                    
                    elif command == "unsubscribe":
                        # Handle board unsubscription
                        board_id = message_data.get("data", {}).get("board_id")
                        if not board_id:
                            error_message = WebSocketMessage(
                                event=WebSocketEventType.ERROR,
                                data={"message": "Missing board_id", "code": 400}
                            )
                            await websocket.send_text(error_message.model_dump_json())
                            api_logger.warning(f"WebSocket: User {user.id} tried to unsubscribe without board_id")
                            continue
                        
                        api_logger.info(f"WebSocket: User {user.id} unsubscribing from board {board_id}")
                        
                        # Unsubscribe user from board updates
                        manager.unsubscribe_from_board(user.id, board_id)
                        
                        success_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": f"Unsubscribed from board {board_id}"}
                        )
                        await websocket.send_text(success_message.model_dump_json())
                    
                    else:
                        # Unknown command
                        error_message = WebSocketMessage(
                            event=WebSocketEventType.ERROR,
                            data={"message": f"Unknown command: {command}", "code": 400}
                        )
                        await websocket.send_text(error_message.model_dump_json())
                        api_logger.warning(f"WebSocket: User {user.id} sent unknown command: {command}")
                
                elif "event" in message_data:
                    # Обработка событий
                    event = message_data.get("event")
                    if event == "card_moved":
                        # Можно добавить логирование или другую обработку
                        api_logger.info(f"WebSocket: Received card_moved event from user {user.id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    elif event == "column_updated":
                        # Обработка column_updated
                        api_logger.info(f"WebSocket: Received column_updated event from user {user.id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    elif event == "columns_reordered":
                        # Обработка columns_reordered
                        api_logger.info(f"WebSocket: Received columns_reordered event from user {user.id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    else:
                        # Неизвестное событие
                        error_message = WebSocketMessage(
                            event=WebSocketEventType.ERROR,
                            data={"message": f"Unknown event: {event}", "code": 400}
                        )
                        await websocket.send_text(error_message.model_dump_json())
                
                else:
                    # Неизвестный формат сообщения
                    error_message = WebSocketMessage(
                        event=WebSocketEventType.ERROR,
                        data={"message": "Invalid message format", "code": 400}
                    )
                    await websocket.send_text(error_message.model_dump_json())
        
        except WebSocketDisconnect:
            # Handle client disconnect
            manager.disconnect(websocket, user.id)
            api_logger.info(f"WebSocket: User {user.id} disconnected (normal)")
        
        except Exception as e:
            # Handle other errors
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": f"Error: {str(e)}", "code": 500}
            )
            api_logger.error(f"WebSocket: Error in connection for user {user.id}: {str(e)}")
            try:
                await websocket.send_text(error_message.model_dump_json())
            except:
                # Client is probably disconnected, so clean up
                manager.disconnect(websocket, user.id)
                api_logger.info(f"WebSocket: User {user.id} disconnected during error handling")
    
    except HTTPException as he:
        # Authentication failed
        api_logger.warning(f"WebSocket: Authentication failed from {client_host}: {he.detail}")
        try:
            await websocket.accept()
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": "Authentication failed", "code": 401}
            )
            await websocket.send_text(error_message.model_dump_json())
            await websocket.close(code=1008)  # Policy violation
        except Exception as e:
            api_logger.error(f"WebSocket: Error sending auth failure message: {str(e)}")
    
    except Exception as e:
        # Unexpected error
        api_logger.error(f"WebSocket: Unexpected error from {client_host}: {str(e)}")
        try:
            await websocket.accept()
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": f"Unexpected error: {str(e)}", "code": 500}
            )
            await websocket.send_text(error_message.model_dump_json())
            await websocket.close(code=1011)  # Internal error
        except Exception as close_error:
            api_logger.error(f"WebSocket: Error sending error message: {str(close_error)}")


@router.websocket("/ws/board/{board_id}")
async def board_websocket_endpoint(
    board_id: int,
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    """
    WebSocket endpoint for real-time board-specific updates.
    
    Authentication is done via token query parameter:
    ws://example.com/api/v1/ws/board/123?token=your_access_token
    
    This automatically subscribes the user to the specified board if they have access.
    No additional subscribe command is needed.
    
    Commands from client:
    - {"command": "ping", "data": {}}
    """
    client_host = websocket.client.host if hasattr(websocket, 'client') and websocket.client else "unknown"
    
    try:
        # Get token from query parameter
        if not token:
            token = websocket.query_params.get("token")
        
        api_logger.info(f"WebSocket: New board-specific connection attempt for board {board_id} from {client_host}")
        
        # Authenticate user
        user = await get_current_user_from_token(token=token, db=db)
        
        api_logger.info(f"WebSocket: User {user.id} ({user.username}) authenticated for board {board_id} from {client_host}")
        
        # Check if user has access to the board
        user_role = await BoardService.get_user_role(db, board_id, user.id, user)
        if not user_role:
            # User doesn't have access to this board
            await websocket.accept()
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": "Access denied to this board", "code": 403}
            )
            await websocket.send_text(error_message.model_dump_json())
            await websocket.close(code=1008)  # Policy violation
            api_logger.warning(f"WebSocket: User {user.id} denied access to board {board_id}")
            return
        
        # Accept connection
        await manager.connect(websocket, user.id)
        
        # Automatically subscribe user to this board
        manager.subscribe_to_board(user.id, board_id)
        
        # Send welcome message
        welcome_message = WebSocketMessage(
            event=WebSocketEventType.PING,
            data={"message": f"Connected to board {board_id} updates stream"}
        )
        await websocket.send_text(welcome_message.model_dump_json())
        api_logger.info(f"WebSocket: User {user.id} automatically subscribed to board {board_id}")
        
        try:
            # Main message loop
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Проверяем формат сообщения
                if "command" in message_data:
                    # Обработка команд
                    command = message_data.get("command")
                    api_logger.info(f"WebSocket: Received command '{command}' from user {user.id} on board {board_id}")
                    
                    if command == "ping":
                        # Respond to ping
                        pong_message = WebSocketMessage(
                            event=WebSocketEventType.PONG,
                            data={}
                        )
                        await websocket.send_text(pong_message.model_dump_json())
                        api_logger.info(f"WebSocket: Sent pong response to user {user.id} on board {board_id}")
                    else:
                        # Unknown command - for board-specific endpoint, we only support ping
                        error_message = WebSocketMessage(
                            event=WebSocketEventType.ERROR,
                            data={"message": f"Unknown command: {command}", "code": 400}
                        )
                        await websocket.send_text(error_message.model_dump_json())
                        api_logger.warning(f"WebSocket: User {user.id} sent unknown command: {command} on board {board_id}")
                
                elif "event" in message_data:
                    # Обработка событий
                    event = message_data.get("event")
                    if event == "card_moved":
                        # Можно добавить логирование или другую обработку
                        api_logger.info(f"WebSocket: Received card_moved event from user {user.id} on board {board_id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    elif event == "column_updated":
                        # Обработка column_updated
                        api_logger.info(f"WebSocket: Received column_updated event from user {user.id} on board {board_id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    elif event == "columns_reordered":
                        # Обработка columns_reordered
                        api_logger.info(f"WebSocket: Received columns_reordered event from user {user.id} on board {board_id}")
                        # Отправляем подтверждение
                        ack_message = WebSocketMessage(
                            event=WebSocketEventType.PING,
                            data={"message": "Event received"}
                        )
                        await websocket.send_text(ack_message.model_dump_json())
                    else:
                        # Неизвестное событие
                        error_message = WebSocketMessage(
                            event=WebSocketEventType.ERROR,
                            data={"message": f"Unknown event: {event}", "code": 400}
                        )
                        await websocket.send_text(error_message.model_dump_json())
                
                else:
                    # Неизвестный формат сообщения
                    error_message = WebSocketMessage(
                        event=WebSocketEventType.ERROR,
                        data={"message": "Invalid message format", "code": 400}
                    )
                    await websocket.send_text(error_message.model_dump_json())
        
        except WebSocketDisconnect:
            # Handle client disconnect
            manager.disconnect(websocket, user.id)
            # Also unsubscribe from board
            manager.unsubscribe_from_board(user.id, board_id)
            api_logger.info(f"WebSocket: User {user.id} disconnected from board {board_id} (normal)")
        
        except Exception as e:
            # Handle other errors
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": f"Error: {str(e)}", "code": 500}
            )
            api_logger.error(f"WebSocket: Error in board connection for user {user.id} on board {board_id}: {str(e)}")
            try:
                await websocket.send_text(error_message.model_dump_json())
            except:
                # Client is probably disconnected, so clean up
                manager.disconnect(websocket, user.id)
                manager.unsubscribe_from_board(user.id, board_id)
                api_logger.info(f"WebSocket: User {user.id} disconnected from board {board_id} during error handling")
    
    except HTTPException as he:
        # Authentication failed
        api_logger.warning(f"WebSocket: Authentication failed for board {board_id} from {client_host}: {he.detail}")
        try:
            await websocket.accept()
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": "Authentication failed", "code": 401}
            )
            await websocket.send_text(error_message.model_dump_json())
            await websocket.close(code=1008)  # Policy violation
        except Exception as e:
            api_logger.error(f"WebSocket: Error sending auth failure message for board {board_id}: {str(e)}")
    
    except Exception as e:
        # Unexpected error
        api_logger.error(f"WebSocket: Unexpected error for board {board_id} from {client_host}: {str(e)}")
        try:
            await websocket.accept()
            error_message = WebSocketMessage(
                event=WebSocketEventType.ERROR,
                data={"message": f"Unexpected error: {str(e)}", "code": 500}
            )
            await websocket.send_text(error_message.model_dump_json())
            await websocket.close(code=1011)  # Internal error
        except Exception as close_error:
            api_logger.error(f"WebSocket: Error sending error message for board {board_id}: {str(close_error)}") 