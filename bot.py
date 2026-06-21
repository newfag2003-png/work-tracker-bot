import asyncio
import logging
import re
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from utils.scheduler import scheduler
from utils.helpers import now_local

from config import BOT_TOKEN, BUTTONS, DEFAULT_HOURLY_RATE, NIGHT_BONUS, ADMIN_IDS
from database import (
    init_db, user_exists, register_user, get_user, get_user_by_name, get_balance, update_balance,
    save_work_session, get_last_session, get_hourly_rate, get_objects,
    add_object, get_last_used_object, get_sessions_for_period,
    get_total_earned, get_total_expenses, get_total_paid,
    add_expense, get_pending_expenses, approve_expense, reject_expense, get_expense_by_id,
    add_salary_payment, get_pending_payments, confirm_salary_payment, reject_salary_payment,
    set_hourly_rate, hide_object, get_all_users, get_sessions_for_edit,
    delete_work_session, update_work_session, get_salary_payment_by_id,
    get_all_objects_with_status, show_object, delete_object, get_object_usage_stats,
    object_exists, update_work_session_time, update_work_session_object, update_work_session_report,
    get_forecast_stats_30_days, get_all_objects_stats_all_time, get_expenses_stats_last_30_days, get_payments_stats_last_30_days
)
from keyboards import (
    get_main_keyboard, get_admin_button_keyboard, get_admin_panel_keyboard,
    get_objects_keyboard, get_confirm_keyboard, get_night_shift_inline,
    get_expense_confirm_inline, get_salary_confirm_inline, get_edit_sessions_keyboard,
    get_edit_field_keyboard, get_manage_objects_keyboard,
    get_report_menu_keyboard, get_years_keyboard_for_report, get_months_keyboard_for_report,
    get_inline_months_keyboard  # <--- ДОБАВИТЬ ЭТУ СТРОКУ
)
from utils.helpers import is_admin, format_duration, validate_time_format
from utils.excel_generator import (
    create_current_month_excel,
    create_monthly_archive_excel,
    create_yearly_archive_excel,
    create_admin_current_month_excel,
    create_admin_monthly_archive_excel,
    create_admin_yearly_archive_excel
)
from handlers import admin  # <--- ДОБАВИТЬ ЭТУ СТРОКУ

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============= СОСТОЯНИЯ =============

class WorkStates(StatesGroup):
    idle = State()
    working = State()
    choosing_object = State()
    confirming_stop = State()
    asking_night = State()
    asking_daily_report = State()
    waiting_expense_amount = State()
    waiting_expense_desc = State()
    waiting_expense_photo = State()
    waiting_fix_choice = State()
    waiting_fix_field = State()
    waiting_new_time = State()
    waiting_new_report = State()
    waiting_new_object = State()
    waiting_manual_end_time = State()
    waiting_name = State()
    confirming_delete = State()
    admin_menu = State()
    admin_choosing_user = State()
    admin_entering_salary = State()
    admin_choosing_user_for_rate = State()
    admin_entering_rate = State()
    admin_adding_object = State()
    admin_hiding_object = State()
    admin_choosing_report_user = State()
    admin_managing_objects = State()
    admin_confirming_delete_object = State()
    admin_reports_menu = State()
    admin_report_choosing_year = State()
    admin_report_choosing_month = State()
    employee_export_menu = State()
    employee_export_choosing_year = State()
    employee_export_choosing_month = State()
    
# Хранилище активных сессий
active_work_sessions = {}

# ============= СТАРТ И РЕГИСТРАЦИЯ =============

@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    print(f"🔍 Проверка пользователя {user_id}...")
    
    exists = user_exists(user_id)
    
    if not exists:
        await state.set_state(WorkStates.waiting_name)
        await message.answer("👋 Здравствуйте! Как вас зовут?")
        return
    
    user = get_user(user_id)
    is_working = user_id in active_work_sessions
    
    keyboard = get_main_keyboard(user_id, is_working)
    
    if user_id in ADMIN_IDS:
        admin_keyboard = get_admin_button_keyboard()
        keyboard.keyboard.extend(admin_keyboard.keyboard)
    
    await message.answer(
        f"С возвращением, {user['username']}! 👋\n\n📌 Начните работу или выберите действие в меню.",
        reply_markup=keyboard
    )
    await state.set_state(WorkStates.idle)

@dp.message(WorkStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    user_id = message.from_user.id
    
    if not name:
        await message.answer("❌ Пожалуйста, введите ваше имя")
        return
    
    register_user(user_id, name)
    await message.answer(f"✅ Приятно познакомиться, {name}!")
    
    keyboard = get_main_keyboard(user_id, False)
    
    if user_id in ADMIN_IDS:
        admin_keyboard = get_admin_button_keyboard()
        keyboard.keyboard.extend(admin_keyboard.keyboard)
    
    await message.answer(
        "📋 *Главное меню*\n\n👇 Используйте кнопки ниже:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(WorkStates.idle)

# ============= НАЧАТЬ РАБОТУ =============

@dp.message(F.text == BUTTONS["start_work"])
async def start_work(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin_user = user_id in ADMIN_IDS
    
    # Проверка: есть ли активная работа в памяти
    if user_id in active_work_sessions:
        await message.answer("⚠️ Вы уже работаете! Сначала завершите смену.")
        await show_main_menu(message, state, working=True)
        return
    
    # Дополнительная проверка: есть ли незавершённая смена в базе
    from database import execute_query
    active_session = execute_query(
        "SELECT * FROM work_sessions WHERE user_id = ? AND (daily_report IS NULL OR daily_report = '') ORDER BY start_time DESC LIMIT 1",
        (user_id,), 
        fetch_one=True
    )
    
    if active_session:
        # Восстанавливаем сессию в память
        start_time = active_session["start_time"]
        # Если это строка — преобразуем, если уже datetime — оставляем
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        active_work_sessions[user_id] = {
            "object_name": active_session["object_name"],
            "start_time": start_time
        }
        await message.answer("⚠️ Ваша предыдущая смена восстановлена! Нажмите ⛔ ЗАКОНЧИТЬ РАБОТУ")
        await show_main_menu(message, state, working=True)
        return
    
    last_object = get_last_used_object(user_id)
    available_objects = get_objects()
    
    if last_object and last_object in available_objects:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"🔄 {last_object} (последний)")],
                [KeyboardButton(text="📋 ВЫБРАТЬ ИЗ СПИСКА")],
                [KeyboardButton(text=BUTTONS["cancel"])]
            ],
            resize_keyboard=True
        )
        await message.answer(f"Начать работу на {last_object}?", reply_markup=keyboard)
        await state.set_state(WorkStates.choosing_object)
        await state.update_data(last_object=last_object)
    else:
        if not available_objects:
            await message.answer("❌ Нет доступных объектов для работы. Обратитесь к администратору.")
            return
        
        await message.answer(
            "Выберите объект:", 
            reply_markup=get_objects_keyboard(user_id, is_admin_user)
        )
        await state.set_state(WorkStates.choosing_object)


@dp.message(WorkStates.choosing_object, F.text.startswith("🔄"))
async def select_last_object(message: Message, state: FSMContext):
    data = await state.get_data()
    object_name = data.get("last_object")
    
    available_objects = get_objects()
    if object_name not in available_objects:
        await message.answer("❌ Этот объект больше недоступен. Выберите другой.")
        user_id = message.from_user.id
        is_admin_user = user_id in ADMIN_IDS
        await message.answer(
            "Выберите объект:",
            reply_markup=get_objects_keyboard(user_id, is_admin_user)
        )
        return
    
    await start_work_with_object(message, state, object_name)


@dp.message(WorkStates.choosing_object, F.text.startswith("📦"))
async def select_object(message: Message, state: FSMContext):
    object_name = message.text.replace("📦 ", "")
    
    available_objects = get_objects()
    if object_name not in available_objects:
        await message.answer("❌ Этот объект недоступен. Выберите другой.")
        return
    
    await start_work_with_object(message, state, object_name)


