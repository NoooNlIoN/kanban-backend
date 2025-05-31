from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from src.db.base import Base


class UserStatistic(Base):
    """Модель статистики пользователя"""
    
    __tablename__ = "user_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    completed_tasks = Column(Integer, default=0, nullable=False)
    active_days_streak = Column(Integer, default=0, nullable=False)
    total_completed_tasks = Column(Integer, default=0, nullable=False)
    total_created_tasks = Column(Integer, default=0, nullable=False)
    total_comments = Column(Integer, default=0, nullable=False)
    
    # Отношение к пользователю
    user = relationship("User", backref="statistic", uselist=False) 