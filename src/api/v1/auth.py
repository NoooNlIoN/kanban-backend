from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session
from src.schemas.auth import UserCreate, UserResponse, TokenResponse, RefreshTokenRequest
from src.services.security_service import SecurityService
from src.api.dependencies.auth import get_current_active_user
from src.models.user import User
from src.services.user_statistic_service import UserStatisticService
from src.logs import debug_logger

# Create router
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Register a new user
    """
    # Check if email already exists
    existing_user = await SecurityService.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_user = await SecurityService.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create hashed password
    hashed_password = SecurityService.create_password_hash(user_data.password)
    
    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )
    
    # Add user to database
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Создаем запись статистики для нового пользователя
    await UserStatisticService.create(db, user.id)
    debug_logger.debug(f"Создана статистика для нового пользователя {user.id}")
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Login for access token
    
    This endpoint is compatible with OAuth2 password flow
    """
    # Authenticate user
    user = await SecurityService.authenticate_user(
        db, form_data.username, form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Обновляем счетчик активных дней пользователя
    await UserStatisticService.update_active_streak(db, user.id)
    debug_logger.debug(f"Обновлен счетчик активных дней для пользователя {user.id}")
    
    # Create access token
    tokens = SecurityService.create_tokens(user.id)
    
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Refresh access token
    """
    # Refresh tokens
    tokens = await SecurityService.refresh_tokens(db, refresh_data.refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return tokens


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information
    """
    return current_user 