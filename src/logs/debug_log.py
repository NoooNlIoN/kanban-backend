import logging
import sys
import os
import json
import inspect
import datetime
from pathlib import Path
from functools import wraps
import traceback

# Создаем директорию для логов, если её нет
log_dir = Path(__file__).parent
log_dir.mkdir(exist_ok=True)

# Константы для цветного вывода
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
END = '\033[0m'

# Форматтер для красивого вывода объектов
def format_object(obj):
    if hasattr(obj, '__dict__'):
        return str(obj.__dict__)
    if isinstance(obj, (list, dict, tuple, set)):
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
        except:
            return str(obj)
    return str(obj)

class DebugLogger:
    """Расширенный логгер для дебага с подробной информацией и цветным выводом"""
    
    def __init__(self, name="debug", level=logging.DEBUG):
        # Создаем основной логгер
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False
        
        # Очищаем handlers если они уже были добавлены
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Форматтер для логов
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        # Консольный форматтер (упрощенный)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        # Обработчик для вывода в файл
        file_handler = logging.FileHandler(log_dir / "debug.log", encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        
        # Обработчик для вывода в консоль с цветами
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(level)
        
        # Добавляем обработчики к логгеру
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message, *args, **kwargs):
        """Дебаг лог с информацией о вызывающем коде"""
        frame = inspect.currentframe().f_back
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        function = frame.f_code.co_name
        
        # Получаем относительный путь к файлу
        try:
            src_index = filename.index("src")
            filename = filename[src_index:]
        except:
            pass
        
        caller_info = f"{BLUE}[{filename}:{lineno} - {function}]{END}"
        self.logger.debug(f"{caller_info} {message}", *args, **kwargs)
    
    def info(self, message, *args, **kwargs):
        """Информационный лог"""
        self.logger.info(f"{GREEN}{message}{END}", *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        """Предупреждение"""
        self.logger.warning(f"{YELLOW}{message}{END}", *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        """Лог ошибок"""
        # Добавляем трейс к сообщению об ошибке
        trace = traceback.format_exc()
        if trace and trace != 'NoneType: None\n':
            message = f"{message}\n{RED}Traceback:{END}\n{trace}"
        self.logger.error(f"{RED}{message}{END}", *args, **kwargs)
    
    def critical(self, message, *args, **kwargs):
        """Критическая ошибка"""
        trace = traceback.format_exc()
        if trace and trace != 'NoneType: None\n':
            message = f"{message}\n{RED}Traceback:{END}\n{trace}"
        self.logger.critical(f"{BOLD}{RED}{message}{END}", *args, **kwargs)
    
    def start_func(self, func_name=None, params=None):
        """Логирование начала функции с параметрами"""
        if not func_name:
            frame = inspect.currentframe().f_back
            func_name = frame.f_code.co_name
        
        params_str = ""
        if params:
            params_str = f" с параметрами: {format_object(params)}"
        
        self.debug(f"{PURPLE}Начало выполнения функции {func_name}{END}{params_str}")
    
    def end_func(self, func_name=None, result=None, execution_time=None):
        """Логирование окончания функции с результатом"""
        if not func_name:
            frame = inspect.currentframe().f_back
            func_name = frame.f_code.co_name
        
        result_str = ""
        if result is not None:
            if isinstance(result, (dict, list, tuple, set)):
                # Ограничиваем вывод результата для больших объектов
                result_str = f", результат: {format_object(result)[:1000]}"
                if len(format_object(result)) > 1000:
                    result_str += "... [обрезано]"
            else:
                result_str = f", результат: {result}"
        
        time_str = ""
        if execution_time:
            time_str = f", время выполнения: {execution_time:.4f}с"
        
        self.debug(f"{PURPLE}Окончание выполнения функции {func_name}{END}{result_str}{time_str}")
    
    def log_exception(self, message="Произошло исключение"):
        """Логирование исключения с трейсом"""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type:
            tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self.error(f"{message}: {exc_type.__name__}: {exc_value}\n{tb_str}")
        else:
            self.error(message)
    
    def log_request(self, request, extra_info=None):
        """Логирование входящего HTTP запроса"""
        method = getattr(request, 'method', 'UNKNOWN')
        url = str(getattr(request, 'url', 'UNKNOWN'))
        client = getattr(request, 'client', None)
        client_host = client.host if client else "unknown"
        headers = dict(getattr(request, 'headers', {}))
        
        info = (
            f"{CYAN}HTTP запрос:{END} {method} {url}\n"
            f"{CYAN}Клиент:{END} {client_host}\n"
            f"{CYAN}Заголовки:{END} {json.dumps(headers, indent=2, ensure_ascii=False)}"
        )
        
        if extra_info:
            info += f"\n{CYAN}Дополнительно:{END} {extra_info}"
        
        self.debug(info)
    
    def log_response(self, response, process_time=None):
        """Логирование исходящего HTTP ответа"""
        status_code = getattr(response, 'status_code', 'UNKNOWN')
        headers = dict(getattr(response, 'headers', {}))
        
        color = GREEN if 200 <= status_code < 400 else YELLOW if 400 <= status_code < 500 else RED
        
        info = (
            f"{CYAN}HTTP ответ:{END} {color}Статус {status_code}{END}\n"
            f"{CYAN}Заголовки:{END} {json.dumps(headers, indent=2, ensure_ascii=False)}"
        )
        
        if process_time is not None:
            info += f"\n{CYAN}Время обработки:{END} {process_time:.3f}с"
        
        self.debug(info)
    
    def log_data(self, name, data):
        """Логирование произвольных данных в удобном формате"""
        formatted_data = format_object(data)
        self.debug(f"{CYAN}{name}:{END}\n{formatted_data}")

def log_function(logger=None):
    """Декоратор для автоматического логирования функций"""
    if logger is None:
        logger = debug_logger
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_args = {}
            # Добавляем имена аргументов
            func_args.update(zip(inspect.getfullargspec(func).args, args))
            # Добавляем kwargs
            func_args.update(kwargs)
            
            # Не логируем self и cls для методов классов
            if 'self' in func_args:
                func_args.pop('self')
            if 'cls' in func_args:
                func_args.pop('cls')
            
            start_time = datetime.datetime.now()
            logger.start_func(func.__name__, func_args)
            
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.datetime.now() - start_time).total_seconds()
                logger.end_func(func.__name__, result, execution_time)
                return result
            except Exception as e:
                logger.log_exception(f"Ошибка в функции {func.__name__}")
                raise
        
        return wrapper
    
    return decorator

# Создаем глобальный экземпляр логгера для дебага
debug_logger = DebugLogger() 