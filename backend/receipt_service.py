import requests
import json
import base64
import os
import re
from typing import Optional, Dict, Any
from .database import get_db

DEFAULT_CATEGORIES = [
    "식비", "카페/간식", "마트/장보기", "교통/차량", "주거/통신", 
    "생활용품", "의료/건강", "문화/여가", "경조사/선물", "기타지출"
]

def get_gemini_api_key() -> Optional[str]:
    """환경변수 또는 DB settings에서 Gemini API 키 조회"""
    # 1. 환경변수 확인
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    # 2. DB settings 확인
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
        row = cursor.fetchone()
        conn.close()
        if row:
            val = row['value'] if isinstance(row, dict) else row[0]
            if val and str(val).strip():
                return str(val).strip()
    except Exception as e:
        print(f"API 키 조회 중 오류: {e}")

    return None

def analyze_receipt_with_gemini(image_bytes: bytes, mime_type: str = "image/jpeg", api_key: Optional[str] = None) -> Dict[str, Any]:
    """Gemini 1.5 Flash Vision API를 사용하여 영수증 이미지 분석 및 JSON 데이터 추출"""
    key = api_key or get_gemini_api_key()
    if not key:
        return {
            "success": False,
            "error": "GEMINI_API_KEY_REQUIRED",
            "message": "Gemini API 키가 등록되지 않았습니다. [설정] 메뉴에서 무료 API 키를 등록해주세요."
        }

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    categories_str = ", ".join([f"'{c}'" for c in DEFAULT_CATEGORIES])
    prompt = f"""
    당신은 한국 가계부 영수증 전문 분석 AI입니다.
    제공된 영수증(신용카드 전표, 마트 영수증, 간이영수증 등) 이미지를 정확하게 분석하여 다음 정보들을 추출하세요.
    반드시 순수한 JSON 형식으로만 응답하고, 마크다운 코드블록(```json 등)이나 다른 설명 텍스트를 절대 붙이지 마세요.

    JSON 형식:
    {{
        "amount": 숫자 (최종 결제 금액 또는 합계 금액, 원 단위 정수, 쉼표 없이 숫자만),
        "date": "YYYY-MM-DD" (영수증에 인쇄된 거래 날짜. 연도가 없으면 2026년 기준),
        "store_name": "상호명 또는 가게 이름",
        "memo": "상호명 및 대표 구매 품목 요약 (예: 스타벅스 아메리카노, 이마트 장보기 등)",
        "category": {categories_str} 중 가장 알맞은 단 하나의 카테고리
    }}
    """

    # Gemini endpoint (supports 1.5 flash and 2.0 flash)
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash"]
    last_error = ""

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    continue

                content_text = candidates[0]["content"]["parts"][0]["text"].strip()
                if content_text.startswith("```"):
                    content_text = re.sub(r"^```(?:json)?", "", content_text).strip()
                    content_text = re.sub(r"```$", "", content_text).strip()

                parsed = json.loads(content_text)

                # 1. Sanitize amount (숫자 또는 "15,000원" 형태 정제)
                raw_amt = parsed.get("amount", 0)
                try:
                    if isinstance(raw_amt, str):
                        cleaned = re.sub(r"[^\d]", "", raw_amt)
                        amount = int(cleaned) if cleaned else 0
                    else:
                        amount = int(raw_amt)
                except Exception:
                    amount = 0

                # 2. Sanitize date (YYYY-MM-DD)
                date_val = str(parsed.get("date", "")).strip()
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                    from datetime import datetime
                    date_val = datetime.now().strftime("%Y-%m-%d")

                # 3. Sanitize category
                cat = parsed.get("category", "기타지출")
                if cat not in DEFAULT_CATEGORIES:
                    cat = "기타지출"

                store = str(parsed.get("store_name", "")).strip()
                memo = str(parsed.get("memo", "")).strip()
                if not memo and store:
                    memo = store

                return {
                    "success": True,
                    "amount": amount,
                    "date": date_val,
                    "store_name": store,
                    "memo": memo,
                    "category": cat
                }
            else:
                last_error = f"API 오류 ({res.status_code}): {res.text[:120]}"
        except json.JSONDecodeError:
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "success": False,
        "message": f"영수증 분석에 실패했습니다. ({last_error if last_error else '영수증이 선명한지 확인해주세요'})"
    }
