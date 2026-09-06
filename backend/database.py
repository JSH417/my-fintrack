import os
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "fintrack.db")

def is_postgres():
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

class DBCursorWrapper:
    def __init__(self, cursor, is_pg: bool):
        self.cursor = cursor
        self.is_pg = is_pg
        self.lastrowid = None

    def execute(self, sql: str, params: Optional[Any] = None):
        if self.is_pg:
            pg_sql = sql.replace("?", "%s")
            pg_sql = pg_sql.replace("strftime('%Y-%m', date)", "substr(date, 1, 7)")
            pg_sql = pg_sql.replace("strftime('%Y-%m', t.date)", "substr(t.date, 1, 7)")

            # Handle INSERT OR REPLACE
            if "INSERT OR REPLACE INTO budgets" in pg_sql:
                pg_sql = """
                    INSERT INTO budgets (profile_id, month, category, amount)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (profile_id, month, category) DO UPDATE SET amount = EXCLUDED.amount
                """
            elif "INSERT OR REPLACE INTO settings" in pg_sql:
                pg_sql = """
                    INSERT INTO settings (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """

            is_insert = pg_sql.strip().upper().startswith("INSERT INTO")
            if is_insert and "RETURNING" not in pg_sql.upper() and "ON CONFLICT" not in pg_sql.upper():
                pg_sql += " RETURNING id"
                if params is not None:
                    self.cursor.execute(pg_sql, params)
                else:
                    self.cursor.execute(pg_sql)
                try:
                    row = self.cursor.fetchone()
                    if row and 'id' in row:
                        self.lastrowid = row['id']
                except Exception:
                    pass
                return self

            if params is not None:
                self.cursor.execute(pg_sql, params)
            else:
                self.cursor.execute(pg_sql)
            return self
        else:
            if params is not None:
                self.cursor.execute(sql, params)
            else:
                if ";" in sql.strip() and sql.strip().count(";") > 1:
                    self.cursor.executescript(sql)
                else:
                    self.cursor.execute(sql)
            try:
                self.lastrowid = self.cursor.lastrowid
            except Exception:
                pass
            return self

    def executemany(self, sql: str, seq_of_params):
        if self.is_pg:
            pg_sql = sql.replace("?", "%s")
            self.cursor.executemany(pg_sql, seq_of_params)
        else:
            self.cursor.executemany(sql, seq_of_params)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()

class DBWrapper:
    def __init__(self, conn, is_pg: bool):
        self.conn = conn
        self.is_pg = is_pg

    def cursor(self):
        return DBCursorWrapper(self.conn.cursor(), self.is_pg)

    def commit(self):
        if not self.is_pg:
            self.conn.commit()

    def close(self):
        self.conn.close()

def get_db():
    if is_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        conn.autocommit = True
        return DBWrapper(conn, is_pg=True)
    else:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return DBWrapper(conn, is_pg=False)

