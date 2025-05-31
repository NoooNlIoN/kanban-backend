from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.db.base import Base


class Column(Base):
    """Модель колонки/списка для канбан-системы"""
    
    __tablename__ = "columns"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    order = Column(Integer, default=0)  # Для сортировки колонок
    board_id = Column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношение many-to-one с доской
    board = relationship("Board", back_populates="columns")
    
    # Отношение one-to-many с карточками
    cards = relationship("Card", back_populates="column", cascade="all, delete-orphan") 