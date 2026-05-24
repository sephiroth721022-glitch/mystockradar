import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

st.set_page_config(page_title="完美股票分析系統 v3.1", page_icon="📈", layout="wide")

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
    if not name: return []
    exact = {v: k for k, v in CHINESE_NAMES.items()}
    if name in exact: return [exact[name]]
    return [k for k, v in CHINESE_NAMES.items() if name in v]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_taiwan_stock_data(code: str, period=None, start=None, end=None):
    base = normalize_taiwan_code(code)
    candidates = [code] if code.endswith(('.TW', '.TWO')) else [f"{base}.TW", f"{base}.TWO", base]
    for sym in candidates:
        try:
            ticker = yf.Ticker(sym)
            if start and end:
                hist = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)
            else:
                hist = ticker.history(period=period or "6mo", interval="1d", auto_adjust=True)
            if not hist.empty and len(hist) >= 5:
                info = ticker.info or {}
                return sym, hist, info
        except:
            continue
    return f"{base}.TW", pd.DataFrame(), {}

def calculate_indicators(df: pd.DataFrame):
    df = df.copy()
    # KD 快速版
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['RSV'] = df['RSV'].fillna(50)
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()

    # 完整 KD（%K %D %J）
    k_period, smooth_k, d_period = 14, 3, 3
    low_min14 = df['Low'].rolling(k_period).min()
    high_max14 = df['High'].rolling(k_period).max()
    df['%K'] = 100 * (df['Close'] - low_min14) / (high_max14 - low_min14)
    df['%K'] = df['%K'].rolling(smooth_k).mean()
    df['%D'] = df['%K'].rolling(d_period).mean()
    df['%J'] = 3 * df['%K'] - 2 * df['%D']

    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # 均線 + 布林
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
        '%K': round(df['%K'].iloc[-1], 2),
        '%D': round(df['%D'].iloc[-1], 2),
        '%J': round(df['%J'].iloc[-1], 2),
        'D': round(df['D'].iloc[-1], 2),
        'RSI': round(df['RSI'].iloc[-1], 2) if not np.isnan(df['RSI'].iloc[-1]) else 50,
        'MA20': round(df['MA20'].iloc[-1], 2),
        'SMA50': round(df['SMA50'].iloc[-1], 2),
        'SMA200': round(df['SMA200'].iloc[-1], 2),
        'MACD': round(df['MACD'].iloc[-1], 2),
        'Signal': round(df['Signal'].iloc[-1], 2),
        'Hist': round(df['Hist'].iloc[-1], 2),
        'Hist_prev': round(df['Hist'].iloc[-2], 2) if len(df) > 1 else 0,
        'UpperBand': round(df['UpperBand'].iloc[-1], 2),
        'LowerBand': round(df['LowerBand'].iloc[-1], 2),
    }
    return latest, df

def get_macd_text(latest):
    if latest['Hist'] > 0:
        if latest['Hist'] > latest['Hist_prev']:
            return "🔴 紅柱放大（多頭動能增強）"
        else:
            return "🔴 紅柱縮小（多頭動能減弱）"
    else:
        if abs(latest['Hist']) > abs(latest['Hist_prev']):
            return "🟢 綠柱放大（空頭動能增強）"
        else:
            return "🟢 綠柱縮小（空頭動能減弱）"

def get_kd_text(latest):
    k, d = latest['%K'], latest['%D']
    if k > d:
        if k > 80:
            return "🟢 黃金交叉（%K > %D）＋ 短線過熱"
        return "🟢 黃金交叉（%K 已向上穿越 %D，短線轉強）"
    else:
        if k < 20:
            return "🔴 死亡交叉（%K < %D）＋ 超賣區"
        return "🔴 死亡交叉（%K 向下穿越 %D，短線轉弱）"

