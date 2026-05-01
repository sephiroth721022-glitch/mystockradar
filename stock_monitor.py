import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

# 網頁配置
st.set_page_config(page_title="專業設備股雷達", layout="wide")

# 中文翻譯字典 (完整涵蓋你的名單)
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

# 你的 17 檔核心追蹤名單
TRACKING_LIST = [
    '2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', 
    '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066'
]

def format_pct(val):
    if pd.isna(val) or val is None: return 'N/A'
    return f"{round(val * 100, 2)}%"

st.title("🛡️ 核心持股與設備追蹤系統")

# --- 1. 每日追蹤名單：全數據大閱兵 ---
st.subheader("📋 核心追蹤清單 (全數據監控)")
if st.button("🔄 立即更新追蹤數據"):
    all_tracking_data = []
    with st.spinner("正在掃描 17 檔核心標的，請稍候..."):
        for code in TRACKING_LIST:
            valid = False
            for suffix in ['.TW', '.TWO']:
                t = yf.Ticker(f"{code}{suffix}")
                h = t.history(period="6mo")
                if not h.empty:
                    valid = True
                    try:
                        info = t.info
                        last_p = round(h['Close'].iloc[-1], 2)
                        change = round(h['Close'].iloc[-1] - h['Close'].iloc[-2], 2)
                        
                        # 技術指標計算
                        ma20 = h['Close'].rolling(window=20).mean().iloc[-1]
                        exp1 = h['Close'].ewm(span=12, adjust=False).mean()
                        exp2 = h['Close'].ewm(span=26, adjust=False).mean()
                        macd = exp1 - exp2
                        sig = macd.ewm(span=9, adjust=False).mean()
                        m_val = (macd - sig).iloc[-1]
                        m_prev = (macd - sig).iloc[-2]
                        
                        if m_val > 0:
                            m_status = "📈紅柱" if m_val > m_prev else "📉紅縮"
                        else:
                            m_status = "🩸綠柱" if m_val < m_prev else "🟢反彈"

                        all_tracking_data.append({
                            "名稱": CHINESE_NAMES.get(code, code),
                            "代號": code,
                            "現價": last_p,
                            "漲跌": change,
                            "毛利率": format_pct(info.get('grossMargins')),
                            "營收年增": format_pct(info.get('revenueGrowth')),
                            "P/E": info.get('trailingPE', 'N/A'),
                            "MACD": m_status,
                            "月線": "🔴站上" if last_p > ma20 else "🟢跌破"
                        })
                    except: pass
                    break
    if all_tracking_data:
        st.dataframe(pd.DataFrame(all_tracking_data), use_container_width=True)

st.divider()

# --- 2. 個股技術 K 線分析 ---
st.subheader("🔍 個股 K 線與趨勢圖")
target = st.text_input("輸入代號查看細節 (例如: 3260)", "3260")
if target:
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{target}{suffix}")
        h = t.history(period="6mo")
        if not h.empty:
            # 繪製 K 線
            fig = go.Figure(data=[go.Candlestick(x=h.index, open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'], name='K線')])
            fig.add_trace(go.Scatter(x=h.index, y=h['Close'].rolling(window=20).mean(), line=dict(color='orange', width=1.5), name='20MA'))
            fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            break

# --- 3. 判讀指南 ---
with st.expander("📖 數據判讀詳細指南"):
    st.markdown("""
    *   **現價/漲跌**：當日走勢。
    *   **毛利率**：產品競爭力關鍵（設備股建議 > 35%）。
    *   **MACD 🟢反彈**：代表殺盤力道衰竭，是極短線的買進參考點。
    *   **月線 🔴站上**：代表中期波段趨勢轉強。
    """)
