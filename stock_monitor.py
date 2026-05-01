import streamlit as st
import yfinance as yf
import pandas as pd
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="行動決策終極雷達", layout="wide")

# 中文字典擴充
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

# 狀態管理：追蹤名單
if 'my_list' not in st.session_state:
    st.session_state.my_list = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def get_ultra_data(code):
    """抓取全方位量化數據"""
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="1y")
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                # 1. 量能深度分析
                vol_now = h['Volume'].iloc[-1]
                vol_avg5 = h['Volume'].rolling(5).mean().iloc[-1]
                v_ratio = round(vol_now / vol_avg5, 2) if vol_avg5 > 0 else 1.0
                
                # 2. 技術指標
                ma20 = h['Close'].rolling(20).mean().iloc[-1]
                bias = round(((p - ma20) / ma20) * 100, 2)
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                
                # 3. 買賣點綜合判定
                advice = "⚪ 盤整"
                if rsi < 30 and v_ratio > 1.2: advice = "💎 底部帶量 (買進訊號)"
                elif v_ratio > 2 and p > ma20: advice = "🚀 噴發起漲 (強勢追蹤)"
                elif rsi > 75: advice = "🚨 乖離過大 (分批出場)"

                return {
                    "basic": {"name": CHINESE_NAMES.get(code, code), "id": code, "p": p, "adv": advice},
                    "tech": {"rsi": rsi, "bias": f"{bias}%", "v_ratio": f"{v_ratio}x", "ma20": round(ma20,1)},
                    "finance": {
                        "毛利": f"{round(info.get('grossMargins', 0)*100, 1)}%",
                        "殖利率": f"{round(info.get('dividendYield', 0)*100, 1)}%",
                        "Beta": round(info.get('beta', 0), 2),
                        "研發比": f"{round(info.get('researchDevelopment', 0)/max(info.get('totalRevenue',1),1)*100, 1)}%",
                        "外資佔": f"{round(info.get('heldPercentInstitutions', 0)*100, 1)}%",
                        "現金流": "正向" if info.get('operatingCashflow', 0) > 0 else "緊繃"
                    }
                }
            except: pass
    return None

# --- 側邊欄管理 (恢復刪除功能) ---
st.sidebar.header("⚙️ 追蹤名單管理")
add_input = st.sidebar.text_input("輸入代號新增:")
if add_input and st.sidebar.button("確認新增"):
    if add_input not in st.session_state.my_list:
        st.session_state.my_list.append(add_input)
        st.rerun()

del_target = st.sidebar.selectbox("選擇代號刪除:", ["---"] + st.session_state.my_list)
if del_target != "---" and st.sidebar.button("確認刪除"):
    st.session_state.my_list.remove(del_target)
    st.rerun()

# --- 主畫面 ---
st.title("📱 終極行動決策儀表板")

if st.button("🔄 刷新全數據 (含量能與五大進階指標)"):
    with st.spinner("深度掃描中..."):
        for c in st.session_state.my_list:
            d = get_ultra_data(c)
            if d:
                with st.container():
                    # 第一層：大字標題與核心建議
                    c1, c2 = st.columns([2, 1])
                    c1.subheader(f"{d['basic']['name']} ({d['basic']['id']})  💰{d['basic']['p']}")
                    c2.info(f"{d['basic']['adv']}")
                    
                    # 第二層：量能與技術分析 (手機首排)
                    t1, t2, t3, t4 = st.columns(4)
                    t1.metric("RSI", d['tech']['rsi'])
                    t2.metric("量能比", d['tech']['v_ratio'])
                    t3.metric("乖離率", d['tech']['bias'])
                    t4.metric("月線價", d['tech']['ma20'])
                    
                    # 第三層：深度財報與籌碼 (手機次排)
                    f1, f2, f3, f4, f5, f6 = st.columns(6)
                    f1.caption(f"毛利: {d['finance']['毛利']}")
                    f2.caption(f"殖利率: {d['finance']['殖利率']}")
                    f3.caption(f"Beta: {d['finance']['Beta']}")
                    f4.caption(f"研發比: {d['finance']['研發比']}")
                    f5.caption(f"外資佔: {d['finance']['外資佔']}")
                    f6.caption(f"現金流: {d['finance']['現金流']}")
                    st.divider()

with st.expander("📝 為什麼要看這「新增的五項」資訊？"):
    st.markdown("""
    ### 1. 成交量能比 (V-Ratio)
    *   **爆量**：若數值 > 2x，代表今日成交量是平均的兩倍，必有大事發生，通常是起漲或出貨的關鍵點。

    ### 2. Beta 值 (與大盤關聯度)
    *   **Beta > 1**：大盤漲 1% 它漲更多，大盤跌它也跌更慘。設備股通常 Beta 較高。

    ### 3. 研發比率 (R&D Ratio)
    *   **長期競爭力**：設備廠若不研發就會被淘汰。研發比高代表公司在準備未來的秘密武器。

    ### 4. 外資佔比與現金流
    *   **籌碼面**：外資佔比高代表法人長期認同。
    *   **現金流**：確保公司賺的是真錢，不是收不回來的呆帳。
    """)