def init_db():
    """데이터베이스 스키마 생성 및 초기화 (SQLite/PostgreSQL 양방향 지원)"""
    conn = get_db()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '👤',
            default_mode TEXT DEFAULT 'simple',
            font_size TEXT DEFAULT 'large',
            theme_color TEXT DEFAULT '#10B981',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            balance DOUBLE PRECISION DEFAULT 0,
            currency TEXT DEFAULT 'KRW',
            is_investment INTEGER DEFAULT 0,
            color TEXT DEFAULT '#4F46E5',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            icon TEXT DEFAULT 'tag',
            color TEXT DEFAULT '#64748B'
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            category TEXT NOT NULL,
            account_id INTEGER,
            to_account_id INTEGER,
            memo TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            UNIQUE(profile_id, month, category)
        );
        CREATE TABLE IF NOT EXISTS investments (
            id SERIAL PRIMARY KEY,
            profile_id TEXT NOT NULL DEFAULT 'me',
            account_id INTEGER,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
            avg_buy_price DOUBLE PRECISION NOT NULL DEFAULT 0,
            current_price DOUBLE PRECISION NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'KRW',
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id SERIAL PRIMARY KEY,
            investment_id INTEGER,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity DOUBLE PRECISION NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            fee DOUBLE PRECISION DEFAULT 0,
            total_amount DOUBLE PRECISION NOT NULL,
            memo TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        cursor.execute("SELECT COUNT(*) as cnt FROM profiles")
        cnt = cursor.fetchone()['cnt']
        if cnt == 0:
            cursor.execute("""
                INSERT INTO profiles (id, name, icon, default_mode, font_size, theme_color)
                VALUES 
                ('mom', '어머니 가계부', '🌸', 'simple', 'large', '#10B981'),
                ('me', '내 가계부', '👤', 'pro', 'normal', '#4F46E5')
                ON CONFLICT (id) DO NOTHING
            """)

        cursor.execute("SELECT COUNT(*) as cnt FROM accounts")
        if cursor.fetchone()['cnt'] == 0:
            cursor.execute("""
                INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES 
                ('mom', '생활비 통장', 'bank', 0, '#10B981', 0),
                ('mom', '현금 지갑', 'cash', 0, '#F59E0B', 0),
                ('me', '내 주거래 통장', 'bank', 0, '#3B82F6', 0),
                ('me', '내 현금 지갑', 'cash', 0, '#10B981', 0),
                ('me', '투자/증권 계좌', 'investment', 0, '#8B5CF6', 1)
            """)

        cursor.execute("SELECT COUNT(*) as cnt FROM categories")
        if cursor.fetchone()['cnt'] == 0:
            cursor.execute("""
                INSERT INTO categories (name, type, icon, color) VALUES 
                ('식비', 'expense', 'utensils', '#EF4444'),
                ('카페/간식', 'expense', 'coffee', '#F97316'),
                ('마트/장보기', 'expense', 'shopping-cart', '#F59E0B'),
                ('교통/차량', 'expense', 'car', '#10B981'),
                ('주거/통신', 'expense', 'home', '#06B6D4'),
                ('생활용품', 'expense', 'box', '#3B82F6'),
                ('의료/건강', 'expense', 'heart-pulse', '#EC4899'),
                ('문화/여가', 'expense', 'film', '#8B5CF6'),
                ('경조사/선물', 'expense', 'gift', '#6366F1'),
                ('기타지출', 'expense', 'more-horizontal', '#64748B'),
                ('월급/급여', 'income', 'briefcase', '#10B981'),
                ('상여금', 'income', 'award', '#059669'),
                ('용돈', 'income', 'smile', '#34D399'),
                ('부수입', 'income', 'trending-up', '#3B82F6'),
                ('배당/금융소득', 'income', 'coins', '#F59E0B'),
                ('기타수입', 'income', 'plus-circle', '#6B7280')
                ON CONFLICT (name) DO NOTHING
            """)

        cursor.execute("INSERT INTO settings (key, value) VALUES ('usd_krw_rate', '1350.0') ON CONFLICT (key) DO NOTHING")

    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '👤',
            default_mode TEXT DEFAULT 'simple',
            font_size TEXT DEFAULT 'large',
            theme_color TEXT DEFAULT '#10B981',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            balance REAL DEFAULT 0,
            currency TEXT DEFAULT 'KRW',
            is_investment INTEGER DEFAULT 0,
            color TEXT DEFAULT '#4F46E5',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            icon TEXT DEFAULT 'tag',
            color TEXT DEFAULT '#64748B'
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            account_id INTEGER,
            to_account_id INTEGER,
            memo TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL,
            FOREIGN KEY (to_account_id) REFERENCES accounts(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT 'mom',
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            UNIQUE(profile_id, month, category),
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT 'me',
            account_id INTEGER,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            avg_buy_price REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'KRW',
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investment_id INTEGER,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            memo TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investment_id) REFERENCES investments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        cursor.execute("SELECT COUNT(*) FROM profiles")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO profiles (id, name, icon, default_mode, font_size, theme_color) VALUES ('mom', '어머니 가계부', '🌸', 'simple', 'large', '#10B981')")
            cursor.execute("INSERT INTO profiles (id, name, icon, default_mode, font_size, theme_color) VALUES ('me', '내 가계부', '👤', 'pro', 'normal', '#4F46E5')")

        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('mom', '생활비 통장', 'bank', 0, '#10B981', 0)")
            cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('mom', '현금 지갑', 'cash', 0, '#F59E0B', 0)")
            cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '내 주거래 통장', 'bank', 0, '#3B82F6', 0)")
            cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '내 현금 지갑', 'cash', 0, '#10B981', 0)")
            cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '투자/증권 계좌', 'investment', 0, '#8B5CF6', 1)")

        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ("식비", "expense", "utensils", "#EF4444"),
                ("카페/간식", "expense", "coffee", "#F97316"),
                ("마트/장보기", "expense", "shopping-cart", "#F59E0B"),
                ("교통/차량", "expense", "car", "#10B981"),
                ("주거/통신", "expense", "home", "#06B6D4"),
                ("생활용품", "expense", "box", "#3B82F6"),
                ("의료/건강", "expense", "heart-pulse", "#EC4899"),
                ("문화/여가", "expense", "film", "#8B5CF6"),
                ("경조사/선물", "expense", "gift", "#6366F1"),
                ("기타지출", "expense", "more-horizontal", "#64748B"),
                ("월급/급여", "income", "briefcase", "#10B981"),
                ("상여금", "income", "award", "#059669"),
                ("용돈", "income", "smile", "#34D399"),
                ("부수입", "income", "trending-up", "#3B82F6"),
                ("배당/금융소득", "income", "coins", "#F59E0B"),
                ("기타수입", "income", "plus-circle", "#6B7280")
            ]
            cursor.executemany("INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)", default_categories)

        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_krw_rate', '1350.0')")
        conn.commit()

    cursor.close()
    conn.close()

