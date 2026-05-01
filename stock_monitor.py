import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="旗艦級股市決策儀表板", layout="wide")

# --- 1. 內建初始名單與中文字典 ---
INITIAL_LIST = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

def get_full_analysis(code):
    """旗艦級數據運算核心"""
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="1y")
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                # 技術指標
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                
                ma20 = h['Close'].rolling(20).mean().iloc[-1]
                ma60 = h['Close'].rolling(60).mean().iloc[-1]
                bias = round(((p - ma20) / ma20) * 100, 2)
                
                # 買賣點建議
                advice = "⚪ 觀望"
                if rsi < 30: advice = "💎 超跌買點"
                elif rsi > 80: advice = "🚨 乖離過大"
                elif p > ma20 > ma60: advice = "🚀 強勢多頭"

                return {
                    "名稱": CHINESE_NAMES.get(code, info.get('shortName', code)),
                    "代號": code, "現價": p, "RSI": rsi, "乖離%": bias,
                    "毛利": f"{round(info.get('grossMargins', 0)*100, 1)}%",
                    "殖利率": f"{round(info.get('dividendYield', 0)*100, 2)}%" if info.get('dividendYield') else "0%",
                    "現金流": "🟢 正向" if info.get('freeCashflow', 0) > 0 else "🔴 負向",
                    "負債比": f"{round(info.get('debtToEquity', 0), 1)}%",
                    "決策建議": advice
                }
            except: pass
    return None

# --- 2. 側邊欄：動態更改追蹤清單 ---
st.sidebar.header("⚙️ 追蹤清單管理")
# 利用 Session State 儲存使用者更改的名單
if 'my_list' not in st.session_state:
    st.session_state.my_list = INITIAL_LIST.copy()

new_stock = st.sidebar.text_input("新增代號 (按 Enter 送出):")
if new_stock and new_stock not in st.session_state.my_list:
    st.session_state.my_list.append(new_stock)
    st.sidebar.success(f"已新增 {new_stock}")

stock_to_remove = st.sidebar.selectbox("刪除代號:", ["請選擇"] + st.session_state.my_list)
if st.sidebar.button("確認刪除"):
    if stock_to_remove != "請選擇":
        st.session_state.my_list.remove(stock_to_remove)
        st.sidebar.warning(f"已移除 {stock_to_remove}")

# --- 3. 主畫面顯示 ---
st.title("🏛️ 互動式股市全方位決策中心")

st.subheader("📊 我的即時監控清單")
if st.button("🔄 重新整理所有數據"):
    results = []
    with st.spinner("正在運算全球金融數據..."):
        for c in st.session_state.my_list:
            data = get_full_analysis(c)
            if data: results.append(data)
    st.dataframe(pd.DataFrame(results), use_container_width=True)

st.divider()

# --- 4. 技術指標白話圖解說明 ---
st.subheader("💡 投資決策圖解說明")
col1, col2 = st.columns(2)

with col1:
    st.markdown("### K 線與均線的關係")
    st.write("K 線記錄了每一天的戰鬥過程。當股價（K 線）在月線（MA20）之上，代表最近 20 天買的人都賺錢，氣勢正在你這邊 。")
    # 
    
with col2:
    st.markdown("### RSI 指標：超買與超賣")
    st.write("RSI 就像是一個情緒溫度計。數值高於 70 代表大家搶瘋了（隨時會冷卻）；低於 30 代表大家恐慌殺出（隨時會反彈） 。")
    # 

with st.expander("📝 點我看更多「決策欄位」詳細解析"):
    st.markdown("""
    *   **現金流 (Free Cash Flow)**：這是一家公司口袋裡的真現金。如果是負值，代表公司一直在燒錢，風險較高 。
    *   **負債比**：設備股通常需要大量資金擴廠，但負債比過高在利息上升時會吃掉利潤 。
    *   **乖離%**：衡量你買的價格是否「太貴」。乖離率 > 10% 就像拉得太緊的橡皮筋，縮回來的力道會很強 。
    """)