@dp.message(WorkStates.choosing_object, F.text == "📋 ВЫБРАТЬ ИЗ СПИСКА")
async def select_from_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin_user = user_id in ADMIN_IDS
    
    available_objects = get_objects()
    
    if not available_objects:
        await message.answer("❌ Нет доступных объектов для работы. Обратитесь к администратору.")
        return
    
    await message.answer(
        "Выберите объект:",
        reply_markup=get_objects_keyboard(user_id, is_admin_user)
    )
    await state.set_state(WorkStates.choosing_object)


@dp.message(WorkStates.choosing_object, F.text == BUTTONS["cancel"])
async def cancel_start(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)


async def show_objects_list(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin_user = user_id in ADMIN_IDS
    objects = get_objects()
    
    if not objects:
        await message.answer("❌ Нет доступных объектов для работы. Обратитесь к администратору.")
        return
    
    keyboard = []
    for obj in objects:
        keyboard.append([KeyboardButton(text=f"📦 {obj}")])
    
    if is_admin_user:
        keyboard.append([KeyboardButton(text="➕ ДРУГОЙ ОБЪЕКТ")])
    
    keyboard.append([KeyboardButton(text=BUTTONS["cancel"])])
    
    await message.answer(
        "Выберите объект:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    )
    await state.set_state(WorkStates.choosing_object)


async def start_work_with_object(message: Message, state: FSMContext, object_name: str):
    user_id = message.from_user.id
    start_time = now_local()
    
    active_work_sessions[user_id] = {
        "object_name": object_name,
        "start_time": start_time
    }
    
    await state.update_data(
        object_name=object_name,
        start_time=start_time.isoformat()
    )
    await state.set_state(WorkStates.working)
    
    await show_main_menu(message, state, working=True)
    
    await message.answer(
        f"✅ Работа начата в {start_time.strftime('%H:%M')} на {object_name}\n\n"
        f"📌 Когда закончите, нажмите ⛔ ЗАКОНЧИТЬ РАБОТУ"
    )
# ============= ЗАКОНЧИТЬ РАБОТУ =============

@dp.message(F.text == BUTTONS["stop_work"])
async def stop_work(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in active_work_sessions:
        await message.answer("❌ Нет активной работы")
        return
    
    await state.set_state(WorkStates.confirming_stop)
    await message.answer("⚠️ Завершить работу?", reply_markup=get_confirm_keyboard())

@dp.message(WorkStates.confirming_stop, F.text == "✅ ДА")
async def confirm_stop(message: Message, state: FSMContext):
    user_id = message.from_user.id
    session = active_work_sessions.get(user_id)
    
    if not session:
        await message.answer("❌ Нет активной работы")
        await state.set_state(WorkStates.idle)
        return
    
    start_time = session["start_time"]
    object_name = session["object_name"]
    end_time = now_local()
    
    if end_time < start_time:
        await state.update_data(
            temp_start=start_time.isoformat(),
            temp_end=end_time.isoformat(),
            temp_object=object_name
        )
        await state.set_state(WorkStates.asking_night)
        await message.answer(
            "⚠️ Вы закончили работу раньше, чем начали.\n\nЭто ночная смена?",
            reply_markup=get_night_shift_inline()
        )
        return
    
    await calculate_and_save_work(message, state, start_time, end_time, object_name, False)

@dp.callback_query(WorkStates.asking_night, F.data == "night_yes")
async def night_shift_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_time = datetime.fromisoformat(data["temp_start"])
    end_time = datetime.fromisoformat(data["temp_end"])
    object_name = data["temp_object"]
    
    end_time = end_time + timedelta(days=1)
    
    await callback.message.delete()
    await calculate_and_save_work(callback.message, state, start_time, end_time, object_name, True)
    await callback.answer()

@dp.callback_query(WorkStates.asking_night, F.data == "night_no")
async def night_shift_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Введите правильное время окончания в формате ЧЧ:ММ (например: 18:30)")
    await state.set_state(WorkStates.waiting_manual_end_time)
    await callback.answer()

@dp.message(WorkStates.waiting_manual_end_time)
async def manual_end_time(message: Message, state: FSMContext):
    if not validate_time_format(message.text.strip()):
        await message.answer("❌ Неверный формат! Введите время в формате ЧЧ:ММ")
        return
    
    try:
        time_str = message.text.strip()
        hour, minute = map(int, time_str.split(':'))
        
        data = await state.get_data()
        start_time = datetime.fromisoformat(data["temp_start"])
        object_name = data["temp_object"]
        
        end_time = start_time.replace(hour=hour, minute=minute)
        
        if end_time < start_time:
            end_time = end_time + timedelta(days=1)
        
        await calculate_and_save_work(message, state, start_time, end_time, object_name, False)
        
    except Exception as e:
        await message.answer("❌ Ошибка! Попробуйте ещё раз.")

async def calculate_and_save_work(message: Message, state: FSMContext,
                                   start_time, end_time, object_name, is_night: bool):
    user_id = message.from_user.id
    
    duration = end_time - start_time
    hours = duration.total_seconds() / 3600
    
    hourly_rate = get_hourly_rate(user_id)
    earnings = int(hours * hourly_rate)
    
    if is_night:
        earnings = int(earnings * NIGHT_BONUS)
    
    save_work_session(user_id, object_name, start_time, end_time,
                      int(duration.total_seconds()), is_night, earnings, "")
    
    update_balance(user_id, earnings_change=earnings)
    
    if user_id in active_work_sessions:
        del active_work_sessions[user_id]
    
    await state.set_state(WorkStates.asking_daily_report)
    await state.update_data(
        last_earnings=earnings,
        last_duration=duration,
        last_is_night=is_night
    )
    
    night_text = " 🌙 (ночная смена, +20%)" if is_night else ""
    
    await message.answer(
        f"✅ Работа завершена!{night_text}\n"
        f"⏱ Длительность: {format_duration(duration)}\n"
        f"💰 Заработано: {earnings:,} ₴\n\n"
        f"📝 Что вы сегодня делали? (кратко)"
    )

@dp.message(WorkStates.asking_daily_report)
async def save_daily_report(message: Message, state: FSMContext):
    report = message.text.strip()
    
    last_session = get_last_session(message.from_user.id)
    
    if last_session:
        update_work_session(
            last_session["id"],
            last_session["start_time"],
            last_session["end_time"],
            last_session["duration"],
            last_session["is_night"],
            last_session["earnings"],
            last_session["object_name"],
            report
        )
    
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)
    
    balance = get_balance(message.from_user.id)
    
    await message.answer(f"✅ Отчёт сохранён!\n\n💳 Текущий баланс: {balance:,} ₴")

@dp.message(WorkStates.confirming_stop, F.text == "❌ НЕТ")
async def cancel_stop(message: Message, state: FSMContext):
    await state.set_state(WorkStates.working)
    await show_main_menu(message, state, True)
    await message.answer("❌ Завершение работы отменено")

# ============= МОЙ БАЛАНС =============

@dp.message(F.text == BUTTONS["my_balance"])
async def show_balance(message: Message):
    user_id = message.from_user.id
    
    balance = get_balance(user_id)
    total_earned = get_total_earned(user_id)
    total_expenses = get_total_expenses(user_id)
    total_paid = get_total_paid(user_id)
    
    today = now_local().date().date()
    sessions_today = get_sessions_for_period(user_id, 1)
    sessions_week = get_sessions_for_period(user_id, 7)
    
    today_earnings = sum(s["earnings"] for s in sessions_today if s["start_time"][:10] == str(today))
    week_earnings = sum(s["earnings"] for s in sessions_week)
    
    await message.answer(
        f"💰 *{balance:,} ₴*\n\n"
        f"📈 Сегодня: +{today_earnings:,} ₴\n"
        f"📊 За неделю: +{week_earnings:,} ₴\n\n"
        f"📅 *За всё время:*\n"
        f"• Заработано: {total_earned:,} ₴\n"
        f"• Компенсаций: {total_expenses:,} ₴\n"
        f"• Выплачено: {total_paid:,} ₴",
        parse_mode="Markdown"
    )

# ============= СТАТИСТИКА =============

@dp.message(F.text == BUTTONS["statistics"])
async def show_statistics(message: Message):
    user_id = message.from_user.id
    
    balance = get_balance(user_id)
    total_earned = get_total_earned(user_id)
    total_expenses = get_total_expenses(user_id)
    total_paid = get_total_paid(user_id)
    
    sessions = get_sessions_for_period(user_id, 30)
    
    total_hours = sum(s["duration"] for s in sessions) / 3600
    total_earned_period = sum(s["earnings"] for s in sessions)
    night_sessions = [s for s in sessions if s["is_night"]]
    
    objects_count = {}
    for s in sessions:
        obj = s["object_name"]
        objects_count[obj] = objects_count.get(obj, 0) + 1
    
    top_object = max(objects_count.items(), key=lambda x: x[1])[0] if objects_count else "—"
    
    history = ""
    for s in sessions[:10]:
        date = s["start_time"][:10]
        obj = s["object_name"]
        hours = s["duration"] / 3600
        earnings = s["earnings"]
        night_mark = " 🌙" if s["is_night"] else ""
        report = f"\n   📝 {s['daily_report'][:50]}" if s["daily_report"] else ""
        history += f"• {date} ({obj}) {hours:.1f}ч - {earnings:,}₴{night_mark}{report}\n"
    
    await message.answer(
        f"📊 *ОТЧЁТ ЗА ПОСЛЕДНИЕ 30 ДНЕЙ*\n\n"
        f"💰 *ТЕКУЩИЙ БАЛАНС:* {balance:,} ₴\n\n"
        f"📈 *ЗА ПЕРИОД:*\n"
        f"• Отработано: {len(sessions)} дней\n"
        f"• Всего часов: {total_hours:.1f} ч\n"
        f"• Заработано: {total_earned_period:,} ₴\n"
        f"• Ночных смен: {len(night_sessions)}\n\n"
        f"🏆 Чаще всего: {top_object}\n\n"
        f"📅 *ИСТОРИЯ:*\n{history}\n\n"
        f"📊 *ЗА ВСЁ ВРЕМЯ:*\n"
        f"• Всего заработано: {total_earned:,} ₴\n"
        f"• Компенсаций: {total_expenses:,} ₴\n"
        f"• Выплачено: {total_paid:,} ₴",
        parse_mode="Markdown"
    )

# ============= РАСХОДНИКИ =============

@dp.message(F.text == BUTTONS["expenses"])
async def add_expense_start(message: Message, state: FSMContext):
    await state.set_state(WorkStates.waiting_expense_amount)
    await message.answer("💰 Введите сумму расхода в гривнах:")

@dp.message(WorkStates.waiting_expense_amount)
async def expense_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
        await state.update_data(expense_amount=amount)
        await state.set_state(WorkStates.waiting_expense_desc)
        await message.answer("📝 Что купили?")
    except ValueError:
        await message.answer("❌ Введите положительное число!")

@dp.message(WorkStates.waiting_expense_desc)
async def expense_desc(message: Message, state: FSMContext):
    description = message.text.strip()
    await state.update_data(expense_desc=description)
    await state.set_state(WorkStates.waiting_expense_photo)
    await message.answer("🧾 Отправьте фото чека (или нажмите /skip)")

@dp.message(WorkStates.waiting_expense_photo, F.photo)
async def expense_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await save_expense(message, state, photo_file_id)

@dp.message(WorkStates.waiting_expense_photo, F.text == "/skip")
async def expense_skip_photo(message: Message, state: FSMContext):
    await save_expense(message, state, None)

async def save_expense(message: Message, state: FSMContext, photo_file_id):
    data = await state.get_data()
    user_id = message.from_user.id
    amount = data["expense_amount"]
    description = data["expense_desc"]
    
    expense_id = add_expense(user_id, amount, description, photo_file_id)
    
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)
    
    await message.answer(
        f"✅ Расход отправлен на подтверждение администратору!\n\n"
        f"📋 Сумма: {amount:,} ₴\n📝 {description}\n\n⏳ Статус: ожидает подтверждения"
    )
    
    user = get_user(user_id)
    for admin_id in ADMIN_IDS:
        try:
            text = f"📋 *НОВЫЙ РАСХОД НА ПОДТВЕРЖДЕНИЕ*\n\n" \
                   f"👤 Сотрудник: {user['username']}\n" \
                   f"💰 Сумма: {amount:,} ₴\n" \
                   f"📝 Описание: {description}\n" \
                   f"🆔 ID: {expense_id}"
            
            if photo_file_id:
                await bot.send_photo(
                    admin_id,
                    photo=photo_file_id,
                    caption=text,
                    reply_markup=get_expense_confirm_inline(expense_id),
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    admin_id,
                    text,
                    reply_markup=get_expense_confirm_inline(expense_id),
                    parse_mode="Markdown"
                )
            print(f"✅ Уведомление отправлено админу {admin_id}")
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

# ============= ПОДТВЕРЖДЕНИЕ РАСХОДОВ (АДМИН) =============

@dp.callback_query(F.data.startswith("expense_approve_"))
async def approve_expense_callback(callback: CallbackQuery):
    print(f"🔔 Получен callback: {callback.data}")
    
    try:
        expense_id = int(callback.data.split("_")[2])
        admin_id = callback.from_user.id
        
        if admin_id not in ADMIN_IDS:
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        
        expense = approve_expense(expense_id, admin_id)
        
        if expense:
            await callback.message.answer(
                f"✅ *РАСХОД ПОДТВЕРЖДЁН!*\n\n"
                f"💰 Сумма: {expense['amount']:,} ₴\n"
                f"📝 Описание: {expense['description']}\n"
                f"🆔 ID: {expense_id}",
                parse_mode="Markdown"
            )
            await callback.message.delete()
            await callback.answer("✅ Расход подтверждён", show_alert=True)
            
            user = get_user(expense["user_id"])
            if user:
                await bot.send_message(
                    expense["user_id"],
                    f"✅ *РАСХОД ПОДТВЕРЖДЁН!*\n\n"
                    f"💰 Сумма: {expense['amount']:,} ₴\n"
                    f"📝 Описание: {expense['description']}\n\n"
                    f"💳 Компенсация добавлена к вашему балансу.",
                    parse_mode="Markdown"
                )
        else:
            await callback.answer("❌ Расход уже обработан", show_alert=True)
            
    except Exception as e:
        print(f"Ошибка approve_expense_callback: {e}")
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)

