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
    if not name: return []
    exact_match = {v: k for k, v in CHINESE_NAMES.items()}
    if name in exact_match: return [exact_match[name]]
    return [k for k, v in CHINESE_NAMES.items() if name in v]

@st.cache_data(ttl=3600)
def fetch_taiwan_stock_data(code: str, period: str):
    code = normalize_taiwan_code(code)
    possible_symbols = [code] if code.endswith(('.TW', '.TWO')) else [f'{code}.TW', f'{code}.TWO']
    
    for symbol in possible_symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if not hist.empty and len(hist) >= 5:
                # 容錯處理：如果 info 抓不到，給空字典，不要讓程式崩潰
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
    # KD
    df['RSV'] = (df['Close'] - df['Low'].rolling(9).min()) / (df['High'].rolling(9).max() - df['Low'].rolling(9).min()) * 100
    df['RSV'] = df['RSV'].fillna(50)
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    df['RSI'] = 100 - 100 / (1 + gain.div(loss.replace(0, np.nan)))
    
    # 布林通道 & 均線
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()
    
    # MACD
    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    
    latest = {
        'K': round(df['K'].iloc[-1], 2),
        'D': round(df['D'].iloc[-1], 2),
        'RSI': round(df['RSI'].iloc[-1], 2) if not np.isnan(df['RSI'].iloc[-1]) else 50,
        'UpperBand': round(df['UpperBand'].iloc[-1], 2) if not np.isnan(df['UpperBand'].iloc[-1]) else 0,
        'LowerBand': round(df['LowerBand'].iloc[-1], 2) if not np.isnan(df['LowerBand'].iloc[-1]) else 0,
        'MA20': round(df['MA20'].iloc[-1], 2) if not np.isnan(df['MA20'].iloc[-1]) else 0,
        'SMA50': round(df['SMA50'].iloc[-1], 2) if not np.isnan(df['SMA50'].iloc[-1]) else 0,
        'SMA200': round(df['SMA200'].iloc[-1], 2) if not np.isnan(df['SMA200'].iloc[-1]) else 0,
        'MACD': round(df['MACD'].iloc[-1], 2),
        'Signal': round(df['Signal'].iloc[-1], 2),
        'Hist': round(df['Hist'].iloc[-1], 2),
        'Hist_prev': round(df['Hist'].iloc[-2], 2) if len(df) > 1 else 0
    }
    return latest, df

# --- 判斷邏輯 ---
def kd_judgement(latest: dict) -> str:
    return '黃金交叉' if latest['K'] > latest['D'] else '死亡交叉'

def rsi_judgement(latest: dict) -> str:
    if latest['RSI'] >= 70: return '偏強過熱'
    if latest['RSI'] <= 30: return '超賣區間'
    return '中性震盪'

def macd_judgement(latest: dict) -> str:
    if latest['Hist'] > 0:
        return '紅柱擴張' if abs(latest['Hist']) > abs(latest['Hist_prev']) else '紅柱縮小'
    else:
        return '綠柱擴張' if abs(latest['Hist']) > abs(latest['Hist_prev']) else '綠柱縮小'

def trend_judgement(latest: dict, close_price: float) -> str:
    if latest['SMA50'] > 0 and latest['SMA200'] > 0:
        if close_price > latest['SMA50'] and latest['SMA50'] > latest['SMA200']: return '多頭排列'
        if close_price < latest['SMA50'] and latest['SMA50'] < latest['SMA200']: return '空頭排列'
    return '震盪整理'

# --- 繪圖邏輯 ---
def create_stock_figure(df: pd.DataFrame, code: str):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # 價格與均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    if 'MA20' in df: fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='月線(20)'), row=1, col=1)
    if 'SMA50' in df: fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='green', width=1.5), name='季線(50)'), row=1, col=1)
    
    # MACD
    colors = np.where(df['Hist'] >= 0, 'red', 'green') # 台股習慣紅漲綠跌
    fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD 柱狀體'), row=2, col=1)
    
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis_rangeslider_visible=False, showlegend=False)
    return fig

# ==========================================
# 介面呈現 (圖解儀表板版面)
# ==========================================
st.title("📈 完美股票全方位分析系統")
st.markdown("---")

col1, col2 = st.columns([2, 1])
with col1:
    codes_input = st.text_input("輸入股票代號 (例如 2327, 2330, 0050)", value="2327").strip()
with col2:
    period = st.selectbox("期間", ['3mo', '6mo', '1y', '2y'], index=1)

