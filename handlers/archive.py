import os
from datetime import datetime
from aiogram import F, Router
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext

from config import BUTTONS, ADMIN_IDS
from database import (
    get_user, get_sessions_for_period, get_sessions_for_month,
    get_all_users, get_balance, get_hourly_rate
)
from keyboards import (
    get_archive_menu_keyboard, get_admin_archive_menu_keyboard,
    get_years_keyboard, get_months_keyboard, get_main_keyboard,
    get_admin_button_keyboard
)
from utils.excel_generator import (
    create_current_month_excel, create_monthly_archive_excel,
    create_yearly_archive_excel, create_admin_current_month_excel,
    create_admin_monthly_archive_excel, create_admin_yearly_archive_excel
)

# СОЗДАЁМ РОУТЕР
router = Router()

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def back_to_main_menu(message: Message, state: FSMContext, user_id: int, is_working: bool = False):
    """Вернуться в главное меню"""
    keyboard = get_main_keyboard(user_id, is_working)
    
    if user_id in ADMIN_IDS:
        admin_keyboard = get_admin_button_keyboard()
        keyboard.keyboard.extend(admin_keyboard.keyboard)
    
    await message.answer("📋 Главное меню:", reply_markup=keyboard)
    await state.set_state("idle")

def get_available_months_from_sessions(user_id: int):
    """Получить список месяцев из рабочих сессий"""
    sessions = get_sessions_for_period(user_id, 365)
    months = set()
    for session in sessions:
        month = session["start_time"][:7]
        months.add(month)
    return sorted(list(months), reverse=True)

def get_available_years_from_sessions(user_id: int):
    """Получить список годов из рабочих сессий"""
    months = get_available_months_from_sessions(user_id)
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    return years

def get_global_available_months_from_sessions():
    """Получить список месяцев из всех рабочих сессий"""
    users = get_all_users()
    all_months = set()
    for user in users:
        months = get_available_months_from_sessions(user["user_id"])
        all_months.update(months)
    return sorted(list(all_months), reverse=True)

def get_global_available_years_from_sessions():
    """Получить список годов из всех рабочих сессий"""
    months = get_global_available_months_from_sessions()
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    return years

# ============= АРХИВ ДЛЯ СОТРУДНИКА =============

