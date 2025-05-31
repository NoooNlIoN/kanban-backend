from pydantic import BaseModel, EmailStr
from src.models.board import BoardUserRole


class TransferOwnershipRequest(BaseModel):
    """Schema for transferring board ownership"""
    new_owner_id: int


class ChangeUserRoleRequest(BaseModel):
    """Schema for changing a user's role on a board"""
    user_id: int
    role: BoardUserRole


class AddUserRequest(BaseModel):
    """Schema for adding a user to a board"""
    user_id: int
    role: BoardUserRole = BoardUserRole.MEMBER


class AddUserByEmailRequest(BaseModel):
    """Schema for adding a user to a board by email"""
    email: EmailStr
    role: BoardUserRole = BoardUserRole.MEMBER


class RemoveUserRequest(BaseModel):
    """Schema for removing a user from a board"""
    user_id: int 