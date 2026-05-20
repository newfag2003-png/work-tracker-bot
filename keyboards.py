from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import BUTTONS
from database import get_objects, get_last_used_object

def get_main_keyboard(user_id: int, is_working: bool = False):
    """Главная клавиатура"""
    status_text = "🔴 ВЫ СЕЙЧАС РАБОТАЕТЕ" if is_working else "⚪ ВЫ НЕ РАБОТАЕТЕ"
    work_button = BUTTONS["stop_work"] if is_working else BUTTONS["start_work"]
    
    keyboard = [
        [KeyboardButton(text=status_text)],
        [KeyboardButton(text=work_button)],
        [KeyboardButton(text=BUTTONS["my_balance"]), KeyboardButton(text=BUTTONS["statistics"])],
        [KeyboardButton(text=BUTTONS["expenses"]), KeyboardButton(text=BUTTONS["fix"])],
        [KeyboardButton(text=BUTTONS["delete_last"])],
        [KeyboardButton(text=BUTTONS["archive"]), KeyboardButton(text=BUTTONS["help"])]
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
        [KeyboardButton(text=BUTTONS["admin_archive"])],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_archive_menu_keyboard():
    """Клавиатура меню архива для сотрудника"""
    keyboard = [
        [KeyboardButton(text="📎 ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")],
        [KeyboardButton(text="📁 МЕСЯЧНЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text="📁 ГОДОВЫЕ ОТЧЁТЫ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_archive_menu_keyboard():
    """Клавиатура меню архива для админа"""
    keyboard = [
        [KeyboardButton(text="📎 ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ (все сотрудники)")],
        [KeyboardButton(text="📁 МЕСЯЧНЫЕ ОТЧЁТЫ (все сотрудники)")],
        [KeyboardButton(text="📁 ГОДОВЫЕ ОТЧЁТЫ (все сотрудники)")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_years_keyboard(years):
    """Клавиатура выбора года"""
    keyboard = []
    row = []
    for i, year in enumerate(years):
        row.append(KeyboardButton(text=str(year)))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text=BUTTONS["back"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_months_keyboard():
    """Клавиатура выбора месяца"""
    months = [
        "01 ЯНВ", "02 ФЕВ", "03 МАР", "04 АПР",
        "05 МАЙ", "06 ИЮН", "07 ИЮЛ", "08 АВГ",
        "09 СЕН", "10 ОКТ", "11 НОЯ", "12 ДЕК"
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

def get_objects_keyboard(user_id: int, is_admin: bool = False):
    """Клавиатура выбора объекта"""
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
    """Клавиатура подтверждения"""
    keyboard = [[KeyboardButton(text="✅ ДА"), KeyboardButton(text="❌ НЕТ")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_night_shift_inline():
    """Инлайн-клавиатура для вопроса о ночной смене"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, НОЧНАЯ СМЕНА", callback_data="night_yes"),
         InlineKeyboardButton(text="❌ НЕТ, ОШИБКА", callback_data="night_no")]
    ])
    return keyboard

def get_expense_confirm_inline(expense_id: int):
    """Инлайн-клавиатура для подтверждения расходов (админ)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"expense_approve_{expense_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"expense_reject_{expense_id}")]
    ])
    return keyboard

def get_salary_confirm_inline(payment_id: int):
    """Инлайн-клавиатура для подтверждения выплаты (сотрудник)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"salary_confirm_{payment_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"salary_reject_{payment_id}")]
    ])
    return keyboard

def get_manage_objects_keyboard(objects):
    """Клавиатура управления объектами (по 2 кнопки в строке)"""
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
    """Клавиатура выбора записи для редактирования"""
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
    """Клавиатура выбора поля для редактирования"""
    keyboard = [
        [KeyboardButton(text="🕐 ВРЕМЯ НАЧАЛА"), KeyboardButton(text="🕐 ВРЕМЯ ОКОНЧАНИЯ")],
        [KeyboardButton(text="📍 ОБЪЕКТ"), KeyboardButton(text="📝 ОТЧЁТ ЗА ДЕНЬ")],
        [KeyboardButton(text=BUTTONS["cancel"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ============= КЛАВИАТУРЫ ДЛЯ ОТЧЁТОВ =============

def get_report_menu_keyboard():
    """Клавиатура меню отчётов"""
    keyboard = [
        [KeyboardButton(text="📦 ОТЧЁТ ПО ОБЪЕКТАМ")],
        [KeyboardButton(text="💸 ОТЧЁТ ПО РАСХОДАМ")],
        [KeyboardButton(text="💰 ОТЧЁТ ПО ВЫПЛАТАМ")],
        [KeyboardButton(text="📈 ПРОГНОЗ")],
        [KeyboardButton(text=BUTTONS["back"])]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_years_keyboard_for_report(years):
    """Клавиатура выбора года для отчётов"""
    keyboard = []
    row = []
    for i, year in enumerate(years):
        row.append(KeyboardButton(text=str(year)))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text=BUTTONS["back"])])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_months_keyboard_for_report():
    """Клавиатура выбора месяца для отчётов"""
    months = [
        "01 ЯНВ", "02 ФЕВ", "03 МАР", "04 АПР",
        "05 МАЙ", "06 ИЮН", "07 ИЮЛ", "08 АВГ",
        "09 СЕН", "10 ОКТ", "11 НОЯ", "12 ДЕК"
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