import sqlite3
import os
from datetime import datetime
import time

DB_PATH = "data/work_tracker.db"

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
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'employee',
            hourly_rate INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица баланса
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
    
    # Рабочие сессии
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
    
    # Расходы
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
    
    # Выплаты зарплаты
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
    
    # История ставок
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
    
    # Объекты работы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            is_hidden BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Месячная сводка (архив для сотрудника)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            month VARCHAR(7),
            total_hours REAL,
            total_earned INTEGER,
            total_expenses INTEGER,
            total_paid INTEGER,
            closing_balance INTEGER,
            excel_file_path TEXT,
            UNIQUE(user_id, month),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Общая месячная сводка (архив для админа)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_monthly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month VARCHAR(7),
            total_employees INTEGER,
            total_hours REAL,
            total_earned INTEGER,
            total_expenses INTEGER,
            total_paid INTEGER,
            total_balance INTEGER,
            excel_file_path TEXT,
            UNIQUE(month)
        )
    """)
    
    # Годовая сводка (для сотрудника)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS yearly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            year INTEGER,
            total_hours REAL,
            total_earned INTEGER,
            total_expenses INTEGER,
            total_paid INTEGER,
            closing_balance INTEGER,
            UNIQUE(user_id, year),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Общая годовая сводка (для админа)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_yearly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            total_employees INTEGER,
            total_hours REAL,
            total_earned INTEGER,
            total_expenses INTEGER,
            total_paid INTEGER,
            total_balance INTEGER,
            UNIQUE(year)
        )
    """)
    
    # Добавляем объекты по умолчанию
    default_objects = ["Склад №3", "Офис", "Завод"]
    for obj in default_objects:
        cursor.execute("INSERT OR IGNORE INTO objects (name) VALUES (?)", (obj,))
    
    conn.commit()
    conn.close()
    print("✅ База данных создана!")

def user_exists(user_id: int) -> bool:
    result = execute_query("SELECT 1 FROM users WHERE user_id = ?", (int(user_id),), fetch_one=True)
    return result is not None

def register_user(user_id: int, username: str):
    execute_query("INSERT INTO users (user_id, username) VALUES (?, ?)", (int(user_id), username))
    execute_query("INSERT INTO user_balance (user_id) VALUES (?)", (int(user_id),))

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
    """Получить только видимые объекты (не скрытые)"""
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

