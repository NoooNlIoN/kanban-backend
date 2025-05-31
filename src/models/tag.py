from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship

from src.db.base import Base


# Ассоциативная таблица для связи many-to-many между тегами и карточками
card_tags = Table(
    "card_tags",
    Base.metadata,
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("card_id", Integer, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
)


class Tag(Base):
    """Модель тегов для карточек"""
    
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=True)
    
    # Отношения
    board = relationship("Board", backref="tags")
    cards = relationship("Card", secondary=card_tags, backref="tags") 