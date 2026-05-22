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
    '2317': '鴻海', '2454': '聯發科', '0050': '元大台灣50'
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
    if code.endswith(('.TW', '.TWO')):
        try:
            hist, info = fetch_stock_data(code, period)
            return code, hist, info
        except Exception:
            return code, pd.DataFrame(), {}

    for suffix in ['.TW', '.TWO']:
        symbol = f'{code}{suffix}'
        try:
            hist, info = fetch_stock_data(symbol, period)
        except Exception:
            hist = pd.DataFrame()
            info = {}
        if not hist.empty:
            return symbol, hist, info

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
    if latest['K'] > latest['D']:
        return 'KD 黃金交叉'
    return 'KD 死亡交叉'


def rsi_judgement(latest: dict) -> str:
    if latest['RSI'] >= 70:
        return 'RSI 過熱'
    if latest['RSI'] <= 30:
        return 'RSI 超賣'
    return 'RSI 中性'


def bollinger_judgement(latest: dict, close_price: float) -> str:
    if close_price >= latest['UpperBand']:
        return '價格觸及布林上軌，可能過熱'
    if close_price <= latest['LowerBand']:
        return '價格接近布林下軌，可能反彈'
    return '價格位於布林帶內側'


def macd_judgement(latest: dict) -> str:
    hist_current = latest['Hist']
    hist_prev = latest['Hist_prev']
    hist_abs_current = abs(hist_current)
    hist_abs_prev = abs(hist_prev)
    
    if hist_current > 0:  # 紅柱
        if hist_abs_current > hist_abs_prev:
            return 'MACD 紅柱擴張，多頭動能增強'
        elif hist_abs_current < hist_abs_prev:
            return 'MACD 紅柱縮小，多頭動能衰減，警訊'
        else:
            return 'MACD 多頭勢頭'
    else:  # 綠柱
        if hist_abs_current > hist_abs_prev:
            return 'MACD 綠柱擴張，空頭動能增強，危險'
        elif hist_abs_current < hist_abs_prev:
            return 'MACD 綠柱縮小，空頭衰減，反彈訊號'
        else:
            return 'MACD 空頭勢頭'


def trend_judgement(latest: dict, close_price: float) -> str:
    if latest['SMA50'] and latest['SMA200']:
        if close_price > latest['SMA50'] and close_price > latest['SMA200']:
            return '價格站上SMA50/SMA200，趨勢偏多'
        if close_price < latest['SMA50'] and close_price < latest['SMA200']:
            return '價格跌破SMA50/SMA200，趨勢偏空'
        return '多空分歧，趨勢待觀察'
    if latest['SMA50']:
        return '價格相對SMA50的趨勢判斷可參考中期趨勢'
    return '資料不足，無法判斷中長期趨勢'


def valuation_judgement(info: dict) -> str:
    pe = info.get('trailingPE')
    if pe and pe > 25:
        return 'P/E 偏高，估值需要留意'
    if pe and pe < 15:
        return 'P/E 偏低，估值相對吸引'
    return '估值一般'


def build_signal_text(latest: dict, close_price: float, info: dict):
    texts = [
        kd_judgement(latest),
        rsi_judgement(latest),
        bollinger_judgement(latest, close_price),
        macd_judgement(latest),
        trend_judgement(latest, close_price)
    ]
    return '；'.join(texts)


