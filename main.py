from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd
from dotenv import load_dotenv
from google import generativeai as genai
import os
import re
from datetime import datetime, timedelta
from typing import List
from pykrx import stock
import matplotlib.pyplot as plt
from pykrx import stock
from predictor import AdvancedStockPredictor
from fastapi.responses import HTMLResponse, StreamingResponse
import io

load_dotenv()

genai.configure(api_key="AIzaSyAlC2_u2HwWakWbUTjBH_4W-ErwQaxWtVQ")

# from deepsearch_api import (
#     search_symbol,
#     get_company_overview,
#     get_latest_news,
#     parse_main_products,
# )

app = FastAPI()

templates = Jinja2Templates(directory="template")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})

# corp_list.csv는 'corp_name'과 'stock_code' 열이 존재해야 함
df = pd.read_csv("corp_list.csv", dtype=str)

# corp_name → stock_code 매핑 dict 생성
NAME_TO_TICKER = dict(zip(df["회사명"], df["종목코드"]))

def extract_ticker(text: str):
    for name, ticker in NAME_TO_TICKER.items():
        if name in text:
            return str(ticker).zfill(6), name
    # 숫자 5~6자리 종목코드 직접 입력한 경우
    m = re.search(r"\b\d{5,6}\b", text)
    if m:
        return m.group(0).zfill(6), None
    return None, None

def fetch_stock_data(ticker: str):
    data = {
        "per": None,
        "roe": None,
        "debt_ratio": None,
        "sales": None,
        "market_cap": None,
        "main_products": None,
        "return_1y": None,
        "return_3y": None,
    }

    try:
        today = datetime.today().strftime("%Y%m%d")
        price_df = stock.get_market_ohlcv_by_date(fromdate="20200101", todate=today, ticker=ticker)
        if price_df.empty:
            return data

        current = price_df["종가"].iloc[-1]
        
        date_1y = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
        price_df_1y = price_df.loc[price_df.index >= date_1y]
        if not price_df_1y.empty:
            past_1y_price = price_df_1y["종가"].iloc[0]
            data["return_1y"] = round((current / past_1y_price - 1) * 100, 2)

        date_3y = (datetime.today() - timedelta(days=365 * 3)).strftime("%Y%m%d")
        price_df_3y = price_df.loc[price_df.index >= date_3y]
        if not price_df_3y.empty:
            past_3y_price = price_df_3y["종가"].iloc[0]
            data["return_3y"] = round((current / past_3y_price - 1) * 100, 2)

        finance = stock.get_market_fundamental_by_date(fromdate=today, todate=today, ticker=ticker)
        if not finance.empty:
            data["per"] = round(finance["PER"].iloc[0], 2) if finance["PER"].iloc[0] else None
            data["roe"] = round(finance["ROE"].iloc[0], 2) if finance["ROE"].iloc[0] else None

        corp_info = stock.get_market_cap_by_date(fromdate=today, todate=today, ticker=ticker)
        if not corp_info.empty:
            data["market_cap"] = int(corp_info["시가총액"].iloc[0])

    except Exception as e:
        print("pykrx error", e)

    return data


def build_stock_info(ticker: str):
    try:
        name = stock.get_market_ticker_name(ticker)
        return {
            "name": name,
            "summary": "상세 업종 정보는 제공되지 않습니다.",
            "description": "공식 사업 내용은 별도로 확인해 주세요.",
            "products": [],
        }
    except Exception as e:
        print("build_stock_info error", e)
        return None


SYSTEM_PROMPT_TEMPLATE = """
너는 주식과 회사 정보를 중학생도 이해할 수 있게 쉽게 설명해 주는 봇이야.
추가설명 - 중학생 눈높이 이런건 안적어도 돼, 그냥 부가 설명이라고 해, 
진짜 중학생한테 알려주는게 아니라 중학생도 이해할수 있을 정도로 설명하는게 목표야
주의사항같은거 말하지말고 마지막에 그냥
투자의 책임은 본인에게 있습니다 한마디만 넣어줘
마크다운언어로 예쁘게 작성해줘
"""

