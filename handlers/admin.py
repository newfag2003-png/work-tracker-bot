import os
from datetime import datetime
from aiogram import F, Router
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database import get_all_users, get_balance, get_user_by_name, get_hourly_rate
from keyboards import get_admin_panel_keyboard, get_admin_export_menu_keyboard
from utils.excel_generator import create_admin_monthly_archive_excel, create_admin_yearly_archive_excel

router = Router()


class AdminExportStates(StatesGroup):
    choosing_year = State()
    choosing_month = State()


# ============= ГЛАВНОЕ МЕНЮ ЭКСПОРТА =============

@router.message(F.text == "📎 ЭКСПОРТ ВСЕХ")
async def admin_export_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await state.set_state("admin_export_menu")
    await message.answer(
        "📎 *АДМИНСКИЙ ЭКСПОРТ*\n\n"
        "📌 Здесь можно выгрузить общие отчёты по ВСЕМ сотрудникам.\n\n"
        "Выберите тип отчёта:",
        reply_markup=get_admin_export_menu_keyboard(),
        parse_mode="Markdown"
    )


# ============= ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ =============

@router.message(F.text == "📎 ОБЩИЙ ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")
async def admin_export_current_month(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    now = datetime.now()
    month_name = now.strftime("%B %Y")
    
    await message.answer(f"📊 Формирую общий отчёт за {month_name}...")
    
    try:
        filename = create_admin_monthly_archive_excel(now.year, now.month)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption=f"📊 Общий отчёт за {month_name}"
            )
            os.remove(filename)
        else:
            await message.answer("❌ Нет данных за текущий месяц")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


# ============= МЕСЯЧНЫЕ ОТЧЁТЫ =============

@router.message(F.text == "📁 ОБЩИЕ МЕСЯЧНЫЕ ОТЧЁТЫ")
async def admin_monthly_reports(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    current_year = datetime.now().year
    await state.update_data(admin_selected_year=current_year, admin_export_type="monthly")
    
    from keyboards import get_inline_months_keyboard_for_admin
    await message.answer(
        f"📅 **ВЫБЕРИТЕ МЕСЯЦ {current_year} ГОДА:**",
        reply_markup=get_inline_months_keyboard_for_admin(current_year),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("admin_report_month_"))
async def admin_choose_month_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора месяца для админских отчётов (inline-кнопки)"""
    
    await callback.answer()
    
    # Кнопка "Назад"
    if callback.data == "admin_report_month_back":
        await callback.message.delete()
        await admin_export_menu(callback.message, state)
        return
    
    # Разбираем данные: "admin_report_month_01 ЯНВАРЬ_2026"
    parts = callback.data.split("_")
    month_with_name = parts[3]      # "01 ЯНВАРЬ"
    year = parts[4]                 # "2026"
    month_num = int(month_with_name.split()[0])  # "01" -> 1
    
    # Удаляем сообщение с кнопками
    await callback.message.delete()
    
    # Формируем отчёт
    status_msg = await callback.message.answer(f"📊 Формирую общий отчёт за {month_with_name} {year}...")
    
    try:
        from utils.excel_generator import create_admin_monthly_archive_excel
        filename = create_admin_monthly_archive_excel(int(year), month_num)
        
        await status_msg.delete()
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await callback.message.answer_document(
                document=document,
                caption=f"✅ Общий отчёт за {month_with_name} {year}"
            )
            os.remove(filename)
        else:
            await callback.message.answer(f"❌ Нет данных за {month_with_name} {year}")
        
        await state.clear()
        
    except Exception as e:
        await status_msg.delete()
        await callback.message.answer(f"❌ Ошибка: {e}")

# ============= ГОДОВЫЕ ОТЧЁТЫ =============

@router.message(F.text == "📁 ОБЩИЕ ГОДОВЫЕ ОТЧЁТЫ")
async def admin_yearly_reports(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await state.update_data(admin_export_type="yearly")
    await state.set_state(AdminExportStates.choosing_year)
    
    await message.answer(
        "📅 *ВВЕДИТЕ ГОД (например: 2026):*",
        parse_mode="Markdown"
    )


# ============= ВЫБОР ГОДА =============

@router.message(AdminExportStates.choosing_year)
async def admin_choose_year(message: Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "🔙 НАЗАД":
        await admin_export_menu(message, state)
        return
    
    if not text.isdigit() or len(text) != 4:
        await message.answer("❌ Введите корректный год (например: 2026)")
        return
    
    year = int(text)
    data = await state.get_data()
    export_type = data.get("admin_export_type")
    
    if export_type == "yearly":
        await message.answer(f"📊 Формирую общий отчёт за {year} год...")
        
        filename = create_admin_yearly_archive_excel(year)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption=f"📊 Общий отчёт за {year} год"
            )
            os.remove(filename)
        else:
            await message.answer(f"❌ Нет данных за {year} год")
        
        await state.clear()
    else:
        await state.update_data(admin_selected_year=year)
        await state.set_state(AdminExportStates.choosing_month)
        
        from keyboards import get_months_keyboard_for_report
        await message.answer(
            f"📅 *ВЫБЕРИТЕ МЕСЯЦ {year} ГОДА:*",
            reply_markup=get_months_keyboard_for_report(),
            parse_mode="Markdown"
        )

# ============= ВЫДАТЬ ЗАРПЛАТУ =============

@router.message(F.text == "💰 ВЫДАТЬ ЗАРПЛАТУ")
async def admin_give_salary(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("❌ Нет зарегистрированных сотрудников")
        return
    
    keyboard = []
    for user in users:
        balance = get_balance(user["user_id"])
        keyboard.append([KeyboardButton(text=f"{user['username']} (баланс: {balance} ₴)")])
    
    keyboard.append([KeyboardButton(text="🔙 НАЗАД")])
    
    await message.answer(
        "Выберите сотрудника:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    )
    await state.set_state("admin_choosing_user")


@router.message(F.text == "💹 НАЗНАЧИТЬ СТАВКУ")
async def admin_assign_rate(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("❌ Нет зарегистрированных сотрудников")
        return
    
    keyboard = []
    for user in users:
        rate = get_hourly_rate(user["user_id"])
        keyboard.append([KeyboardButton(text=f"{user['username']} (ставка: {rate} ₴/ч)")])
    
    keyboard.append([KeyboardButton(text="🔙 НАЗАД")])
    
    await message.answer(
        "Выберите сотрудника:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    )
    await state.set_state("admin_choosing_user_for_rate")


# ============= БЭКАП В GOOGLE SHEETS =============

@router.message(F.text == "📤 СДЕЛАТЬ БЭКАП")
async def manual_backup(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await message.answer("📦 Выполняю бэкап в Google Sheets... Это может занять несколько секунд.")
    
    from database import backup_to_google_sheets
    success = backup_to_google_sheets()
    
    if success:
        await message.answer("✅ Бэкап успешно завершён!\n\n📊 Данные скопированы в Google Таблицу.")
    else:
        await message.answer("❌ Ошибка бэкапа. Проверьте настройки Google Sheets API.")


# ============= НАЗАД В ГЛАВНОЕ МЕНЮ =============

@router.message(F.text == "🔙 НАЗАД")
async def admin_back(message: Message, state: FSMContext):
    from bot import show_main_menu
    await show_main_menu(message, state)