from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.db.base import Base


class Notification(Base):
    """Модель уведомлений для пользователей"""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=True)
    type = Column(String(50), nullable=False)  # CARD_ASSIGNED, NEW_COMMENT, DEADLINE_APPROACHING, etc.
    message = Column(String(255), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Отношения
    user = relationship("User", backref="notifications")
    card = relationship("Card", backref="notifications") 