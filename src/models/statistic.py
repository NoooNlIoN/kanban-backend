from sqlalchemy import Column, Integer, String, Date, Text
from sqlalchemy.orm import relationship

from src.db.base import Base


class Statistic(Base):
    """Модель агрегированной статистики системы"""
    
    __tablename__ = "statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(Date, nullable=False)
    cards_created = Column(Integer, nullable=False, default=0)
    cards_completed = Column(Integer, nullable=False, default=0)
    comments_posted = Column(Integer, nullable=False, default=0)
    active_users = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)