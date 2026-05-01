import streamlit as st
import yfinance as yf
import pandas as pd
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="行動決策雷達", layout="wide")

# 中文字典
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

if 'my_list' not in st.session_state:
    st.session_state.my_list = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def get_mobile_data(code):
    """抓取手機優化的深度數據"""
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="6mo")
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                
                # --- 量能分析 ---
                vol_now = h['Volume'].iloc[-1]
                vol_avg = h['Volume'].rolling(5).mean().iloc[-1]
                vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 1.0
                vol_status = "🔥 量增" if vol_ratio > 1.5 else ("🧊 量縮" if vol_ratio < 0.7 else "平穩")
                
                # --- 技術與籌碼指標 ---
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                
                ma20 = h['Close'].rolling(20).mean().iloc[-1]
                bias = round(((p - ma20) / ma20) * 100, 2)
                
                # --- 營運與籌碼 ---
                inst_own = info.get('heldPercentInstitutions', 0)
                cash = info.get('totalCash', 0) / 1e9 # 單位：十億
                
                # 建議邏輯
                advice = "⚪ 觀望"
                if rsi < 35 and vol_ratio > 1.2: advice = "💎 量增打底 (關注)"
                elif p > ma20 and vol_ratio > 2: advice = "🚀 帶量突破 (強勢)"
                elif rsi > 75: advice = "🚨 過熱減碼"

                return {
                    "基本": {"名稱": CHINESE_NAMES.get(code, code), "代號": code, "現價": p, "決策": advice},
                    "量能": {"RSI": rsi, "量能比": f"{vol_ratio}x", "量態": vol_status, "乖離": f"{bias}%"},
                    "財報": {"毛利": f"{round(info.get('grossMargins', 0)*100, 1)}%", "殖利率": f"{round(info.get('dividendYield', 0)*100, 1)}%", "負債比": f"{round(info.get('debtToEquity', 0), 1)}%", "現金(10億)": round(cash, 2)}
                }
            except: pass
    return None

st.title("📱 旗艦行動決策儀表板")

# 側邊欄管理
st.sidebar.header("⚙️ 名單管理")
new_stock = st.sidebar.text_input("新增代號:")
if new_stock and st.sidebar.button("確認新增"):
    if new_stock not in st.session_state.my_list:
        st.session_state.my_list.append(new_stock)
        st.rerun()

st.subheader("📋 核心追蹤 (手機雙排模式)")
if st.button("🔄 刷新全數據分析"):
    with st.spinner("量化運算中..."):
        for c in st.session_state.my_list:
            d = get_mobile_data(c)
            if d:
                # --- 手機版雙排卡片設計 ---
                with st.container():
                    # 第一排：基本資訊與決策
                    c1, c2, c3 = st.columns([1.5, 1, 1.5])
                    c1.markdown(f"**{d['基本']['名稱']} ({d['基本']['代號']})**")
                    c2.markdown(f"💰 **{d['基本']['現價']}**")
                    c3.markdown(f"📢 `{d['基本']['決策']}`")
                    
                    # 第二排：技術量能與財報數據
                    c4, c5, c6, c7 = st.columns(4)
                    c4.caption(f"RSI: {d['量能']['RSI']}")
                    c5.caption(f"量比: {d['量能']['量能比']}")
                    c6.caption(f"毛利: {d['財報']['毛利']}")
                    c7.caption(f"殖利率: {d['財報']['殖利率']}")
                    st.divider()

with st.expander("📝 為什麼成交量很重要？(K 線量價解析)"):
    st.markdown("""
    ### 1. 量是價的先行指標
    *   **量增價漲**：代表買氣真實，股價漲勢有實力支撐。
    *   **量縮價漲**：小心！這叫「量價背離」，代表買盤後繼無力，隨時可能反轉下殺。
    *   **爆量長黑**：主力在大舉出貨的訊號，通常建議先避開。

    

    ### 2. 進階必看資訊：現金與負債
    *   **手持現金**：景氣不好時，現金越多的公司越能熬過寒冬，甚至進行擴廠併購。
    *   **量能比 (Volume Ratio)**：目前的成交量除以 5 日平均量。超過 1.5 倍代表有「大人」進場玩這檔股票了。
    """)