@dp.callback_query(F.data.startswith("expense_reject_"))
async def reject_expense_callback(callback: CallbackQuery):
    print(f"🔔 Получен callback: {callback.data}")
    
    try:
        expense_id = int(callback.data.split("_")[2])
        admin_id = callback.from_user.id
        
        if admin_id not in ADMIN_IDS:
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        
        expense = get_expense_by_id(expense_id)
        reject_expense(expense_id, admin_id, "Отклонено администратором")
        
        await callback.message.answer(
            f"❌ *РАСХОД ОТКЛОНЁН!*\n\n"
            f"💰 Сумма: {expense['amount']:,} ₴\n"
            f"📝 Описание: {expense['description']}\n"
            f"🆔 ID: {expense_id}",
            parse_mode="Markdown"
        )
        await callback.message.delete()
        await callback.answer("❌ Расход отклонён", show_alert=True)
        
        if expense:
            user = get_user(expense["user_id"])
            if user:
                await bot.send_message(
                    expense["user_id"],
                    f"❌ *РАСХОД ОТКЛОНЁН!*\n\n"
                    f"💰 Сумма: {expense['amount']:,} ₴\n"
                    f"📝 Описание: {expense['description']}\n\n"
                    f"Причина: Отклонено администратором.",
                    parse_mode="Markdown"
                )
        
    except Exception as e:
        print(f"Ошибка reject_expense_callback: {e}")
        await callback.answer("❌ Ошибка при отклонении", show_alert=True)

# ============= ПОДТВЕРЖДЕНИЕ ВЫПЛАТЫ (СОТРУДНИК) =============