def get_overall_recommendation(latest, close_price):
    score = 50
    reasons = []
    if latest['SMA200'] > 0 and latest['SMA50'] > 0:
        if close_price > latest['SMA50'] > latest['SMA200']:
            score += 20
            reasons.append("✅ 多頭排列")
        elif close_price < latest['SMA50'] < latest['SMA200']:
            score -= 15
            reasons.append("⚠️ 空頭排列")
    if latest['Hist'] > 0:
        score += 12
        if latest['Hist'] > latest['Hist_prev']:
            score += 8
    else:
        score -= 8
    if 35 <= latest['RSI'] <= 65:
        score += 10
    elif latest['RSI'] > 70:
        score -= 12
    if latest['%K'] > latest['%D']:
        score += 10
        if latest['%K'] > 80:
            score -= 5
    else:
        score -= 5
    if close_price > latest['MA20']:
        score += 7
    else:
        score -= 5

    score = max(0, min(100, score))
    if score >= 80:
        return "★★★★★", "強勢多頭", "積極進場，拉回加碼", score, reasons
    elif score >= 65:
        return "★★★★☆", "偏多格局", "等回測月線再布局", score, reasons
    elif score >= 50:
        return "★★★☆☆", "震盪整理", "觀望為主", score, reasons
    elif score >= 35:
        return "★★☆☆☆", "偏空格局", "保守操作", score, reasons
    else:
        return "★☆☆☆☆", "弱勢空頭", "暫時避開", score, reasons

def fetch_monthly_revenue(code: str):
    try:
        url = f"https://www.twse.com.tw/exchangeReport/FMSRFK?response=json&stockNo={code}"
        r = requests.get(url, timeout=6)
        data = r.json()
        if data.get("stat") == "OK" and data.get("data"):
            df = pd.DataFrame(data["data"], columns=["日期", "營收(千元)", "上月比較%", "去年同月比較%"])
            df = df.tail(4)  # 取最近4個月
            return df
    except:
        pass
    return None

def backtest_strategy(df):
    df_bt = df.copy()
    df_bt['signal'] = 0
    df_bt.loc[(df_bt['Close'] > df_bt['SMA50']) & (df_bt['Hist'] > 0) & (df_bt['%K'] > df_bt['%D']), 'signal'] = 1
    df_bt.loc[(df_bt['Close'] < df_bt['SMA50']) | (df_bt['Hist'] < 0) | (df_bt['%K'] < df_bt['%D']), 'signal'] = -1
    df_bt['position'] = df_bt['signal'].shift(1).fillna(0)
    df_bt['returns'] = df_bt['Close'].pct_change()
    df_bt['strategy_returns'] = df_bt['position'] * df_bt['returns']
    df_bt['cum_strategy'] = (1 + df_bt['strategy_returns']).cumprod()
    df_bt['cum_bh'] = (1 + df_bt['returns']).cumprod()

    total_ret = round((df_bt['cum_strategy'].iloc[-1] - 1) * 100, 2)
    bh_ret = round((df_bt['cum_bh'].iloc[-1] - 1) * 100, 2)
    peak = df_bt['cum_strategy'].cummax()
    max_dd = round(((df_bt['cum_strategy'] - peak) / peak).min() * 100, 2)
    win_rate = round((df_bt['strategy_returns'] > 0).sum() / max(1, (df_bt['strategy_returns'] != 0).sum()) * 100, 1)
    return df_bt, total_ret, bh_ret, max_dd, win_rate

# ==================== 主介面 ====================
st.title("📈 完美股票分析系統 v3.1（文字版）")
st.caption("台股專用 | 完整KD文字說明 + 每月營收成長率 + 策略回測")

with st.sidebar:
    st.header("⚙️ 設定")
    period = st.selectbox("期間", ['1mo','3mo','6mo','1y','2y','5y','max'], index=2)
    use_custom = st.checkbox("自訂日期")
    if use_custom:
        start_date = st.date_input("開始", datetime(2024, 6, 1))
        end_date = st.date_input("結束", datetime.now().date())
    else:
        start_date = end_date = None

st.markdown("### 🔥 快速選擇")
cols = st.columns(5)
for col, (name, code) in zip(cols, [("台積電","2330"),("鴻海","2317"),("聯發科","2454"),("0050","0050"),("漢唐","2404")]):
    if col.button(name, use_container_width=True):
        st.session_state.codes_input = code
        st.rerun()

if "codes_input" not in st.session_state:
    st.session_state.codes_input = "2330"

codes_input = st.text_input("股票代號 / 名稱（逗號分隔）", value=st.session_state.codes_input, key="codes_input")

