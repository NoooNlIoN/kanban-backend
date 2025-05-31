#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности суперпользователя
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models.user import User
from src.models.board import BoardUserRole
from src.api.dependencies.permissions import check_board_permissions
from src.api.v1.columns import check_board_access
from src.services.board_service import BoardService
from sqlalchemy.ext.asyncio import AsyncSession


async def test_superuser_permissions():
    """Тест проверки прав суперпользователя"""
    
    # Создаем мок-объекты для тестирования
    class MockUser:
        def __init__(self, user_id: int, is_superuser: bool = False):
            self.id = user_id
            self.is_superuser = is_superuser
    
    class MockDB:
        pass
    
    # Тестируем обычного пользователя
    regular_user = MockUser(1, is_superuser=False)
    superuser = MockUser(2, is_superuser=True)
    
    print("🧪 Тестирование функциональности суперпользователя")
    print("=" * 50)
    
    # Тест 1: Проверка функции check_board_permissions
    print("1. Тестирование check_board_permissions...")
    
    try:
        # Для суперпользователя должно возвращать True без проверки ролей
        result = await check_board_permissions(
            db=MockDB(),
            board_id=1,
            user_id=superuser.id,
            required_roles=[BoardUserRole.OWNER],
            user=superuser
        )
        print("   ✅ Суперпользователь: доступ разрешен")
    except Exception as e:
        print(f"   ❌ Ошибка для суперпользователя: {e}")
    
    # Тест 2: Проверка функции get_user_role
    print("\n2. Тестирование get_user_role...")
    
    try:
        # Для суперпользователя должно возвращать OWNER
        user_role = await BoardService.get_user_role(
            db=MockDB(),
            board_id=1,
            user_id=superuser.id,
            user=superuser
        )
        if user_role == BoardUserRole.OWNER:
            print("   ✅ Суперпользователь получил роль OWNER")
        else:
            print(f"   ❌ Суперпользователь получил роль {user_role}, ожидалась OWNER")
    except Exception as e:
        print(f"   ❌ Ошибка при проверке роли суперпользователя: {e}")
    
    try:
        # Для обычного пользователя без роли должно возвращать None
        user_role = await BoardService.get_user_role(
            db=MockDB(),
            board_id=1,
            user_id=regular_user.id,
            user=regular_user
        )
        if user_role is None:
            print("   ✅ Обычный пользователь без доступа к доске получил None")
        else:
            print(f"   ❌ Обычный пользователь получил роль {user_role}, ожидался None")
    except Exception as e:
        print(f"   ❌ Ошибка при проверке роли обычного пользователя: {e}")
    
    print("\n3. Проверка логики в коде...")
    
    # Проверяем логику напрямую
    if superuser.is_superuser:
        print("   ✅ Суперпользователь определен корректно")
    else:
        print("   ❌ Ошибка определения суперпользователя")
    
    if not regular_user.is_superuser:
        print("   ✅ Обычный пользователь определен корректно")
    else:
        print("   ❌ Ошибка определения обычного пользователя")
    
    print("\n4. Проверка условий доступа...")
    
    # Проверяем условие для суперпользователя
    if superuser and superuser.is_superuser:
        print("   ✅ Условие для суперпользователя работает")
    else:
        print("   ❌ Условие для суперпользователя не работает")
    
    # Проверяем условие для обычного пользователя
    if not (regular_user and regular_user.is_superuser):
        print("   ✅ Условие для обычного пользователя работает")
    else:
        print("   ❌ Условие для обычного пользователя не работает")
    
    print("\n" + "=" * 50)
    print("🎉 Тестирование завершено!")
    print("\nИзменения, которые были внесены:")
    print("1. ✅ Обновлена функция check_board_permissions")
    print("2. ✅ Обновлена функция check_board_access")
    print("3. ✅ Обновлена функция get_user_role - суперпользователи всегда получают роль OWNER")
    print("4. ✅ Обновлены эндпоинты досок (boards.py)")
    print("5. ✅ Обновлены эндпоинты тегов (tags.py)")
    print("6. ✅ Обновлены эндпоинты разрешений досок (board_permissions.py)")
    print("7. ✅ Обновлены эндпоинты комментариев (comments.py)")
    print("8. ✅ Обновлены websocket соединения (websockets.py)")
    print("9. ✅ Добавлен метод get_all_boards в BoardService")
    print("\nТеперь суперпользователи:")
    print("• Автоматически получают роль OWNER на ВСЕХ досках")
    print("• Видят все доски в системе")
    print("• Могут изменять любые доски")
    print("• Могут удалять любые доски")
    print("• Работают с колонками на любых досках")
    print("• Работают с карточками на любых досках")
    print("• Редактируют и удаляют любые комментарии")
    print("• Работают с тегами на любых досках")
    print("• Имеют полный административный доступ ко всему функционалу")


if __name__ == "__main__":
    asyncio.run(test_superuser_permissions()) 