@dp.callback_query(F.data.startswith("salary_confirm_"))
async def confirm_salary_callback(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    success = confirm_salary_payment(payment_id)
    
    if success:
        payment = get_salary_payment_by_id(payment_id)
        
        await callback.message.answer(
            callback.message.text + "\n\n✅ ВЫПЛАТА ПОДТВЕРЖДЕНА"
        )
        await callback.message.delete()
        await callback.answer("✅ Выплата подтверждена", show_alert=True)
        
        user = get_user(user_id)
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"✅ *ПОДТВЕРЖДЕНИЕ ВЫПЛАТЫ*\n\n"
                f"👤 Сотрудник: {user['username']}\n"
                f"💰 Сумма: {payment['amount']:,} ₴\n"
                f"📅 Дата: {now_local().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"✅ Выплата подтверждена сотрудником",
                parse_mode="Markdown"
            )
    else:
        await callback.answer("❌ Выплата уже обработана", show_alert=True)

@dp.callback_query(F.data.startswith("salary_reject_"))
async def reject_salary_callback(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    payment = get_salary_payment_by_id(payment_id)
    reject_salary_payment(payment_id)
    
    await callback.message.answer(
        callback.message.text + "\n\n❌ ВЫПЛАТА ОТКЛОНЕНА"
    )
    await callback.message.delete()
    await callback.answer("❌ Выплата отклонена", show_alert=True)
    
    user = get_user(user_id)
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"❌ *ОТКЛОНЕНИЕ ВЫПЛАТЫ*\n\n"
            f"👤 Сотрудник: {user['username']}\n"
            f"💰 Сумма: {payment['amount']:,} ₴\n"
            f"📅 Дата: {now_local().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"❌ Сотрудник отклонил выплату",
            parse_mode="Markdown"
        )

# ============= АДМИН-ПАНЕЛЬ =============

@dp.message(F.text == "👑 АДМИН-ПАНЕЛЬ")
async def admin_panel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к админ-панели")
        return
    
    await state.set_state(WorkStates.admin_menu)
    await message.answer(
        "👑 *АДМИН-ПАНЕЛЬ*\n\nВыберите действие:",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )

# ----- ВЫДАТЬ ЗАРПЛАТУ -----

@dp.message(F.text == "💰 ВЫДАТЬ ЗАРПЛАТУ")
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
    await state.set_state(WorkStates.admin_choosing_user)

@dp.message(WorkStates.admin_choosing_user, F.text != "🔙 НАЗАД")
async def admin_choose_user_for_salary(message: Message, state: FSMContext):
    username = message.text.split(" (")[0]
    user = get_user_by_name(username)
    
    if not user:
        await message.answer("❌ Сотрудник не найден")
        return
    
    await state.update_data(salary_user_id=user["user_id"], salary_username=username)
    await state.set_state(WorkStates.admin_entering_salary)
    await message.answer(
        f"👤 Сотрудник: {username}\n"
        f"💰 Текущий баланс: {get_balance(user['user_id']):,} ₴\n\n"
        f"Введите сумму выплаты в гривнах:"
    )