if st.button("🚀 執行分析", type="primary", use_container_width=True):
    items = [i.strip() for i in codes_input.split(',') if i.strip()]
    for item in items:
        code_list = resolve_chinese_name_to_codes(item) if any(ord(c) > 127 for c in item) else [item]
        for code in code_list:
            with st.spinner(f"分析 {code} 中..."):
                if use_custom and start_date and end_date:
                    symbol, hist, info = fetch_taiwan_stock_data(code, start=start_date.strftime("%Y-%m-%d"), end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"))
                else:
                    symbol, hist, info = fetch_taiwan_stock_data(code, period=period)

            if hist.empty:
                st.error(f"❌ {code} 無法取得數據")
                continue

            latest, hist = calculate_indicators(hist)
            close_price = round(float(hist['Close'].iloc[-1]), 2)
            stock_name = CHINESE_NAMES.get(code.replace('.TW','').replace('.TWO',''), code)
            stars, trend, strategy, score, reasons = get_overall_recommendation(latest, close_price)

            with st.expander(f"📊 {stock_name} ({symbol}) | 健康分數 {score}/100 | {trend}", expanded=True):
                # 即時報價
                st.markdown("### ⚡ 即時報價")
                try:
                    rt = yf.Ticker(symbol)
                    fi = rt.fast_info
                    last_price = fi.get('lastPrice', close_price)
                    prev = fi.get('previousClose', close_price)
                    chg_pct = ((last_price - prev) / prev * 100) if prev > 0 else 0
                    st.metric("最新成交價", f"{last_price:.2f} TWD", f"{chg_pct:+.2f}%")
                except:
                    st.info("即時報價暫時無法取得（非交易時段）")

                # 綜合評分
                st.markdown(f"<h2 style='text-align:center;color:#FFD700'>{stars}</h2>", unsafe_allow_html=True)
                st.write(f"**趨勢**：{trend}　**策略**：{strategy}")
                for r in reasons:
                    st.write(f"- {r}")

                # 技術訊號（文字版）
                st.markdown("### ❷ 技術訊號總覽（文字說明）")
                macd_text = get_macd_text(latest)
                kd_text = get_kd_text(latest)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**MACD**：{macd_text}")
                    st.metric("MACD柱狀體", latest['Hist'], delta=round(latest['Hist'] - latest['Hist_prev'], 2))
                with col2:
                    st.markdown(f"**KD**：{kd_text}")
                    st.metric("完整KD", f"%K {latest['%K']} / %D {latest['%D']} / %J {latest['%J']}")

                st.metric("RSI", latest['RSI'])
                st.metric("月線 (MA20)", latest['MA20'])

                # 每月營收成長率（新增）
                st.markdown("### ❸ 每月營收成長率（最新）")
                rev_df = fetch_monthly_revenue(code)
                if rev_df is not None and not rev_df.empty:
                    st.dataframe(rev_df, use_container_width=True, hide_index=True)
                    st.caption("資料來源：台灣證交所（每月更新）")
                else:
                    st.warning("無法取得每月營收數據（建議至 TWSE 官網查詢）")

                # 回測
                st.markdown("### ❹ 策略回測驗證")
                df_bt, strat_ret, bh_ret, maxdd, winrate = backtest_strategy(hist)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("策略總報酬", f"{strat_ret}%")
                m2.metric("Buy & Hold", f"{bh_ret}%")
                m3.metric("最大回撤", f"{maxdd}%")
                m4.metric("勝率", f"{winrate}%")

                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['cum_strategy'], name="策略權益曲線", line=dict(color="#00C853", width=3)))
                fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['cum_bh'], name="Buy & Hold", line=dict(color="#FF9800", width=2, dash="dash")))
                fig_bt.update_layout(height=320, title="策略 vs Buy & Hold 權益曲線", showlegend=True)
                st.plotly_chart(fig_bt, use_container_width=True)

                # 下載
                csv = hist.to_csv(index=True).encode('utf-8-sig')
                st.download_button("📥 下載完整技術數據 CSV", csv, f"{symbol}_v3.1_analysis.csv", "text/csv")

st.markdown("---")
st.caption("免責聲明：本系統僅供參考，投資有風險。數據來源 Yahoo Finance 與 TWSE。")
