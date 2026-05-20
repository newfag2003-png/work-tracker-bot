import asyncio
from datetime import datetime, timedelta
from aiogram import Bot

from database import (
    get_all_users, get_weekly_stats, get_balance, get_weekly_expenses,
    get_weekly_payments, get_sessions_for_period, get_user,
    auto_cancel_expired_expenses, auto_cancel_expired_payments
)
from config import (
    REMINDER_HOUR, REMINDER_MINUTE, WEEKLY_REPORT_DAY,
    WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE, ADMIN_IDS
)

async def daily_reminder(bot: Bot):
    """Ежедневное напоминание в 08:50"""
    now = datetime.now()
    
    if now.hour == REMINDER_HOUR and now.minute == REMINDER_MINUTE:
        users = get_all_users()
        for user in users:
            try:
                await bot.send_message(
                    user["user_id"],
                    "🌅 *ДОБРОЕ УТРО!*\n\n"
                    "Не забудьте начать рабочий день!\n"
                    "Нажмите ⏱ НАЧАТЬ РАБОТУ или напишите `начать`",
                    parse_mode="Markdown"
                )
                print(f"📨 Напоминание отправлено {user['username']}")
            except Exception as e:
                print(f"Ошибка отправки: {e}")
        await asyncio.sleep(60)

async def weekly_report(bot: Bot):
    """Еженедельный отчёт по воскресеньям в 09:00"""
    now = datetime.now()
    
    if now.weekday() == WEEKLY_REPORT_DAY and now.hour == WEEKLY_REPORT_HOUR and now.minute == WEEKLY_REPORT_MINUTE:
        users = get_all_users()
        
        for user in users:
            try:
                balance = get_balance(user["user_id"])
                stats = get_weekly_stats(user["user_id"], 7)
                expenses = get_weekly_expenses(user["user_id"], 7)
                payments = get_weekly_payments(user["user_id"], 7)
                
                change = stats['total_earned'] + expenses - payments
                
                report = f"📊 *ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ*\n\n"
                report += f"📅 *Период:* {get_week_range()}\n\n"
                report += f"⏱ *Отработано:* {stats['work_days']} дней\n"
                report += f"🕐 *Всего часов:* {stats['total_hours']:.1f} ч\n"
                report += f"💰 *Заработано:* {stats['total_earned']:,} ₴\n"
                
                if expenses > 0:
                    report += f"💸 *Компенсации:* +{expenses:,} ₴\n"
                if payments > 0:
                    report += f"💵 *Выплачено:* -{payments:,} ₴\n"
                
                report += f"\n📈 *Изменение баланса:* {change:+,} ₴\n"
                report += f"💳 *Текущий баланс:* {balance:,} ₴\n"
                
                if stats['night_sessions'] > 0:
                    report += f"\n🌙 *Ночных смен:* {stats['night_sessions']}\n"
                
                report += f"\n🏆 *Чаще всего:* {stats['top_object']}\n"
                
                await bot.send_message(
                    user["user_id"],
                    report,
                    parse_mode="Markdown"
                )
                print(f"📨 Еженедельный отчёт отправлен {user['username']}")
                
            except Exception as e:
                print(f"Ошибка отправки отчёта {user['username']}: {e}")
        
        await asyncio.sleep(60)

