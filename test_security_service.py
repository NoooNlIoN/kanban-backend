import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from jose import jwt

from src.services.security_service import SecurityService
from src.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


class TestSecurityService:
    """Юниттесты для SecurityService"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.mock_db = AsyncMock(spec=AsyncSession)
        self.test_user = User(
            id=1,
            email="test@example.com",
            username="testuser",
            hashed_password="$2b$12$test_hashed_password",
            is_active=True,
            is_superuser=False
        )

    def test_create_password_hash(self):
        """Тест создания хеша пароля"""
        password = "testpassword123"
        hash_result = SecurityService.create_password_hash(password)
        
        # Проверяем что хеш создался и отличается от исходного пароля
        assert hash_result != password
        assert len(hash_result) > 0
        assert hash_result.startswith("$2b$")

    def test_verify_password_correct(self):
        """Тест проверки корректного пароля"""
        password = "testpassword123"
        hash_password = SecurityService.create_password_hash(password)
        
        # Проверяем что пароль верифицируется корректно
        assert SecurityService.verify_password(password, hash_password) is True

    def test_verify_password_incorrect(self):
        """Тест проверки неверного пароля"""
        correct_password = "testpassword123"
        wrong_password = "wrongpassword"
        hash_password = SecurityService.create_password_hash(correct_password)
        
        # Проверяем что неверный пароль не проходит верификацию
        assert SecurityService.verify_password(wrong_password, hash_password) is False

    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self):
        """Тест поиска пользователя по email - найден"""
        # Создаем цепочку моков для результата
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.test_user
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        
        self.mock_db.execute.return_value = mock_result
        
        # Вызываем функцию
        result = await SecurityService.get_user_by_email(self.mock_db, "test@example.com")
        
        # Проверяем результат
        assert result == self.test_user
        self.mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self):
        """Тест поиска пользователя по email - не найден"""
        # Создаем цепочку моков для пустого результата
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        
        self.mock_db.execute.return_value = mock_result
        
        # Вызываем функцию
        result = await SecurityService.get_user_by_email(self.mock_db, "nonexistent@example.com")
        
        # Проверяем результат
        assert result is None
        self.mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_found(self):
        """Тест поиска пользователя по username - найден"""
        # Создаем цепочку моков для результата
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.test_user
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        
        self.mock_db.execute.return_value = mock_result
        
        # Вызываем функцию
        result = await SecurityService.get_user_by_username(self.mock_db, "testuser")
        
        # Проверяем результат
        assert result == self.test_user
        self.mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self):
        """Тест поиска пользователя по username - не найден"""
        # Создаем цепочку моков для пустого результата
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        
        self.mock_db.execute.return_value = mock_result
        
        # Вызываем функцию
        result = await SecurityService.get_user_by_username(self.mock_db, "nonexistent")
        
        # Проверяем результат
        assert result is None
        self.mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self):
        """Тест поиска пользователя по ID - найден"""
        # Создаем цепочку моков для результата
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.test_user
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        
        self.mock_db.execute.return_value = mock_result
        
        # Вызываем функцию
        result = await SecurityService.get_user_by_id(self.mock_db, 1)
        
        # Проверяем результат
        assert result == self.test_user
        self.mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_success_by_username(self):
        """Тест успешной аутентификации по username"""
        username = "testuser"
        password = "testpassword123"
        
        # Создаем пользователя с правильным хешем пароля
        hashed_password = SecurityService.create_password_hash(password)
        test_user = User(
            id=1,
            email="test@example.com",
            username=username,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False
        )
        
        # Мокаем поиск пользователя
        with patch.object(SecurityService, 'get_user_by_username', return_value=test_user):
            result = await SecurityService.authenticate_user(self.mock_db, username, password)
            assert result == test_user

    @pytest.mark.asyncio
    async def test_authenticate_user_success_by_email(self):
        """Тест успешной аутентификации по email"""
        email = "test@example.com"
        password = "testpassword123"
        
        # Создаем пользователя с правильным хешем пароля
        hashed_password = SecurityService.create_password_hash(password)
        test_user = User(
            id=1,
            email=email,
            username="testuser",
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False
        )
        
        # Мокаем поиск пользователя (не найден по username, найден по email)
        with patch.object(SecurityService, 'get_user_by_username', return_value=None), \
             patch.object(SecurityService, 'get_user_by_email', return_value=test_user):
            result = await SecurityService.authenticate_user(self.mock_db, email, password)
            assert result == test_user

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self):
        """Тест аутентификации с неверным паролем"""
        username = "testuser"
        correct_password = "testpassword123"
        wrong_password = "wrongpassword"
        
        # Создаем пользователя с правильным хешем пароля
        hashed_password = SecurityService.create_password_hash(correct_password)
        test_user = User(
            id=1,
            email="test@example.com",
            username=username,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False
        )
        
        # Мокаем поиск пользователя
        with patch.object(SecurityService, 'get_user_by_username', return_value=test_user):
            result = await SecurityService.authenticate_user(self.mock_db, username, wrong_password)
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        """Тест аутентификации несуществующего пользователя"""
        username = "nonexistent"
        password = "testpassword123"
        
        # Мокаем поиск пользователя (не найден)
        with patch.object(SecurityService, 'get_user_by_username', return_value=None), \
             patch.object(SecurityService, 'get_user_by_email', return_value=None):
            result = await SecurityService.authenticate_user(self.mock_db, username, password)
            assert result is None

    @patch('src.services.security_service.settings')
    def test_create_access_token(self, mock_settings):
        """Тест создания access токена"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        
        data = {"sub": "1"}
        expires_delta = timedelta(minutes=30)
        
        token = SecurityService.create_access_token(data, expires_delta)
        
        # Проверяем что токен создался
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Декодируем токен и проверяем содержимое
        decoded = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        assert decoded["sub"] == "1"
        assert decoded["type"] == "access"

    @patch('src.services.security_service.settings')
    def test_create_refresh_token(self, mock_settings):
        """Тест создания refresh токена"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7
        
        data = {"sub": "1"}
        expires_delta = timedelta(days=7)
        
        token = SecurityService.create_refresh_token(data, expires_delta)
        
        # Проверяем что токен создался
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Декодируем токен и проверяем содержимое
        decoded = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        assert decoded["sub"] == "1"
        assert decoded["type"] == "refresh"
        assert "jti" in decoded  # JWT ID для предотвращения повторного использования

    @patch('src.services.security_service.settings')
    def test_create_tokens(self, mock_settings):
        """Тест создания пары токенов"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7
        
        user_id = 1
        tokens = SecurityService.create_tokens(user_id)
        
        # Проверяем структуру ответа
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
        
        # Проверяем что токены валидны
        access_decoded = jwt.decode(tokens["access_token"], "test_secret_key", algorithms=["HS256"])
        refresh_decoded = jwt.decode(tokens["refresh_token"], "test_secret_key", algorithms=["HS256"])
        
        assert access_decoded["sub"] == "1"
        assert access_decoded["type"] == "access"
        assert refresh_decoded["sub"] == "1"
        assert refresh_decoded["type"] == "refresh"

    @patch('src.services.security_service.settings')
    def test_verify_token_valid_access(self, mock_settings):
        """Тест проверки валидного access токена"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        
        # Создаем токен
        data = {"sub": "1", "type": "access", "exp": datetime.utcnow() + timedelta(minutes=30)}
        token = jwt.encode(data, "test_secret_key", algorithm="HS256")
        
        # Проверяем токен
        result = SecurityService.verify_token(token, "access")
        
        assert result is not None
        assert result["sub"] == "1"
        assert result["type"] == "access"

    @patch('src.services.security_service.settings')
    def test_verify_token_expired(self, mock_settings):
        """Тест проверки истекшего токена"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        
        # Создаем истекший токен
        data = {"sub": "1", "type": "access", "exp": datetime.utcnow() - timedelta(minutes=30)}
        token = jwt.encode(data, "test_secret_key", algorithm="HS256")
        
        # Проверяем токен
        result = SecurityService.verify_token(token, "access")
        
        assert result is None

    @patch('src.services.security_service.settings')
    def test_verify_token_wrong_type(self, mock_settings):
        """Тест проверки токена неправильного типа"""
        # Настройка мок настроек
        mock_settings.SECRET_KEY = "test_secret_key"
        mock_settings.ALGORITHM = "HS256"
        
        # Создаем refresh токен
        data = {"sub": "1", "type": "refresh", "exp": datetime.utcnow() + timedelta(days=7)}
        token = jwt.encode(data, "test_secret_key", algorithm="HS256")
        
        # Проверяем как access токен
        result = SecurityService.verify_token(token, "access")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self):
        """Тест успешного обновления токенов"""
        user_id = 1
        
        # Мокаем verify_token для возврата валидного payload
        valid_payload = {"sub": str(user_id), "type": "refresh"}
        
        with patch.object(SecurityService, 'verify_token', return_value=valid_payload), \
             patch.object(SecurityService, 'get_user_by_id', return_value=self.test_user), \
             patch.object(SecurityService, 'create_tokens') as mock_create_tokens:
            
            mock_create_tokens.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer"
            }
            
            result = await SecurityService.refresh_tokens(self.mock_db, "valid_refresh_token")
            
            assert result is not None
            assert result["access_token"] == "new_access_token"
            assert result["refresh_token"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid_token(self):
        """Тест обновления токенов с невалидным токеном"""
        with patch.object(SecurityService, 'verify_token', return_value=None):
            result = await SecurityService.refresh_tokens(self.mock_db, "invalid_refresh_token")
            assert result is None

    @pytest.mark.asyncio
    async def test_refresh_tokens_user_not_found(self):
        """Тест обновления токенов для несуществующего пользователя"""
        user_id = 999
        
        # Мокаем verify_token для возврата валидного payload
        valid_payload = {"sub": str(user_id), "type": "refresh"}
        
        with patch.object(SecurityService, 'verify_token', return_value=valid_payload), \
             patch.object(SecurityService, 'get_user_by_id', return_value=None):
            
            result = await SecurityService.refresh_tokens(self.mock_db, "valid_refresh_token")
            assert result is None


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 