def create_stock_figure(df: pd.DataFrame, code: str):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.5, 0.2, 0.25],
        specs=[[{"type": "candlestick"}], [{"type": "scatter"}], [{"type": "scatter"}]]
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='K 線'
        ),
        row=1,
        col=1
    )

    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='blue', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['UpperBand'], line=dict(color='orange', width=1, dash='dash'), name='UpperBand'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['LowerBand'], line=dict(color='orange', width=1, dash='dash'), name='LowerBand'), row=1, col=1)
    if 'SMA50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='green', width=1), name='SMA50'), row=1, col=1)
    if 'SMA200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], line=dict(color='purple', width=1), name='SMA200'), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=1), name='RSI'), row=2, col=1)
    fig.add_hline(y=70, line=dict(color='red', dash='dash'), row=2, col=1)
    fig.add_hline(y=30, line=dict(color='green', dash='dash'), row=2, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=np.where(df['Hist'] >= 0, 'green', 'red'), name='MACD Hist'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue', width=1), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange', width=1), name='Signal'), row=3, col=1)

    fig.update_layout(
        title_text=f"{code} 技術指標分析",
        xaxis_rangeslider_visible=False,
        legend_orientation='h',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    return fig


# 介面呈現
st.title("📈 完美股票全方位分析系統")
st.write(f"系統更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

col1, col2 = st.columns([2, 1])
with col1:
    codes_input = st.text_input(
        "輸入台灣股票代號或中文名稱（可用逗號分隔多個項目，例如 2330, 0050, 台積電）",
        value=''
    ).strip()

with col2:
    period = st.selectbox("歷史數據期間", ['3mo', '6mo', '1y', '2y'], index=1)
    show_chart = st.checkbox('顯示技術指標圖表', value=True)

def parse_input_codes(codes_input: str) -> tuple[list[str], list[str]]:
    items = [item.strip() for item in codes_input.split(',') if item.strip()]
    resolved_codes = []
    unknown_items = []

    for item in items:
        item_code = normalize_taiwan_code(item).replace('.TW', '').replace('.TWO', '')
        if item in CHINESE_NAMES.values() or any(ord(ch) > 127 for ch in item):
            code_matches = resolve_chinese_name_to_codes(item)
            if code_matches:
                resolved_codes.extend(code_matches)
                continue

        if item_code.isdigit() or item_code.endswith(('.TW', '.TWO')):
            resolved_codes.append(item_code)
        else:
            unknown_items.append(item)

    return list(dict.fromkeys(resolved_codes)), unknown_items


if st.button("執行全方位健檢"):
    codes, unknown_items = parse_input_codes(codes_input)
    if unknown_items:
        st.warning('以下輸入項目無對應股票代號: ' + ', '.join(unknown_items))

    if not codes:
        st.warning('請先選擇或輸入至少一個股票代號。')
    else:
        results = []
        for code in codes:
            with st.spinner(f'抓取 {code} 資料...'):
                symbol, hist, info = fetch_taiwan_stock_data(code, period)

            if hist.empty or len(hist) < 35:
                st.warning(f'{code} 的歷史資料不足，請確認代號是否正確或更換期間。')
                continue

            latest, hist = calculate_indicators(hist)
            close_price = float(hist['Close'].iloc[-1])
            fund_info = {
                'P/E': info.get('trailingPE', 'N/A'),
                'P/B': info.get('priceToBook', 'N/A'),
                'ROE': info.get('returnOnEquity', 'N/A'),
                'DividendYield': info.get('dividendYield', 'N/A')
            }
            signal_text = build_signal_text(latest, close_price, info)

            results.append({
                '代號': code,
                '名稱': CHINESE_NAMES.get(code.replace('.TW', ''), code),
                '收盤價': round(close_price, 2),
                'KD 判斷': kd_judgement(latest),
                'RSI 判斷': rsi_judgement(latest),
                'MACD 判斷': macd_judgement(latest),
                '布林 判斷': bollinger_judgement(latest, close_price),
                '趨勢判斷': trend_judgement(latest, close_price),
                '判斷': signal_text
            })

            if show_chart:
                st.subheader(f"{code} 技術分析圖表")
                fig = create_stock_figure(hist, code)
                st.plotly_chart(fig, use_container_width=True)

        if results:
            df_result = pd.DataFrame(results)
            st.dataframe(df_result, use_container_width=True)

with st.expander("📊 【股市數據判讀指南】(點擊展開)"):
    st.markdown("""
    - **財報基礎**：毛利率/營益率高代表競爭力與本業獲利強。
    - **估值指標**：P/E < 15 偏低，P/B < 1.2 有長線價值。
    - **技術指標**：
      - **RSI**：> 70 過熱 | < 30 超賣。
      - **KD**：黃金交叉(買進訊號) | 死亡交叉(賣出訊號)。
      - **MACD**：Hist > 0 多頭勢頭 | Hist < 0 空頭勢頭。
      - **布林**：觸上軌(過熱) | 觸下軌(超跌反彈點)。
      - **SMA50 / SMA200**：價格站上代表中長線趨勢偏多。
    - 表格現在只顯示技術指標判斷結果，不再顯示原始數值。
    """)

st.info("💡 部署後可透過 Streamlit 介面選股、查詢期間、並檢視技術指標圖表。")
