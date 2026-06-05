from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import BUTTONS
from database import get_objects, get_last_used_object

def get_main_keyboard(user_id: int, is_working: bool = False):
    """Главная клавиатура для сотрудника"""
    status_text = "🔴 ВЫ СЕЙЧАС РАБОТАЕТЕ" if is_working else "⚪ ВЫ НЕ РАБОТАЕТЕ"
    work_button = BUTTONS["stop_work"] if is_working else BUTTONS["start_work"]
    
    keyboard = [
        [KeyboardButton(text=status_text)],
        [KeyboardButton(text=work_button)],
        [KeyboardButton(text=BUTTONS["my_balance"]), KeyboardButton(text=BUTTONS["statistics"])],
        [KeyboardButton(text=BUTTONS["expenses"]), KeyboardButton(text=BUTTONS["fix"])],
        [KeyboardButton(text=BUTTONS["delete_last"])],
        [KeyboardButton(text="📎 МОЙ ЭКСПОРТ"), KeyboardButton(text=BUTTONS["help"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_button_keyboard():
    """Кнопка для входа в админ-панель"""
    keyboard = [[KeyboardButton(text=BUTTONS["admin_panel"])]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_panel_keyboard():
    """Клавиатура админ-панели"""
    keyboard = [
        [KeyboardButton(text="💰 ВЫДАТЬ ЗАРПЛАТУ"), KeyboardButton(text="💹 НАЗНАЧИТЬ СТАВКУ")],
        [KeyboardButton(text="📋 ЗАРПЛАТНАЯ ВЕДОМОСТЬ"), KeyboardButton(text="➕ ДОБАВИТЬ ОБЪЕКТ")],
        [KeyboardButton(text="📦 УПРАВЛЕНИЕ ОБЪЕКТАМИ"), KeyboardButton(text="⏳ РАСХОДЫ НА ПРОВЕРКЕ")],
        [KeyboardButton(text="🟢 КТО РАБОТАЕТ"), KeyboardButton(text="📊 ОТЧЁТ")],
        [KeyboardButton(text="📤 СДЕЛАТЬ БЭКАП"), KeyboardButton(text="📎 ЭКСПОРТ ВСЕХ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_employee_export_menu_keyboard():
    """Клавиатура меню экспорта для сотрудника"""
    keyboard = [
        [KeyboardButton(text="📎 МОЙ ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")],
        [KeyboardButton(text="📁 МОИ МЕСЯЧНЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text="📁 МОИ ГОДОВЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_export_menu_keyboard():
    """Клавиатура меню экспорта для администратора"""
    keyboard = [
        [KeyboardButton(text="📎 ОБЩИЙ ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")],
        [KeyboardButton(text="📁 ОБЩИЕ МЕСЯЧНЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text="📁 ОБЩИЕ ГОДОВЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_objects_keyboard(user_id: int, is_admin: bool = False):
    objects = get_objects()
    if not objects:
        keyboard = [[KeyboardButton(text="❌ НЕТ ДОСТУПНЫХ ОБЪЕКТОВ")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    keyboard = []
    for obj in objects:
        keyboard.append([KeyboardButton(text=f"📦 {obj}")])
    
    if is_admin:
        keyboard.append([KeyboardButton(text="➕ ДРУГОЙ ОБЪЕКТ")])
    
    keyboard.append([KeyboardButton(text=BUTTONS["cancel"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_confirm_keyboard():
    keyboard = [[KeyboardButton(text="✅ ДА"), KeyboardButton(text="❌ НЕТ")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_night_shift_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, НОЧНАЯ СМЕНА", callback_data="night_yes"),
         InlineKeyboardButton(text="❌ НЕТ, ОШИБКА", callback_data="night_no")]
    ])

def get_expense_confirm_inline(expense_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"expense_approve_{expense_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"expense_reject_{expense_id}")]
    ])

def get_salary_confirm_inline(payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"salary_confirm_{payment_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"salary_reject_{payment_id}")]
    ])

def get_manage_objects_keyboard(objects):
    keyboard = []
    for obj in objects:
        is_hidden = obj["is_hidden"]
        name = obj["name"]
        if is_hidden:
            show_hide_button = f"👁 ПОКАЗАТЬ {name}"
        else:
            show_hide_button = f"🚫 СКРЫТЬ {name}"
        delete_button = f"🗑 УДАЛИТЬ {name}"
        keyboard.append([KeyboardButton(text=show_hide_button), KeyboardButton(text=delete_button)])
    keyboard.append([KeyboardButton(text=BUTTONS["back"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_edit_sessions_keyboard(sessions):
    keyboard = []
    for i, session in enumerate(sessions, 1):
        date = session["start_time"][:10]
        obj = session["object_name"]
        hours = session["duration"] / 3600
        earnings = session["earnings"]
        keyboard.append([KeyboardButton(text=f"{i}️⃣ {date} | {obj} | {hours:.1f}ч | {earnings}₴")])
    keyboard.append([KeyboardButton(text=BUTTONS["cancel"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_edit_field_keyboard():
    keyboard = [
        [KeyboardButton(text="🕐 ВРЕМЯ НАЧАЛА"), KeyboardButton(text="🕐 ВРЕМЯ ОКОНЧАНИЯ")],
        [KeyboardButton(text="📍 ОБЪЕКТ"), KeyboardButton(text="📝 ОТЧЁТ ЗА ДЕНЬ")],
        [KeyboardButton(text=BUTTONS["cancel"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_report_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="📦 ОТЧЁТ ПО ОБЪЕКТАМ")],
        [KeyboardButton(text="💸 ОТЧЁТ ПО РАСХОДАМ")],
        [KeyboardButton(text="💰 ОТЧЁТ ПО ВЫПЛАТАМ")],
        [KeyboardButton(text="📈 ПРОГНОЗ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_years_keyboard_for_report(years):
    """Клавиатура выбора года для отчётов (только год, без лишнего)"""
    keyboard = []
    # Показываем только последние 3 года + текущий
    current_year = datetime.now().year
    years_to_show = sorted(set([current_year - 2, current_year - 1, current_year, current_year + 1, current_year + 2]))
    years_to_show = [y for y in years_to_show if y >= 2024]
    
    row = []
    for year in years_to_show:
        row.append(KeyboardButton(text=str(year)))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text=BUTTONS["back"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_months_keyboard_for_report():
    """Клавиатура выбора месяца (3 колонки, 4 ряда)"""
    months = [
        "01 ЯНВ", "02 ФЕВ", "03 МАР",
        "04 АПР", "05 МАЙ", "06 ИЮН",
        "07 ИЮЛ", "08 АВГ", "09 СЕН",
        "10 ОКТ", "11 НОЯ", "12 ДЕК"
    ]
    keyboard = []
    row = []
    for month in months:
        row.append(KeyboardButton(text=month))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text=BUTTONS["back"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_inline_months_keyboard(year: int):
    """Inline-клавиатура для выбора месяца (кнопки под сообщением)"""
    months = [
        ("01 ЯНВ", "01 ЯНВАРЬ"), ("02 ФЕВ", "02 ФЕВРАЛЬ"), ("03 МАР", "03 МАРТ"),
        ("04 АПР", "04 АПРЕЛЬ"), ("05 МАЙ", "05 МАЙ"), ("06 ИЮН", "06 ИЮНЬ"),
        ("07 ИЮЛ", "07 ИЮЛЬ"), ("08 АВГ", "08 АВГУСТ"), ("09 СЕН", "09 СЕНТЯБРЬ"),
        ("10 ОКТ", "10 ОКТЯБРЬ"), ("11 НОЯ", "11 НОЯБРЬ"), ("12 ДЕК", "12 ДЕКАБРЬ")
    ]
    
    keyboard = []
    row = []
    for short, full in months:
        # Создаём кнопку с уникальным идентификатором
        button = InlineKeyboardButton(
            text=short,  # То, что увидит пользователь: "06 ИЮН"
            callback_data=f"report_month_{full}_{year}"  # Скрытые данные: "report_month_06 ИЮНЬ_2026"
        )
        row.append(button)
        if len(row) == 3:  # По 3 кнопки в ряд
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton(text="🔙 НАЗАД", callback_data="report_month_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_years_keyboard():
    """Inline-клавиатура для выбора года"""
    from datetime import datetime
    current_year = datetime.now().year
    years = [current_year - 2, current_year - 1, current_year, current_year + 1]
    
    keyboard = []
    row = []
    for year in years:
        button = InlineKeyboardButton(text=str(year), callback_data=f"report_year_{year}")
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_years_keyboard():
    """Inline-клавиатура для выбора года (текущий + 4 предыдущих)"""
    from datetime import datetime
    current_year = datetime.now().year
    
    # Показываем текущий год и 4 предыдущих
    years = [current_year, current_year - 1, current_year - 2, current_year - 3, current_year - 4]
    
    keyboard = []
    row = []
    for year in years:
        button = InlineKeyboardButton(text=str(year), callback_data=f"report_year_{year}")
        row.append(button)
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_inline_months_keyboard_for_admin(year: int):
    """Inline-клавиатура для выбора месяца (админская версия)"""
    months = [
        ("01 ЯНВ", "01 ЯНВАРЬ"), ("02 ФЕВ", "02 ФЕВРАЛЬ"), ("03 МАР", "03 МАРТ"),
        ("04 АПР", "04 АПРЕЛЬ"), ("05 МАЙ", "05 МАЙ"), ("06 ИЮН", "06 ИЮНЬ"),
        ("07 ИЮЛ", "07 ИЮЛЬ"), ("08 АВГ", "08 АВГУСТ"), ("09 СЕН", "09 СЕНТЯБРЬ"),
        ("10 ОКТ", "10 ОКТЯБРЬ"), ("11 НОЯ", "11 НОЯБРЬ"), ("12 ДЕК", "12 ДЕКАБРЬ")
    ]
    
    keyboard = []
    row = []
    for short, full in months:
        button = InlineKeyboardButton(
            text=short,
            callback_data=f"admin_report_month_{full}_{year}"
        )
        row.append(button)
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)