import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты из тестируемых модулей
from src.api.v1.auth import register, login, refresh_token, get_current_user_info
from src.schemas.auth import UserCreate, RefreshTokenRequest
from src.models.user import User
from src.services.security_service import SecurityService
from src.services.user_statistic_service import UserStatisticService


class TestAuthEndpoints:
    """Юниттесты для эндпоинтов аутентификации"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.mock_db = AsyncMock(spec=AsyncSession)
        self.mock_user = User(
            id=1,
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=False
        )

    @pytest.mark.asyncio
    async def test_register_success(self):
        """Тест успешной регистрации пользователя"""
        # Подготовка данных
        user_data = UserCreate(
            email="newuser@example.com",
            username="newuser",
            password="password123"
        )

        # Мокаем зависимости
        with patch.object(SecurityService, 'get_user_by_email', return_value=None), \
             patch.object(SecurityService, 'get_user_by_username', return_value=None), \
             patch.object(SecurityService, 'create_password_hash', return_value="hashed_password"), \
             patch.object(UserStatisticService, 'create', new_callable=AsyncMock) as mock_stats:
            
            # Мокаем операции с базой данных
            self.mock_db.add = MagicMock()
            self.mock_db.commit = AsyncMock()
            self.mock_db.refresh = AsyncMock()
            
            # Мокаем созданного пользователя после refresh
            async def mock_refresh(user):
                user.id = 1
            self.mock_db.refresh.side_effect = mock_refresh

            # Вызываем функцию
            result = await register(user_data, self.mock_db)

            # Проверяем результат
            assert result.email == user_data.email
            assert result.username == user_data.username
            
            # Проверяем вызовы
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once()
            mock_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_email_exists(self):
        """Тест регистрации с уже существующим email"""
        user_data = UserCreate(
            email="existing@example.com",
            username="newuser",
            password="password123"
        )

        # Мокаем существующего пользователя
        with patch.object(SecurityService, 'get_user_by_email', return_value=self.mock_user):
            
            # Проверяем исключение
            with pytest.raises(HTTPException) as exc_info:
                await register(user_data, self.mock_db)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Email already registered" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_register_username_exists(self):
        """Тест регистрации с уже существующим username"""
        user_data = UserCreate(
            email="newuser@example.com",
            username="existinguser",
            password="password123"
        )

        # Мокаем проверки
        with patch.object(SecurityService, 'get_user_by_email', return_value=None), \
             patch.object(SecurityService, 'get_user_by_username', return_value=self.mock_user):
            
            # Проверяем исключение
            with pytest.raises(HTTPException) as exc_info:
                await register(user_data, self.mock_db)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Username already taken" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Тест успешной аутентификации"""
        # Подготовка данных
        form_data = OAuth2PasswordRequestForm(
            username="testuser",
            password="password123"
        )

        tokens = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "bearer"
        }

        # Мокаем зависимости
        with patch.object(SecurityService, 'authenticate_user', return_value=self.mock_user), \
             patch.object(SecurityService, 'create_tokens', return_value=tokens), \
             patch.object(UserStatisticService, 'update_active_streak', new_callable=AsyncMock):

            # Вызываем функцию
            result = await login(form_data, self.mock_db)

            # Проверяем результат
            assert result == tokens

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Тест аутентификации с неверными данными"""
        form_data = OAuth2PasswordRequestForm(
            username="wronguser",
            password="wrongpassword"
        )

        # Мокаем неудачную аутентификацию
        with patch.object(SecurityService, 'authenticate_user', return_value=None):
            
            # Проверяем исключение
            with pytest.raises(HTTPException) as exc_info:
                await login(form_data, self.mock_db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Incorrect username/email or password" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_login_inactive_user(self):
        """Тест аутентификации неактивного пользователя"""
        form_data = OAuth2PasswordRequestForm(
            username="testuser",
            password="password123"
        )

        # Создаем неактивного пользователя
        inactive_user = User(
            id=1,
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
            is_active=False,
            is_superuser=False
        )

        # Мокаем аутентификацию неактивного пользователя
        with patch.object(SecurityService, 'authenticate_user', return_value=inactive_user):
            
            # Проверяем исключение
            with pytest.raises(HTTPException) as exc_info:
                await login(form_data, self.mock_db)
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Inactive user" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Тест успешного обновления токена"""
        refresh_data = RefreshTokenRequest(
            refresh_token="valid_refresh_token"
        )

        new_tokens = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer"
        }

        # Мокаем успешное обновление токенов
        with patch.object(SecurityService, 'refresh_tokens', return_value=new_tokens):
            
            # Вызываем функцию
            result = await refresh_token(refresh_data, self.mock_db)

            # Проверяем результат
            assert result == new_tokens

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self):
        """Тест обновления с недействительным токеном"""
        refresh_data = RefreshTokenRequest(
            refresh_token="invalid_refresh_token"
        )

        # Мокаем неудачное обновление токенов
        with patch.object(SecurityService, 'refresh_tokens', return_value=None):
            
            # Проверяем исключение
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(refresh_data, self.mock_db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid refresh token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_info_success(self):
        """Тест успешного получения информации о пользователе"""
        # Вызываем функцию
        result = await get_current_user_info(self.mock_user)

        # Проверяем результат
        assert result == self.mock_user
        assert result.email == "test@example.com"
        assert result.username == "testuser"
        assert result.is_active == True
        assert result.is_superuser == False

    @pytest.mark.asyncio
    async def test_get_current_user_info_superuser(self):
        """Тест получения информации о суперпользователе"""
        # Создаем суперпользователя
        superuser = User(
            id=1,
            email="admin@example.com",
            username="admin",
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=True
        )

        # Вызываем функцию
        result = await get_current_user_info(superuser)

        # Проверяем результат
        assert result.is_superuser == True
        assert result.email == "admin@example.com"
        assert result.username == "admin"


class TestAuthIntegration:
    """Интеграционные тесты для auth эндпоинтов"""

    @pytest.mark.asyncio
    async def test_register_login_flow(self):
        """Тест полного цикла регистрация -> вход"""
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Данные для регистрации
        user_data = UserCreate(
            email="integration@example.com",
            username="integrationuser",
            password="password123"
        )

        # Мокаем успешную регистрацию
        with patch.object(SecurityService, 'get_user_by_email', return_value=None), \
             patch.object(SecurityService, 'get_user_by_username', return_value=None), \
             patch.object(SecurityService, 'create_password_hash', return_value="hashed_password"), \
             patch.object(UserStatisticService, 'create', new_callable=AsyncMock):
            
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            
            async def mock_refresh(user):
                user.id = 1
            mock_db.refresh.side_effect = mock_refresh

            # Регистрируем пользователя
            registered_user = await register(user_data, mock_db)
            assert registered_user.email == user_data.email

        # Затем тестируем вход
        form_data = OAuth2PasswordRequestForm(
            username="integrationuser",
            password="password123"
        )

        registered_user_mock = User(
            id=1,
            email="integration@example.com",
            username="integrationuser",
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=False
        )

        tokens = {
            "access_token": "integration_access_token",
            "refresh_token": "integration_refresh_token",
            "token_type": "bearer"
        }

        # Мокаем успешный вход
        with patch.object(SecurityService, 'authenticate_user', return_value=registered_user_mock), \
             patch.object(SecurityService, 'create_tokens', return_value=tokens), \
             patch.object(UserStatisticService, 'update_active_streak', new_callable=AsyncMock):

            # Входим в систему
            login_result = await login(form_data, mock_db)
            assert login_result == tokens

    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """Тест граничных случаев"""
        mock_db = AsyncMock(spec=AsyncSession)

        # Тест с пустыми данными
        with pytest.raises(Exception):  # Pydantic validation error
            user_data = UserCreate(
                email="",
                username="",
                password=""
            )

        # Тест с некорректным email
        with pytest.raises(Exception):  # Pydantic validation error
            user_data = UserCreate(
                email="not-an-email",
                username="validuser",
                password="password123"
            )

        # Тест с коротким паролем
        with pytest.raises(Exception):  # Pydantic validation error
            user_data = UserCreate(
                email="test@example.com",
                username="validuser",
                password="123"  # Слишком короткий
            )

        # Тест с коротким username
        with pytest.raises(Exception):  # Pydantic validation error
            user_data = UserCreate(
                email="test@example.com",
                username="ab",  # Слишком короткий
                password="password123"
            )


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 