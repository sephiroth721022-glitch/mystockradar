import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ==================== 頁面設定 ====================
st.set_page_config(
    page_title="完美股票分析系統 v2.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 基礎資料 ====================
CHINESE_NAMES = {
    '3131': '弘塑', '3583': '辛耘', '6187': '萬潤', '1560': '中砂',
    '3680': '家登', '3413': '京鼎', '2404': '漢唐', '6196': '帆宣',
    '6640': '均華', '6667': '信紘科', '6515': '穎崴', '3402': '漢科',
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2317': '鴻海', '2454': '聯發科', '0050': '元大台灣50', '3026': '禾伸堂',
    '2382': '廣達', '2308': '台達電', '2882': '國泰金', '2881': '富邦金'
}

def normalize_taiwan_code(code: str) -> str:
    return code.upper().replace(' ', '').replace('.TW', '').replace('.TWO', '')

def resolve_chinese_name_to_codes(name: str) -> list[str]:
    name = name.strip()
    if not name:
        return []
    exact_match = {v: k for k, v in CHINESE_NAMES.items()}
    if name in exact_match:
        return [exact_match[name]]
    return [k for k, v in CHINESE_NAMES.items() if name in v]

# ==================== 資料擷取（大幅強化版） ====================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_taiwan_stock_data(code: str, period: str = None, start: str = None, end: str = None):
    base = normalize_taiwan_code(code)
    candidates = []
    if code.endswith(('.TW', '.TWO')):
        candidates = [code]
    else:
        candidates = [f"{base}.TW", f"{base}.TWO", base]

    for sym in candidates:
        try:
            ticker = yf.Ticker(sym)
            if start and end:
                hist = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)
            else:
                hist = ticker.history(period=period or "6mo", interval="1d", auto_adjust=True)

            if not hist.empty and len(hist) >= 5:
                info = {}
                try:
                    info = ticker.info or {}
                except:
                    pass

                holders = pd.DataFrame()
                try:
                    holders = ticker.institutional_holders or pd.DataFrame()
                except:
                    pass

                return sym, hist, info, holders
        except Exception:
            continue

    return f"{base}.TW", pd.DataFrame(), {}, pd.DataFrame()

# ==================== 技術指標計算（強化版） ====================
def calculate_indicators(df: pd.DataFrame):
    df = df.copy()

    # KD
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['RSV'] = df['RSV'].fillna(50)
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()

    # RSI（更穩健版）
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # 布林通道 + 均線
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

    # 新增 ATR + OBV
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()

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
        'Hist_prev': round(df['Hist'].iloc[-2], 2) if len(df) > 1 else 0,
        'ATR': round(df['ATR'].iloc[-1], 2) if not np.isnan(df['ATR'].iloc[-1]) else 0,
        'OBV': int(df['OBV'].iloc[-1]) if not np.isnan(df['OBV'].iloc[-1]) else 0
    }
    return latest, df

# ==================== 綜合評分系統（核心升級） ====================
def get_overall_recommendation(latest: dict, close_price: float, df: pd.DataFrame):
    score = 50
    reasons = []

    # 1. 趨勢排列
    if latest['SMA200'] > 0 and latest['SMA50'] > 0:
        if close_price > latest['SMA50'] > latest['SMA200']:
            score += 20
            reasons.append("✅ 多頭排列（價 > 季線 > 年線）")
        elif close_price < latest['SMA50'] < latest['SMA200']:
            score -= 15
            reasons.append("⚠️ 空頭排列（價 < 季線 < 年線）")
        else:
            reasons.append("➡️ 均線糾結，震盪整理中")

    # 2. MACD
    if latest['Hist'] > 0:
        score += 12
        reasons.append("✅ MACD 紅柱（多頭動能）")
        if latest['Hist'] > latest['Hist_prev']:
            score += 8
            reasons.append("📈 紅柱擴張中（動能增強）")
    else:
        score -= 8
        reasons.append("⚠️ MACD 綠柱（空頭動能）")

    # 3. RSI
    if 35 <= latest['RSI'] <= 65:
        score += 10
        reasons.append("✅ RSI 中性偏強（無過熱）")
    elif latest['RSI'] > 70:
        score -= 12
        reasons.append("⚠️ RSI 超買區（可能回檔）")
    elif latest['RSI'] < 30:
        score += 8
        reasons.append("✅ RSI 超賣（潛在反彈）")

    # 4. KD
    if latest['K'] > latest['D']:
        score += 10
        reasons.append("✅ KD 黃金交叉")
        if latest['K'] > 80:
            score -= 5
            reasons.append("⚠️ K值過高（短線過熱）")
    else:
        score -= 5
        reasons.append("⚠️ KD 死亡交叉")

    # 5. 布林位置
    if latest['UpperBand'] > 0 and latest['LowerBand'] > 0:
        bb_pos = (close_price - latest['LowerBand']) / (latest['UpperBand'] - latest['LowerBand'])
        if bb_pos < 0.2:
            score += 8
            reasons.append("✅ 股價接近布林下軌（低檔支撐）")
        elif bb_pos > 0.8:
            score -= 8
            reasons.append("⚠️ 股價接近布林上軌（高檔壓力）")

    # 6. 價格 vs 月線
    if close_price > latest['MA20']:
        score += 7
        reasons.append("✅ 站上月線（短線偏多）")
    else:
        score -= 5
        reasons.append("⚠️ 跌破月線（短線偏弱）")

    score = max(0, min(100, score))

    if score >= 80:
        stars, trend_text, strategy_text = "★★★★★", "強勢多頭", "積極進場，拉回視為買點"
    elif score >= 65:
        stars, trend_text, strategy_text = "★★★★☆", "偏多格局", "等回測月線或季線支撐再布局"
    elif score >= 50:
        stars, trend_text, strategy_text = "★★★☆☆", "震盪整理", "觀望為主，等待明確訊號"
    elif score >= 35:
        stars, trend_text, strategy_text = "★★☆☆☆", "偏空格局", "保守操作，設好停損"
    else:
        stars, trend_text, strategy_text = "★☆☆☆☆", "弱勢空頭", "暫時避開，等待底部訊號"

    return stars, trend_text, strategy_text, score, reasons