@router.message(F.text == BUTTONS["archive"])
async def archive_menu(message: Message, state: FSMContext):
    await state.set_state("archive_menu")
    await message.answer(
        "📁 *АРХИВ*\n\nВыберите действие:",
        reply_markup=get_archive_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.message(F.text == "📎 ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")
async def export_current_month(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    await message.answer("📊 Формирую отчёт за текущий месяц...")
    
    try:
        filename = create_current_month_excel(user_id)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption="📊 Отчёт за текущий месяц"
            )
        else:
            await message.answer("❌ Нет данных за текущий месяц")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(F.text == "📁 МЕСЯЧНЫЕ ОТЧЁТЫ")
async def monthly_reports_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    months = get_available_months_from_sessions(user_id)
    
    if not months:
        await message.answer("❌ Нет доступных месячных отчётов")
        return
    
    await state.update_data(archive_type="monthly")
    await state.set_state("archive_choosing_year")
    
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    
    await message.answer(
        "📅 *ВЫБЕРИТЕ ГОД:*",
        reply_markup=get_years_keyboard(years),
        parse_mode="Markdown"
    )

@router.message(F.text == "📁 ГОДОВЫЕ ОТЧЁТЫ")
async def yearly_reports_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    years = get_available_years_from_sessions(user_id)
    
    if not years:
        await message.answer("❌ Нет доступных годовых отчётов")
        return
    
    await state.update_data(archive_type="yearly")
    await state.set_state("archive_choosing_year")
    
    await message.answer(
        "📅 *ВЫБЕРИТЕ ГОД:*",
        reply_markup=get_years_keyboard(years),
        parse_mode="Markdown"
    )

# ============= АРХИВ ДЛЯ АДМИНА =============

@router.message(F.text == BUTTONS["admin_archive"])
async def admin_archive_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await state.set_state("admin_archive_menu")
    await message.answer(
        "📁 *АРХИВ ВСЕХ СОТРУДНИКОВ*\n\nВыберите действие:",
        reply_markup=get_admin_archive_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.message(F.text == "📎 ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ (все сотрудники)")
async def admin_export_current_month(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await message.answer("📊 Формирую общий отчёт за текущий месяц...")
    
    try:
        filename = create_admin_current_month_excel()
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption="📊 Общий отчёт за текущий месяц"
            )
        else:
            await message.answer("❌ Нет данных за текущий месяц")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(F.text == "📁 МЕСЯЧНЫЕ ОТЧЁТЫ (все сотрудники)")
async def admin_monthly_reports_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    months = get_global_available_months_from_sessions()
    
    if not months:
        await message.answer("❌ Нет доступных месячных отчётов")
        return
    
    await state.update_data(admin_archive_type="monthly")
    await state.set_state("admin_archive_choosing_year")
    
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    
    await message.answer(
        "📅 *ВЫБЕРИТЕ ГОД:*",
        reply_markup=get_years_keyboard(years),
        parse_mode="Markdown"
    )

@router.message(F.text == "📁 ГОДОВЫЕ ОТЧЁТЫ (все сотрудники)")
async def admin_yearly_reports_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    years = get_global_available_years_from_sessions()
    
    if not years:
        await message.answer("❌ Нет доступных годовых отчётов")
        return
    
    await state.update_data(admin_archive_type="yearly")
    await state.set_state("admin_archive_choosing_year")
    
    await message.answer(
        "📅 *ВЫБЕРИТЕ ГОД:*",
        reply_markup=get_years_keyboard(years),
        parse_mode="Markdown"
    )

# ============= ВЫБОР ГОДА И МЕСЯЦА (ДЛЯ СОТРУДНИКА) =============

@router.message(lambda msg: msg.text and msg.text.isdigit() and len(msg.text) == 4)
async def archive_choose_year(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "archive_choosing_year":
        return
    
    try:
        year = int(message.text.strip())
        data = await state.get_data()
        archive_type = data.get("archive_type")
        
        if archive_type == "yearly":
            await message.answer("📊 Формирую годовой отчёт...")
            
            try:
                filename = create_yearly_archive_excel(message.from_user.id, year)
                
                if filename and os.path.exists(filename):
                    document = FSInputFile(filename)
                    await message.answer_document(
                        document=document,
                        caption=f"📊 Годовой отчёт за {year} год"
                    )
                else:
                    await message.answer("❌ Отчёт не найден")
            except Exception as e:
                await message.answer(f"❌ Ошибка: {e}")
            
            await state.set_state("idle")
            await back_to_main_menu(message, state, message.from_user.id, False)
            
        elif archive_type == "monthly":
            await state.update_data(selected_year=year)
            await state.set_state("archive_choosing_month")
            
            await message.answer(
                f"📅 *ВЫБЕРИТЕ МЕСЯЦ {year} ГОДА:*",
                reply_markup=get_months_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Неизвестный тип отчёта")
            
    except ValueError:
        await message.answer("❌ Введите корректный год")

@router.message(lambda msg: msg.text and len(msg.text) > 2 and msg.text[:2].isdigit())
async def archive_choose_month(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "archive_choosing_month":
        return
    
    month_text = message.text.strip()
    month_num = int(month_text.split()[0])
    
    data = await state.get_data()
    year = data.get("selected_year")
    archive_type = data.get("archive_type")
    
    await message.answer("📊 Формирую отчёт...")
    
    try:
        if archive_type == "monthly":
            filename = create_monthly_archive_excel(message.from_user.id, year, month_num)
        else:
            filename = create_yearly_archive_excel(message.from_user.id, year)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            caption = f"📊 Отчёт за {month_text} {year}" if archive_type == "monthly" else f"📊 Отчёт за {year} год"
            await message.answer_document(document=document, caption=caption)
        else:
            await message.answer("❌ Отчёт не найден")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.set_state("idle")
    await back_to_main_menu(message, state, message.from_user.id, False)

# ============= ВЫБОР ГОДА И МЕСЯЦА (ДЛЯ АДМИНА) =============

@router.message(lambda msg: msg.text and msg.text.isdigit() and len(msg.text) == 4)
async def admin_archive_choose_year(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "admin_archive_choosing_year":
        return
    
    try:
        year = int(message.text.strip())
        data = await state.get_data()
        archive_type = data.get("admin_archive_type")
        
        if archive_type == "yearly":
            await message.answer("📊 Формирую общий годовой отчёт...")
            
            try:
                filename = create_admin_yearly_archive_excel(year)
                
                if filename and os.path.exists(filename):
                    document = FSInputFile(filename)
                    await message.answer_document(
                        document=document,
                        caption=f"📊 Общий годовой отчёт за {year} год"
                    )
                else:
                    await message.answer("❌ Отчёт не найден")
            except Exception as e:
                await message.answer(f"❌ Ошибка: {e}")
            
            await state.set_state("idle")
            await back_to_main_menu(message, state, message.from_user.id, False)
            
        elif archive_type == "monthly":
            await state.update_data(admin_selected_year=year)
            await state.set_state("admin_archive_choosing_month")
            
            await message.answer(
                f"📅 *ВЫБЕРИТЕ МЕСЯЦ {year} ГОДА:*",
                reply_markup=get_months_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Неизвестный тип отчёта")
            
    except ValueError:
        await message.answer("❌ Введите корректный год")

@router.message(lambda msg: msg.text and len(msg.text) > 2 and msg.text[:2].isdigit())
async def admin_archive_choose_month(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "admin_archive_choosing_month":
        return
    
    month_text = message.text.strip()
    month_num = int(month_text.split()[0])
    
    data = await state.get_data()
    year = data.get("admin_selected_year")
    archive_type = data.get("admin_archive_type")
    
    await message.answer("📊 Формирую общий отчёт...")
    
    try:
        if archive_type == "monthly":
            filename = create_admin_monthly_archive_excel(year, month_num)
        else:
            filename = create_admin_yearly_archive_excel(year)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            caption = f"📊 Общий отчёт за {month_text} {year}" if archive_type == "monthly" else f"📊 Общий отчёт за {year} год"
            await message.answer_document(document=document, caption=caption)
        else:
            await message.answer("❌ Отчёт не найден")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.set_state("idle")
    await back_to_main_menu(message, state, message.from_user.id, False)

# ============= КНОПКА НАЗАД =============

@router.message(F.text == BUTTONS["back"])
async def archive_back(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if current_state in ["archive_menu", "admin_archive_menu"]:
        await back_to_main_menu(message, state, user_id, False)
    else:
        await state.set_state("idle")
        await back_to_main_menu(message, state, user_id, False)