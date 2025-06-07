from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

from src.db import init_db
from src.core import get_settings
from src.api.v1 import api_router
from src.core.middleware import RequestLoggingMiddleware
from src.logs.server_log import api_logger

# Get application settings
settings = get_settings()

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        # Get Alembic config file path
        alembic_cfg = Config(os.path.join(Path(__file__).parent.parent, "alembic.ini"))
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        # Initialize database on startup
        await init_db()
        print("✅ Database migrations applied and initialized successfully")
    except Exception as e:
        print(f"❌ Error applying migrations: {e}")
        raise
    
    yield
    # Clean up resources on shutdown
    pass

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Kanban board with authentication",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include API router
app.include_router(api_router)

@app.get("/")
async def root(request: Request):
    """Health check endpoint"""
    print(f"Received request: {request.method} {request.url}")
    api_logger.info(f"Received health check request: {request.method} {request.url}")
    return {"message": f"{settings.PROJECT_NAME} is running"}


if __name__ == "__main__":
    import uvicorn
    print("\033[1;36m" + "=" * 50 + "\033[0m")  # Cyan
    print("\033[1;36m" + "  Запуск API сервера канбан-доски" + "\033[0m")  # Cyan
    print("\033[1;36m" + "=" * 50 + "\033[0m")  # Cyan
    
    api_logger.info(f"Сервер запускается на http://0.0.0.0:8000")
    
    # Запускаем uvicorn с настройкой логирования
    uvicorn.run(
        "src.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG,
        log_level="info"
    )