# ==================== 專業圖表 ====================
def create_stock_figure(df: pd.DataFrame, stock_name: str, code: str):
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.48, 0.15, 0.20, 0.17],
        vertical_spacing=0.025,
        subplot_titles=("K線 + 布林通道 + 均線", "成交量", "MACD", "RSI + KD 指標")
    )

    # Row 1: K線 + 均線 + 布林
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='K線'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FF8C00', width=2), name='月線(20)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='#32CD32', width=2), name='季線(50)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], line=dict(color='#9370DB', width=2), name='年線(200)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['UpperBand'], line=dict(color='rgba(255,0,0,0.6)', width=1, dash='dash'), name='布林上軌'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['LowerBand'], line=dict(color='rgba(0,255,0,0.6)', width=1, dash='dash'), name='布林下軌'), row=1, col=1)

    # Row 2: 成交量
    vol_color = np.where(df['Close'] >= df['Open'], '#00C853', '#FF1744')
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_color, name='成交量'), row=2, col=1)

    # Row 3: MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2196F3', width=2), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#FF9800', width=2), name='Signal'), row=3, col=1)
    colors = np.where(df['Hist'] >= 0, '#FF1744', '#00C853')
    fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='柱狀體'), row=3, col=1)

    # Row 4: RSI + KD
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#9C27B0', width=2.5), name='RSI'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='#03A9F4', width=2), name='K值'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='#FF5722', width=2), name='D值'), row=4, col=1)

    # 超買超賣線
    for y, color, dash in [(70, 'red', 'dash'), (30, 'green', 'dash'), (80, 'darkred', 'dot'), (20, 'darkgreen', 'dot')]:
        fig.add_hline(y=y, line_dash=dash, line_color=color, line_width=1, row=4, col=1)

    fig.update_layout(
        height=820,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=True,
        title=f"{stock_name} ({code}) 專業技術分析圖"
    )
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="量", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="指標值", row=4, col=1, range=[0, 100])

    return fig

# ==================== 主介面 ====================
st.title("📈 完美股票全方位分析系統 v2.0")
st.markdown("**台股專用 | 即時技術指標 + 綜合評分 + 專業圖表**")
st.markdown("---")

# 側邊欄 + 快速選擇
with st.sidebar:
    st.header("⚙️ 分析參數")
    period = st.selectbox("預設期間", ['1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'], index=2)
    use_custom = st.checkbox("使用自訂日期範圍")

    if use_custom:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("開始日期", datetime(2024, 6, 1))
        with col2:
            end_date = st.date_input("結束日期", datetime.now().date())
    else:
        start_date = end_date = None

    st.markdown("---")
    st.caption("資料來源：Yahoo Finance\n建議在台股收盤後使用")

# 快速選擇熱門股
st.markdown("### 🔥 快速選擇熱門股")
qc_cols = st.columns(5)
quick_list = [("台積電", "2330"), ("鴻海", "2317"), ("聯發科", "2454"), ("元大50", "0050"), ("漢唐", "2404")]

for col, (name, code) in zip(qc_cols, quick_list):
    if col.button(name, use_container_width=True):
        st.session_state.codes_input = code
        st.rerun()

if "codes_input" not in st.session_state:
    st.session_state.codes_input = "2327,2330"

codes_input = st.text_input(
    "輸入股票代號或中文名稱（逗號分隔）",
    value=st.session_state.codes_input,
    key="codes_input",
    placeholder="例如：2330, 台積電, 0050, 2317"
)

