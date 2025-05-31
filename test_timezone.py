from datetime import datetime

# Тест преобразования даты с часовым поясом в naive datetime
print("Тест преобразования даты с часовым поясом в naive datetime:")

# ISO строка с UTC (Z)
iso_string = '2025-05-29T20:59:59.000Z'
print(f"Исходная строка с UTC (Z): {iso_string}")

# Преобразуем Z в +00:00
iso_string_fixed = iso_string.replace('Z', '+00:00')
print(f"Строка с заменой Z на +00:00: {iso_string_fixed}")

# Парсим в datetime
dt_with_tz = datetime.fromisoformat(iso_string_fixed)
print(f"Преобразовано в datetime с TZ: {dt_with_tz}, tzinfo: {dt_with_tz.tzinfo}")

# Удаляем часовой пояс
dt_naive = dt_with_tz.replace(tzinfo=None)
print(f"Без часового пояса: {dt_naive}, tzinfo: {dt_naive.tzinfo}")

# Моделируем запись в базу
print(f"\nСимуляция SQL запроса:")
print(f"UPDATE cards SET deadline='{dt_naive.isoformat()}', updated_at=CURRENT_TIMESTAMP WHERE cards.id = 24")

print("\nОжидаемый результат: успех, так как datetime без tzinfo совместим с TIMESTAMP WITHOUT TIME ZONE") 