from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import sqlite3

from .database import get_db, init_db, recalculate_account_balances, reset_database, load_sample_data
from .price_service import get_usd_krw_rate, fetch_live_price, update_all_investments
from .receipt_service import analyze_receipt_with_gemini

app = FastAPI(title="FinTrack - 스마트 가계부 & 투자 포트폴리오 (가족 멀티프로필)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
APP_PROFILE = os.environ.get("APP_PROFILE", "").strip().lower()

@app.on_event("startup")
def on_startup():
    init_db()

# ----------------- Pydantic Models -----------------

class TransactionCreate(BaseModel):
    profile_id: Optional[str] = "mom"
    date: str
    type: str  # 'expense', 'income', 'transfer'
    amount: float
    category: str
    account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    memo: Optional[str] = ""

class TransactionUpdate(BaseModel):
    date: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    memo: Optional[str] = None

class BudgetSet(BaseModel):
    profile_id: Optional[str] = "mom"
    month: str  # YYYY-MM
    category: str
    amount: float

class AccountCreate(BaseModel):
    profile_id: Optional[str] = "mom"
    name: str
    type: str
    initial_balance: Optional[float] = 0.0
    balance: Optional[float] = 0.0
    color: Optional[str] = "#3B82F6"
    is_investment: Optional[int] = 0

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    initial_balance: Optional[float] = None
    color: Optional[str] = None

class InvestmentCreate(BaseModel):
    profile_id: Optional[str] = "me"
    account_id: Optional[int] = None
    symbol: str
    name: str
    category: str  # 'kr_stock', 'us_stock', 'crypto', 'savings', 'etf', 'fund', 'etc'
    quantity: float
    avg_buy_price: float
    current_price: Optional[float] = None
    currency: Optional[str] = "KRW"
    notes: Optional[str] = ""
    link_cash_account_id: Optional[int] = None

class InvestmentTrade(BaseModel):
    investment_id: int
    date: str
    type: str  # 'buy', 'sell', 'dividend'
    quantity: Optional[float] = 0.0
    price: Optional[float] = 0.0
    fee: Optional[float] = 0.0
    total_amount: Optional[float] = None
    memo: Optional[str] = ""
    sync_to_ledger: Optional[bool] = True
    account_id: Optional[int] = None

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    default_mode: Optional[str] = None
    font_size: Optional[str] = None

class PinVerify(BaseModel):
    pin: str

class PinChange(BaseModel):
    current_pin: str
    new_pin: str

class PinToggle(BaseModel):
    enabled: bool
    pin: Optional[str] = None

# ----------------- Configuration & Profiles -----------------

@app.get("/api/config")
def get_config():
    """배포 환경 설정 정보 반환 (독립 사이트 모드 여부 등)"""
    return {
        "app_profile": APP_PROFILE if APP_PROFILE in ["mom", "me"] else None
    }

@app.get("/api/profiles")
def get_profiles():
    conn = get_db()
    cursor = conn.cursor()
    if APP_PROFILE in ["mom", "me"]:
        cursor.execute("SELECT * FROM profiles WHERE id = ?", (APP_PROFILE,))
    else:
        cursor.execute("SELECT * FROM profiles ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: str, p: ProfileUpdate):
    conn = get_db()
    cursor = conn.cursor()
    updates = []
    params = []
    if p.name:
        updates.append("name = ?")
        params.append(p.name)
    if p.default_mode:
        updates.append("default_mode = ?")
        params.append(p.default_mode)
    if p.font_size:
        updates.append("font_size = ?")
        params.append(p.font_size)

    if updates:
        params.append(profile_id)
        cursor.execute(f"UPDATE profiles SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()
    return {"success": True}

# ----------------- Dashboard & Summary -----------------

@app.get("/api/summary")
def get_summary(profile_id: str = "mom", month: Optional[str] = None):
    """프로필별 수입, 지출, 잔액, 투자 및 순자산 요약 정보"""
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    if not month:
        month = datetime.now().strftime("%Y-%m")
    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()

    # 프로필 정보 조회
    cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
    profile = cursor.fetchone()
    if not profile:
        profile_mode = 'simple'
        profile_font = 'large'
        profile_name = '어머니 가계부'
    else:
        profile_mode = profile['default_mode']
        profile_font = profile['font_size']
        profile_name = profile['name']

    # 1. 이번 달 수입 및 지출
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
        FROM transactions
        WHERE profile_id = ? AND strftime('%Y-%m', date) = ?
    """, (profile_id, month))
    row = cursor.fetchone()
    month_income = row['total_income']
    month_expense = row['total_expense']
    month_net = month_income - month_expense

    # 2. 오늘 지출 및 수입
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as today_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as today_expense
        FROM transactions
        WHERE profile_id = ? AND date = ?
    """, (profile_id, today_str))
    today_row = cursor.fetchone()
    today_income = today_row['today_income']
    today_expense = today_row['today_expense']

    # 3. 예산 소진 현황
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total_budget FROM budgets WHERE profile_id = ? AND month = ?", (profile_id, month))
    total_budget = cursor.fetchone()['total_budget']
    budget_usage_pct = (month_expense / total_budget * 100) if total_budget > 0 else 0.0

    # 4. 현금 및 일반 은행 계좌 잔액
    cursor.execute("SELECT COALESCE(SUM(balance), 0) as cash_total FROM accounts WHERE profile_id = ? AND is_investment = 0", (profile_id,))
    cash_total = cursor.fetchone()['cash_total']

    # 5. 투자 계좌 현금 예수금
    cursor.execute("SELECT COALESCE(SUM(balance), 0) as invest_cash FROM accounts WHERE profile_id = ? AND is_investment = 1", (profile_id,))
    invest_cash = cursor.fetchone()['invest_cash']

    # 실시간 환율
    usd_rate = get_usd_krw_rate()

    # 6. 보유 투자 종목 평가금액 계산
    cursor.execute("SELECT symbol, name, category, quantity, avg_buy_price, current_price, currency FROM investments WHERE profile_id = ?", (profile_id,))
    investments = cursor.fetchall()
    
    total_invest_cost_krw = 0.0
    total_invest_value_krw = 0.0

    for inv in investments:
        rate = usd_rate if inv['currency'] == 'USD' else 1.0
        cur_price = inv['current_price'] if (inv['current_price'] and inv['current_price'] > 0) else inv['avg_buy_price']
        cost_krw = (inv['quantity'] * inv['avg_buy_price']) * rate
        val_krw = (inv['quantity'] * cur_price) * rate
        total_invest_cost_krw += cost_krw
        total_invest_value_krw += val_krw

    invest_profit_krw = total_invest_value_krw - total_invest_cost_krw
    invest_profit_rate = (invest_profit_krw / total_invest_cost_krw * 100) if total_invest_cost_krw > 0 else 0.0

    total_net_worth = cash_total + invest_cash + total_invest_value_krw

    conn.close()

    return {
        "profile_id": profile_id,
        "profile_name": profile_name,
        "mode": profile_mode,
        "font_size": profile_font,
        "month": month,
        "today": {
            "date": today_str,
            "expense": today_expense,
            "income": today_income
        },
        "monthly": {
            "income": month_income,
            "expense": month_expense,
            "net": month_net,
            "budget": total_budget,
            "budget_usage_pct": round(budget_usage_pct, 1)
        },
        "cash_total": cash_total,
        "investments": {
            "invest_cash": invest_cash,
            "total_cost_krw": round(total_invest_cost_krw),
            "total_value_krw": round(total_invest_value_krw),
            "profit_krw": round(invest_profit_krw),
            "profit_rate_pct": round(invest_profit_rate, 2),
            "holdings_count": len(investments)
        },
        "net_worth": round(total_net_worth),
        "usd_krw_rate": usd_rate
    }

# ----------------- Transactions (가계부 거래) -----------------

@app.get("/api/transactions")
def list_transactions(
    profile_id: str = "mom",
    month: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200
):
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT 
            t.id, t.profile_id, t.date, t.type, t.amount, t.category, t.memo, t.created_at,
            t.account_id, a1.name as account_name, a1.color as account_color,
            t.to_account_id, a2.name as to_account_name,
            c.icon as category_icon, c.color as category_color
        FROM transactions t
        LEFT JOIN accounts a1 ON t.account_id = a1.id
        LEFT JOIN accounts a2 ON t.to_account_id = a2.id
        LEFT JOIN categories c ON t.category = c.name
        WHERE t.profile_id = ?
    """
    params = [profile_id]

    if month:
        query += " AND strftime('%Y-%m', t.date) = ?"
        params.append(month)
    if type and type != 'all':
        query += " AND t.type = ?"
        params.append(type)
    if category and category != 'all':
        query += " AND t.category = ?"
        params.append(category)
    if search:
        query += " AND (t.memo LIKE ? OR t.category LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY t.date DESC, t.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result

@app.post("/api/transactions")
def create_transaction(tx: TransactionCreate):
    conn = get_db()
    cursor = conn.cursor()

    p_id = APP_PROFILE if APP_PROFILE in ["mom", "me"] else (tx.profile_id or "mom")
    cursor.execute("""
        INSERT INTO transactions (profile_id, date, type, amount, category, account_id, to_account_id, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (p_id, tx.date, tx.type, tx.amount, tx.category, tx.account_id, tx.to_account_id, tx.memo or ""))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    recalculate_account_balances(p_id)
    return {"success": True, "id": new_id}

@app.get("/api/transactions/{tx_id}")
def get_transaction(tx_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다.")
    return dict(row)

@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: int, tx: TransactionUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_id FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다.")

    p_id = row['profile_id'] if isinstance(row, dict) else row[0]

    updates = []
    params = []
    if tx.date is not None:
        updates.append("date = ?")
        params.append(tx.date)
    if tx.type is not None:
        updates.append("type = ?")
        params.append(tx.type)
    if tx.amount is not None:
        updates.append("amount = ?")
        params.append(tx.amount)
    if tx.category is not None:
        updates.append("category = ?")
        params.append(tx.category)
    if tx.account_id is not None:
        updates.append("account_id = ?")
        params.append(tx.account_id)
    if tx.to_account_id is not None:
        updates.append("to_account_id = ?")
        params.append(tx.to_account_id)
    if tx.memo is not None:
        updates.append("memo = ?")
        params.append(tx.memo)

    if updates:
        params.append(tx_id)
        cursor.execute(f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    conn.close()
    if p_id:
        recalculate_account_balances(p_id)
    return {"success": True}

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_id FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    p_id = row['profile_id'] if row else None

    cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()

    if p_id:
        recalculate_account_balances(p_id)
    return {"success": True}

@app.get("/api/calendar")
def get_calendar_data(profile_id: str = "mom", month: str = "2026-09"):
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            date,
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense,
            COUNT(*) as count
        FROM transactions
        WHERE profile_id = ? AND strftime('%Y-%m', date) = ?
        GROUP BY date
    """, (profile_id, month))
    rows = cursor.fetchall()
    conn.close()

    daily_map = {}
    for r in rows:
        daily_map[r['date']] = {
            "income": r['income'],
            "expense": r['expense'],
            "count": r['count']
        }
    return daily_map

# ----------------- Budgets -----------------

@app.get("/api/budgets")
def get_budgets(profile_id: str = "mom", month: str = "2026-09"):
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            c.name as category,
            c.color,
            c.icon,
            COALESCE(b.amount, 0) as budget_amount,
            COALESCE(exp.spent, 0) as spent_amount
        FROM categories c
        LEFT JOIN budgets b ON c.name = b.category AND b.month = ? AND b.profile_id = ?
        LEFT JOIN (
            SELECT category, SUM(amount) as spent
            FROM transactions
            WHERE profile_id = ? AND strftime('%Y-%m', date) = ? AND type = 'expense'
            GROUP BY category
        ) exp ON c.name = exp.category
        WHERE c.type = 'expense'
        ORDER BY budget_amount DESC, spent_amount DESC
    """, (month, profile_id, profile_id, month))
    rows = cursor.fetchall()
    conn.close()

    result = []
    total_budget = 0
    total_spent = 0

    for r in rows:
        b_amt = r['budget_amount']
        s_amt = r['spent_amount']
        total_budget += b_amt
        total_spent += s_amt
        pct = round((s_amt / b_amt * 100), 1) if b_amt > 0 else 0.0
        result.append({
            "category": r['category'],
            "color": r['color'],
            "icon": r['icon'],
            "budget": b_amt,
            "spent": s_amt,
            "remaining": b_amt - s_amt,
            "percentage": pct
        })

    return {
        "profile_id": profile_id,
        "month": month,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "remaining": total_budget - total_spent,
        "categories": result
    }

@app.post("/api/budgets")
def set_budget(item: BudgetSet):
    conn = get_db()
    cursor = conn.cursor()
    p_id = APP_PROFILE if APP_PROFILE in ["mom", "me"] else (item.profile_id or "mom")
    cursor.execute("""
        INSERT OR REPLACE INTO budgets (profile_id, month, category, amount)
        VALUES (?, ?, ?, ?)
    """, (p_id, item.month, item.category, item.amount))
    conn.commit()
    conn.close()
    return {"success": True}

# ----------------- Accounts & Categories -----------------

@app.get("/api/accounts")
def get_accounts(profile_id: str = "mom"):
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE profile_id = ? ORDER BY is_investment ASC, id ASC", (profile_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/accounts")
def create_account(acc: AccountCreate):
    conn = get_db()
    cursor = conn.cursor()
    p_id = APP_PROFILE if APP_PROFILE in ["mom", "me"] else (acc.profile_id or "mom")
    init_bal = acc.initial_balance if acc.initial_balance is not None else (acc.balance or 0.0)
    cursor.execute("""
        INSERT INTO accounts (profile_id, name, type, balance, initial_balance, color, is_investment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (p_id, acc.name, acc.type, init_bal, init_bal, acc.color, acc.is_investment))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    recalculate_account_balances(p_id)
    return {"success": True, "id": new_id}

@app.put("/api/accounts/{acc_id}")
def update_account(acc_id: int, acc: AccountUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_id FROM accounts WHERE id = ?", (acc_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="통장을 찾을 수 없습니다.")

    p_id = row['profile_id'] if isinstance(row, dict) else row[0]

    updates = []
    params = []
    if acc.name is not None:
        updates.append("name = ?")
        params.append(acc.name)
    if acc.type is not None:
        updates.append("type = ?")
        params.append(acc.type)
    if acc.initial_balance is not None:
        updates.append("initial_balance = ?")
        params.append(acc.initial_balance)
    if acc.color is not None:
        updates.append("color = ?")
        params.append(acc.color)

    if updates:
        params.append(acc_id)
        cursor.execute(f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    conn.close()
    if p_id:
        recalculate_account_balances(p_id)
    return {"success": True}

@app.delete("/api/accounts/{acc_id}")
def delete_account(acc_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/categories")
def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY type DESC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- Investments -----------------

@app.get("/api/investments")
def get_investments(profile_id: str = "me"):
    if APP_PROFILE in ["mom", "me"]:
        profile_id = APP_PROFILE

    usd_rate = get_usd_krw_rate()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            i.*,
            a.name as account_name
        FROM investments i
        LEFT JOIN accounts a ON i.account_id = a.id
        WHERE i.profile_id = ?
        ORDER BY i.id DESC
    """, (profile_id,))
    rows = cursor.fetchall()
    conn.close()

    items = []
    total_cost_krw = 0.0
    total_val_krw = 0.0

    category_labels = {
        "kr_stock": "국내주식",
        "us_stock": "미국주식",
        "crypto": "가상자산",
        "etf": "ETF",
        "savings": "예/적금",
        "fund": "펀드",
        "etc": "기타자산"
    }

    for r in rows:
        item = dict(r)
        rate = usd_rate if item['currency'] == 'USD' else 1.0
        cur_price = item['current_price'] if (item['current_price'] and item['current_price'] > 0) else item['avg_buy_price']
        
        cost_orig = item['quantity'] * item['avg_buy_price']
        cost_krw = cost_orig * rate
        val_orig = item['quantity'] * cur_price
        val_krw = val_orig * rate
        profit_krw = val_krw - cost_krw
        profit_rate = (profit_krw / cost_krw * 100) if cost_krw > 0 else 0.0

        item['category_label'] = category_labels.get(item['category'], item['category'])
        item['cost_krw'] = round(cost_krw)
        item['value_krw'] = round(val_krw)
        item['profit_krw'] = round(profit_krw)
        item['profit_rate'] = round(profit_rate, 2)
        item['exchange_rate'] = rate

        total_cost_krw += cost_krw
        total_val_krw += val_krw
        items.append(item)

    total_profit_krw = total_val_krw - total_cost_krw
    total_profit_rate = (total_profit_krw / total_cost_krw * 100) if total_cost_krw > 0 else 0.0

    allocation = {}
    for it in items:
        cat_name = it['category_label']
        allocation[cat_name] = allocation.get(cat_name, 0.0) + it['value_krw']

    return {
        "profile_id": profile_id,
        "items": items,
        "summary": {
            "total_cost_krw": round(total_cost_krw),
            "total_value_krw": round(total_val_krw),
            "profit_krw": round(total_profit_krw),
            "profit_rate": round(total_profit_rate, 2),
            "usd_krw_rate": usd_rate
        },
        "allocation": allocation
    }

@app.post("/api/investments")
def add_investment(inv: InvestmentCreate):
    conn = get_db()
    cursor = conn.cursor()
    p_id = APP_PROFILE if APP_PROFILE in ["mom", "me"] else (inv.profile_id or "me")

    cur_price = inv.current_price
    if cur_price is None or cur_price <= 0:
        live = fetch_live_price(inv.symbol, inv.category)
        cur_price = live if live else inv.avg_buy_price

    cursor.execute("""
        INSERT INTO investments (profile_id, account_id, symbol, name, category, quantity, avg_buy_price, current_price, currency, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (p_id, inv.account_id, inv.symbol.strip(), inv.name.strip(), inv.category, inv.quantity, inv.avg_buy_price, cur_price, inv.currency, inv.notes or ""))
    new_id = cursor.lastrowid

    total_spent = inv.quantity * inv.avg_buy_price
    cursor.execute("""
        INSERT INTO investment_transactions (investment_id, date, type, quantity, price, fee, total_amount, memo)
        VALUES (?, ?, 'buy', ?, ?, 0, ?, '최초 등록')
    """, (new_id, datetime.now().strftime("%Y-%m-%d"), inv.quantity, inv.avg_buy_price, total_spent))

    if inv.link_cash_account_id:
        usd_rate = get_usd_krw_rate()
        amount_krw = total_spent * (usd_rate if inv.currency == 'USD' else 1.0)
        cursor.execute("""
            INSERT INTO transactions (profile_id, date, type, amount, category, account_id, memo)
            VALUES (?, ?, 'expense', ?, '기타지출', ?, ?)
        """, (p_id, datetime.now().strftime("%Y-%m-%d"), amount_krw, inv.link_cash_account_id, f"[{inv.name}] 주식/자산 매수"))

    conn.commit()
    conn.close()

    if inv.link_cash_account_id:
        recalculate_account_balances(p_id)

    return {"success": True, "id": new_id}

@app.delete("/api/investments/{inv_id}")
def delete_investment(inv_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM investments WHERE id = ?", (inv_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/investments/refresh-prices")
def refresh_prices():
    try:
        res = update_all_investments()
        return res
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"시세 갱신 중 오류: {str(e)}", "usd_krw_rate": get_usd_krw_rate()}

@app.post("/api/investments/trade")
def record_trade(trade: InvestmentTrade):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM investments WHERE id = ?", (trade.investment_id,))
    inv = cursor.fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")

    p_id = inv['profile_id']
    inv_curr = inv['currency']
    usd_rate = get_usd_krw_rate()
    rate = usd_rate if inv_curr == 'USD' else 1.0

    qty = trade.quantity or 0.0
    price = trade.price or 0.0
    fee = trade.fee or 0.0

    if trade.total_amount is not None and trade.total_amount > 0:
        total_amount = trade.total_amount
    elif trade.type == 'dividend' and price > 0 and qty == 0:
        total_amount = price
    else:
        total_amount = (qty * price) + fee

    cursor.execute("""
        INSERT INTO investment_transactions (investment_id, date, type, quantity, price, fee, total_amount, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (trade.investment_id, trade.date, trade.type, qty, price, fee, total_amount, trade.memo or ""))

    curr_qty = inv['quantity']
    curr_avg = inv['avg_buy_price']

    if trade.type == 'buy':
        new_qty = curr_qty + qty
        new_avg = ((curr_qty * curr_avg) + (qty * price)) / new_qty if new_qty > 0 else 0
        cursor.execute("UPDATE investments SET quantity = ?, avg_buy_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, new_avg, trade.investment_id))

        if trade.sync_to_ledger and trade.account_id:
            krw_spent = total_amount * rate
            cursor.execute("""
                INSERT INTO transactions (profile_id, date, type, amount, category, account_id, memo)
                VALUES (?, ?, 'expense', ?, '기타지출', ?, ?)
            """, (p_id, trade.date, krw_spent, trade.account_id, f"[{inv['name']}] 추가 매수 ({qty}주)"))

    elif trade.type == 'sell':
        new_qty = max(0.0, curr_qty - qty)
        cursor.execute("UPDATE investments SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, trade.investment_id))

        if trade.sync_to_ledger and trade.account_id:
            krw_received = (qty * price - fee) * rate
            cursor.execute("""
                INSERT INTO transactions (profile_id, date, type, amount, category, account_id, memo)
                VALUES (?, ?, 'income', ?, '부수입', ?, ?)
            """, (p_id, trade.date, krw_received, trade.account_id, f"[{inv['name']}] 매도 대금 입금 ({qty}주)"))

    elif trade.type == 'dividend':
        if trade.sync_to_ledger and trade.account_id:
            krw_div = total_amount * rate
            cursor.execute("""
                INSERT INTO transactions (profile_id, date, type, amount, category, account_id, memo)
                VALUES (?, ?, 'income', ?, '배당/금융소득', ?, ?)
            """, (p_id, trade.date, krw_div, trade.account_id, f"[{inv['name']}] 배당금 수령"))

    conn.commit()
    conn.close()

    if trade.sync_to_ledger and trade.account_id:
        recalculate_account_balances(p_id)

    return {"success": True}

# ----------------- Receipt AI Scanner & Settings -----------------

@app.post("/api/receipt/scan")
async def scan_receipt(file: UploadFile = File(...)):
    """영수증 사진을 받아 Gemini 비전 AI로 분석 후 JSON 반환"""
    contents = await file.read()
    mime = file.content_type or "image/jpeg"
    result = analyze_receipt_with_gemini(contents, mime_type=mime)
    return result

@app.get("/api/settings")
def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    res = {r['key']: r['value'] for r in rows}
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and not res.get("gemini_api_key"):
        res["gemini_api_key"] = env_key
    return res

@app.post("/api/settings")
def update_settings(payload: Dict[str, str]):
    conn = get_db()
    cursor = conn.cursor()
    for k, v in payload.items():
        cursor.execute("DELETE FROM settings WHERE key = ?", (k,))
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    return {"success": True}

# ----------------- PIN Security & App Lock -----------------

@app.get("/api/pin/status")
def get_pin_status():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'app_pin_enabled'")
    row = cursor.fetchone()
    enabled = False
    if row:
        val = row['value'] if isinstance(row, dict) else row[0]
        enabled = (str(val) == "1" or str(val).lower() == "true")
    conn.close()
    return {"enabled": enabled, "has_pin": True}

@app.post("/api/pin/verify")
def verify_pin(payload: PinVerify):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'app_pin'")
    row = cursor.fetchone()
    conn.close()
    stored_pin = "0000"
    if row:
        stored_pin = row['value'] if isinstance(row, dict) else row[0]

    if payload.pin.strip() == stored_pin:
        return {"valid": True}
    return JSONResponse(status_code=400, content={"valid": False, "message": "비밀번호가 올바르지 않습니다."})

@app.post("/api/pin/change")
def change_pin(payload: PinChange):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'app_pin'")
    row = cursor.fetchone()
    stored_pin = "0000"
    if row:
        stored_pin = row['value'] if isinstance(row, dict) else row[0]

    if payload.current_pin.strip() != stored_pin:
        conn.close()
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다. (초기 비밀번호: 0000)")

    new_pin = payload.new_pin.strip()
    if len(new_pin) != 4 or not new_pin.isdigit():
        conn.close()
        raise HTTPException(status_code=400, detail="새 비밀번호는 4자리 숫자여야 합니다.")

    cursor.execute("DELETE FROM settings WHERE key = 'app_pin'")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('app_pin', ?)", (new_pin,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}

@app.post("/api/pin/toggle")
def toggle_pin(payload: PinToggle):
    conn = get_db()
    cursor = conn.cursor()

    if payload.pin:
        cursor.execute("SELECT value FROM settings WHERE key = 'app_pin'")
        row = cursor.fetchone()
        stored_pin = "0000"
        if row:
            stored_pin = row['value'] if isinstance(row, dict) else row[0]
        if payload.pin.strip() != stored_pin:
            conn.close()
            raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다. (초기 비밀번호: 0000)")

    new_val = "1" if payload.enabled else "0"
    cursor.execute("DELETE FROM settings WHERE key = 'app_pin_enabled'")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('app_pin_enabled', ?)", (new_val,))
    conn.commit()
    conn.close()
    return {"success": True, "enabled": payload.enabled}

# ----------------- Data Reset & Sample -----------------

@app.post("/api/data/reset")
def reset_data():
    reset_database(seed_sample=False)
    return {"success": True, "message": "데이터가 깔끔하게 초기화되었습니다."}

@app.post("/api/data/load-sample")
def load_sample():
    reset_database(seed_sample=True)
    return {"success": True, "message": "샘플 데이터가 로드되었습니다."}

# ----------------- Frontend Static Files -----------------

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()

        import time
        v_tag = f"?v={int(time.time())}"
        content = content.replace("/static/app.js", f"/static/app.js{v_tag}")
        content = content.replace("/static/style.css", f"/static/style.css{v_tag}")

        if APP_PROFILE in ["mom", "me"]:
            inject_script = f"""
            <script>
                window.SERVER_APP_PROFILE = '{APP_PROFILE}';
            </script>
            """
            content = content.replace("</head>", f"{inject_script}\n</head>")

            # Server-side HTML transformation: remove switcher and display standalone title directly
            content = content.replace('id="profileSwitcherBox" class="flex', 'id="profileSwitcherBox" class="hidden')
            content = content.replace('id="standaloneTitleBox" class="hidden flex', 'id="standaloneTitleBox" class="flex')

            if APP_PROFILE == "mom":
                content = content.replace('<title>행복 가계부 & 자산관리</title>', '<title>어머니 행복 가계부 🌸</title>')
                content = content.replace('<h1 id="standaloneTitle" class="text-base sm:text-lg font-black text-slate-900">어머니 행복 가계부</h1>', '<h1 id="standaloneTitle" class="text-base sm:text-lg font-black text-slate-900">어머니 행복 가계부 🌸</h1>')
            elif APP_PROFILE == "me":
                content = content.replace('<title>행복 가계부 & 자산관리</title>', '<title>내 가계부 & 자산관리 💼</title>')
                content = content.replace('<span id="standaloneIcon" class="text-2xl">🌸</span>', '<span id="standaloneIcon" class="text-2xl">💼</span>')
                content = content.replace('<h1 id="standaloneTitle" class="text-base sm:text-lg font-black text-slate-900">어머니 행복 가계부</h1>', '<h1 id="standaloneTitle" class="text-base sm:text-lg font-black text-slate-900">내 스마트 가계부 & 자산관리 💼</h1>')

        return HTMLResponse(content, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    return JSONResponse({"message": "FinTrack API is running. Frontend index.html not found."})
