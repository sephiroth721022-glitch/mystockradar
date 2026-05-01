import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# 網頁配置
st.set_page_config(page_title="專業股市分析雷達", layout="wide")

# 💡 擴充中文名稱字典 (加入你新增的追蹤清單)
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光投控', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

# 你的每日追蹤名單
TRACKING_LIST = [
    '2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', 
    '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066'
]

def format_pct(val):
    if pd.isna(val) or val is None: return 'N/A'
    return f"{round(val * 100, 2)}%"

st.title("📈 專業股市 K 線與全方位健檢系統")

# --- 側邊欄：每日追蹤清單快報 ---
st.sidebar.header("📋 每日追蹤快報")
if st.sidebar.button("刷新追蹤名單"):
    t_data = []
    for code in TRACKING_LIST:
        for suffix in ['.TW', '.TWO']:
            t = yf.Ticker(f"{code}{suffix}")
            h = t.history(period="2d")
            if not h.empty:
                name = CHINESE_NAMES.get(code, code)
                price = round(h['Close'].iloc[-1], 2)
                change = round(h['Close'].iloc[-1] - h['Close'].iloc[-2], 2)
                t_data.append({"代號": code, "名稱": name, "現價": price, "漲跌": change})
                break
    st.sidebar.table(pd.DataFrame(t_data))

# --- 主畫面：個股深度健檢與 K 線圖 ---
st.subheader("🔍 個股深度健檢與技術圖表")
target_code = st.text_input("請輸入單一股票代號查看 K 線圖 (例如: 3260)", "3260")

if target_code:
    valid = False
    for suffix in ['.TW', '.TWO']:
        ticker = f"{target_code}{suffix}"
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        if not hist.empty:
            valid = True
            info = stock.info
            name = CHINESE_NAMES.get(target_code, info.get('shortName', target_code))
            
            # --- 顯示基本面與技術面表格 ---
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            m_val = (macd - signal).iloc[-1]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("名稱/代號", f"{name} ({target_code})")
            col2.metric("最新收盤價", f"{round(hist['Close'].iloc[-1], 2)}")
            col3.metric("毛利率", format_pct(info.get('grossMargins')))
            col4.metric("營收年增", format_pct(info.get('revenueGrowth')))

            # --- 繪製 K 線圖 ---
            fig = go.Figure(data=[go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='K線'
            )])
            # 加入 20 日均線
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(window=20).mean(), 
                                     line=dict(color='orange', width=1), name='20MA'))
            
            fig.update_layout(title=f"{name} ({target_code}) 半年 K 線圖",
                              xaxis_rangeslider_visible=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
            
            # 詳細數據表
            details = {
                "P/E (本益比)": [info.get('trailingPE', 'N/A')],
                "P/B (淨值比)": [info.get('priceToBook', 'N/A')],
                "MACD 狀態": ["🟢醞釀反彈" if m_val < 0 and m_val > (macd-signal).iloc[-2] else "觀察中"],
                "月線位階": ["🔴站上" if hist['Close'].iloc[-1] > ma20 else "🟢跌破"]
            }
            st.table(pd.DataFrame(details))
            break
    if not valid:
        st.error("找不到該股票資料。")

# --- 判讀指南 ---
with st.expander("📊 點我看【數據判讀詳細指南】"):
    st.markdown("""
    ### [1] K 線與均線 (20MA)
    *   **20MA (月線)**：股價在橘色線之上代表短期強勢。
    ### [2] 財報指標
    *   **毛利率**：越高代表產品競爭力越強。
    *   **本益比 (P/E)**：< 15 偏便宜，> 20 偏貴。
    ### [3] 動能指標
    *   **MACD 🟢反彈醞釀**：綠柱縮短，代表殺盤結束，準備上攻。
    """)
