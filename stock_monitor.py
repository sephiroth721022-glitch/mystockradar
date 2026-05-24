import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 頁面設定
st.set_page_config(page_title="完美股票分析系統", layout="wide")

# 基礎資料設定
CHINESE_NAMES = {
    '3131': '弘塑', '3583': '辛耘', '6187': '萬潤', '1560': '中砂',
    '3680': '家登', '3413': '京鼎', '2404': '漢唐', '6196': '帆宣',
    '6640': '均華', '6667': '信紘科', '6515': '穎崴', '3402': '漢科',
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2317': '鴻海', '2454': '聯發科', '0050': '元大台灣50', '3026': '禾伸堂'
}

def normalize_taiwan_code(code: str) -> str:
    return code.upper().replace(' ', '')

def resolve_chinese_name_to_codes(name: str) -> list[str]:
    name = name.strip()
    if not name:
        return []
    exact_match = {v: k for k, v in CHINESE_NAMES.items()}
    if name in exact_match:
        return [exact_match[name]]
    partial_matches = [k for k, v in CHINESE_NAMES.items() if name in v]
    return partial_matches

@st.cache_data(ttl=3600)
def fetch_stock_data(symbol: str, period: str):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    info = ticker.info or {}
    return hist, info

@st.cache_data(ttl=3600)
def fetch_taiwan_stock_data(code: str, period: str):
    code = normalize_taiwan_code(code)
    # 建立可能的符號清單
    possible_symbols = []
    if code.endswith(('.TW', '.TWO')):
        possible_symbols = [code]
    else:
        possible_symbols = [f'{code}.TW', f'{code}.TWO']

    for symbol in possible_symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            # 只要有歷史資料，就視為成功
            if not hist.empty and len(hist) >= 5:
                try:
                    info = ticker.info if ticker.info is not None else {}
                except:
                    info = {}
                return symbol, hist, info
        except Exception:
            continue
    return f'{code}.TW', pd.DataFrame(), {}

def calculate_indicators(df: pd.DataFrame):
    df = df.copy()
    df['RSV'] = (df['Close'] - df['Low'].rolling(9).min()) / (
        df['High'].rolling(9).max() - df['Low'].rolling(9).min()) * 100
    df['RSV'] = df['RSV'].fillna(50)
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()

    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    df['RSI'] = 100 - 100 / (1 + gain.div(loss.replace(0, np.nan)))

    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()

    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    latest = {
        'K': round(df['K'].iloc[-1], 2),
        'D': round(df['D'].iloc[-1], 2),
        'RSI': round(df['RSI'].iloc[-1], 2),
        'UpperBand': round(df['UpperBand'].iloc[-1], 2),
        'LowerBand': round(df['LowerBand'].iloc[-1], 2),
        'MA20': round(df['MA20'].iloc[-1], 2) if not np.isnan(df['MA20'].iloc[-1]) else None,
        'SMA50': round(df['SMA50'].iloc[-1], 2) if not np.isnan(df['SMA50'].iloc[-1]) else None,
        'SMA200': round(df['SMA200'].iloc[-1], 2) if not np.isnan(df['SMA200'].iloc[-1]) else None,
        'MACD': round(df['MACD'].iloc[-1], 2),
        'Signal': round(df['Signal'].iloc[-1], 2),
        'Hist': round(df['Hist'].iloc[-1], 2),
        'Hist_prev': round(df['Hist'].iloc[-2], 2) if len(df) > 1 else 0
    }
    return latest, df

def kd_judgement(latest: dict) -> str:
    return 'KD 黃金交叉' if latest['K'] > latest['D'] else 'KD 死亡交叉'

def rsi_judgement(latest: dict) -> str:
    if latest['RSI'] >= 70: return 'RSI 過熱'
    if latest['RSI'] <= 30: return 'RSI 超賣'
    return 'RSI 中性'

def bollinger_judgement(latest: dict, close_price: float) -> str:
    if close_price >= latest['UpperBand']: return '價格觸及布林上軌'
    if close_price <= latest['LowerBand']: return '價格接近布林下軌'
    return '價格位於布林帶內側'

def macd_judgement(latest: dict) -> str:
    hist_current = latest['Hist']
    hist_prev = latest['Hist_
