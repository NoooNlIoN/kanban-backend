from fastapi import APIRouter
from src.api.v1.auth import router as auth_router
from src.api.v1.users import router as users_router
from src.api.v1.boards import router as boards_router
from src.api.v1.columns import router as columns_router
from src.api.v1.cards import router as cards_router, board_cards_router
from src.api.v1.board_permissions import router as board_permissions_router
from src.api.v1.comments import router as comments_router
from src.api.v1.websockets import router as websocket_router
from src.api.v1.tags import router as tags_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(boards_router)
api_router.include_router(columns_router)
api_router.include_router(cards_router)
api_router.include_router(board_cards_router)
api_router.include_router(board_permissions_router)
api_router.include_router(comments_router)
api_router.include_router(websocket_router)
api_router.include_router(tags_router) 