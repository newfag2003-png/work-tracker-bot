import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Настройки работы
DEFAULT_HOURLY_RATE = 200
NIGHT_BONUS = 1.2
NIGHT_START = 22
NIGHT_END = 6

# Архивация (1-го числа каждого месяца)
ARCHIVE_DAY = 1
ARCHIVE_HOUR = 3
ARCHIVE_MINUTE = 0

# Отправка отчёта админу после архивации
SEND_REPORT_HOUR = 4
SEND_REPORT_MINUTE = 0

# Ежедневное напоминание
REMINDER_HOUR = 8
REMINDER_MINUTE = 50

# Еженедельный отчёт
WEEKLY_REPORT_DAY = 6
WEEKLY_REPORT_HOUR = 9
WEEKLY_REPORT_MINUTE = 0

# Названия кнопок
BUTTONS = {
    "start_work": "⏱ НАЧАТЬ РАБОТУ",
    "stop_work": "⛔ ЗАКОНЧИТЬ РАБОТУ",
    "my_balance": "💰 МОЙ БАЛАНС",
    "statistics": "📊 СТАТИСТИКА",
    "expenses": "💸 РАСХОДНИК",
    "fix": "✏️ ИСПРАВИТЬ",
    "delete_last": "🗑 УДАЛИТЬ ПОСЛЕДНЕЕ",
    "my_export": "📎 МОЙ ЭКСПОРТ",      # <--- ДОБАВИТЬ
    "archive": "📁 АРХИВ",              # <--- ДОБАВИТЬ
    "help": "❓ ПОМОЩЬ",
    "admin_panel": "👑 АДМИН-ПАНЕЛЬ",
    "admin_archive": "📁 АРХИВ ВСЕХ",   # <--- ДОБАВИТЬ
    "back": "🔙 НАЗАД",
    "cancel": "❌ ОТМЕНА"
}