if st.button("執行全方位健檢", type="primary"):
    items = [i.strip() for i in codes_input.split(',')]
    for item in items:
        if not item: continue
        code_list = resolve_chinese_name_to_codes(item) if any(ord(c) > 127 for c in item) else [item]
        
        for code in code_list:
            with st.spinner(f"正在分析 {code}..."):
                symbol, hist, info = fetch_taiwan_stock_data(code, period)
                
            if hist.empty:
                st.error(f'❌ {code} 無法取得數據，請確認代號是否正確。')
                continue
                
            latest, hist = calculate_indicators(hist)
            close_price = round(float(hist['Close'].iloc[-1]), 2)
            stock_name = CHINESE_NAMES.get(code.replace('.TW', '').replace('.TWO', ''), code)

            # --- 綜合評分邏輯 (簡單範例) ---
            stars = "★★★☆☆"
            trend_text = "震盪"
            strategy_text = "觀望為主"
            if close_price > latest['SMA50'] and latest['Hist'] > 0:
                stars = "★★★★☆"
                trend_text = "偏多"
                strategy_text = "等拉回，不追漲"
            elif close_price < latest['SMA50'] and latest['Hist'] < 0:
                stars = "★★☆☆☆"
                trend_text = "偏空"
                strategy_text = "保守應對"

            # 【區塊 1：大標題與策略】
            st.markdown(f"<h1 style='text-align: center; color: #B22222; font-weight: 900; margin-bottom: 0px;'>{stock_name} {code} | 短中期進場圖解</h1>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style='background-color: #f0f2f6; padding: 12px; border-radius: 8px; text-align: center; font-size: 18px; font-weight: bold; margin-top: 15px; margin-bottom: 20px;'>
                ⭐ 綜合評等：<span style='color:#e6a100;'>{stars}</span> &nbsp;&nbsp;|&nbsp;&nbsp; 📈 趨勢：{trend_text} &nbsp;&nbsp;|&nbsp;&nbsp; 🎯 策略：{strategy_text}
            </div>
            """, unsafe_allow_html=True)

            # 【區塊 2：主圖與結論】
            st.markdown("### ❶ 價格走勢與均線")
            col_chart, col_summary = st.columns([2.5, 1])
            with col_chart:
                fig = create_stock_figure(hist, code)
                st.plotly_chart(fig, use_container_width=True)
            
            with col_summary:
                st.markdown("#### 📝 走勢結構")
                if close_price > latest['MA20']:
                    st.success("✔️ 股價站上月線\n\n✔️ 短線具備支撐\n\n✔️ 留意量能變化")
                else:
                    st.warning("⚠️ 股價跌破月線\n\n⚠️ 短線需注意防守\n\n⚠️ 避免過度追價")
                
                st.info(f"**最新收盤價：** {close_price}\n\n**布林上軌：** {latest['UpperBand']}\n\n**布林下軌：** {latest['LowerBand']}")

            # 【區塊 3：技術訊號總覽】
            st.markdown("### ❷ 技術訊號總覽")
            t1, t2, t3, t4 = st.columns(4)
            with t1:
                st.markdown(f"**🔵 MACD: {macd_judgement(latest)}**")
                st.metric("MACD 柱狀體", latest['Hist'], delta=round(latest['Hist'] - latest['Hist_prev'], 2))
            with t2:
                st.markdown(f"**🟠 RSI: {rsi_judgement(latest)}**")
                st.metric("RSI 數值", latest['RSI'])
            with t3:
                st.markdown(f"**🟢 KD: {kd_judgement(latest)}**")
                st.metric("K值", latest['K'])
            with t4:
                st.markdown(f"**🟣 均線: {trend_judgement(latest, close_price)}**")
                st.metric("月線 (MA20)", latest['MA20'])

            st.markdown("---")

            # 【區塊 4：籌碼與資金面 (無真實數據，以佔位符呈現版面)】
            st.markdown("### ❸ 籌碼與資金面 (示意區塊)")
            f1, f2, f3, f4 = st.columns(4)
            f1.warning("🏢 投信：待確認")
            f2.info("👤 大戶：待確認")
            f3.error("💰 融資：待確認")
            f4.success("🧑‍💼 法人：待確認")

            st.markdown("---")

            # 【區塊 5：進場策略與行動規劃】
            st.markdown("### ❹ 進場策略與行動規劃")
            s1, s2 = st.columns([1, 2])
            with s1:
                st.markdown("#### 可以進場嗎？")
                if trend_text == "偏多":
                    st.success("✅ **可以，但等拉回更好**")
                else:
                    st.warning("⏸️ **建議先觀望，等待訊號**")
            with s2:
                buy_zone_low = round(latest['MA20'] * 0.98, 1) if latest['MA20'] > 0 else round(close_price * 0.95, 1)
                buy_zone_high = round(latest['MA20'] * 1.02, 1) if latest['MA20'] > 0 else close_price
                stop_loss = round(latest['LowerBand'], 1)
                
                st.markdown(f"""
                - 🎯 **觀察買點：** `{buy_zone_low} ~ {buy_zone_high}` (回測支撐區企穩再布局)
                - ⚠️ **不追價區：** `{latest['UpperBand']} 以上` (高檔追價風險高)
                - 🛑 **防守點位：** `{stop_loss}` (跌破轉弱，嚴守紀律)
                """)
            
            st.markdown("<p style='text-align: center; color: gray; margin-top: 30px;'>💡 原則：順勢操作、等回測、設停損，才能提高勝率、保護資金！</p>", unsafe_allow_html=True)
