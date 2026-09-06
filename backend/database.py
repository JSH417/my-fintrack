import sqlite3
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "fintrack.db")

def get_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """데이터베이스 및 기본 테이블 생성 (멀티 프로필 지원)"""
    conn = get_db()
    cursor = conn.cursor()

    # 0. 프로필 테이블 (profiles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,           -- 'mom', 'me'
        name TEXT NOT NULL,           -- '어머니 가계부', '내 가계부'
        icon TEXT DEFAULT '👤',
        default_mode TEXT DEFAULT 'simple', -- 'simple', 'pro'
        font_size TEXT DEFAULT 'large',      -- 'large', 'normal'
        theme_color TEXT DEFAULT '#10B981',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 1. 계좌 및 지갑 (accounts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL DEFAULT 'mom',
        name TEXT NOT NULL,
        type TEXT NOT NULL, -- 'bank', 'cash', 'card', 'investment', 'crypto', 'savings'
        balance REAL DEFAULT 0,
        currency TEXT DEFAULT 'KRW',
        is_investment INTEGER DEFAULT 0,
        color TEXT DEFAULT '#4F46E5',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    );
    """)

    # 2. 카테고리 (categories)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        type TEXT NOT NULL, -- 'expense', 'income'
        icon TEXT DEFAULT 'tag',
        color TEXT DEFAULT '#64748B'
    );
    """)

    # 3. 거래 내역 (transactions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL DEFAULT 'mom',
        date TEXT NOT NULL, -- YYYY-MM-DD
        type TEXT NOT NULL, -- 'expense', 'income', 'transfer'
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
    """)

    # 4. 예산 설정 (budgets)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL DEFAULT 'mom',
        month TEXT NOT NULL, -- YYYY-MM
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(profile_id, month, category),
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    );
    """)

    # 5. 투자 보유 종목 (investments)
    cursor.execute("""
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
    """)

    # 6. 투자 매매 기록 (investment_transactions)
    cursor.execute("""
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
    """)

    # 7. 앱 설정 (settings)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # 기본 프로필 생성 (어머니 가계부 & 내 가계부)
    cursor.execute("SELECT COUNT(*) FROM profiles")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO profiles (id, name, icon, default_mode, font_size, theme_color)
            VALUES ('mom', '어머니 가계부', '🌸', 'simple', 'large', '#10B981')
        """)
        cursor.execute("""
            INSERT INTO profiles (id, name, icon, default_mode, font_size, theme_color)
            VALUES ('me', '내 가계부', '👤', 'pro', 'normal', '#4F46E5')
        """)

    # 기본 계좌 등록 (프로필별 분리)
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        # 어머니 계좌 (투자 없이 깔끔한 생활 통장과 현금)
        cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('mom', '생활비 통장', 'bank', 0, '#10B981', 0)")
        cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('mom', '현금 지갑', 'cash', 0, '#F59E0B', 0)")

        # 내 계좌 (주거래 통장, 현금, 증권/투자 계좌)
        cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '내 주거래 통장', 'bank', 0, '#3B82F6', 0)")
        cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '내 현금 지갑', 'cash', 0, '#10B981', 0)")
        cursor.execute("INSERT INTO accounts (profile_id, name, type, balance, color, is_investment) VALUES ('me', '투자/증권 계좌', 'investment', 0, '#8B5CF6', 1)")

    # 기본 카테고리 등록
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

    # 전역 기본 설정
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_krw_rate', '1350.0')")

    conn.commit()
    conn.close()

def recalculate_account_balances(profile_id: Optional[str] = None):
    """지정한 프로필(또는 전체)의 계좌 잔액을 거래 내역 기준으로 재계산"""
    conn = get_db()
    cursor = conn.cursor()

    if profile_id:
        cursor.execute("SELECT id FROM accounts WHERE profile_id = ?", (profile_id,))
    else:
        cursor.execute("SELECT id FROM accounts")
    accounts = [row["id"] for row in cursor.fetchall()]

    for acc_id in accounts:
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id = ? AND type = 'income'", (acc_id,))
        income_sum = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id = ? AND type = 'expense'", (acc_id,))
        expense_sum = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id = ? AND type = 'transfer'", (acc_id,))
        transfer_out_sum = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE to_account_id = ? AND type = 'transfer'", (acc_id,))
        transfer_in_sum = cursor.fetchone()[0]

        new_balance = income_sum - expense_sum - transfer_out_sum + transfer_in_sum
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, acc_id))

    conn.commit()
    conn.close()

def reset_database(seed_sample: bool = False):
    """데이터베이스 초기화 (프로필 및 계좌 기본 틀만 복원하고 내역은 완전 빈 상태)"""
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
    """체험용 샘플 데이터 (어머니 가계부와 내 가계부 각각 등록)"""
    conn = get_db()
    cursor = conn.cursor()

    current_month = datetime.now().strftime("%Y-%m")

    # 어머니 계좌 잔액 및 내역
    cursor.execute("UPDATE accounts SET balance = 850000 WHERE profile_id = 'mom' AND name = '생활비 통장'")
    cursor.execute("UPDATE accounts SET balance = 120000 WHERE profile_id = 'mom' AND name = '현금 지갑'")

    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'mom' AND name = '생활비 통장'")
    mom_bank = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'mom' AND name = '현금 지갑'")
    mom_cash = cursor.fetchone()[0]

    sample_mom_txs = [
        ("mom", f"{current_month}-01", "income", 1000000, "용돈", mom_bank, None, "자녀가 보낸 생활비"),
        ("mom", f"{current_month}-02", "expense", 32000, "마트/장보기", mom_bank, None, "전통시장 장보기"),
        ("mom", f"{current_month}-04", "expense", 8500, "카페/간식", mom_cash, None, "동네 카페 모임"),
        ("mom", f"{current_month}-06", "expense", 15000, "의료/건강", mom_bank, None, "내과 진료 및 약국 처방")
    ]
    cursor.executemany("""
        INSERT INTO transactions (profile_id, date, type, amount, category, account_id, to_account_id, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_mom_txs)

    # 내 계좌 잔액, 가계부 내역 및 주식 포트폴리오
    cursor.execute("UPDATE accounts SET balance = 3200000 WHERE profile_id = 'me' AND name = '내 주거래 통장'")
    cursor.execute("UPDATE accounts SET balance = 10000000 WHERE profile_id = 'me' AND name = '투자/증권 계좌'")

    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'me' AND name = '내 주거래 통장'")
    me_bank = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM accounts WHERE profile_id = 'me' AND name = '투자/증권 계좌'")
    me_invest = cursor.fetchone()[0]

    sample_me_txs = [
        ("me", f"{current_month}-01", "income", 3800000, "월급/급여", me_bank, None, "급여 입금"),
        ("me", f"{current_month}-02", "expense", 48000, "식비", me_bank, None, "저녁 식사"),
        ("me", f"{current_month}-03", "expense", 65000, "주거/통신", me_bank, None, "통신비 자동이체"),
        ("me", f"{current_month}-05", "transfer", 500000, "기타지출", me_bank, me_invest, "증권 계좌로 시드머니 이체")
    ]
    cursor.executemany("""
        INSERT INTO transactions (profile_id, date, type, amount, category, account_id, to_account_id, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_me_txs)

    # 내 투자 종목 샘플
    sample_investments = [
        ("me", me_invest, "005930.KS", "삼성전자", "kr_stock", 50, 72000, 78500, "KRW", "우량주 장기보유"),
        ("me", me_invest, "AAPL", "애플", "us_stock", 10, 185.0, 225.5, "USD", "미국 기술주"),
        ("me", me_invest, "KRW-BTC", "비트코인", "crypto", 0.05, 85000000, 108000000, "KRW", "적립식 비트코인")
    ]
    cursor.executemany("""
        INSERT INTO investments (profile_id, account_id, symbol, name, category, quantity, avg_buy_price, current_price, currency, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_investments)

    conn.commit()
    conn.close()

    recalculate_account_balances()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with Multi-Profile at:", DB_PATH)
