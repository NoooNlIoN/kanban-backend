from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean
from sqlalchemy.orm import relationship

from src.db.base import Base


# Ассоциативная таблица для связи many-to-many между пользователями и карточками
card_users = Table(
    "card_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("card_id", Integer, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
)


class Card(Base):
    """Модель карточки для канбан-системы"""
    
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)  # Цвет карточки (например, в hex формате: #RRGGBB)
    order = Column(Integer, default=0)  # Для сортировки карточек внутри колонки
    column_id = Column(Integer, ForeignKey("columns.id", ondelete="CASCADE"), nullable=False)
    completed = Column(Boolean, default=False)  # Field to mark card as completed
    deadline = Column(DateTime, nullable=True)  # Дедлайн карточки
    is_archived = Column(Boolean, default=False)  # Пометка на удаление
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Отношение many-to-one с колонкой
    column = relationship("Column", back_populates="cards")
    
    # Отношение many-to-many с пользователями (прикрепленные к карточке)
    assigned_users = relationship("User", secondary=card_users, backref="assigned_cards")
    
    # Отношение one-to-many с комментариями
    comments = relationship("Comment", back_populates="card", cascade="all, delete-orphan")


class Comment(Base):
    """Модель комментария к карточке"""
    
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Отношение many-to-one с карточкой
    card = relationship("Card", back_populates="comments")
    
    # Отношение many-to-one с пользователем
    user = relationship("User", backref="comments") 