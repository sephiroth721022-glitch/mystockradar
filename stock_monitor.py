import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="旗艦股市決策雷達", layout="wide")

# 完整中文字典 (包含 17 檔與設備股)
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴',
    '3131': '弘塑', '3583': '辛耘', '6187': '萬潤', '1560': '中砂',
    '3680': '家登', '3413': '京鼎', '2404': '漢唐', '6196': '帆宣'
}

TRACKING_LIST = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def get_flagship_data(code):
    """抓取旗艦級全方位數據"""
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="1y") # 抓一年份數據以計算乖離與殖利率
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                # 1. 技術面：RSI & 布林
                delta = h['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                
                ma20 = h['Close'].rolling(20).mean()
                ma60 = h['Close'].rolling(60).mean() # 季線
                std20 = h['Close'].rolling(20).std()
                lower = ma20.iloc[-1] - 2 * std20.iloc[-1]
                
                # 2. 籌碼與估值
                yield_rate = info.get('dividendYield', 0)
                yield_rate = f"{round(yield_rate * 100, 2)}%" if yield_rate else "N/A"
                
                # 3. 綜合判定邏輯
                bias = round(((p - ma20.iloc[-1]) / ma20.iloc[-1]) * 100, 2) # 乖離率
                
                advice = "🟡 盤整觀望"
                if rsi < 30 or p <= lower: advice = "💎 極度超跌 (找買點)"
                elif rsi > 75: advice = "🚨 乖離過大 (勿追)"
                elif p > ma20.iloc[-1] and ma20.iloc[-1] > ma60.iloc[-1]: advice = "🚀 多頭排列 (強勢)"

                return {
                    "名稱": CHINESE_NAMES.get(code, info.get('shortName', code)),
                    "現價": p,
                    "漲跌%": f"{round(((p - h['Close'].iloc[-2])/h['Close'].iloc[-2])*100, 2)}%",
                    "RSI": rsi,
                    "乖離率%": bias,
                    "殖利率": yield_rate,
                    "毛利率": f"{round(info.get('grossMargins', 0)*100, 2)}%",
                    "負債比": f"{round(info.get('debtToEquity', 0), 2)}%",
                    "本益比": info.get('trailingPE', 'N/A'),
                    "決策建議": advice
                }
            except: pass
    return None

st.title("🏛️ 旗艦級股市決策監控中心")

# --- 核心清單區 ---
st.subheader("📊 17 檔核心追蹤名單 (旗艦數據)")
if st.button("🔄 執行深度掃描"):
    results = []
    with st.spinner("正在彙整全球金融數據與量化指標..."):
        for c in TRACKING_LIST:
            data = get_flagship_data(c)
            if data: results.append(data)
    st.dataframe(pd.DataFrame(results), use_container_width=True)

st.divider()

# --- 手動健檢區 ---
st.subheader("🔍 全方位個股手動健檢")
user_input = st.text_input("請輸入代號 (例如: 2330, 3260, 1802)", "")
if user_input:
    custom_results = []
    codes = [c.strip() for c in user_input.split(',')]
    for c in codes:
        res = get_flagship_data(c)
        if res: custom_results.append(res)
    if custom_results:
        st.dataframe(pd.DataFrame(custom_results), use_container_width=True)

# --- 深度教學 ---
with st.expander("📝 旗艦指標實戰解析 (如何看懂這張表？)"):
    st.markdown("""
    ### 1. 乖離率 (Bias)
    *   **定義**：股價距離月線 (20MA) 的遠近。
    *   **應用**：乖離率太大 (例如 > 10%) 通常代表短線漲太多，隨時會拉回修正。

    ### 2. 殖利率 (Yield Rate)
    *   **定義**：公司配息與股價的比率。
    *   **應用**：在震盪市中，殖利率 > 4% 的標的具備較強的抗跌性（防守墊）。

    ### 3. 負債比 (Debt to Equity)
    *   **應用**：負債比過高 (例如 > 200%) 的公司在升息環境下壓力較大，選股建議挑選財務穩健者。

    ### 4. 決策建議邏輯
    *   **🚀 多頭排列**：股價 > 月線 > 季線。這代表趨勢向上，適合波段持有。
    *   **💎 極度超跌**：RSI 與布林下軌同時出現訊號，反彈勝率極高。
    """)
