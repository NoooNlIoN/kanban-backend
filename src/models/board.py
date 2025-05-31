from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Enum
from sqlalchemy.orm import relationship
import enum

from src.db.base import Base


# Enum для ролей пользователей на доске
class BoardUserRole(enum.Enum):
    OWNER = "owner"        # Создатель доски
    ADMIN = "admin"        # Администратор
    MEMBER = "member"      # Обычный пользователь


# Ассоциативная таблица для связи many-to-many между пользователями и досками с указанием роли
board_users = Table(
    "board_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("board_id", Integer, ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True),
    Column("role", Enum(BoardUserRole), nullable=False, default=BoardUserRole.MEMBER)
)


class Board(Base):
    """Модель доски для канбан-системы"""
    
    __tablename__ = "boards"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношение к создателю доски
    owner = relationship("User", backref="owned_boards", foreign_keys=[owner_id])
    
    # Отношение many-to-many с пользователями (все участники доски)
    users = relationship("User", secondary=board_users, backref="boards")
    
    # Отношение one-to-many с колонками/списками
    columns = relationship("Column", back_populates="board", cascade="all, delete-orphan") 