@dp.message(WorkStates.admin_entering_salary)
async def admin_enter_salary_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
        
        data = await state.get_data()
        user_id = data["salary_user_id"]
        username = data["salary_username"]
        
        payment_id = add_salary_payment(user_id, amount)
        
        await state.set_state(WorkStates.admin_menu)
        await message.answer(
            f"✅ Запрос на выплату {amount:,} ₴ отправлен {username}",
            reply_markup=get_admin_panel_keyboard()
        )
        
        await bot.send_message(
            user_id,
            f"💰 *ЗАПРОС НА ВЫДАЧУ ЗАРПЛАТЫ*\n\n"
            f"Сумма: {amount:,} ₴\n"
            f"Текущий баланс: {get_balance(user_id):,} ₴\n\n"
            f"После выплаты останется: {get_balance(user_id) - amount:,} ₴",
            reply_markup=get_salary_confirm_inline(payment_id),
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму!")

# ----- НАЗНАЧИТЬ СТАВКУ -----

@dp.message(F.text == "💹 НАЗНАЧИТЬ СТАВКУ")
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
    await state.set_state(WorkStates.admin_choosing_user_for_rate)

@dp.message(WorkStates.admin_choosing_user_for_rate, F.text != "🔙 НАЗАД")
async def admin_choose_user_for_rate(message: Message, state: FSMContext):
    username = message.text.split(" (")[0]
    user = get_user_by_name(username)
    
    if not user:
        await message.answer("❌ Сотрудник не найден")
        return
    
    await state.update_data(rate_user_id=user["user_id"], rate_username=username)
    await state.set_state(WorkStates.admin_entering_rate)
    await message.answer(
        f"👤 Сотрудник: {username}\n"
        f"💰 Текущая ставка: {get_hourly_rate(user['user_id'])} ₴/ч\n\n"
        f"Введите новую ставку в гривнах/час:"
    )

@dp.message(WorkStates.admin_entering_rate)
async def admin_enter_rate(message: Message, state: FSMContext):
    try:
        new_rate = int(message.text.strip())
        if new_rate <= 0:
            raise ValueError
        
        data = await state.get_data()
        user_id = data["rate_user_id"]
        username = data["rate_username"]
        old_rate = get_hourly_rate(user_id)
        
        set_hourly_rate(user_id, new_rate, message.from_user.id)
        
        await state.set_state(WorkStates.admin_menu)
        await message.answer(
            f"✅ Ставка {username} изменена: {old_rate} ₴/ч → {new_rate} ₴/ч",
            reply_markup=get_admin_panel_keyboard()
        )
        
        await bot.send_message(
            user_id,
            f"📢 *ИЗМЕНЕНИЕ СТАВКИ*\n\n"
            f"Ваша новая ставка: {new_rate} ₴/ч\n"
            f"Было: {old_rate} ₴/ч\n\n"
            f"Изменение вступило в силу с текущего момента.",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму!")

# ----- ЗАРПЛАТНАЯ ВЕДОМОСТЬ -----

@dp.message(F.text == "📋 ЗАРПЛАТНАЯ ВЕДОМОСТЬ")
async def admin_salary_report(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("❌ Нет зарегистрированных сотрудников")
        return
    
    report = "📊 *ЗАРПЛАТНАЯ ВЕДОМОСТЬ*\n\n"
    total_balance = 0
     
    for user in users:
        balance = get_balance(user["user_id"])
        total_earned = get_total_earned(user["user_id"])
        total_expenses = get_total_expenses(user["user_id"])
        total_paid = get_total_paid(user["user_id"])
        hourly_rate = get_hourly_rate(user["user_id"])
        
        total_balance += balance
        
        emoji = "🟢" if balance >= 0 else "🔴"
        report += f"{emoji} *{user['username']}* ({hourly_rate} ₴/ч)\n"
        report += f"   Заработано: {total_earned:,} ₴\n"
        report += f"   Компенсации: {total_expenses:,} ₴\n"
        report += f"   Выплачено: {total_paid:,} ₴\n"
        report += f"   ─────────────────\n"
        report += f"   💰 БАЛАНС: {balance:,} ₴\n\n"
    
    report += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"💰 ОБЩИЙ БАЛАНС: {total_balance:,} ₴"
    
    await message.answer(report, parse_mode="Markdown")

# ----- ДОБАВИТЬ ОБЪЕКТ -----

@dp.message(F.text == "➕ ДОБАВИТЬ ОБЪЕКТ")
async def admin_add_object(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await state.set_state(WorkStates.admin_adding_object)
    await message.answer("🏭 Введите название нового объекта:")

@dp.message(WorkStates.admin_adding_object)
async def admin_process_add_object(message: Message, state: FSMContext):
    object_name = message.text.strip()
    add_object(object_name)
    
    await state.set_state(WorkStates.admin_menu)
    await message.answer(
        f"✅ Объект \"{object_name}\" добавлен!",
        reply_markup=get_admin_panel_keyboard()
    )

# ----- УПРАВЛЕНИЕ ОБЪЕКТАМИ -----

@dp.message(F.text == "📦 УПРАВЛЕНИЕ ОБЪЕКТАМИ")
async def admin_manage_objects(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    objects = get_all_objects_with_status()
    
    if not objects:
        await message.answer("❌ Нет объектов")
        return
    
    text = "📦 *УПРАВЛЕНИЕ ОБЪЕКТАМИ*\n\n"
    for obj in objects:
        status = "🔒 СКРЫТ" if obj["is_hidden"] else "🔓 ВИДИМ"
        text += f"• {obj['name']} — {status}\n"
    
    text += "\n👇 Выберите действие:"
    await message.answer(text, parse_mode="Markdown")
    
    await state.set_state(WorkStates.admin_managing_objects)
    await state.update_data(objects=objects)
    
    await message.answer(
        "Выберите объект и действие:",
        reply_markup=get_manage_objects_keyboard(objects)
    )

@dp.message(WorkStates.admin_managing_objects, F.text.startswith("🚫 СКРЫТЬ"))
async def admin_hide_object_from_manage(message: Message, state: FSMContext):
    object_name = message.text.replace("🚫 СКРЫТЬ ", "")
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    hide_object(object_name)
    await message.answer(f"✅ Объект \"{object_name}\" скрыт из списка")
    await admin_manage_objects(message, state)

@dp.message(WorkStates.admin_managing_objects, F.text.startswith("👁 ПОКАЗАТЬ"))
async def admin_show_object_from_manage(message: Message, state: FSMContext):
    object_name = message.text.replace("👁 ПОКАЗАТЬ ", "")
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    objects = get_all_objects_with_status()
    for obj in objects:
        if obj["name"] == object_name:
            show_object(obj["id"])
            break
    
    await message.answer(f"✅ Объект \"{object_name}\" снова виден сотрудникам")
    await admin_manage_objects(message, state)

@dp.message(WorkStates.admin_managing_objects, F.text.startswith("🗑 УДАЛИТЬ"))
async def admin_delete_object_from_manage(message: Message, state: FSMContext):
    object_name = message.text.replace("🗑 УДАЛИТЬ ", "")
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    objects = get_all_objects_with_status()
    obj_id = None
    for obj in objects:
        if obj["name"] == object_name:
            obj_id = obj["id"]
            break
    
    stats = get_object_usage_stats(obj_id) if obj_id else None
    
    if stats and stats["sessions_count"] > 0:
        hours = stats["total_seconds"] / 3600
        await message.answer(
            f"⚠️ *ВНИМАНИЕ!*\n\n"
            f"Объект \"{object_name}\" использовался в работе:\n"
            f"• Количество смен: {stats['sessions_count']}\n"
            f"• Всего часов: {hours:.1f} ч\n"
            f"• Заработано: {stats['total_earned']:,} ₴\n\n"
            f"Удаление объекта удалит все эти записи!\n\n"
            f"Вы уверены?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="✅ ДА, УДАЛИТЬ"), KeyboardButton(text="❌ НЕТ")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        await state.set_state(WorkStates.admin_confirming_delete_object)
        await state.update_data(delete_object_id=obj_id, delete_object_name=object_name)
    else:
        delete_object(obj_id)
        await message.answer(f"✅ Объект \"{object_name}\" удалён")
        await admin_manage_objects(message, state)

@dp.message(WorkStates.admin_confirming_delete_object, F.text == "✅ ДА, УДАЛИТЬ")
async def admin_confirm_delete_object(message: Message, state: FSMContext):
    data = await state.get_data()
    obj_id = data.get("delete_object_id")
    obj_name = data.get("delete_object_name")
    
    if obj_id:
        delete_object(obj_id)
        await message.answer(f"✅ Объект \"{obj_name}\" удалён")
    
    await state.set_state(WorkStates.admin_menu)
    await admin_manage_objects(message, state)

@dp.message(WorkStates.admin_confirming_delete_object, F.text == "❌ НЕТ")
async def admin_cancel_delete_object(message: Message, state: FSMContext):
    await message.answer("❌ Удаление отменено")
    await state.set_state(WorkStates.admin_menu)
    await admin_manage_objects(message, state)

@dp.message(F.text == "🔙 НАЗАД")
async def admin_back(message: Message, state: FSMContext):
    await show_main_menu(message, state)

# ----- РАСХОДЫ НА ПРОВЕРКЕ -----

@dp.message(F.text == "⏳ РАСХОДЫ НА ПРОВЕРКЕ")
async def admin_pending_expenses(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    expenses = get_pending_expenses()
    
    if not expenses:
        await message.answer("✅ Нет расходов на проверке")
        return
    
    for expense in expenses:
        await message.answer(
            f"📋 *РАСХОД #{expense['id']}*\n\n"
            f"👤 Сотрудник: {expense['username']}\n"
            f"💰 Сумма: {expense['amount']:,} ₴\n"
            f"📝 Описание: {expense['description']}\n"
            f"🧾 Фото: {'есть' if expense['photo_file_id'] else 'нет'}",
            reply_markup=get_expense_confirm_inline(expense['id']),
            parse_mode="Markdown"
        )

# ----- КТО РАБОТАЕТ СЕЙЧАС -----

@dp.message(F.text == "🟢 КТО РАБОТАЕТ")
async def admin_who_is_working(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    if not active_work_sessions:
        await message.answer("🟢 Сейчас никто не работает")
        return
    
    text = "🟢 *СЕЙЧАС РАБОТАЮТ:*\n\n"
    for uid, session in active_work_sessions.items():
        user = get_user(uid)
        if user:
            start_time = session["start_time"]
            duration = now_local() - start_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            text += f"• *{user['username']}*\n"
            text += f"  📍 {session['object_name']}\n"
            text += f"  ⏱ с {start_time.strftime('%H:%M')} ({hours}ч {minutes}мин)\n\n"
    
    await message.answer(text, parse_mode="Markdown")

# ----- ОТЧЁТ ПО СОТРУДНИКАМ -----

@dp.message(F.text == "📊 ОТЧЁТ ПО СОТРУДНИКАМ")
async def admin_report_employees(message: Message, state: FSMContext):
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
        keyboard.append([KeyboardButton(text=f"{user['username']}")])
    keyboard.append([KeyboardButton(text="🔙 НАЗАД")])
    
    await message.answer(
        "Выберите сотрудника:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    )
    await state.set_state(WorkStates.admin_choosing_report_user)

@dp.message(WorkStates.admin_choosing_report_user, F.text != "🔙 НАЗАД")
async def admin_show_user_report(message: Message, state: FSMContext):
    username = message.text.strip()
    user = get_user_by_name(username)
    
    if not user:
        await message.answer("❌ Сотрудник не найден")
        return
    
    balance = get_balance(user["user_id"])
    total_earned = get_total_earned(user["user_id"])
    total_expenses = get_total_expenses(user["user_id"])
    total_paid = get_total_paid(user["user_id"])
    hourly_rate = get_hourly_rate(user["user_id"])
    
    sessions = get_sessions_for_period(user["user_id"], 30)
    total_hours = sum(s["duration"] for s in sessions) / 3600 if sessions else 0
    total_earned_period = sum(s["earnings"] for s in sessions) if sessions else 0
    
    await state.set_state(WorkStates.admin_menu)
    
    await message.answer(
        f"📊 *ОТЧЁТ СОТРУДНИКА: {username}*\n\n"
        f"💰 Текущий баланс: {balance:,} ₴\n"
        f"⭐ Ставка: {hourly_rate} ₴/ч\n\n"
        f"📈 *За всё время:*\n"
        f"• Заработано: {total_earned:,} ₴\n"
        f"• Компенсаций: {total_expenses:,} ₴\n"
        f"• Выплачено: {total_paid:,} ₴\n\n"
        f"📅 *За последние 30 дней:*\n"
        f"• Часов: {total_hours:.1f} ч\n"
        f"• Заработано: {total_earned_period:,} ₴",
        parse_mode="Markdown",
        reply_markup=get_admin_panel_keyboard()
    )

# ============= ИСПРАВИТЬ ЗАПИСЬ =============

@dp.message(F.text == BUTTONS["fix"])
async def fix_record(message: Message, state: FSMContext):
    print(f"🔧 Кнопка ИСПРАВИТЬ нажата!")
    user_id = message.from_user.id
    
    sessions = get_sessions_for_edit(user_id)
    print(f"📋 Найдено сессий: {len(sessions) if sessions else 0}")
    
    if not sessions:
        await message.answer("❌ Нет записей за последние 2 дня для редактирования")
        return
    
    await state.update_data(sessions=sessions)
    await state.set_state(WorkStates.waiting_fix_choice)
    
    keyboard = []
    for i, session in enumerate(sessions, 1):
        date = session["start_time"][:10]
        obj = session["object_name"]
        hours = session["duration"] / 3600
        earnings = session["earnings"]
        keyboard.append([KeyboardButton(text=f"{i}️⃣ {date} | {obj} | {hours:.1f}ч | {earnings}₴")])
    keyboard.append([KeyboardButton(text=BUTTONS["cancel"])])
    
    await message.answer(
        "📋 *ВЫБЕРИТЕ ЗАПИСЬ ДЛЯ РЕДАКТИРОВАНИЯ:*\n\n"
        "Нажмите на кнопку с нужной записью:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

@dp.message(WorkStates.waiting_fix_choice, F.text == BUTTONS["cancel"])
async def fix_choose_cancel(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

@dp.message(WorkStates.waiting_fix_choice)
async def fix_choose_session(message: Message, state: FSMContext):
    print(f"🔧 Выбрана запись: {message.text}")
    
    data = await state.get_data()
    sessions = data.get("sessions", [])
    
    try:
        text = message.text.strip()
        
        numbers = re.findall(r'\d+', text)
        if not numbers:
            await message.answer("❌ Пожалуйста, нажмите на кнопку с записью")
            return
        
        num = int(numbers[0])
        
        if num < 1 or num > len(sessions):
            await message.answer(f"❌ Неверный номер. Выберите от 1 до {len(sessions)}")
            return
        
        selected_session = sessions[num - 1]
        await state.update_data(selected_session=selected_session)
        await state.set_state(WorkStates.waiting_fix_field)
        
        field_keyboard = [
            [KeyboardButton(text="🕐 ВРЕМЯ НАЧАЛА"), KeyboardButton(text="🕐 ВРЕМЯ ОКОНЧАНИЯ")],
            [KeyboardButton(text="📍 ОБЪЕКТ"), KeyboardButton(text="📝 ОТЧЁТ ЗА ДЕНЬ")],
            [KeyboardButton(text=BUTTONS["cancel"])]
        ]
        
        await message.answer(
            f"📋 *ВЫБРАНА ЗАПИСЬ:*\n"
            f"📅 Дата: {selected_session['start_time'][:10]}\n"
            f"📍 Объект: {selected_session['object_name']}\n"
            f"🕐 Время: {selected_session['start_time'][11:16]} - {selected_session['end_time'][11:16]}\n"
            f"💰 Заработано: {selected_session['earnings']} ₴\n"
            f"📝 Отчёт: {selected_session['daily_report'] or '—'}\n\n"
            f"Что хотите исправить?",
            reply_markup=ReplyKeyboardMarkup(keyboard=field_keyboard, resize_keyboard=True),
            parse_mode="Markdown"
        )
        print(f"✅ Запись выбрана, показано меню исправления")
        
    except Exception as e:
        print(f"❌ Ошибка в fix_choose_session: {e}")
        await message.answer(f"❌ Ошибка: попробуйте ещё раз")

# --- ХЕНДЛЕРЫ ДЛЯ ИСПРАВЛЕНИЯ ПОЛЕЙ ---

@dp.message(WorkStates.waiting_fix_field, F.text == "🕐 ВРЕМЯ НАЧАЛА")
async def fix_start_time(message: Message, state: FSMContext):
    await state.update_data(fix_field="start_time")
    await state.set_state(WorkStates.waiting_new_time)
    await message.answer(
        "🕐 Введите новое время начала в формате ЧЧ:ММ\n"
        "Например: 09:00 или 14:30"
    )

@dp.message(WorkStates.waiting_fix_field, F.text == "🕐 ВРЕМЯ ОКОНЧАНИЯ")
async def fix_end_time(message: Message, state: FSMContext):
    await state.update_data(fix_field="end_time")
    await state.set_state(WorkStates.waiting_new_time)
    await message.answer(
        "🕐 Введите новое время окончания в формате ЧЧ:ММ\n"
        "Например: 18:00 или 23:30"
    )

@dp.message(WorkStates.waiting_fix_field, F.text == "📍 ОБЪЕКТ")
async def fix_object(message: Message, state: FSMContext):
    await state.update_data(fix_field="object")
    await state.set_state(WorkStates.waiting_new_object)
    
    from database import execute_query
    result = execute_query("SELECT name FROM objects WHERE is_hidden = 0 ORDER BY name", fetch_all=True)
    
    if not result:
        await message.answer("❌ Нет доступных объектов")
        return
    
    # Создаём кнопки БЕЗ эмодзи
    keyboard = []
    for row in result:
        name = row["name"]
        keyboard.append([KeyboardButton(text=name)])
    
    keyboard.append([KeyboardButton(text=BUTTONS["cancel"])])
    
    await message.answer(
        "📍 Выберите новый объект:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    )

@dp.message(WorkStates.waiting_fix_field, F.text == "📝 ОТЧЁТ ЗА ДЕНЬ")
async def fix_report(message: Message, state: FSMContext):
    await state.update_data(fix_field="report")
    await state.set_state(WorkStates.waiting_new_report)
    await message.answer("📝 Введите новый отчёт:")

@dp.message(WorkStates.waiting_fix_field, F.text == BUTTONS["cancel"])
async def fix_field_cancel(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

# --- ХЕНДЛЕРЫ ДЛЯ ВВОДА НОВОГО ВРЕМЕНИ ---

@dp.message(WorkStates.waiting_new_time, F.text == BUTTONS["cancel"])
async def fix_time_cancel(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

@dp.message(WorkStates.waiting_new_time)
async def fix_process_time(message: Message, state: FSMContext):
    if not validate_time_format(message.text.strip()):
        await message.answer("❌ Неверный формат! Введите время в формате ЧЧ:ММ\nНапример: 09:00")
        return
    
    data = await state.get_data()
    session = data.get("selected_session")
    field = data.get("fix_field")
    
    try:
        time_str = message.text.strip()
        hour, minute = map(int, time_str.split(':'))
        
        if field == "start_time":
            new_start = datetime.strptime(f"{session['start_time'][:10]} {time_str}", "%Y-%m-%d %H:%M")
            new_end = datetime.fromisoformat(session["end_time"])
            
            if new_start >= new_end:
                await message.answer("❌ Время начала не может быть позже времени окончания!")
                return
            
            duration = new_end - new_start
            hours = duration.total_seconds() / 3600
            hourly_rate = get_hourly_rate(message.from_user.id)
            new_earnings = int(hours * hourly_rate)
            if session["is_night"]:
                new_earnings = int(new_earnings * NIGHT_BONUS)
            
            update_work_session_time(session["id"], new_start, new_end, int(duration.total_seconds()), session["is_night"], new_earnings)
            
            diff = new_earnings - session["earnings"]
            update_balance(message.from_user.id, earnings_change=diff)
            
            await message.answer(f"✅ Время начала изменено!\n💰 Изменение баланса: {diff:+} ₴")
            
        elif field == "end_time":
            new_end = datetime.strptime(f"{session['end_time'][:10]} {time_str}", "%Y-%m-%d %H:%M")
            new_start = datetime.fromisoformat(session["start_time"])
            
            if new_end <= new_start:
                await message.answer("❌ Время окончания не может быть раньше времени начала!")
                return
            
            duration = new_end - new_start
            hours = duration.total_seconds() / 3600
            hourly_rate = get_hourly_rate(message.from_user.id)
            new_earnings = int(hours * hourly_rate)
            if session["is_night"]:
                new_earnings = int(new_earnings * NIGHT_BONUS)
            
            update_work_session_time(session["id"], new_start, new_end, int(duration.total_seconds()), session["is_night"], new_earnings)
            
            diff = new_earnings - session["earnings"]
            update_balance(message.from_user.id, earnings_change=diff)
            
            await message.answer(f"✅ Время окончания изменено!\n💰 Изменение баланса: {diff:+} ₴")
        
        await state.set_state(WorkStates.idle)
        await show_main_menu(message, state)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# --- ХЕНДЛЕРЫ ДЛЯ ВЫБОРА ОБЪЕКТА ПРИ РЕДАКТИРОВАНИИ ---

@dp.message(WorkStates.waiting_new_object, F.text == BUTTONS["cancel"])
async def fix_object_cancel(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

@dp.message(WorkStates.waiting_new_object)
async def fix_process_object(message: Message, state: FSMContext):
    raw_text = message.text.strip()
    print(f"🔧 Получено: '{raw_text}'")
    
    # Убираем эмодзи 📦 если есть
    if raw_text.startswith("📦 "):
        object_name = raw_text[2:].strip()
    else:
        object_name = raw_text
    
    print(f"🔧 Очищенное название: '{object_name}'")
    
    if object_name == BUTTONS["cancel"] or raw_text == BUTTONS["cancel"]:
        await state.set_state(WorkStates.idle)
        await show_main_menu(message, state)
        return
    
    # Получаем все доступные объекты из БД
    from database import execute_query
    all_objects = execute_query("SELECT name FROM objects WHERE is_hidden = 0", fetch_all=True)
    object_names = [row["name"] for row in all_objects] if all_objects else []
    print(f"🔧 Доступные объекты в БД: {object_names}")
    
    # Проверяем, есть ли такой объект
    if object_name in object_names:
        data = await state.get_data()
        session = data.get("selected_session")
        
        if session:
            update_work_session_object(session["id"], object_name)
            await message.answer(f"✅ Объект изменён на \"{object_name}\"!")
        else:
            await message.answer("❌ Ошибка: сессия не найдена")
    else:
        await message.answer(f"❌ Объект \"{object_name}\" не найден. Доступные объекты: {', '.join(object_names)}")
        return
    
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

# --- ХЕНДЛЕР ДЛЯ НОВОГО ОТЧЁТА ---

@dp.message(WorkStates.waiting_new_report, F.text == BUTTONS["cancel"])
async def fix_report_cancel(message: Message, state: FSMContext):
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

@dp.message(WorkStates.waiting_new_report)
async def fix_process_report(message: Message, state: FSMContext):
    report = message.text.strip()
    
    data = await state.get_data()
    session = data.get("selected_session")
    
    update_work_session_report(session["id"], report)
    
    await message.answer(f"✅ Отчёт изменён!\n📝 Новый отчёт: {report}")
    
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)
# ============= УДАЛИТЬ ПОСЛЕДНЮЮ ЗАПИСЬ =============

@dp.message(F.text == BUTTONS["delete_last"])
async def delete_last_session(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    last_session = get_last_session(user_id)
    
    if not last_session:
        await message.answer("❌ Нет записей для удаления")
        return
    
    date = last_session["start_time"][:10]
    obj = last_session["object_name"]
    hours = last_session["duration"] / 3600
    earnings = last_session["earnings"]
    report = last_session["daily_report"] or "—"
    
    await state.update_data(delete_session_id=last_session["id"], delete_earnings=earnings)
    await state.set_state(WorkStates.confirming_delete)
    
    await message.answer(
        f"⚠️ *УДАЛЕНИЕ ЗАПИСИ*\n\n"
        f"📅 Дата: {date}\n"
        f"📍 Объект: {obj}\n"
        f"⏱ Длительность: {hours:.1f} ч\n"
        f"💰 Заработано: {earnings} ₴\n"
        f"📝 Отчёт: {report}\n\n"
        f"❓ Вы уверены, что хотите удалить эту запись?\n\n"
        f"⚠️ Восстановить запись будет невозможно!",
        reply_markup=get_confirm_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(WorkStates.confirming_delete, F.text == "✅ ДА")
async def confirm_delete_session(message: Message, state: FSMContext):
    data = await state.get_data()
    session_id = data.get("delete_session_id")
    earnings = data.get("delete_earnings")
    
    if session_id:
        delete_work_session(session_id)
        update_balance(message.from_user.id, earnings_change=-earnings)
        await message.answer(f"✅ Запись удалена!\n💰 Баланс изменён: -{earnings} ₴")
    else:
        await message.answer("❌ Ошибка при удалении")
    
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

@dp.message(WorkStates.confirming_delete, F.text == "❌ НЕТ")
async def cancel_delete_session(message: Message, state: FSMContext):
    await message.answer("❌ Удаление отменено")
    await state.set_state(WorkStates.idle)
    await show_main_menu(message, state)

# ============= ПОМОЩЬ =============

@dp.message(F.text == BUTTONS["help"])
async def show_help(message: Message):
    await message.answer(
        "📖 *СПРАВКА*\n\n"
        "*Основные команды:*\n"
        "• ⏱ НАЧАТЬ РАБОТУ — начать смену\n"
        "• ⛔ ЗАКОНЧИТЬ РАБОТУ — завершить смену\n"
        "• 💰 МОЙ БАЛАНС — текущий баланс\n"
        "• 💸 РАСХОДНИК — добавить трату\n"
        "• 📊 СТАТИСТИКА — ваш отчёт\n"
        "• ✏️ ИСПРАВИТЬ — редактировать запись\n"
        "• 🗑 УДАЛИТЬ ПОСЛЕДНЕЕ — удалить запись\n\n"
        "*Важно:*\n"
        "• Ночные смены оплачиваются +20%\n"
        "• Данные старше 30 дней архивируются",
        parse_mode="Markdown"
    )

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def show_main_menu(message: Message, state: FSMContext, working: bool = False):
    user_id = message.from_user.id
    
    # Если параметр working не передан - определяем сами
    if not working:
        working = user_id in active_work_sessions
    
    keyboard = get_main_keyboard(user_id, working)
    
    if user_id in ADMIN_IDS:
        admin_keyboard = get_admin_button_keyboard()
        keyboard.keyboard.extend(admin_keyboard.keyboard)
    
    await message.answer("📋 Главное меню:", reply_markup=keyboard)
    await state.set_state(WorkStates.idle)

# ============= ОТЧЁТЫ (АДМИН) =============

@dp.message(F.text == "📊 ОТЧЁТ")
async def admin_reports_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    await state.set_state("admin_reports_menu")
    await message.answer(
        "📊 *ОТЧЁТЫ*\n\nВыберите тип отчёта:",
        reply_markup=get_report_menu_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(F.text == "📦 ОТЧЁТ ПО ОБЪЕКТАМ")
async def report_objects(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    from database import get_all_objects_stats_all_time
    result = get_all_objects_stats_all_time()
    
    if not result:
        await message.answer("❌ Нет данных по объектам")
        await state.set_state("admin_menu")
        return
    
    report = "📦 *ОТЧЁТ ПО ОБЪЕКТАМ (ЗА ВСЁ ВРЕМЯ)*\n\n"
    
    for username, objects in result.items():
        report += f"👤 *{username}*\n"
        for obj in objects:
            report += f"   • {obj['object_name']}: {obj['hours']:.1f}ч ({obj['earned']:,}₴) - {obj['count']} смен\n"
        report += "\n"
    
    await message.answer(report, parse_mode="Markdown")
    await state.set_state("admin_menu")


@dp.message(F.text == "💸 ОТЧЁТ ПО РАСХОДАМ")
async def report_expenses(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    from database import get_expenses_stats_last_30_days
    stats = get_expenses_stats_last_30_days()
    
    report = f"💸 *ОТЧЁТ ПО РАСХОДАМ (ПОСЛЕДНИЕ 30 ДНЕЙ)*\n\n"
    report += f"📊 *ИТОГИ:*\n"
    report += f"• ✅ Подтверждено: {stats['total_approved']:,} ₴\n"
    report += f"• ⏳ Ожидает: {stats['total_pending']:,} ₴\n"
    report += f"• ❌ Отклонено: {stats['total_rejected']:,} ₴\n\n"
    report += f"📋 *ДЕТАЛИ:*\n"
    
    for expense in stats['expenses'][:20]:
        status_emoji = "✅" if expense["status"] == "approved" else ("⏳" if expense["status"] == "pending" else "❌")
        date = expense["created_at"][:10] if expense["created_at"] else ""
        report += f"{status_emoji} {date} {expense['username']}: {expense['amount']:,}₴ - {expense['description'][:30]}\n"
    
    if len(stats['expenses']) > 20:
        report += f"\n... и ещё {len(stats['expenses']) - 20} записей"
    
    await message.answer(report, parse_mode="Markdown")
    await state.set_state("admin_menu")


@dp.message(F.text == "💰 ОТЧЁТ ПО ВЫПЛАТАМ")
async def report_payments(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    from database import get_payments_stats_last_30_days
    stats = get_payments_stats_last_30_days()
    
    report = f"💰 *ОТЧЁТ ПО ВЫПЛАТАМ (ПОСЛЕДНИЕ 30 ДНЕЙ)*\n\n"
    report += f"📊 *ИТОГИ:*\n"
    report += f"• ✅ Подтверждено: {stats['total_confirmed']:,} ₴\n"
    report += f"• ⏳ Ожидает: {stats['total_pending']:,} ₴\n"
    report += f"• ❌ Отклонено: {stats['total_rejected']:,} ₴\n\n"
    report += f"📋 *ДЕТАЛИ:*\n"
    
    for payment in stats['payments'][:20]:
        status_emoji = "✅" if payment["status"] == "confirmed" else ("⏳" if payment["status"] == "pending" else "❌")
        date = payment["created_at"][:10] if payment["created_at"] else ""
        report += f"{status_emoji} {date} {payment['username']}: {payment['amount']:,}₴\n"
    
    if len(stats['payments']) > 20:
        report += f"\n... и ещё {len(stats['payments']) - 20} записей"
    
    await message.answer(report, parse_mode="Markdown")
    await state.set_state("admin_menu")


@dp.message(F.text == "📈 ПРОГНОЗ")
async def report_forecast(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа")
        return
    
    from database import get_forecast_stats_30_days
    stats = get_forecast_stats_30_days()
    
    report = f"📈 *ПРОГНОЗ НА 30 ДНЕЙ*\n\n"
    report += f"📊 *СТАТИСТИКА ЗА ПОСЛЕДНИЕ 30 ДНЕЙ:*\n"
    report += f"• Дней с данными: {stats['days_with_data']}\n"
    report += f"• Всего часов: {stats['current_hours']:.1f} ч\n"
    report += f"• Заработано: {stats['current_earned']:,} ₴\n"
    report += f"• Среднее в день: {stats['avg_hours_per_day']:.1f} ч / {stats['avg_earned_per_day']:.0f} ₴\n\n"
    report += f"📈 *ПРОГНОЗ НА СЛЕДУЮЩИЕ 30 ДНЕЙ:*\n"
    report += f"• Прогноз часов: +{stats['forecast_hours_30d']:.1f} ч\n"
    report += f"• Прогноз заработка: +{stats['forecast_earned_30d']:,} ₴"
    
    await message.answer(report, parse_mode="Markdown")
    await state.set_state("admin_menu")


@dp.message(F.text == "🔙 НАЗАД")
async def reports_back(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == "admin_reports_menu":
        await admin_panel(message, state)
    else:
        await state.set_state("admin_menu")
        await admin_panel(message, state)

# ============= ЭКСПОРТ ДЛЯ СОТРУДНИКА =============

@dp.message(F.text == "📎 МОЙ ЭКСПОРТ")
async def employee_export_menu(message: Message, state: FSMContext):
    from keyboards import get_employee_export_menu_keyboard
    await state.set_state("employee_export_menu")
    await message.answer(
        "📎 *МОЙ ЭКСПОРТ*\n\nВыберите тип отчёта:",
        reply_markup=get_employee_export_menu_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(F.text == "📎 МОЙ ЭКСПОРТ ЗА ТЕКУЩИЙ МЕСЯЦ")
async def employee_export_current_month(message: Message, state: FSMContext):
    user_id = message.from_user.id
    now = now_local()
    
    await message.answer(f"📊 Формирую ваш отчёт за {now.strftime('%B %Y')}...")
    
    try:
        from utils.excel_generator import create_monthly_archive_excel
        filename = create_monthly_archive_excel(user_id, now.year, now.month)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption=f"📊 Ваш отчёт за {now.strftime('%B %Y')}"
            )
            os.remove(filename)
        else:
            await message.answer("❌ Нет данных за текущий месяц")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@dp.message(F.text == "📁 МОИ МЕСЯЧНЫЕ ОТЧЁТЫ")
async def employee_monthly_reports(message: Message, state: FSMContext):
    current_year = now_local().year
    await state.update_data(selected_year=current_year, export_type="monthly")
    # НЕ устанавливаем state, потому что используем callback_query
    
    # Используем новую inline-клавиатуру
    await message.answer(
        f"📅 **ВЫБЕРИТЕ МЕСЯЦ {current_year} ГОДА:**",
        reply_markup=get_inline_months_keyboard(current_year),
        parse_mode="Markdown"
    )

@dp.message(F.text == "📁 МОИ ГОДОВЫЕ ОТЧЁТЫ")
async def employee_yearly_reports(message: Message, state: FSMContext):
    await state.update_data(export_type="yearly")
    await state.set_state(WorkStates.employee_export_choosing_year)
    
    await message.answer(
        "📅 *ВВЕДИТЕ ГОД (например: 2026):*",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("report_month_"))
async def employee_choose_month(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора месяца"""
    
    print(f"🔥 Хендлер месяцев сработал! Данные: {callback.data}")
    
    await callback.answer()
    
    # Кнопка "Назад"
    if callback.data == "report_month_back":
        await callback.message.delete()
        return
    
    # Разбираем данные: "report_month_01 ЯНВАРЬ_2026"
    parts = callback.data.split("_")
    month_with_name = parts[2]      # "01 ЯНВАРЬ"
    year = parts[3]                 # "2026"
    
    # Берём только число из месяца
    month_num = int(month_with_name.split()[0])  # "01" -> 1
    
    # Удаляем сообщение с кнопками
    await callback.message.delete()
    
    # Формируем отчёт
    status_msg = await callback.message.answer(f"📊 Формирую ваш отчёт за {month_with_name} {year}...")
    
    try:
        from utils.excel_generator import create_monthly_archive_excel
        filename = create_monthly_archive_excel(
            callback.from_user.id,
            int(year),
            month_num
        )
        
        await status_msg.delete()
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await callback.message.answer_document(
                document=document,
                caption=f"✅ Ваш отчёт за {month_with_name} {year}"
            )
            os.remove(filename)
        else:
            await callback.message.answer(f"❌ Нет данных за {month_with_name} {year}")
        
        await state.clear()
        
    except Exception as e:
        await status_msg.delete()
        await callback.message.answer(f"❌ Ошибка: {e}")

@dp.message(WorkStates.employee_export_choosing_year)
async def employee_choose_year_text(message: Message, state: FSMContext):
    """Обработчик текстового ввода года для годового отчёта"""
    
    try:
        year = int(message.text.strip())
        
        if year < 2000 or year > 2100:
            await message.answer("❌ Введите корректный год (например: 2026)")
            return
        
        await message.answer(f"📊 Формирую ваш отчёт за {year} год...")
        
        from utils.excel_generator import create_yearly_archive_excel
        filename = create_yearly_archive_excel(message.from_user.id, year)
        
        if filename and os.path.exists(filename):
            document = FSInputFile(filename)
            await message.answer_document(
                document=document,
                caption=f"✅ Ваш годовой отчёт за {year} год"
            )
            os.remove(filename)
        else:
            await message.answer(f"❌ Нет данных за {year} год")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректный год (цифрами, например: 2026)")
     
# ============= ЗАПУСК =============

# Подключаем роутеры
dp.include_router(admin.router)  # <--- ДОБАВИТЬ ЭТУ СТРОКУ

async def main():
    init_db()
    print("🤖 Бот запущен!")
    print(f"👑 Администраторы: {ADMIN_IDS}")
    
    asyncio.create_task(scheduler(bot))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())