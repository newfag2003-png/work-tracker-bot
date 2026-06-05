import sqlite3
import os
from datetime import datetime
import time
import gspread
from google.oauth2.service_account import Credentials
import json

DB_PATH = "data/work_tracker.db"

# ============= НАСТРОЙКА GOOGLE SHEETS =============
# Настройка Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = "1ioTxs9llMd6oEzvxrG6UQ9vVi4EkO3Y2Ecda_FuG2Aw"  # ВАШ ID

def get_db_connection():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetch_one=False, fetch_all=False, retries=3):
    for attempt in range(retries):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.execute(query, params)
            conn.commit()
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return cursor.lastrowid if cursor.lastrowid else True
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < retries - 1:
                time.sleep(1)
                continue
            raise e
        finally:
            if conn:
                conn.close()
    return None

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'employee',
            hourly_rate INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_balance (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_expenses INTEGER DEFAULT 0,
            total_paid INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            object_name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            is_night BOOLEAN DEFAULT 0,
            earnings INTEGER,
            daily_report TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            description TEXT,
            photo_file_id TEXT,
            status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            rejected_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            confirmed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            old_rate INTEGER,
            new_rate INTEGER,
            changed_by INTEGER,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            is_hidden BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    default_objects = ["Склад №3", "Офис", "Завод"]
    for obj in default_objects:
        cursor.execute("INSERT OR IGNORE INTO objects (name) VALUES (?)", (obj,))
    
    conn.commit()
    conn.close()
    print("✅ База данных создана!")

# ============= ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ =============

def user_exists(user_id: int) -> bool:
    result = execute_query("SELECT 1 FROM users WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result is not None

def register_user(user_id: int, username: str):
    from config import DEFAULT_HOURLY_RATE
    execute_query("INSERT INTO users (user_id, username, hourly_rate) VALUES (?, ?, ?)", 
                  (int(user_id), username, DEFAULT_HOURLY_RATE))
    execute_query("INSERT INTO user_balance (user_id) VALUES (?)", (int(user_id),))

def get_hourly_rate(user_id: int) -> int:
    result = execute_query("SELECT hourly_rate FROM users WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result["hourly_rate"] if result else 200

def set_hourly_rate(user_id: int, new_rate: int, admin_id: int):
    execute_query("UPDATE users SET hourly_rate = ? WHERE user_id = ?", (new_rate, int(user_id)))

def get_user(user_id: int):
    return execute_query("SELECT * FROM users WHERE user_id = ?", (int(user_id),), fetch_one=True)

def get_user_by_name(username: str):
    return execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)

def get_all_users():
    return execute_query("SELECT * FROM users WHERE role = 'employee'", fetch_all=True) or []

def get_balance(user_id: int) -> int:
    result = execute_query("SELECT balance FROM user_balance WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result["balance"] if result else 0

def get_total_earned(user_id: int) -> int:
    result = execute_query("SELECT total_earned FROM user_balance WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result["total_earned"] if result else 0

def get_total_expenses(user_id: int) -> int:
    result = execute_query("SELECT total_expenses FROM user_balance WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result["total_expenses"] if result else 0

def get_total_paid(user_id: int) -> int:
    result = execute_query("SELECT total_paid FROM user_balance WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result["total_paid"] if result else 0

def update_balance(user_id: int, earnings_change: int = 0, expenses_change: int = 0, paid_change: int = 0):
    conn = get_db_connection()
    try:
        current = conn.execute("SELECT * FROM user_balance WHERE user_id = ?", (int(user_id),)).fetchone()
        new_balance = current["balance"] + earnings_change + expenses_change - paid_change
        new_total_earned = current["total_earned"] + earnings_change
        new_total_expenses = current["total_expenses"] + expenses_change
        new_total_paid = current["total_paid"] + paid_change
        conn.execute("""
            UPDATE user_balance 
            SET balance = ?, total_earned = ?, total_expenses = ?, total_paid = ?, last_updated = ?
            WHERE user_id = ?
        """, (new_balance, new_total_earned, new_total_expenses, new_total_paid, datetime.now(), int(user_id)))
        conn.commit()
        return new_balance
    finally:
        conn.close()

# ============= РАБОЧИЕ СЕССИИ =============

def save_work_session(user_id: int, object_name: str, start_time, end_time, duration: int, is_night: bool, earnings: int, report: str):
    return execute_query("""
        INSERT INTO work_sessions (user_id, object_name, start_time, end_time, duration, is_night, earnings, daily_report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (int(user_id), object_name, start_time, end_time, duration, is_night, earnings, report))

def get_last_session(user_id: int):
    return execute_query("""
        SELECT * FROM work_sessions 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 1
    """, (int(user_id),), fetch_one=True)

def get_sessions_for_period(user_id: int, days: int = 30):
    return execute_query("""
        SELECT * FROM work_sessions 
        WHERE user_id = ? AND created_at > date('now', ?)
        ORDER BY start_time DESC
    """, (int(user_id), f'-{days} days'), fetch_all=True) or []

def get_sessions_for_edit(user_id: int):
    return execute_query("""
        SELECT * FROM work_sessions 
        WHERE user_id = ? AND created_at > date('now', '-2 days')
        ORDER BY start_time DESC
    """, (int(user_id),), fetch_all=True) or []

def delete_work_session(session_id: int):
    return execute_query("DELETE FROM work_sessions WHERE id = ?", (session_id,))

def update_work_session(session_id: int, start_time, end_time, duration: int, is_night: bool, earnings: int, object_name: str, report: str = None):
    if report:
        return execute_query("""
            UPDATE work_sessions 
            SET start_time = ?, end_time = ?, duration = ?, is_night = ?, earnings = ?, object_name = ?, daily_report = ?
            WHERE id = ?
        """, (start_time, end_time, duration, is_night, earnings, object_name, report, session_id))
    else:
        return execute_query("""
            UPDATE work_sessions 
            SET start_time = ?, end_time = ?, duration = ?, is_night = ?, earnings = ?, object_name = ?
            WHERE id = ?
        """, (start_time, end_time, duration, is_night, earnings, object_name, session_id))

def get_objects():
    objects = execute_query("SELECT name FROM objects WHERE is_hidden = 0 ORDER BY name", fetch_all=True)
    if objects:
        return [obj["name"] for obj in objects]
    return []

def add_object(name: str):
    return execute_query("INSERT OR IGNORE INTO objects (name) VALUES (?)", (name,))

def hide_object(name: str):
    return execute_query("UPDATE objects SET is_hidden = 1 WHERE name = ?", (name,))

def get_last_used_object(user_id: int):
    result = execute_query("""
        SELECT object_name FROM work_sessions 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 1
    """, (int(user_id),), fetch_one=True)
    return result["object_name"] if result else None

def get_hourly_rate(user_id: int) -> int:
    user = execute_query("SELECT hourly_rate FROM users WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return user["hourly_rate"] if user else 100

def set_hourly_rate(user_id: int, new_rate: int, changed_by: int):
    old_rate = get_hourly_rate(user_id)
    execute_query("UPDATE users SET hourly_rate = ? WHERE user_id = ?", (new_rate, int(user_id)))
    execute_query("""
        INSERT INTO rate_history (user_id, old_rate, new_rate, changed_by)
        VALUES (?, ?, ?, ?)
    """, (int(user_id), old_rate, new_rate, changed_by))

def add_expense(user_id: int, amount: int, description: str, photo_file_id: str = None):
    return execute_query("""
        INSERT INTO expenses (user_id, amount, description, photo_file_id)
        VALUES (?, ?, ?, ?)
    """, (int(user_id), amount, description, photo_file_id))

def get_pending_expenses():
    return execute_query("""
        SELECT e.*, u.username 
        FROM expenses e
        JOIN users u ON e.user_id = u.user_id
        WHERE e.status = 'pending'
        ORDER BY e.created_at DESC
    """, fetch_all=True) or []

def approve_expense(expense_id: int, admin_id: int):
    conn = get_db_connection()
    try:
        expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if expense and expense["status"] == "pending":
            conn.execute("UPDATE expenses SET status = 'approved', approved_by = ? WHERE id = ?", (admin_id, expense_id))
            conn.commit()
            conn.close()
            update_balance(expense["user_id"], expenses_change=expense["amount"])
            return expense
        conn.close()
        return None
    except Exception as e:
        conn.close()
        raise e

def reject_expense(expense_id: int, admin_id: int, reason: str):
    return execute_query("""
        UPDATE expenses SET status = 'rejected', approved_by = ?, rejected_reason = ? WHERE id = ?
    """, (admin_id, reason, expense_id))

def get_expense_by_id(expense_id: int):
    return execute_query("SELECT * FROM expenses WHERE id = ?", (expense_id,), fetch_one=True)

def add_salary_payment(user_id: int, amount: int):
    return execute_query("""
        INSERT INTO salary_payments (user_id, amount, status)
        VALUES (?, ?, 'pending')
    """, (int(user_id), amount))

def get_pending_payments(user_id: int = None):
    if user_id:
        return execute_query("""
            SELECT * FROM salary_payments 
            WHERE user_id = ? AND status = 'pending'
        """, (int(user_id),), fetch_all=True) or []
    else:
        return execute_query("""
            SELECT * FROM salary_payments 
            WHERE status = 'pending'
        """, fetch_all=True) or []

def confirm_salary_payment(payment_id: int):
    conn = get_db_connection()
    try:
        payment = conn.execute("SELECT * FROM salary_payments WHERE id = ?", (payment_id,)).fetchone()
        if payment and payment["status"] == "pending":
            conn.execute("""
                UPDATE salary_payments 
                SET status = 'confirmed', confirmed_at = ? 
                WHERE id = ?
            """, (datetime.now(), payment_id))
            conn.commit()
            conn.close()
            update_balance(payment["user_id"], paid_change=payment["amount"])
            return True
        conn.close()
        return False
    except Exception as e:
        conn.close()
        raise e

def reject_salary_payment(payment_id: int):
    return execute_query("UPDATE salary_payments SET status = 'rejected' WHERE id = ?", (payment_id,))

def get_salary_payment_by_id(payment_id: int):
    return execute_query("SELECT * FROM salary_payments WHERE id = ?", (payment_id,), fetch_one=True)

def get_all_objects_with_status():
    result = execute_query("SELECT id, name, is_hidden FROM objects ORDER BY name", fetch_all=True) or []
    return [{"id": r["id"], "name": r["name"], "is_hidden": r["is_hidden"]} for r in result]

def show_object(object_id: int):
    return execute_query("UPDATE objects SET is_hidden = 0 WHERE id = ?", (object_id,))

def delete_object(object_id: int):
    return execute_query("DELETE FROM objects WHERE id = ?", (object_id,))

def get_object_usage_stats(object_id: int):
    stats = execute_query("""
        SELECT 
            COUNT(*) as sessions_count,
            SUM(duration) as total_seconds,
            SUM(earnings) as total_earned
        FROM work_sessions 
        WHERE object_name = (SELECT name FROM objects WHERE id = ?)
    """, (object_id,), fetch_one=True)
    return stats

def object_exists(object_name: str) -> bool:
    result = execute_query(
        "SELECT 1 FROM objects WHERE name = ? AND is_hidden = 0",
        (object_name,),
        fetch_one=True
    )
    return result is not None

def update_work_session_time(session_id: int, start_time, end_time, duration: int, is_night: bool, earnings: int):
    return execute_query("""
        UPDATE work_sessions 
        SET start_time = ?, end_time = ?, duration = ?, is_night = ?, earnings = ?
        WHERE id = ?
    """, (start_time, end_time, duration, is_night, earnings, session_id))

def update_work_session_object(session_id: int, object_name: str):
    return execute_query("""
        UPDATE work_sessions 
        SET object_name = ?
        WHERE id = ?
    """, (object_name, session_id))

def update_work_session_report(session_id: int, report: str):
    return execute_query("""
        UPDATE work_sessions 
        SET daily_report = ?
        WHERE id = ?
    """, (report, session_id))

# ============= ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ =============

def get_weekly_stats(user_id: int, days: int = 7):
    sessions = get_sessions_for_period(user_id, days)
    total_hours = sum(s["duration"] for s in sessions) / 3600 if sessions else 0
    total_earned = sum(s["earnings"] for s in sessions) if sessions else 0
    night_sessions = len([s for s in sessions if s["is_night"]]) if sessions else 0
    work_days = len(set(s["start_time"][:10] for s in sessions)) if sessions else 0
    
    objects_count = {}
    for s in sessions:
        obj = s["object_name"]
        objects_count[obj] = objects_count.get(obj, 0) + 1
    
    top_object = max(objects_count.items(), key=lambda x: x[1])[0] if objects_count else "—"
    
    return {
        "total_hours": total_hours,
        "total_earned": total_earned,
        "night_sessions": night_sessions,
        "work_days": work_days,
        "top_object": top_object,
        "sessions_count": len(sessions)
    }

def get_weekly_expenses(user_id: int, days: int = 7):
    conn = get_db_connection()
    try:
        expenses = conn.execute("""
            SELECT SUM(amount) as total_amount, COUNT(*) as count
            FROM expenses 
            WHERE user_id = ? AND status = 'approved' AND created_at > date('now', ?)
        """, (int(user_id), f'-{days} days')).fetchone()
        return expenses["total_amount"] if expenses and expenses["total_amount"] else 0
    finally:
        conn.close()

def get_weekly_payments(user_id: int, days: int = 7):
    conn = get_db_connection()
    try:
        payments = conn.execute("""
            SELECT SUM(amount) as total_amount, COUNT(*) as count
            FROM salary_payments 
            WHERE user_id = ? AND status = 'confirmed' AND created_at > date('now', ?)
        """, (int(user_id), f'-{days} days')).fetchone()
        return payments["total_amount"] if payments and payments["total_amount"] else 0
    finally:
        conn.close()

# ============= ФУНКЦИИ ДЛЯ АРХИВА (ОТЧЁТЫ) =============

def get_sessions_for_month(user_id: int, year: int, month: int):
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    return execute_query("""
        SELECT * FROM work_sessions 
        WHERE user_id = ? AND start_time >= ? AND start_time < ?
        ORDER BY start_time ASC
    """, (int(user_id), start_date, end_date), fetch_all=True) or []

def get_expenses_for_period_by_date(user_id: int, start_date: str, end_date: str):
    result = execute_query("""
        SELECT SUM(amount) as total FROM expenses 
        WHERE user_id = ? AND status = 'approved' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0

def get_payments_for_period_by_date(user_id: int, start_date: str, end_date: str):
    result = execute_query("""
        SELECT SUM(amount) as total FROM salary_payments 
        WHERE user_id = ? AND status = 'confirmed' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0

def get_expenses_for_period_by_date_list(user_id: int, start_date: str, end_date: str):
    return execute_query("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
    """, (int(user_id), start_date, end_date), fetch_all=True) or []

def get_payments_for_period_by_date_list(user_id: int, start_date: str, end_date: str):
    return execute_query("""
        SELECT * FROM salary_payments 
        WHERE user_id = ? AND created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
    """, (int(user_id), start_date, end_date), fetch_all=True) or []

# ============= ОТЧЁТЫ ДЛЯ АДМИНА =============

def get_all_objects_stats_all_time():
    sessions = execute_query("""
        SELECT u.username, ws.object_name, SUM(ws.duration) as total_seconds, 
               SUM(ws.earnings) as total_earned, COUNT(*) as count
        FROM work_sessions ws
        JOIN users u ON ws.user_id = u.user_id
        GROUP BY u.username, ws.object_name
        ORDER BY u.username, total_seconds DESC
    """, fetch_all=True) or []
    
    result = {}
    for s in sessions:
        username = s["username"]
        if username not in result:
            result[username] = []
        result[username].append({
            "object_name": s["object_name"],
            "hours": s["total_seconds"] / 3600,
            "earned": s["total_earned"],
            "count": s["count"]
        })
    return result

def get_expenses_stats_last_30_days():
    expenses = execute_query("""
        SELECT u.username, e.amount, e.description, e.status, e.created_at
        FROM expenses e
        JOIN users u ON e.user_id = u.user_id
        WHERE e.created_at > date('now', '-30 days')
        ORDER BY e.created_at DESC
    """, fetch_all=True) or []
    
    total_approved = sum(e["amount"] for e in expenses if e["status"] == "approved")
    total_pending = sum(e["amount"] for e in expenses if e["status"] == "pending")
    total_rejected = sum(e["amount"] for e in expenses if e["status"] == "rejected")
    
    return {
        "expenses": expenses,
        "total_approved": total_approved,
        "total_pending": total_pending,
        "total_rejected": total_rejected
    }

def get_payments_stats_last_30_days():
    payments = execute_query("""
        SELECT u.username, p.amount, p.status, p.created_at
        FROM salary_payments p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.created_at > date('now', '-30 days')
        ORDER BY p.created_at DESC
    """, fetch_all=True) or []
    
    total_confirmed = sum(p["amount"] for p in payments if p["status"] == "confirmed")
    total_pending = sum(p["amount"] for p in payments if p["status"] == "pending")
    total_rejected = sum(p["amount"] for p in payments if p["status"] == "rejected")
    
    return {
        "payments": payments,
        "total_confirmed": total_confirmed,
        "total_pending": total_pending,
        "total_rejected": total_rejected
    }

def get_forecast_stats_30_days():
    sessions = execute_query("""
        SELECT SUM(duration) as total_seconds, SUM(earnings) as total_earned, COUNT(*) as count
        FROM work_sessions 
        WHERE created_at > date('now', '-30 days')
    """, fetch_one=True)
    
    current_hours = sessions["total_seconds"] / 3600 if sessions and sessions["total_seconds"] else 0
    current_earned = sessions["total_earned"] if sessions and sessions["total_earned"] else 0
    days_with_data = sessions["count"] if sessions and sessions["count"] else 0
    
    if days_with_data > 0:
        avg_hours_per_day = current_hours / days_with_data
        avg_earned_per_day = current_earned / days_with_data
        forecast_hours_30d = avg_hours_per_day * 30
        forecast_earned_30d = avg_earned_per_day * 30
    else:
        avg_hours_per_day = 0
        avg_earned_per_day = 0
        forecast_hours_30d = 0
        forecast_earned_30d = 0
    
    return {
        "avg_hours_per_day": avg_hours_per_day,
        "avg_earned_per_day": avg_earned_per_day,
        "current_hours": current_hours,
        "current_earned": current_earned,
        "days_with_data": days_with_data,
        "forecast_hours_30d": forecast_hours_30d,
        "forecast_earned_30d": forecast_earned_30d
    }

# ============= АВТОМАТИЧЕСКАЯ ОТМЕНА =============

def auto_cancel_expired_expenses():
    from datetime import datetime, timedelta
    expiration_time = datetime.now() - timedelta(hours=24)
    
    expenses = execute_query("""
        SELECT * FROM expenses 
        WHERE status = 'pending' 
        AND created_at < ?
    """, (expiration_time,), fetch_all=True) or []
    
    cancelled_count = 0
    for expense in expenses:
        execute_query("""
            UPDATE expenses 
            SET status = 'rejected', 
                rejected_reason = 'Автоматическая отмена: не подтверждён в течение 24 часов'
            WHERE id = ?
        """, (expense["id"],))
        cancelled_count += 1
    
    return expenses, cancelled_count

def auto_cancel_expired_payments():
    from datetime import datetime, timedelta
    expiration_time = datetime.now() - timedelta(hours=24)
    
    payments = execute_query("""
        SELECT * FROM salary_payments 
        WHERE status = 'pending' 
        AND created_at < ?
    """, (expiration_time,), fetch_all=True) or []
    
    cancelled_count = 0
    for payment in payments:
        execute_query("""
            UPDATE salary_payments 
            SET status = 'rejected'
            WHERE id = ?
        """, (payment["id"],))
        cancelled_count += 1
    
    return payments, cancelled_count

# ============= БЭКАП В GOOGLE SHEETS =============

def get_gsheet_client():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if os.path.exists(creds_path):
            creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        else:
            print("⚠️ Файл credentials.json не найден")
            return None
    return gspread.authorize(creds)

def backup_to_google_sheets():
    """Полная синхронизация данных в Google Sheets (актуальное состояние)"""
    print("🔍 Начинаем бэкап...")
    
    try:
        client = get_gsheet_client()
        if not client:
            print("❌ Не удалось подключиться к Google Sheets")
            return False
        
        sheet = client.open_by_key(SHEET_ID)
        from database import execute_query
        
        # 1. Бэкап users (сотрудники)
        users = get_all_users()
        print(f"📊 Сотрудники: {len(users)}")
        try:
            ws = sheet.worksheet('Сотрудники')
        except:
            ws = sheet.add_worksheet(title='Сотрудники', rows=100, cols=20)
        ws.clear()
        ws.append_row(['ID', 'Имя', 'Роль', 'Ставка (₴/ч)', 'Дата регистрации', 'Дата обновления'])
        for user in users:
            ws.append_row([
                user['user_id'], 
                user['username'], 
                user['role'] == 'admin' and 'Администратор' or 'Сотрудник', 
                user['hourly_rate'], 
                user['created_at'],
                datetime.now().isoformat()
            ])
        
        # 2. Бэкап work_sessions (рабочие смены)
        sessions = execute_query("SELECT * FROM work_sessions ORDER BY id ASC", fetch_all=True) or []
        print(f"📊 Рабочие смены: {len(sessions)}")
        try:
            ws = sheet.worksheet('Рабочие смены')
        except:
            ws = sheet.add_worksheet(title='Рабочие смены', rows=100000, cols=20)
        ws.clear()
        ws.append_row([
            'ID', 'ID сотрудника', 'Объект', 'Начало', 'Окончание', 
            'Длительность (сек)', 'Ночная смена', 'Заработано (₴)', 'Отчёт', 'Дата создания', 'Дата обновления'
        ])
        for session in sessions:
            ws.append_row([
                session['id'],
                session['user_id'], 
                session['object_name'], 
                session['start_time'], 
                session['end_time'],
                session['duration'], 
                'Да' if session['is_night'] else 'Нет', 
                session['earnings'], 
                session['daily_report'] or '', 
                session['created_at'],
                datetime.now().isoformat()
            ])
        
        # 3. Бэкап expenses (расходы)
        expenses = execute_query("SELECT * FROM expenses ORDER BY id ASC", fetch_all=True) or []
        print(f"📊 Расходы: {len(expenses)}")
        try:
            ws = sheet.worksheet('Расходы')
        except:
            ws = sheet.add_worksheet(title='Расходы', rows=100000, cols=20)
        ws.clear()
        ws.append_row([
            'ID', 'ID сотрудника', 'Сумма (₴)', 'Описание', 'Фото чека', 
            'Статус', 'Кто подтвердил', 'Причина отклонения', 'Дата создания', 'Дата обновления'
        ])
        for expense in expenses:
            status_text = ''
            if expense['status'] == 'approved':
                status_text = '✅ Подтверждён'
            elif expense['status'] == 'rejected':
                status_text = '❌ Отклонён'
            else:
                status_text = '⏳ Ожидает'
            
            ws.append_row([
                expense['id'],
                expense['user_id'], 
                expense['amount'], 
                expense['description'], 
                expense['photo_file_id'] or '',
                status_text, 
                expense['approved_by'] or '',
                expense['rejected_reason'] or '', 
                expense['created_at'],
                datetime.now().isoformat()
            ])
        
        # 4. Бэкап salary_payments (выплаты зарплаты)
        payments = execute_query("SELECT * FROM salary_payments ORDER BY id ASC", fetch_all=True) or []
        print(f"📊 Выплаты: {len(payments)}")
        try:
            ws = sheet.worksheet('Выплаты')
        except:
            ws = sheet.add_worksheet(title='Выплаты', rows=100000, cols=20)
        ws.clear()
        ws.append_row([
            'ID', 'ID сотрудника', 'Сумма (₴)', 'Статус', 'Дата подтверждения', 'Дата создания', 'Дата обновления'
        ])
        for payment in payments:
            status_text = ''
            if payment['status'] == 'confirmed':
                status_text = '✅ Подтверждена'
            elif payment['status'] == 'rejected':
                status_text = '❌ Отклонена'
            else:
                status_text = '⏳ Ожидает'
            
            ws.append_row([
                payment['id'],
                payment['user_id'], 
                payment['amount'], 
                status_text, 
                payment['confirmed_at'] or '',
                payment['created_at'],
                datetime.now().isoformat()
            ])
        
        # 5. Бэкап objects (объекты работы)
        objects = execute_query("SELECT * FROM objects ORDER BY id ASC", fetch_all=True) or []
        print(f"📊 Объекты: {len(objects)}")
        try:
            ws = sheet.worksheet('Объекты')
        except:
            ws = sheet.add_worksheet(title='Объекты', rows=1000, cols=20)
        ws.clear()
        ws.append_row(['ID', 'Название', 'Скрыт', 'Дата создания', 'Дата обновления'])
        for obj in objects:
            ws.append_row([
                obj['id'],
                obj['name'], 
                'Да' if obj['is_hidden'] else 'Нет', 
                obj['created_at'],
                datetime.now().isoformat()
            ])
        
        print(f"✅ Бэкап в Google Sheets выполнен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка бэкапа: {e}")
        import traceback
        traceback.print_exc()
        return False
    

def get_active_session(user_id: int):
    """Проверяет, есть ли у пользователя незавершённая смена (без отчёта)"""
    query = """
        SELECT * FROM work_sessions 
        WHERE user_id = ? AND (daily_report IS NULL OR daily_report = '')
        ORDER BY start_time DESC LIMIT 1
    """
    result = execute_query(query, (user_id,), fetch_one=True)
    return result