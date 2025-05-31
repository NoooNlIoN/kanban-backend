import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.columns import (
    reorder_columns,
    check_board_access,
    create_column,
    get_columns,
    get_column,
    update_column,
    delete_column
)
from src.models.user import User
from src.models.board import Board, BoardUserRole
from src.models.column import Column
from src.schemas.column import (
    ColumnCreate,
    ColumnUpdate,
    ColumnOrderUpdate
)


class TestCheckBoardAccess:
    """Тесты для функции check_board_access"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def regular_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def superuser(self):
        user = MagicMock(spec=User)
        user.id = 2
        user.is_superuser = True
        return user
    
    @pytest.fixture
    def mock_board(self):
        board = MagicMock(spec=Board)
        board.id = 1
        board.title = "Test Board"
        return board
    
    @pytest.mark.asyncio
    async def test_superuser_access_existing_board(self, mock_db, superuser, mock_board):
        """Суперпользователь должен иметь доступ к существующей доске"""
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=mock_board):
            result = await check_board_access(1, mock_db, superuser, require_modify=True)
            assert result == mock_board
    
    @pytest.mark.asyncio
    async def test_superuser_access_nonexistent_board(self, mock_db, superuser):
        """Суперпользователь должен получить ошибку для несуществующей доски"""
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await check_board_access(999, mock_db, superuser)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Board not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_regular_user_access_existing_board(self, mock_db, regular_user, mock_board):
        """Обычный пользователь с правами должен иметь доступ"""
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=mock_board), \
             patch('src.api.v1.columns.check_board_permissions') as mock_check_permissions:
            
            result = await check_board_access(1, mock_db, regular_user, require_modify=False)
            
            assert result == mock_board
            mock_check_permissions.assert_called_once_with(
                db=mock_db,
                board_id=1,
                user_id=regular_user.id,
                required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN, BoardUserRole.MEMBER],
                user=regular_user
            )
    
    @pytest.mark.asyncio
    async def test_regular_user_access_with_modify_permission(self, mock_db, regular_user, mock_board):
        """Обычный пользователь с правами на изменение"""
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=mock_board), \
             patch('src.api.v1.columns.check_board_permissions') as mock_check_permissions:
            
            result = await check_board_access(1, mock_db, regular_user, require_modify=True)
            
            assert result == mock_board
            mock_check_permissions.assert_called_once_with(
                db=mock_db,
                board_id=1,
                user_id=regular_user.id,
                required_roles=[BoardUserRole.OWNER, BoardUserRole.ADMIN],
                user=regular_user
            )
    
    @pytest.mark.asyncio
    async def test_regular_user_access_nonexistent_board(self, mock_db, regular_user):
        """Обычный пользователь должен получить ошибку для несуществующей доски"""
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await check_board_access(999, mock_db, regular_user)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Board not found" in str(exc_info.value.detail)


class TestReorderColumns:
    """Тесты для эндпоинта reorder_columns"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def admin_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def column_order_data(self):
        return ColumnOrderUpdate(column_order=[3, 1, 2])
    
    @pytest.fixture
    def mock_columns(self):
        columns = []
        for i, col_id in enumerate([3, 1, 2]):
            col = MagicMock(spec=Column)
            col.id = col_id
            col.title = f"Column {col_id}"
            col.board_id = 1
            col.order = i
            columns.append(col)
        return columns
    
    @pytest.mark.asyncio
    async def test_reorder_columns_success(self, mock_db, admin_user, column_order_data, mock_columns):
        """Успешное изменение порядка колонок"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.reorder_columns', return_value=True) as mock_reorder, \
             patch('src.api.v1.columns.ColumnService.get_by_board_id', return_value=mock_columns) as mock_get_columns, \
             patch('src.api.v1.columns.notify_column_updated') as mock_notify:
            
            result = await reorder_columns(1, column_order_data, mock_db, admin_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, admin_user, require_modify=True)
            mock_reorder.assert_called_once_with(
                db=mock_db,
                board_id=1,
                column_order=[3, 1, 2]
            )
            mock_get_columns.assert_called_once_with(db=mock_db, board_id=1)
            
            # Проверяем уведомления для каждой колонки
            assert mock_notify.call_count == 3
            
            assert result == {"message": "Columns reordered successfully"}
    
    @pytest.mark.asyncio
    async def test_reorder_columns_service_failure(self, mock_db, admin_user, column_order_data):
        """Ошибка при сбое в сервисе переупорядочивания"""
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.reorder_columns', return_value=False):
            
            with pytest.raises(HTTPException) as exc_info:
                await reorder_columns(1, column_order_data, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to reorder columns" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_reorder_columns_no_access(self, mock_db, admin_user, column_order_data):
        """Ошибка доступа при попытке изменить порядок колонок"""
        with patch('src.api.v1.columns.check_board_access', side_effect=HTTPException(status_code=403, detail="Forbidden")):
            
            with pytest.raises(HTTPException) as exc_info:
                await reorder_columns(1, column_order_data, mock_db, admin_user)
            
            assert exc_info.value.status_code == 403


class TestCreateColumn:
    """Тесты для эндпоинта create_column"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def admin_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def column_create_data(self):
        return ColumnCreate(title="New Column", order=1)
    
    @pytest.fixture
    def mock_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "New Column"
        column.board_id = 1
        column.order = 1
        return column
    
    @pytest.mark.asyncio
    async def test_create_column_success(self, mock_db, admin_user, column_create_data, mock_column):
        """Успешное создание колонки"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.create', return_value=mock_column) as mock_create, \
             patch('src.api.v1.columns.notify_column_created') as mock_notify:
            
            result = await create_column(1, column_create_data, mock_db, admin_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, admin_user, require_modify=True)
            mock_create.assert_called_once_with(
                db=mock_db,
                title="New Column",
                board_id=1,
                order=1
            )
            
            # Проверяем уведомление
            expected_column_data = {
                "id": 1,
                "title": "New Column",
                "board_id": 1,
                "order": 1
            }
            mock_notify.assert_called_once_with(1, expected_column_data)
            
            assert result == mock_column
    
    @pytest.mark.asyncio
    async def test_create_column_no_access(self, mock_db, admin_user, column_create_data):
        """Ошибка доступа при создании колонки"""
        with patch('src.api.v1.columns.check_board_access', side_effect=HTTPException(status_code=403, detail="Forbidden")):
            
            with pytest.raises(HTTPException) as exc_info:
                await create_column(1, column_create_data, mock_db, admin_user)
            
            assert exc_info.value.status_code == 403


class TestGetColumns:
    """Тесты для эндпоинта get_columns"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def member_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def mock_columns(self):
        columns = []
        for i in range(3):
            col = MagicMock(spec=Column)
            col.id = i + 1
            col.title = f"Column {i + 1}"
            col.board_id = 1
            col.order = i
            columns.append(col)
        return columns
    
    @pytest.mark.asyncio
    async def test_get_columns_success(self, mock_db, member_user, mock_columns):
        """Успешное получение колонок"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.get_by_board_id', return_value=mock_columns) as mock_get:
            
            result = await get_columns(1, mock_db, member_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, member_user, require_modify=False)
            mock_get.assert_called_once_with(db=mock_db, board_id=1, load_cards=True)
            
            assert result == {"columns": mock_columns}
    
    @pytest.mark.asyncio
    async def test_get_columns_no_access(self, mock_db, member_user):
        """Ошибка доступа при получении колонок"""
        with patch('src.api.v1.columns.check_board_access', side_effect=HTTPException(status_code=403, detail="Forbidden")):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_columns(1, mock_db, member_user)
            
            assert exc_info.value.status_code == 403


class TestGetColumn:
    """Тесты для эндпоинта get_column"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def member_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def mock_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "Test Column"
        column.board_id = 1
        column.order = 0
        return column
    
    @pytest.mark.asyncio
    async def test_get_column_success(self, mock_db, member_user, mock_column):
        """Успешное получение конкретной колонки"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=mock_column) as mock_get:
            
            result = await get_column(1, 1, mock_db, member_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, member_user, require_modify=False)
            mock_get.assert_called_once_with(db=mock_db, column_id=1, load_cards=True)
            
            assert result == mock_column
    
    @pytest.mark.asyncio
    async def test_get_column_not_found(self, mock_db, member_user):
        """Ошибка при несуществующей колонке"""
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_column(1, 999, mock_db, member_user)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Column not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_column_wrong_board(self, mock_db, member_user):
        """Ошибка при принадлежности колонки другой доске"""
        wrong_column = MagicMock(spec=Column)
        wrong_column.id = 1
        wrong_column.board_id = 2  # Другая доска
        
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=wrong_column):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_column(1, 1, mock_db, member_user)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Column does not belong to the specified board" in str(exc_info.value.detail)


class TestUpdateColumn:
    """Тесты для эндпоинта update_column"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def admin_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def column_update_data(self):
        return ColumnUpdate(title="Updated Column", order=2)
    
    @pytest.fixture
    def mock_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "Test Column"
        column.board_id = 1
        column.order = 0
        return column
    
    @pytest.fixture
    def mock_updated_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "Updated Column"
        column.board_id = 1
        column.order = 2
        return column
    
    @pytest.mark.asyncio
    async def test_update_column_success(self, mock_db, admin_user, column_update_data, mock_column, mock_updated_column):
        """Успешное обновление колонки"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=mock_column) as mock_get, \
             patch('src.api.v1.columns.ColumnService.update', return_value=mock_updated_column) as mock_update, \
             patch('src.api.v1.columns.notify_column_updated') as mock_notify:
            
            result = await update_column(1, 1, column_update_data, mock_db, admin_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, admin_user, require_modify=True)
            mock_get.assert_called_once_with(db=mock_db, column_id=1)
            mock_update.assert_called_once_with(
                db=mock_db,
                column_id=1,
                title="Updated Column",
                order=2
            )
            
            # Проверяем уведомление
            expected_column_data = {
                "id": 1,
                "title": "Updated Column",
                "board_id": 1,
                "order": 2
            }
            mock_notify.assert_called_once_with(1, expected_column_data)
            
            assert result == mock_updated_column
    
    @pytest.mark.asyncio
    async def test_update_column_not_found(self, mock_db, admin_user, column_update_data):
        """Ошибка при обновлении несуществующей колонки"""
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await update_column(1, 999, column_update_data, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Column not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_update_column_wrong_board(self, mock_db, admin_user, column_update_data):
        """Ошибка при обновлении колонки из другой доски"""
        wrong_column = MagicMock(spec=Column)
        wrong_column.id = 1
        wrong_column.board_id = 2  # Другая доска
        
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=wrong_column):
            
            with pytest.raises(HTTPException) as exc_info:
                await update_column(1, 1, column_update_data, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Column does not belong to the specified board" in str(exc_info.value.detail)


class TestDeleteColumn:
    """Тесты для эндпоинта delete_column"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def admin_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = False
        return user
    
    @pytest.fixture
    def mock_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "Test Column"
        column.board_id = 1
        column.order = 0
        return column
    
    @pytest.mark.asyncio
    async def test_delete_column_success(self, mock_db, admin_user, mock_column):
        """Успешное удаление колонки"""
        with patch('src.api.v1.columns.check_board_access') as mock_check_access, \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=mock_column) as mock_get, \
             patch('src.api.v1.columns.ColumnService.delete', return_value=True) as mock_delete, \
             patch('src.api.v1.columns.notify_column_deleted') as mock_notify:
            
            result = await delete_column(1, 1, mock_db, admin_user)
            
            # Проверяем вызовы
            mock_check_access.assert_called_once_with(1, mock_db, admin_user, require_modify=True)
            mock_get.assert_called_once_with(db=mock_db, column_id=1)
            mock_delete.assert_called_once_with(db=mock_db, column_id=1)
            mock_notify.assert_called_once_with(1, 1)
            
            assert result is None  # 204 No Content
    
    @pytest.mark.asyncio
    async def test_delete_column_not_found(self, mock_db, admin_user):
        """Ошибка при удалении несуществующей колонки"""
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_column(1, 999, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Column not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_delete_column_wrong_board(self, mock_db, admin_user):
        """Ошибка при удалении колонки из другой доски"""
        wrong_column = MagicMock(spec=Column)
        wrong_column.id = 1
        wrong_column.board_id = 2  # Другая доска
        
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=wrong_column):
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_column(1, 1, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Column does not belong to the specified board" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_delete_column_service_failure(self, mock_db, admin_user, mock_column):
        """Ошибка при сбое в сервисе удаления"""
        with patch('src.api.v1.columns.check_board_access'), \
             patch('src.api.v1.columns.ColumnService.get_by_id', return_value=mock_column), \
             patch('src.api.v1.columns.ColumnService.delete', return_value=False):
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_column(1, 1, mock_db, admin_user)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to delete column" in str(exc_info.value.detail)


class TestColumnsIntegration:
    """Интеграционные тесты для взаимодействия с суперпользователем"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def superuser(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.is_superuser = True
        return user
    
    @pytest.fixture
    def mock_board(self):
        board = MagicMock(spec=Board)
        board.id = 1
        board.title = "Test Board"
        return board
    
    @pytest.fixture
    def mock_column(self):
        column = MagicMock(spec=Column)
        column.id = 1
        column.title = "Test Column"
        column.board_id = 1
        column.order = 0
        return column
    
    @pytest.mark.asyncio
    async def test_superuser_can_create_column(self, mock_db, superuser, mock_board, mock_column):
        """Суперпользователь может создавать колонки в любой доске"""
        column_create_data = ColumnCreate(title="Super Column", order=1)
        
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=mock_board), \
             patch('src.api.v1.columns.ColumnService.create', return_value=mock_column), \
             patch('src.api.v1.columns.notify_column_created'):
            
            result = await create_column(1, column_create_data, mock_db, superuser)
            assert result == mock_column
    
    @pytest.mark.asyncio
    async def test_superuser_can_reorder_columns(self, mock_db, superuser, mock_board):
        """Суперпользователь может изменять порядок колонок в любой доске"""
        column_order_data = ColumnOrderUpdate(column_order=[2, 1, 3])
        mock_columns = [MagicMock(spec=Column) for _ in range(3)]
        
        with patch('src.api.v1.columns.BoardService.get_by_id', return_value=mock_board), \
             patch('src.api.v1.columns.ColumnService.reorder_columns', return_value=True), \
             patch('src.api.v1.columns.ColumnService.get_by_board_id', return_value=mock_columns), \
             patch('src.api.v1.columns.notify_column_updated'):
            
            result = await reorder_columns(1, column_order_data, mock_db, superuser)
            assert result == {"message": "Columns reordered successfully"} 