def recalculate_account_balances(profile_id: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    if profile_id:
        cursor.execute("SELECT id FROM accounts WHERE profile_id = ?", (profile_id,))
    else:
        cursor.execute("SELECT id FROM accounts")
    accounts = [row["id"] for row in cursor.fetchall()]

    for acc_id in accounts:
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions WHERE account_id = ? AND type = 'income'", (acc_id,))
        income_sum = cursor.fetchone()['s'] if is_postgres() else cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions WHERE account_id = ? AND type = 'expense'", (acc_id,))
        expense_sum = cursor.fetchone()['s'] if is_postgres() else cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions WHERE account_id = ? AND type = 'transfer'", (acc_id,))
        transfer_out_sum = cursor.fetchone()['s'] if is_postgres() else cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions WHERE to_account_id = ? AND type = 'transfer'", (acc_id,))
        transfer_in_sum = cursor.fetchone()['s'] if is_postgres() else cursor.fetchone()[0]

        new_balance = income_sum - expense_sum - transfer_out_sum + transfer_in_sum
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, acc_id))

    conn.commit()
    conn.close()

def reset_database(seed_sample: bool = False):
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM investment_transactions")
    cursor.execute("DELETE FROM investments")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM budgets")
    cursor.execute("DELETE FROM accounts")
    cursor.execute("DELETE FROM categories")
    cursor.execute("DELETE FROM profiles")
    cursor.execute("DELETE FROM settings")

    conn.commit()
    conn.close()

    init_db()
    if seed_sample:
        load_sample_data()

def load_sample_data():
    conn = get_db()
    cursor = conn.cursor()
    current_month = datetime.now().strftime("%Y-%m")

    cursor.execute("UPDATE accounts SET balance = 850000 WHERE profile_id = 'mom' AND name = '생활비 통장'")
    cursor.execute("UPDATE accounts SET balance = 120000 WHERE profile_id = 'mom' AND name = '현금 지갑'")

    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'mom' AND name = '생활비 통장'")
    mom_bank = cursor.fetchone()['id'] if is_postgres() else cursor.fetchone()[0]
    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'mom' AND name = '현금 지갑'")
    mom_cash = cursor.fetchone()['id'] if is_postgres() else cursor.fetchone()[0]

    sample_mom = [
        ("mom", f"{current_month}-01", "income", 1000000, "용돈", mom_bank, None, "자녀가 보낸 생활비"),
        ("mom", f"{current_month}-02", "expense", 32000, "마트/장보기", mom_bank, None, "전통시장 장보기"),
        ("mom", f"{current_month}-04", "expense", 8500, "카페/간식", mom_cash, None, "동네 카페 모임"),
        ("mom", f"{current_month}-06", "expense", 15000, "의료/건강", mom_bank, None, "내과 진료 및 약국 처방")
    ]
    for row in sample_mom:
        cursor.execute("INSERT INTO transactions (profile_id, date, type, amount, category, account_id, to_account_id, memo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)

    cursor.execute("UPDATE accounts SET balance = 3200000 WHERE profile_id = 'me' AND name = '내 주거래 통장'")
    cursor.execute("UPDATE accounts SET balance = 10000000 WHERE profile_id = 'me' AND name = '투자/증권 계좌'")

    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'me' AND name = '내 주거래 통장'")
    me_bank = cursor.fetchone()['id'] if is_postgres() else cursor.fetchone()[0]
    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'me' AND name = '투자/증권 계좌'")
    me_invest = cursor.fetchone()['id'] if is_postgres() else cursor.fetchone()[0]

    sample_me = [
        ("me", f"{current_month}-01", "income", 3800000, "월급/급여", me_bank, None, "급여 입금"),
        ("me", f"{current_month}-02", "expense", 48000, "식비", me_bank, None, "저녁 식사"),
        ("me", f"{current_month}-03", "expense", 65000, "주거/통신", me_bank, None, "통신비 자동이체")
    ]
    for row in sample_me:
        cursor.execute("INSERT INTO transactions (profile_id, date, type, amount, category, account_id, to_account_id, memo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)

    sample_invs = [
        ("me", me_invest, "005930.KS", "삼성전자", "kr_stock", 50, 72000, 78500, "KRW", "우량주 장기보유"),
        ("me", me_invest, "AAPL", "애플", "us_stock", 10, 185.0, 225.5, "USD", "미국 기술주"),
        ("me", me_invest, "KRW-BTC", "비트코인", "crypto", 0.05, 85000000, 108000000, "KRW", "적립식 비트코인")
    ]
    for row in sample_invs:
        cursor.execute("INSERT INTO investments (profile_id, account_id, symbol, name, category, quantity, avg_buy_price, current_price, currency, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)

    conn.commit()
    conn.close()
    recalculate_account_balances()
