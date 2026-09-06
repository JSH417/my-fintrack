import requests
import re
from typing import Optional, Dict, Any
from .database import get_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_usd_krw_rate() -> float:
    """실시간 USD/KRW 환율 조회 (실패 시 DB 설정값 또는 기본 1350.0 반환)"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1d&range=1d"
        res = requests.get(url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            data = res.json()
            rate = data['chart']['result'][0]['meta']['regularMarketPrice']
            if rate and rate > 0:
                return float(rate)
    except Exception as e:
        print(f"환율 조회 실패 (기본값 대체): {e}")

    # DB에 저장된 최근 환율 확인
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'usd_krw_rate'")
        row = cursor.fetchone()
        conn.close()
        if row and row['value']:
            return float(row['value'])
    except Exception:
        pass

    return 1350.0

def fetch_crypto_price_upbit(symbol: str) -> Optional[float]:
    """업비트 원화 마켓 시세 조회 (예: 'BTC', 'KRW-BTC', 'ETH' 등)"""
    clean_sym = symbol.strip().upper()
    if not clean_sym.startswith("KRW-"):
        market = f"KRW-{clean_sym}"
    else:
        market = clean_sym

    try:
        url = f"https://api.upbit.com/v1/ticker?markets={market}"
        res = requests.get(url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return float(data[0]['trade_price'])
    except Exception as e:
        print(f"업비트 시세 조회 실패 ({symbol}): {e}")
    return None

def fetch_stock_price_yahoo(symbol: str) -> Optional[float]:
    """Yahoo Finance를 통한 주식/ETF 시세 조회 (국내/해외)"""
    clean_sym = symbol.strip().upper()

    # 한국 6자리 숫자 종목코드인 경우 코스피(.KS) 우선 시도, 실패 시 코스닥(.KQ) 시도
    candidates = [clean_sym]
    if re.match(r"^\d{6}$", clean_sym):
        candidates = [f"{clean_sym}.KS", f"{clean_sym}.KQ"]
    elif not ("." in clean_sym or "=" in clean_sym or "^" in clean_sym):
        candidates = [clean_sym]

    for ticker in candidates:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
            res = requests.get(url, headers=HEADERS, timeout=4)
            if res.status_code == 200:
                data = res.json()
                result = data.get('chart', {}).get('result')
                if result and len(result) > 0:
                    price = result[0].get('meta', {}).get('regularMarketPrice')
                    if price is not None and price > 0:
                        return float(price)
        except Exception:
            continue
    return None

def fetch_live_price(symbol: str, category: str = "kr_stock") -> Optional[float]:
    """종목코드와 카테고리에 맞춰 최적의 가격 조회"""
    if not symbol:
        return None
    
    # 1. 암호화폐인 경우
    if category == "crypto" or symbol.upper().startswith("KRW-"):
        price = fetch_crypto_price_upbit(symbol)
        if price:
            return price

    # 2. 주식 / ETF 인 경우
    price = fetch_stock_price_yahoo(symbol)
    if price:
        return price

    # 3. 혹시나 암호화폐 티커인데 일반 주식으로 입력했을 경우를 대비해 업비트 추가 시도
    crypto_price = fetch_crypto_price_upbit(symbol)
    if crypto_price:
        return crypto_price

    return None

def update_all_investments() -> Dict[str, Any]:
    """DB에 등록된 모든 투자 종목의 현재 시세를 일괄 갱신하고 최신 환율 반영"""
    usd_rate = get_usd_krw_rate()
    conn = get_db()
    cursor = conn.cursor()

    # 최신 환율 설정 저장
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('usd_krw_rate', ?)", (str(usd_rate),))

    cursor.execute("SELECT id, symbol, category, current_price, currency FROM investments")
    investments = cursor.fetchall()

    updated_count = 0
    results = []

    for inv in investments:
        inv_id = inv['id']
        sym = inv['symbol']
        cat = inv['category']
        old_price = inv['current_price']

        # 예적금, 기타 등 고정 자산은 시세 조회 대상 제외
        if cat in ('savings', 'fund', 'etc'):
            continue

        new_price = fetch_live_price(sym, cat)
        if new_price and new_price > 0:
            cursor.execute("UPDATE investments SET current_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_price, inv_id))
            updated_count += 1
            results.append({
                "id": inv_id,
                "symbol": sym,
                "old_price": old_price,
                "new_price": new_price
            })

    conn.commit()
    conn.close()

    return {
        "success": True,
        "updated_count": updated_count,
        "usd_krw_rate": usd_rate,
        "details": results
    }
