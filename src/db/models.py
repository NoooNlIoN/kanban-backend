# Import all models here for Alembic to discover them
from src.db.base import Base
from src.models.user import User
from src.models.board import Board, board_users, BoardUserRole
from src.models.column import Column
from src.models.card import Card, Comment, card_users 