CHAT_FORMAT_PROMPT = """
아래 형식에 맞춰 한국어로 답변해주세요.

##부도예측 결과
- 부도 가능성 한 문장

##해당 기업 주요매출 제품
###<주요제품 또는 서비스 1>
- 두줄정도설명

###<주요제품 또는 서비스 2>
- 두줄정도설명

##부가설명
- 그냥 회사에 대한 설립일이랑 개요만 설명해

##최신뉴스
- 너가 해당기업에 대한 최신뉴스 2개 정도 조회해서 제목 적고 링크걸어줘

####투자의 책임은 본인에게 있습니다
"""

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message.strip()
    if not user_msg:
        return {"reply": "메시지를 입력해주세요."}

    ticker, stock_name = extract_ticker(user_msg)
    stock_info = build_stock_info(ticker) if ticker else None

    # symbol_id = overview_text = None
    news_items: List[dict] = []

    # try:
    #     symbol_id = search_symbol(stock_name or user_msg)
    #     if symbol_id:
    #         overview_text = get_company_overview(symbol_id)
    #         news_items = get_latest_news(symbol_id, limit=2)
    # except Exception as e:
    #     print("deepsearch error", e)

    data = fetch_stock_data(ticker) if ticker else {}
    main_products = data.get("main_products")

    
    formatted_news_html = "\n최신뉴스\n뉴스 없음"  # deepsearch 주석 처리로 뉴스 없음 고정

    model = genai.GenerativeModel("gemini-1.5-flash")
    try:
        context_parts = [SYSTEM_PROMPT_TEMPLATE, CHAT_FORMAT_PROMPT]
        if main_products:
            context_parts.append("주요 제품:\n" + main_products)

        prompt = "\n".join(context_parts) + f"\n사용자 질문: {user_msg}"
        response = model.generate_content(prompt)
        answer = response.text.strip() + formatted_news_html
    except Exception as e:
        print("🔥 Gemini API 오류:", e)
        answer = f"부도예측 결과\n오류로 정보를 불러오지 못했습니다.\n해당 기업 주요매출 제품\n{main_products or '정보 없음'}\n{formatted_news_html}"

    return {
        "reply": answer,
        "name": stock_name,
        "per": data.get("per"),
        "roe": data.get("roe"),
        "debt_ratio": data.get("debt_ratio"),
        "sales": data.get("sales"),
        "market_cap": data.get("market_cap"),
        "main_products": main_products,
        "return_1y": data.get("return_1y"),
        "return_3y": data.get("return_3y"),
        "stock_info": stock_info,
        "news": news_items,
        "stock_code": ticker,
    }

# 이미지 플롯 생성 API
@app.get("/plot.png")
async def get_plot(stock_code: str = Query(..., alias="ticker")):
    try:
        predictor = AdvancedStockPredictor(stock_code)
        threeago = datetime.today() - timedelta(days=365 * 3)
        predictor.load_data(start_date=threeago)
        forecasts = predictor.comprehensive_forecast()
        trend_signal, trend_changes, ma_short, ma_long = predictor.detect_regime_changes()
        var_95, max_drawdown, drawdown = predictor.calculate_downside_risk()

        buf = io.BytesIO()
        fig, ax1 = plt.subplots(figsize=(8, 6))

        # 주가 및 이동평균선
        ax1.plot(predictor.df_monthly.index, predictor.df_monthly.values, label='주가', color='black', linewidth=2)
        ax1.plot(ma_short.index, ma_short.values, label='6개월 이동평균선', alpha=0.7, color='blue')
        ax1.plot(ma_long.index, ma_long.values, label='1년 이동평균선', alpha=0.7, color='orange')

        # 예측 구간 음영
        ax1.fill_between(forecasts['dates'], forecasts['monte_carlo'][1], forecasts['monte_carlo'][0],
                         alpha=0.3, color='red', label='예측범위')

        # 스타일 적용
        ax1.set_ylabel('주가(원)', fontsize=18)
        ax1.set_xlabel('날짜', fontsize=18)
        ax1.tick_params(axis='both', labelsize=18)
        ax1.legend(fontsize=18)
        ax1.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        print("🔥 Plot 오류:", e)
        return {"error": "차트 생성에 실패했습니다."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