if st.button("🚀 執行全方位健檢", type="primary", use_container_width=True):
    items = [i.strip() for i in codes_input.split(',') if i.strip()]
    if not items:
        st.warning("請至少輸入一個股票代號或名稱")
        st.stop()

    for item in items:
        code_list = resolve_chinese_name_to_codes(item) if any(ord(c) > 127 for c in item) else [item]

        for code in code_list:
            with st.spinner(f"正在分析 {code}..."):
                if use_custom and start_date and end_date:
                    symbol, hist, info, holders = fetch_taiwan_stock_data(
                        code,
                        start=start_date.strftime("%Y-%m-%d"),
                        end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    )
                else:
                    symbol, hist, info, holders = fetch_taiwan_stock_data(code, period=period)

            if hist.empty:
                st.error(f"❌ {code} 無法取得數據\n可能原因：代號錯誤、該股票資料尚未更新、或 Yahoo Finance 暫時限制\n建議至 https://finance.yahoo.com/quote/{code}.TW 手動確認")
                continue

            latest, hist = calculate_indicators(hist)
            close_price = round(float(hist['Close'].iloc[-1]), 2)
            stock_name = CHINESE_NAMES.get(code.replace('.TW', '').replace('.TWO', ''), code)

            stars, trend_text, strategy_text, score, reasons = get_overall_recommendation(latest, close_price, hist)

            # ========== 每檔股票獨立區塊 ==========
            with st.expander(f"📊 {stock_name} ({symbol}) | 健康分數：{score}/100 | {trend_text}", expanded=True):
                # 標題 + 評分
                st.markdown(f"""
                <div style="background: linear-gradient(90deg, #1a237e, #283593); padding: 15px; border-radius: 12px; color: white; text-align: center; margin-bottom: 15px;">
                    <h2 style="margin:0; color:#FFD700;">{stars}</h2>
                    <h3 style="margin:5px 0;">{trend_text}　｜　策略建議：{strategy_text}</h3>
                    <p style="margin:0; font-size:14px;">綜合健康分數：<b>{score}/100</b></p>
                </div>
                """, unsafe_allow_html=True)

                # 理由
                st.markdown("**📋 評分理由**")
                for r in reasons:
                    st.write(f"- {r}")

                # 公司基本資料
                st.markdown("### 公司基本資訊")
                if info:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**產業**：{info.get('sector', '未提供')}")
                        st.write(f"**類別**：{info.get('industry', '未提供')}")
                    with c2:
                        mcap = info.get('marketCap')
                        if mcap:
                            st.metric("市值", f"{mcap/1e9:,.1f} 億")
                        pe = info.get('trailingPE') or info.get('forwardPE')
                        if pe:
                            st.metric("本益比", f"{pe:.1f}")
                else:
                    st.caption("基本資料有限（yfinance 對部分台股支援較低）")

                # 主圖
                st.markdown("### ❶ 專業技術走勢圖")
                fig = create_stock_figure(hist, stock_name, symbol)
                st.plotly_chart(fig, use_container_width=True)

                # 技術訊號總覽
                st.markdown("### ❷ 技術訊號總覽")
                t1, t2, t3, t4 = st.columns(4)
                with t1:
                    st.metric("MACD 柱狀體", latest['Hist'], delta=round(latest['Hist'] - latest['Hist_prev'], 2))
                with t2:
                    st.metric("RSI", latest['RSI'])
                with t3:
                    st.metric("K / D", f"{latest['K']} / {latest['D']}")
                with t4:
                    st.metric("月線 (MA20)", latest['MA20'])

                # 籌碼區
                st.markdown("### ❸ 籌碼與資金面")
                if not holders.empty:
                    st.success("✅ 已取得機構持股資料（前 5 大）")
                    st.dataframe(
                        holders.head(5)[['Holder', '% Out']].style.format({'% Out': '{:.2%}'}),
                        use_container_width=True
                    )
                else:
                    st.warning("⚠️ yfinance 暫無詳細籌碼數據\n建議至「公開資訊觀測站」查詢最新投信/法人買賣超")

                # 進場策略
                st.markdown("### ❹ 進場策略與風險控管")
                buy_low = round(latest['MA20'] * 0.97, 1) if latest['MA20'] > 0 else round(close_price * 0.95, 1)
                buy_high = round(latest['MA20'] * 1.03, 1) if latest['MA20'] > 0 else round(close_price * 1.02, 1)
                stop = round(latest['LowerBand'], 1) if latest['LowerBand'] > 0 else round(close_price * 0.92, 1)

                st.markdown(f"""
                - **觀察買點區間**：`{buy_low} ~ {buy_high}`（回測支撐區企穩再進場）
                - **不追價區**：`{latest['UpperBand']} 以上`
                - **嚴格停損點**：`{stop}`（跌破轉弱立即出場）
                - **ATR 參考**：{latest['ATR']}（建議停損可設 1.5~2 倍 ATR）
                """)

                # 下載按鈕
                csv = hist.to_csv(index=True).encode('utf-8-sig')
                st.download_button(
                    label="📥 下載完整技術指標 CSV",
                    data=csv,
                    file_name=f"{symbol}_{datetime.now().strftime('%Y%m%d')}_indicators.csv",
                    mime="text/csv",
                    use_container_width=True
                )

st.markdown("---")
st.caption("⚠️ 免責聲明：本系統僅供教育與參考用途，投資有風險，請自行判斷。數據來源 Yahoo Finance，可能有延遲或遺漏。")