def get_expenses_for_period(user_id: int, days: int = 30):
    return execute_query("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND created_at > date('now', ?)
        ORDER BY created_at DESC
    """, (int(user_id), f'-{days} days'), fetch_all=True) or []

def get_payments_for_period(user_id: int, days: int = 30):
    return execute_query("""
        SELECT * FROM salary_payments 
        WHERE user_id = ? AND created_at > date('now', ?)
        ORDER BY created_at DESC
    """, (int(user_id), f'-{days} days'), fetch_all=True) or []

# ============= ФУНКЦИИ ДЛЯ ЕЖЕНЕДЕЛЬНОГО ОТЧЁТА =============

def get_weekly_stats(user_id: int, days: int = 7):
    """Получить статистику за неделю"""
    sessions = get_sessions_for_period(user_id, days)
    
    total_hours = sum(s["duration"] for s in sessions) / 3600 if sessions else 0
    total_earned = sum(s["earnings"] for s in sessions) if sessions else 0
    night_sessions = len([s for s in sessions if s["is_night"]]) if sessions else 0
    work_days = len(set(s["start_time"][:10] for s in sessions)) if sessions else 0
    
    # Статистика по объектам
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
    """Получить расходы за неделю"""
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
    """Получить выплаты за неделю"""
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

# ============= ФУНКЦИИ ДЛЯ АРХИВА =============

def get_available_months(user_id: int):
    """Получить список доступных месяцев для отчётов сотрудника"""
    sessions = get_sessions_for_period(user_id, 365)  # за последний год
    months = set()
    for session in sessions:
        month = session["start_time"][:7]  # "2026-05"
        months.add(month)
    return sorted(list(months), reverse=True)

def get_available_years(user_id: int):
    """Получить список доступных годов для отчётов сотрудника"""
    months = get_available_months(user_id)
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    return years

def get_global_available_months():
    """Получить список доступных месяцев для отчётов админа"""
    users = get_all_users()
    all_months = set()
    for user in users:
        months = get_available_months(user["user_id"])
        all_months.update(months)
    return sorted(list(all_months), reverse=True)

def get_global_available_years():
    """Получить список доступных годов для отчётов админа"""
    months = get_global_available_months()
    years = sorted(set(int(m[:4]) for m in months), reverse=True)
    return years

def get_monthly_summary(user_id: int, year: int, month: int):
    """Получить сводку за месяц для сотрудника (из архива)"""
    month_str = f"{year}-{month:02d}"
    return execute_query("""
        SELECT * FROM monthly_summary 
        WHERE user_id = ? AND month = ?
    """, (int(user_id), month_str), fetch_one=True)

def get_yearly_summary(user_id: int, year: int):
    """Получить годовую сводку для сотрудника"""
    return execute_query("""
        SELECT * FROM yearly_summary 
        WHERE user_id = ? AND year = ?
    """, (int(user_id), year), fetch_one=True)

def get_global_monthly_summary(year: int, month: int):
    """Получить общую сводку за месяц для админа"""
    month_str = f"{year}-{month:02d}"
    return execute_query("""
        SELECT * FROM global_monthly_summary 
        WHERE month = ?
    """, (month_str,), fetch_one=True)

def get_global_yearly_summary(year: int):
    """Получить общую годовую сводку для админа"""
    return execute_query("""
        SELECT * FROM global_yearly_summary 
        WHERE year = ?
    """, (year,), fetch_one=True)

def save_monthly_summary(user_id: int, month: str, total_hours: float, total_earned: int, 
                         total_expenses: int, total_paid: int, closing_balance: int, excel_path: str = None):
    """Сохранить месячную сводку для сотрудника"""
    return execute_query("""
        INSERT OR REPLACE INTO monthly_summary 
        (user_id, month, total_hours, total_earned, total_expenses, total_paid, closing_balance, excel_file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (int(user_id), month, total_hours, total_earned, total_expenses, total_paid, closing_balance, excel_path))

def save_global_monthly_summary(month: str, total_employees: int, total_hours: float, 
                                total_earned: int, total_expenses: int, total_paid: int, 
                                total_balance: int, excel_path: str = None):
    """Сохранить общую месячную сводку для админа"""
    return execute_query("""
        INSERT OR REPLACE INTO global_monthly_summary 
        (month, total_employees, total_hours, total_earned, total_expenses, total_paid, total_balance, excel_file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (month, total_employees, total_hours, total_earned, total_expenses, total_paid, total_balance, excel_path))

def delete_sessions_for_month(year: int, month: int):
    """Удалить рабочие сессии за месяц"""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    return execute_query("""
        DELETE FROM work_sessions 
        WHERE start_time >= ? AND start_time < ?
    """, (start_date, end_date))

def aggregate_yearly_data(year: int):
    """Агрегировать данные за год в годовую сводку"""
    # Получаем все месячные сводки за год
    summaries = execute_query("""
        SELECT * FROM monthly_summary 
        WHERE month LIKE ?
        ORDER BY user_id, month
    """, (f"{year}-%",), fetch_all=True) or []
    
    # Группируем по пользователям
    user_data = {}
    for summary in summaries:
        user_id = summary["user_id"]
        if user_id not in user_data:
            user_data[user_id] = {
                "total_hours": 0,
                "total_earned": 0,
                "total_expenses": 0,
                "total_paid": 0,
                "closing_balance": 0
            }
        user_data[user_id]["total_hours"] += summary["total_hours"]
        user_data[user_id]["total_earned"] += summary["total_earned"]
        user_data[user_id]["total_expenses"] += summary["total_expenses"]
        user_data[user_id]["total_paid"] += summary["total_paid"]
        user_data[user_id]["closing_balance"] = summary["closing_balance"]
    
    # Сохраняем годовые сводки
    for user_id, data in user_data.items():
        execute_query("""
            INSERT OR REPLACE INTO yearly_summary 
            (user_id, year, total_hours, total_earned, total_expenses, total_paid, closing_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (int(user_id), year, data["total_hours"], data["total_earned"], 
              data["total_expenses"], data["total_paid"], data["closing_balance"]))
    
    # Общая годовая сводка для админа
    total_employees = len(user_data)
    total_hours = sum(d["total_hours"] for d in user_data.values())
    total_earned = sum(d["total_earned"] for d in user_data.values())
    total_expenses = sum(d["total_expenses"] for d in user_data.values())
    total_paid = sum(d["total_paid"] for d in user_data.values())
    total_balance = sum(d["closing_balance"] for d in user_data.values())
    
    execute_query("""
        INSERT OR REPLACE INTO global_yearly_summary 
        (year, total_employees, total_hours, total_earned, total_expenses, total_paid, total_balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (year, total_employees, total_hours, total_earned, total_expenses, total_paid, total_balance))
    
    return len(user_data)

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

# ============= ФУНКЦИИ ДЛЯ ЭКСПОРТА =============

def get_expenses_for_period_by_date(user_id: int, start_date: str, end_date: str):
    """Получить сумму расходов за период по датам"""
    result = execute_query("""
        SELECT SUM(amount) as total FROM expenses 
        WHERE user_id = ? AND status = 'approved' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0

def get_payments_for_period_by_date(user_id: int, start_date: str, end_date: str):
    """Получить сумму выплат за период по датам"""
    result = execute_query("""
        SELECT SUM(amount) as total FROM salary_payments 
        WHERE user_id = ? AND status = 'confirmed' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0

def get_expenses_for_period_by_date_list(user_id: int, start_date: str, end_date: str):
    """Получить список расходов за период по датам"""
    return execute_query("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
    """, (int(user_id), start_date, end_date), fetch_all=True) or []

def get_payments_for_period_by_date_list(user_id: int, start_date: str, end_date: str):
    """Получить список выплат за период по датам"""
    return execute_query("""
        SELECT * FROM salary_payments 
        WHERE user_id = ? AND created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
    """, (int(user_id), start_date, end_date), fetch_all=True) or []

# ============= АВТОМАТИЧЕСКАЯ ОТМЕНА =============

def auto_cancel_expired_expenses():
    """Автоматически отменяет расходы, ожидающие подтверждения более 24 часов"""
    from datetime import datetime, timedelta
    
    expiration_time = datetime.now() - timedelta(hours=24)
    
    # Находим расходы, которые висят более 24 часов
    expenses = execute_query("""
        SELECT * FROM expenses 
        WHERE status = 'pending' 
        AND created_at < ?
    """, (expiration_time,), fetch_all=True) or []
    
    cancelled_count = 0
    for expense in expenses:
        # Отменяем расход
        execute_query("""
            UPDATE expenses 
            SET status = 'rejected', 
                rejected_reason = 'Автоматическая отмена: не подтверждён в течение 24 часов'
            WHERE id = ?
        """, (expense["id"],))
        cancelled_count += 1
    
    return expenses, cancelled_count


def auto_cancel_expired_payments():
    """Автоматически отменяет выплаты, ожидающие подтверждения более 24 часов"""
    from datetime import datetime, timedelta
    
    expiration_time = datetime.now() - timedelta(hours=24)
    
    # Находим выплаты, которые висят более 24 часов
    payments = execute_query("""
        SELECT * FROM salary_payments 
        WHERE status = 'pending' 
        AND created_at < ?
    """, (expiration_time,), fetch_all=True) or []
    
    cancelled_count = 0
    for payment in payments:
        # Отменяем выплату
        execute_query("""
            UPDATE salary_payments 
            SET status = 'rejected'
            WHERE id = ?
        """, (payment["id"],))
        cancelled_count += 1
    
    return payments, cancelled_count


def get_expired_expenses_for_notification():
    """Получить список расходов, которые были автоматически отменены"""
    from datetime import datetime, timedelta
    
    expiration_time = datetime.now() - timedelta(hours=24)
    
    return execute_query("""
        SELECT e.*, u.username 
        FROM expenses e
        JOIN users u ON e.user_id = u.user_id
        WHERE e.status = 'rejected' 
        AND e.rejected_reason = 'Автоматическая отмена: не подтверждён в течение 24 часов'
        AND e.created_at < ?
    """, (expiration_time,), fetch_all=True) or []

# ============= АРХИВАЦИЯ =============

def archive_old_data():
    """Архивация данных за прошлый месяц (1-го числа)"""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    
    # Определяем прошлый месяц
    if now.month == 1:
        year = now.year - 1
        month = 12
    else:
        year = now.year
        month = now.month - 1
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    print(f"📦 Начинаем архивацию за {year}-{month:02d}...")
    
    # Получаем все записи за прошлый месяц
    sessions = execute_query("""
        SELECT * FROM work_sessions 
        WHERE start_time >= ? AND start_time < ?
        ORDER BY user_id, start_time
    """, (start_date, end_date), fetch_all=True) or []
    
    if not sessions:
        print(f"📭 Нет данных для архивации за {year}-{month:02d}")
        return 0
    
    # Группируем по пользователям
    from collections import defaultdict
    user_sessions = defaultdict(list)
    for session in sessions:
        user_sessions[session["user_id"]].append(session)
    
    # Для каждого пользователя создаём сводку и Excel
    for user_id, user_sessions_list in user_sessions.items():
        total_hours = sum(s["duration"] for s in user_sessions_list) / 3600
        total_earned = sum(s["earnings"] for s in user_sessions_list)
        
        # Получаем расходы и выплаты за месяц
        expenses = get_expenses_for_month(user_id, year, month)
        payments = get_payments_for_month(user_id, year, month)
        
        # Получаем баланс на начало месяца
        opening_balance = get_balance_before_date(user_id, start_date)
        closing_balance = opening_balance + total_earned + expenses - payments
        
        # Сохраняем сводку
        month_str = f"{year}-{month:02d}"
        execute_query("""
            INSERT OR REPLACE INTO monthly_summary 
            (user_id, month, total_hours, total_earned, total_expenses, total_paid, closing_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, month_str, total_hours, total_earned, expenses, payments, closing_balance))
        
        print(f"📦 Архивирован пользователь {user_id} за {month_str}")
    
    # Удаляем детальные записи за прошлый месяц
    deleted = execute_query("""
        DELETE FROM work_sessions 
        WHERE start_time >= ? AND start_time < ?
    """, (start_date, end_date))
    
    print(f"✅ Архивация завершена. Удалено {len(sessions)} записей")
    return len(sessions)


def get_expenses_for_month(user_id: int, year: int, month: int):
    """Получить сумму расходов за месяц"""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    result = execute_query("""
        SELECT SUM(amount) as total FROM expenses 
        WHERE user_id = ? AND status = 'approved' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0


def get_payments_for_month(user_id: int, year: int, month: int):
    """Получить сумму выплат за месяц"""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    result = execute_query("""
        SELECT SUM(amount) as total FROM salary_payments 
        WHERE user_id = ? AND status = 'confirmed' 
        AND created_at >= ? AND created_at < ?
    """, (int(user_id), start_date, end_date), fetch_one=True)
    return result["total"] if result and result["total"] else 0


def get_balance_before_date(user_id: int, date: str):
    """Получить баланс пользователя на дату"""
    result = execute_query("""
        SELECT balance FROM user_balance 
        WHERE user_id = ?
    """, (int(user_id),), fetch_one=True)
    return result["balance"] if result else 0

# ============= ОТЧЁТЫ =============

def get_all_objects_stats_all_time():
    """Получить статистику по объектам за всё время"""
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
    """Получить статистику по расходам за последние 30 дней"""
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
    """Получить статистику по выплатам за последние 30 дней"""
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
    """Получить прогноз на следующие 30 дней"""
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