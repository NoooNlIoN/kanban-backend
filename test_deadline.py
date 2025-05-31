from datetime import datetime
import json

# Тест 1: Преобразование строки ISO с 'Z' в datetime
iso_string = '2025-05-15T20:59:59.000Z'
print(f"ISO строка: {iso_string}")

# Заменяем Z на +00:00 для поддержки Python datetime.fromisoformat()
iso_string_fixed = iso_string.replace('Z', '+00:00')
print(f"Преобразованная строка: {iso_string_fixed}")

try:
    # Парсинг даты
    dt = datetime.fromisoformat(iso_string_fixed)
    print(f"Успешно распарсено: {dt}")
    print(f"Объект datetime: {repr(dt)}")
    
    # Формат для отправки в БД
    print(f"Формат для БД: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # JSON сериализация
    json_data = json.dumps({"deadline": dt.isoformat()})
    print(f"JSON сериализация: {json_data}")
except Exception as e:
    print(f"Ошибка: {type(e).__name__}: {e}")

# Как это будет обрабатываться в коде
print("\nТест обработки в сервисе:")

def update_card_deadline(deadline_str):
    try:
        # Такой код мог бы быть в FastAPI при преобразовании из JSON
        if 'Z' in deadline_str:
            deadline_str = deadline_str.replace('Z', '+00:00')
        
        deadline = datetime.fromisoformat(deadline_str)
        print(f"Deadline в коде: {deadline}")
        
        # Сохранение в базу данных (имитация)
        db_format = deadline.strftime('%Y-%m-%d %H:%M:%S')
        print(f"Формат для БД: {db_format}")
        
        # Возврат в API
        return deadline
    except Exception as e:
        print(f"Ошибка при обработке: {type(e).__name__}: {e}")
        # При ошибке сервис должен вернуть 500 Internal Server Error
        return None

result = update_card_deadline('2025-05-15T20:59:59.000Z')
if result:
    print(f"Успешный результат: {result}")
else:
    print("Ошибка обработки даты") 