async def auto_cancel_expired(bot: Bot):
    """Автоматическая отмена просроченных расходов и выплат (каждый час)"""
    
    # Отменяем просроченные расходы
    cancelled_expenses, expenses_count = auto_cancel_expired_expenses()
    
    if expenses_count > 0:
        print(f"🕐 Автоматически отменено {expenses_count} просроченных расходов")
        
        for expense in cancelled_expenses:
            try:
                user = get_user(expense["user_id"])
                if user:
                    await bot.send_message(
                        expense["user_id"],
                        f"⏰ *АВТОМАТИЧЕСКАЯ ОТМЕНА РАСХОДА*\n\n"
                        f"💰 Сумма: {expense['amount']:,} ₴\n"
                        f"📝 Описание: {expense['description']}\n\n"
                        f"❌ Расход автоматически отклонён, так как не был подтверждён администратором в течение 24 часов.\n\n"
                        f"📞 При необходимости создайте расход заново.",
                        parse_mode="Markdown"
                    )
                    print(f"📨 Уведомление об отмене расхода отправлено {user['username']}")
            except Exception as e:
                print(f"Ошибка уведомления об отмене расхода: {e}")
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⏰ *АВТОМАТИЧЕСКАЯ ОТМЕНА РАСХОДОВ*\n\n"
                    f"❌ Отменено {expenses_count} расходов, не подтверждённых в течение 24 часов.\n\n"
                    f"Для более быстрой обработки расходов проверяйте заявки чаще.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
    
    # Отменяем просроченные выплаты
    cancelled_payments, payments_count = auto_cancel_expired_payments()
    
    if payments_count > 0:
        print(f"🕐 Автоматически отменено {payments_count} просроченных выплат")
        
        for payment in cancelled_payments:
            try:
                user = get_user(payment["user_id"])
                if user:
                    await bot.send_message(
                        payment["user_id"],
                        f"⏰ *АВТОМАТИЧЕСКАЯ ОТМЕНА ВЫПЛАТЫ*\n\n"
                        f"💰 Сумма: {payment['amount']:,} ₴\n\n"
                        f"❌ Выплата автоматически отклонена, так как не была подтверждена в течение 24 часов.\n\n"
                        f"📞 Для получения выплаты обратитесь к администратору.",
                        parse_mode="Markdown"
                    )
                    print(f"📨 Уведомление об отмене выплаты отправлено {user['username']}")
            except Exception as e:
                print(f"Ошибка уведомления об отмене выплаты: {e}")
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⏰ *АВТОМАТИЧЕСКАЯ ОТМЕНА ВЫПЛАТ*\n\n"
                    f"❌ Отменено {payments_count} выплат, не подтверждённых сотрудниками в течение 24 часов.\n\n"
                    f"При необходимости создайте выплату заново.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")

async def archive_scheduler(bot: Bot):
    """Архивация 1-го числа каждого месяца в 03:00"""
    now = datetime.now()
    
    # Проверяем, первое ли число и нужное время
    if now.day == 1 and now.hour == 3 and now.minute == 0:
        from database import archive_old_data
        print("📦 Запущена архивация старых данных...")
        archived_count = archive_old_data()
        
        # Уведомляем администратора
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📦 *АРХИВАЦИЯ ЗАВЕРШЕНА*\n\n"
                    f"🗄 За {get_previous_month_name()} архивировано {archived_count} записей.\n\n"
                    f"✅ Детальные записи удалены, сводка сохранена.\n"
                    f"📎 Excel-файлы за прошлые месяцы доступны через меню АРХИВ.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
        
        await asyncio.sleep(60)

def get_week_range():
    """Получить диапазон текущей недели"""
    today = datetime.now()
    start = today - timedelta(days=today.weekday() + 1)
    end = start + timedelta(days=6)
    return f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}"

def get_previous_month_name():
    """Получить название прошлого месяца"""
    now = datetime.now()
    if now.month == 1:
        month = 12
        year = now.year - 1
    else:
        month = now.month - 1
        year = now.year
    months = ["январь", "февраль", "март", "апрель", "май", "июнь",
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
    return f"{months[month-1]} {year} года"

async def scheduler(bot: Bot):
    """Запуск всех автоматических задач"""
    print("⏰ Планировщик запущен!")
    print(f"📅 Ежедневное напоминание: {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d}")
    print(f"📊 Еженедельный отчёт: воскресенье {WEEKLY_REPORT_HOUR:02d}:{WEEKLY_REPORT_MINUTE:02d}")
    print(f"🕐 Автоотмена: каждый час")
    print(f"🗄 Архивация: 1-го числа каждого месяца в 03:00")
    
    while True:
        await daily_reminder(bot)
        await weekly_report(bot)
        await auto_cancel_expired(bot)
        await archive_scheduler(bot)
        await asyncio.sleep(30)