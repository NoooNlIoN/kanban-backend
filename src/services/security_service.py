from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from src.models.user import User
from src.core import get_settings

# Get application settings
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Access Token Model (for typing)
JWTToken = Dict[str, str]


class SecurityService:
    """Security service for JWT authentication"""

    @staticmethod
    def create_password_hash(password: str) -> str:
        """Create a hashed password"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email"""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalars().first()
    
    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get a user by username"""
        query = select(User).where(User.username == username)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by ID"""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, 
        username_or_email: str, 
        password: str
    ) -> Optional[User]:
        """Authenticate a user by username/email and password"""
        # Check if input is email or username
        is_email = '@' in username_or_email
        
        if is_email:
            user = await SecurityService.get_user_by_email(db, username_or_email)
        else:
            user = await SecurityService.get_user_by_username(db, username_or_email)
        
        if not user:
            return None
        
        if not SecurityService.verify_password(password, user.hashed_password):
            return None
        
        return user

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()
        
        # Add a unique jti (JWT ID) to the token to prevent reuse
        to_encode.update({"jti": str(uuid.uuid4())})
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return encoded_jwt

    @staticmethod
    def create_tokens(user_id: int) -> Dict[str, str]:
        """Create access and refresh tokens for a user"""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        token_data = {"sub": str(user_id)}
        
        access_token = SecurityService.create_access_token(
            data=token_data, 
            expires_delta=access_token_expires
        )
        
        refresh_token = SecurityService.create_refresh_token(
            data=token_data, 
            expires_delta=refresh_token_expires
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode a JWT token"""
        try:
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            return {}

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify a JWT token and return its payload if valid"""
        try:
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            
            # Check token type
            if payload.get("type") != token_type:
                return None
                
            # Check if token is expired
            exp = payload.get("exp")
            if exp is None or datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return None
                
            return payload
                
        except JWTError:
            return None

    @staticmethod
    async def get_current_user(
        db: AsyncSession, 
        token: str
    ) -> Optional[User]:
        """Get the current user from a JWT token"""
        payload = SecurityService.verify_token(token)
        if not payload:
            return None
            
        user_id = payload.get("sub")
        if user_id is None:
            return None
            
        user = await SecurityService.get_user_by_id(db, int(user_id))
        return user

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession, 
        refresh_token: str
    ) -> Optional[Dict[str, str]]:
        """Refresh access token using refresh token"""
        payload = SecurityService.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None
            
        user_id = payload.get("sub")
        if user_id is None:
            return None
            
        user = await SecurityService.get_user_by_id(db, int(user_id))
        if not user:
            return None

        # Create new tokens
        return SecurityService.create_tokens(user.id) 