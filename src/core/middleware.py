import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Импортируем логгеры
from src.logs.server_log import api_logger
from src.logs.debug_log import debug_logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Время начала запроса
        start_time = time.time()
        
        # Получаем информацию о запросе
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else "unknown"
        
        # Логируем детали запроса для дебага
        debug_logger.log_request(request)
        
        # Выполняем запрос
        try:
            response = await call_next(request)
            
            # Вычисляем время выполнения
            process_time = time.time() - start_time
            
            # Логируем информацию о запросе (обычный лог)
            log_message = (
                f"Request: {method} {url} | "
                f"Status: {response.status_code} | "
                f"Client: {client_host} | "
                f"Process Time: {process_time:.3f}s"
            )
            
            # Используем цветной вывод для разных типов запросов
            print(f"\033[92m{log_message}\033[0m")  # Зеленый цвет
            
            # Записываем в стандартный лог
            api_logger.info(log_message)
            
            # Детальный лог ответа
            debug_logger.log_response(response, process_time)
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            debug_logger.log_exception(f"Ошибка при обработке запроса {method} {url}")
            api_logger.error(f"Error processing request {method} {url}: {str(e)}")
            raise 