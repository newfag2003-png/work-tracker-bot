from config import ADMIN_IDS
from datetime import datetime
import pytz

# Часовой пояс Киев
KYIV_TZ = pytz.timezone('Europe/Kiev')

def now_local():
    """
    Возвращает текущее время в часовом поясе Киева (UTC+2 / UTC+3).
    Всегда возвращает "осознанный" (timezone-aware) datetime объект.
    """
    # Получаем текущее время в UTC и затем преобразуем его в киевское время
    return datetime.now(pytz.UTC).astimezone(KYIV_TZ)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def format_duration(duration) -> str:
    """Форматирует timedelta в строку 'Xч Yмин'"""
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0 and minutes > 0:
        return f"{hours}ч {minutes}мин"
    elif hours > 0:
        return f"{hours}ч"
    else:
        return f"{minutes}мин"

def validate_time_format(time_str: str) -> bool:
    """Проверяет корректность формата времени ЧЧ:ММ"""
    try:
        hour, minute = map(int, time_str.split(':'))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except:
        return False
