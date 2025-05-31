import logging
import sys
import os
from pathlib import Path

# Создаем директорию для логов, если её нет
log_dir = Path(__file__).parent
log_dir.mkdir(exist_ok=True)

# Настраиваем логирование в файл и консоль
def setup_logging():
    # Создаем логгер
    logger = logging.getLogger("api_logger")
    logger.setLevel(logging.INFO)
    
    # Форматтер для логов
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Обработчик для вывода в файл
    file_handler = logging.FileHandler(log_dir / "api_requests.log")
    file_handler.setFormatter(formatter)
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Создаем экземпляр логгера
api_logger = setup_logging() 