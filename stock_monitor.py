import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="專業設備股雷達", layout="wide")

# 中文名稱字典
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

TRACKING_LIST = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def get_analysis_data(code):
    """抓取單一股票的量化與財報數據"""
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="6mo")
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                # RSI 計算
                delta = h['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                # 布林與均線
                ma20 = h['Close'].rolling(20).mean()
                std20 = h['Close'].rolling(20).std()
                upper = ma20.iloc[-1] + 2 * std20.iloc[-1]
                lower = ma20.iloc[-1] - 2 * std20.iloc[-1]
                # MACD
                e1 = h['Close'].ewm(span=12, adjust=False).mean()
                e2 = h['Close'].ewm(span=26, adjust=False).mean()
                m = e1 - e2
                s = m.ewm(span=9, adjust=False).mean()
                m_v, m_p = (m-s).iloc[-1], (m-s).iloc[-2]
                
                # 建議邏輯
                advice = "⚪ 震盪整理"
                if rsi < 35 and m_v > m_p: advice = "🔥 超跌反彈"
                elif p <= lower: advice = "🟢 觸及下軌"
                elif rsi > 75: advice = "⚠️ 極度過熱"
                elif p >= upper: advice = "🍎 觸及上軌壓力"
                elif m_v > 0 and m_v > m_p: advice = "📈 多頭攻擊"

                return {
                    "名稱": CHINESE_NAMES.get(code, info.get('shortName', code)),
                    "代號": code, "現價": p, "RSI": rsi, 
                    "P/E": info.get('trailingPE', 'N/A'),
                    "毛利": f"{round(info.get('grossMargins', 0)*100, 2)}%",
                    "營收年增": f"{round(info.get('revenueGrowth', 0)*100, 2)}%",
                    "決策建議": advice
                }
            except: pass
    return None

st.title("🛡️ 17 檔核心清單與個股健檢")

# --- 第一區：17 檔追蹤清單 ---
st.subheader("📋 每日追蹤清單大閱兵")
if st.button("🔄 立即更新追蹤數據"):
    tracking_data = []
    with st.spinner("正在掃描核心名單..."):
        for c in TRACKING_LIST:
            res = get_analysis_data(c)
            if res: tracking_data.append(res)
    st.dataframe(pd.DataFrame(tracking_data), use_container_width=True)

st.divider()

# --- 第二區：自定義手動查詢 ---
st.subheader("🔍 個股手動查詢健檢")
user_input = st.text_input("👉 請輸入代號 (例如: 2330, 3260, 1802)", "")
if user_input:
    custom_data = []
    codes = [c.strip() for c in user_input.split(',')]
    with st.spinner("查詢中..."):
        for c in codes:
            res = get_analysis_data(c)
            if res: custom_data.append(res)
            else: st.error(f"找不到代號 {c}")
    if custom_data:
        st.dataframe(pd.DataFrame(custom_data), use_container_width=True)

# --- 決策指南 ---
with st.expander("📖 投資決策與 K 線指標白話解析"):
    st.markdown("""
    ### 1. K 線的靈魂：開高低收
    *   **紅棒**：當天買盤強勁，收盤價高於開盤價。
    *   **長下影線**：股價曾重挫但被強力拉回，通常代表底部支撐強勁。

    ### 2. 量化指標：什麼時候「該買了」？
    *   **RSI (14)**：低於 35 代表極度超跌，若此時 MACD 綠柱縮短（出現 🟢反彈 訊號），就是極佳買點。
    *   **布林下軌**：股價觸及下軌代表短期跌幅已深，容易出現技術性反彈。

    ### 3. 基本面安全邊際
    *   **毛利與營收**：毛利率越高代表產品越難取代；營收年增率大於 0 代表公司還在成長軌道上。
    """)
