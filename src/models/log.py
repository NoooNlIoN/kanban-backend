from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from src.db.base import Base


class Log(Base):
    """Модель журнала событий системы"""
    
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    
    # Отношение к пользователю
    user = relationship("User", backref="logs") 