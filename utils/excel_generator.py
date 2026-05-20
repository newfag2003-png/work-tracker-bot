import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from database import (
    get_user, get_sessions_for_period, get_sessions_for_month, get_balance,
    get_hourly_rate, get_all_users, get_monthly_summary, get_yearly_summary,
    get_global_monthly_summary, get_global_yearly_summary,
    get_expenses_for_period_by_date, get_payments_for_period_by_date,
    get_expenses_for_period_by_date_list, get_payments_for_period_by_date_list
)

# Создаём папку для архивов
os.makedirs("archives", exist_ok=True)


def create_current_month_excel(user_id: int):
    """Создать Excel за текущий месяц для сотрудника"""
    now = datetime.now()
    return create_monthly_archive_excel(user_id, now.year, now.month)


def create_monthly_archive_excel(user_id: int, year: int, month: int):
    """Создать Excel из архива за указанный месяц для сотрудника"""
    
    # Проверяем, есть ли уже сохранённый файл
    summary = get_monthly_summary(user_id, year, month)
    
    if summary and summary["excel_file_path"] and os.path.exists(summary["excel_file_path"]):
        return summary["excel_file_path"]
    
    # Если нет, создаём из текущих данных
    user = get_user(user_id)
    username = user["username"] if user else f"user_{user_id}"
    
    sessions = get_sessions_for_month(user_id, year, month)
    
    if not sessions:
        return None
    
    wb = Workbook()
    wb.remove(wb.active)
    
    # Сводка
    ws1 = wb.create_sheet("Сводка")
    ws1["A1"] = f"ОТЧЁТ ЗА {month:02d}.{year}"
    ws1["A1"].font = Font(size=16, bold=True)
    ws1.merge_cells("A1:B1")
    
    ws1["A3"] = "Сотрудник:"
    ws1["B3"] = username
    ws1["A4"] = "Период:"
    ws1["B4"] = f"{month:02d}.{year}"
    ws1["A5"] = "Дата отчёта:"
    ws1["B5"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    total_hours = sum(s["duration"] for s in sessions) / 3600
    total_earned = sum(s["earnings"] for s in sessions)
    night_sessions = len([s for s in sessions if s["is_night"]])
    work_days = len(set(s["start_time"][:10] for s in sessions))
    
    ws1["A7"] = "ПОКАЗАТЕЛЬ"
    ws1["B7"] = "ЗНАЧЕНИЕ"
    ws1["A7"].font = Font(bold=True)
    ws1["B7"].font = Font(bold=True)
    
    rows = [
        ("Отработано дней", work_days),
        ("Всего часов", f"{total_hours:.1f} ч"),
        ("Заработано", f"{total_earned:,} ₴"),
        ("Ночных смен", night_sessions),
    ]
    
    row = 8
    for label, value in rows:
        ws1[f"A{row}"] = label
        ws1[f"B{row}"] = value
        row += 1
    
    # Рабочие смены
    ws2 = wb.create_sheet("Рабочие смены")
    headers = ["Дата", "Начало", "Окончание", "Объект", "Длительность", "Ночная", "Заработано", "Отчёт"]
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    for row, session in enumerate(sessions, 2):
        ws2.cell(row=row, column=1, value=session["start_time"][:10])
        ws2.cell(row=row, column=2, value=session["start_time"][11:16])
        ws2.cell(row=row, column=3, value=session["end_time"][11:16])
        ws2.cell(row=row, column=4, value=session["object_name"])
        hours = session["duration"] / 3600
        ws2.cell(row=row, column=5, value=f"{hours:.1f} ч")
        ws2.cell(row=row, column=6, value="Да" if session["is_night"] else "Нет")
        ws2.cell(row=row, column=7, value=f"{session['earnings']:,} ₴")
        ws2.cell(row=row, column=8, value=session["daily_report"] or "—")
    
    for col in range(1, 9):
        ws2.column_dimensions[get_column_letter(col)].width = 12
    
    # Сохраняем
    os.makedirs(f"archives/{year}", exist_ok=True)
    filename = f"archives/{year}/{month:02d}_{username}.xlsx"
    wb.save(filename)
    return filename


def create_yearly_archive_excel(user_id: int, year: int):
    """Создать Excel за год для сотрудника"""
    
    user = get_user(user_id)
    username = user["username"] if user else f"user_{user_id}"
    
    summary = get_yearly_summary(user_id, year)
    
    if not summary:
        return None
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Отчёт за {year}"
    
    ws["A1"] = f"ГОДОВОЙ ОТЧЁТ ЗА {year}"
    ws["A1"].font = Font(size=16, bold=True)
    ws.merge_cells("A1:B1")
    
    ws["A3"] = "Сотрудник:"
    ws["B3"] = username
    ws["A4"] = "Период:"
    ws["B4"] = f"{year} год"
    ws["A5"] = "Дата отчёта:"
    ws["B5"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    ws["A7"] = "ПОКАЗАТЕЛЬ"
    ws["B7"] = "ЗНАЧЕНИЕ"
    ws["A7"].font = Font(bold=True)
    ws["B7"].font = Font(bold=True)
    
    rows = [
        ("Всего часов", f"{summary['total_hours']:.1f} ч"),
        ("Всего заработано", f"{summary['total_earned']:,} ₴"),
        ("Компенсаций", f"{summary['total_expenses']:,} ₴"),
        ("Выплачено", f"{summary['total_paid']:,} ₴"),
        ("Баланс на конец года", f"{summary['closing_balance']:,} ₴"),
    ]
    
    row = 8
    for label, value in rows:
        ws[f"A{row}"] = label
        ws[f"B{row}"] = value
        row += 1
    
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 20
    
    filename = f"archives/{year}/yearly_{username}.xlsx"
    os.makedirs(f"archives/{year}", exist_ok=True)
    wb.save(filename)
    return filename


def create_admin_current_month_excel():
    """Создать общий Excel за текущий месяц для админа"""
    now = datetime.now()
    return create_admin_monthly_archive_excel(now.year, now.month)


def create_admin_monthly_archive_excel(year: int, month: int):
    """Создать общий Excel из архива за указанный месяц для админа"""
    
    summary = get_global_monthly_summary(year, month)
    
    if summary and summary["excel_file_path"] and os.path.exists(summary["excel_file_path"]):
        return summary["excel_file_path"]
    
    users = get_all_users()
    
    if not users:
        return None
    
    wb = Workbook()
    wb.remove(wb.active)
    
    # ============= ЛИСТ 1: СВОДКА =============
    ws1 = wb.create_sheet("Сводка")
    ws1["A1"] = f"ОБЩИЙ ОТЧЁТ ЗА {month:02d}.{year}"
    ws1["A1"].font = Font(size=16, bold=True)
    ws1.merge_cells("A1:D1")
    
    ws1["A3"] = "Дата отчёта:"
    ws1["B3"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    ws1["A4"] = "Период:"
    ws1["B4"] = f"{month:02d}.{year}"
    ws1["A5"] = "Всего сотрудников:"
    ws1["B5"] = len(users)
    
    total_balance = 0
    total_hours_all = 0
    total_earned_all = 0
    total_expenses_all = 0
    total_paid_all = 0
    
    for user in users:
        total_balance += get_balance(user["user_id"])
        sessions = get_sessions_for_month(user["user_id"], year, month)
        total_hours_all += sum(s["duration"] for s in sessions) / 3600 if sessions else 0
        total_earned_all += sum(s["earnings"] for s in sessions) if sessions else 0
        
        # Расходы и выплаты за месяц
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        from database import get_expenses_for_period_by_date, get_payments_for_period_by_date
        total_expenses_all += get_expenses_for_period_by_date(user["user_id"], start_date, end_date)
        total_paid_all += get_payments_for_period_by_date(user["user_id"], start_date, end_date)
    
    ws1["A7"] = "ПОКАЗАТЕЛЬ"
    ws1["B7"] = "ЗНАЧЕНИЕ"
    ws1["A7"].font = Font(bold=True)
    ws1["B7"].font = Font(bold=True)
    
    rows = [
        ("Общий баланс", f"{total_balance:,} ₴"),
        ("Всего отработано часов", f"{total_hours_all:.1f} ч"),
        ("Всего заработано", f"{total_earned_all:,} ₴"),
        ("Всего компенсаций", f"{total_expenses_all:,} ₴"),
        ("Всего выплачено", f"{total_paid_all:,} ₴"),
    ]
    
    row = 8
    for label, value in rows:
        ws1[f"A{row}"] = label
        ws1[f"B{row}"] = value
        row += 1
    
    ws1.column_dimensions["A"].width = 25
    ws1.column_dimensions["B"].width = 20
    
    # ============= ЛИСТ 2: СОТРУДНИКИ =============
    ws2 = wb.create_sheet("Сотрудники")
    
    headers = ["Имя", "Ставка (₴/ч)", "Баланс (₴)", "Часов за месяц", "Заработано за месяц", "Компенсации", "Выплачено"]
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    row = 2
    for user in users:
        sessions = get_sessions_for_month(user["user_id"], year, month)
        hours = sum(s["duration"] for s in sessions) / 3600 if sessions else 0
        earned = sum(s["earnings"] for s in sessions) if sessions else 0
        
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        expenses = get_expenses_for_period_by_date(user["user_id"], start_date, end_date)
        payments = get_payments_for_period_by_date(user["user_id"], start_date, end_date)
        
        ws2.cell(row=row, column=1, value=user["username"])
        ws2.cell(row=row, column=2, value=f"{get_hourly_rate(user['user_id'])} ₴/ч")
        ws2.cell(row=row, column=3, value=f"{get_balance(user['user_id']):,} ₴")
        ws2.cell(row=row, column=4, value=f"{hours:.1f} ч")
        ws2.cell(row=row, column=5, value=f"{earned:,} ₴")
        ws2.cell(row=row, column=6, value=f"{expenses:,} ₴")
        ws2.cell(row=row, column=7, value=f"{payments:,} ₴")
        row += 1
    
    for col in range(1, 8):
        ws2.column_dimensions[get_column_letter(col)].width = 18
    
    # ============= ЛИСТ 3: РАБОЧИЕ СМЕНЫ =============
    ws3 = wb.create_sheet("Рабочие смены")
    
    headers = ["Сотрудник", "Дата", "Начало", "Окончание", "Объект", "Длительность", "Ночная", "Заработано", "Отчёт"]
    for col, header in enumerate(headers, 1):
        cell = ws3.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    row = 2
    for user in users:
        sessions = get_sessions_for_month(user["user_id"], year, month)
        for session in sessions:
            ws3.cell(row=row, column=1, value=user["username"])
            ws3.cell(row=row, column=2, value=session["start_time"][:10])
            ws3.cell(row=row, column=3, value=session["start_time"][11:16])
            ws3.cell(row=row, column=4, value=session["end_time"][11:16])
            ws3.cell(row=row, column=5, value=session["object_name"])
            hours = session["duration"] / 3600
            ws3.cell(row=row, column=6, value=f"{hours:.1f} ч")
            ws3.cell(row=row, column=7, value="Да" if session["is_night"] else "Нет")
            ws3.cell(row=row, column=8, value=f"{session['earnings']:,} ₴")
            ws3.cell(row=row, column=9, value=session["daily_report"] or "—")
            row += 1
    
    for col in range(1, 10):
        ws3.column_dimensions[get_column_letter(col)].width = 14
    
    # ============= ЛИСТ 4: РАСХОДЫ =============
    ws4 = wb.create_sheet("Расходы")
    
    headers = ["Сотрудник", "Дата", "Сумма", "Описание", "Статус"]
    for col, header in enumerate(headers, 1):
        cell = ws4.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    row = 2
    for user in users:
        from database import get_expenses_for_period_by_date_list
        expenses = get_expenses_for_period_by_date_list(user["user_id"], start_date, end_date)
        for expense in expenses:
            ws4.cell(row=row, column=1, value=user["username"])
            ws4.cell(row=row, column=2, value=expense["created_at"][:10] if expense["created_at"] else "")
            ws4.cell(row=row, column=3, value=f"{expense['amount']:,} ₴")
            ws4.cell(row=row, column=4, value=expense["description"])
            status_text = "Подтверждён" if expense["status"] == "approved" else ("Отклонён" if expense["status"] == "rejected" else "Ожидает")
            ws4.cell(row=row, column=5, value=status_text)
            row += 1
    
    for col in range(1, 6):
        ws4.column_dimensions[get_column_letter(col)].width = 18
    
    # ============= ЛИСТ 5: ВЫПЛАТЫ =============
    ws5 = wb.create_sheet("Выплаты")
    
    headers = ["Сотрудник", "Дата", "Сумма", "Статус"]
    for col, header in enumerate(headers, 1):
        cell = ws5.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    row = 2
    for user in users:
        from database import get_payments_for_period_by_date_list
        payments = get_payments_for_period_by_date_list(user["user_id"], start_date, end_date)
        for payment in payments:
            ws5.cell(row=row, column=1, value=user["username"])
            ws5.cell(row=row, column=2, value=payment["created_at"][:10] if payment["created_at"] else "")
            ws5.cell(row=row, column=3, value=f"{payment['amount']:,} ₴")
            status_text = "Подтверждена" if payment["status"] == "confirmed" else ("Отклонена" if payment["status"] == "rejected" else "Ожидает")
            ws5.cell(row=row, column=4, value=status_text)
            row += 1
    
    for col in range(1, 5):
        ws5.column_dimensions[get_column_letter(col)].width = 18
    
    # Сохраняем
    os.makedirs(f"archives/{year}", exist_ok=True)
    filename = f"archives/{year}/{month:02d}_общий.xlsx"
    wb.save(filename)
    return filename


def create_admin_yearly_archive_excel(year: int):
    """Создать общий Excel за год для админа"""
    
    summary = get_global_yearly_summary(year)
    
    if not summary:
        return None
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Общий отчёт за {year}"
    
    ws["A1"] = f"ОБЩИЙ ГОДОВОЙ ОТЧЁТ ЗА {year}"
    ws["A1"].font = Font(size=16, bold=True)
    ws.merge_cells("A1:B1")
    
    ws["A3"] = "Период:"
    ws["B3"] = f"{year} год"
    ws["A4"] = "Дата отчёта:"
    ws["B4"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    ws["A6"] = "ПОКАЗАТЕЛЬ"
    ws["B6"] = "ЗНАЧЕНИЕ"
    ws["A6"].font = Font(bold=True)
    ws["B6"].font = Font(bold=True)
    
    rows = [
        ("Всего сотрудников", summary["total_employees"]),
        ("Всего часов", f"{summary['total_hours']:.1f} ч"),
        ("Всего заработано", f"{summary['total_earned']:,} ₴"),
        ("Компенсаций", f"{summary['total_expenses']:,} ₴"),
        ("Выплачено", f"{summary['total_paid']:,} ₴"),
        ("Общий баланс", f"{summary['total_balance']:,} ₴"),
    ]
    
    row = 7
    for label, value in rows:
        ws[f"A{row}"] = label
        ws[f"B{row}"] = value
        row += 1
    
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 20
    
    filename = f"archives/{year}/yearly_общий.xlsx"
    os.makedirs(f"archives/{year}", exist_ok=True)
    wb.save(filename)
    return filename

def create_monthly_archive_excel(user_id: int, year: int, month: int):
    """Создать Excel из архива за указанный месяц для сотрудника"""
    
    from database import get_expenses_for_period, get_payments_for_period
    
    user = get_user(user_id)
    username = user["username"] if user else f"user_{user_id}"
    
    sessions = get_sessions_for_month(user_id, year, month)
    
    if not sessions:
        return None
    
    wb = Workbook()
    wb.remove(wb.active)
    
    # Сводка
    ws1 = wb.create_sheet("Сводка")
    ws1["A1"] = f"ОТЧЁТ ЗА {month:02d}.{year}"
    ws1["A1"].font = Font(size=16, bold=True)
    ws1.merge_cells("A1:B1")
    
    ws1["A3"] = "Сотрудник:"
    ws1["B3"] = username
    ws1["A4"] = "Период:"
    ws1["B4"] = f"{month:02d}.{year}"
    ws1["A5"] = "Дата отчёта:"
    ws1["B5"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    total_hours = sum(s["duration"] for s in sessions) / 3600
    total_earned = sum(s["earnings"] for s in sessions)
    night_sessions = len([s for s in sessions if s["is_night"]])
    work_days = len(set(s["start_time"][:10] for s in sessions))
    
    # Расходы и выплаты за месяц
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    
    expenses = get_expenses_for_period_by_date(user_id, start_date, end_date)
    payments = get_payments_for_period_by_date(user_id, start_date, end_date)
    
    ws1["A7"] = "ПОКАЗАТЕЛЬ"
    ws1["B7"] = "ЗНАЧЕНИЕ"
    ws1["A7"].font = Font(bold=True)
    ws1["B7"].font = Font(bold=True)
    
    rows = [
        ("Отработано дней", work_days),
        ("Всего часов", f"{total_hours:.1f} ч"),
        ("Заработано", f"{total_earned:,} ₴"),
        ("Компенсации (расходы)", f"{expenses:,} ₴"),
        ("Выплачено", f"{payments:,} ₴"),
        ("Ночных смен", night_sessions),
    ]
    
    row = 8
    for label, value in rows:
        ws1[f"A{row}"] = label
        ws1[f"B{row}"] = value
        row += 1
    
    # Рабочие смены
    ws2 = wb.create_sheet("Рабочие смены")
    headers = ["Дата", "Начало", "Окончание", "Объект", "Длительность", "Ночная", "Заработано", "Отчёт"]
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    for row, session in enumerate(sessions, 2):
        ws2.cell(row=row, column=1, value=session["start_time"][:10])
        ws2.cell(row=row, column=2, value=session["start_time"][11:16])
        ws2.cell(row=row, column=3, value=session["end_time"][11:16])
        ws2.cell(row=row, column=4, value=session["object_name"])
        hours = session["duration"] / 3600
        ws2.cell(row=row, column=5, value=f"{hours:.1f} ч")
        ws2.cell(row=row, column=6, value="Да" if session["is_night"] else "Нет")
        ws2.cell(row=row, column=7, value=f"{session['earnings']:,} ₴")
        ws2.cell(row=row, column=8, value=session["daily_report"] or "—")
    
    # Расходы
    ws3 = wb.create_sheet("Расходы")
    headers = ["Дата", "Сумма", "Описание", "Статус"]
    for col, header in enumerate(headers, 1):
        cell = ws3.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    expenses_list = get_expenses_for_period_by_date_list(user_id, start_date, end_date)
    for row, expense in enumerate(expenses_list, 2):
        ws3.cell(row=row, column=1, value=expense["created_at"][:10] if expense["created_at"] else "")
        ws3.cell(row=row, column=2, value=f"{expense['amount']:,} ₴")
        ws3.cell(row=row, column=3, value=expense["description"])
        status = "Подтверждён" if expense["status"] == "approved" else ("Отклонён" if expense["status"] == "rejected" else "Ожидает")
        ws3.cell(row=row, column=4, value=status)
    
    # Выплаты
    ws4 = wb.create_sheet("Выплаты")
    headers = ["Дата", "Сумма", "Статус"]
    for col, header in enumerate(headers, 1):
        cell = ws4.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    payments_list = get_payments_for_period_by_date_list(user_id, start_date, end_date)
    for row, payment in enumerate(payments_list, 2):
        ws4.cell(row=row, column=1, value=payment["created_at"][:10] if payment["created_at"] else "")
        ws4.cell(row=row, column=2, value=f"{payment['amount']:,} ₴")
        status = "Подтверждена" if payment["status"] == "confirmed" else ("Отклонена" if payment["status"] == "rejected" else "Ожидает")
        ws4.cell(row=row, column=3, value=status)
    
    for col in range(1, 9):
        ws2.column_dimensions[get_column_letter(col)].width = 12
    for col in range(1, 5):
        ws3.column_dimensions[get_column_letter(col)].width = 15
        ws4.column_dimensions[get_column_letter(col)].width = 15
    
    # Сохраняем
    os.makedirs(f"archives/{year}", exist_ok=True)
    filename = f"archives/{year}/{month:02d}_{username}.xlsx"
    wb.save(filename)
    return filename

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