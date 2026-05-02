import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go # 新增：用於畫 K 線
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="行動決策終極雷達", layout="wide")

CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

if 'my_list' not in st.session_state:
    st.session_state.my_list = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def plot_mini_candle(df):
    """產生最近 5 日的簡約 K 線圖"""
    last_5_days = df.tail(5)
    fig = go.Figure(data=[go.Candlestick(
        x=last_5_days.index.strftime('%m/%d'),
        open=last_5_days['Open'],
        high=last_5_days['High'],
        low=last_5_days['Low'],
        close=last_5_days['Close'],
        increasing_line_color='#FF4B4B', # 紅漲
        decreasing_line_color='#00CC96'  # 綠跌
    )])
    fig.update_layout(
        height=200, 
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        yaxis=dict(showgrid=True)
    )
    return fig

def get_ultra_data(code):
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="1y")
        if not h.empty:
            try:
                info = t.info
                p = round(h['Close'].iloc[-1], 2)
                vol_now = h['Volume'].iloc[-1]
                vol_avg5 = h['Volume'].rolling(5).mean().iloc[-1]
                v_ratio = round(vol_now / vol_avg5, 2) if vol_avg5 > 0 else 1.0
                
                ma20 = h['Close'].rolling(20).mean().iloc[-1]
                bias = round(((p - ma20) / ma20) * 100, 2)
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                
                advice = "⚪ 盤整"
                if rsi < 30 and v_ratio > 1.2: advice = "💎 底部帶量 (買進)"
                elif v_ratio > 2 and p > ma20: advice = "🚀 噴發起漲 (追蹤)"
                elif rsi > 75: advice = "🚨 乖離過大 (分批)"

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
                    },
                    "chart_df": h # 回傳歷史資料以便繪圖
                }
            except: pass
    return None

# --- 側邊欄 ---
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

if st.button("🔄 刷新全數據 (含5日K線圖)"):
    with st.spinner("深度掃描中..."):
        for c in st.session_state.my_list:
            d = get_ultra_data(c)
            if d:
                with st.container():
                    # 第一層：標題
                    c1, c2 = st.columns([2, 1])
                    c1.subheader(f"{d['basic']['name']} ({d['basic']['id']})  💰{d['basic']['p']}")
                    c2.info(f"{d['basic']['adv']}")
                    
                    # --- 新增內容：5日K線圖 ---
                    st.plotly_chart(plot_mini_candle(d['chart_df']), use_container_width=True, config={'displayModeBar': False})
                    
                    # 第二層：量能與技術分析
                    t1, t2, t3, t4 = st.columns(4)
                    t1.metric("RSI", d['tech']['rsi'])
                    t2.metric("量能比", d['tech']['v_ratio'])
                    t3.metric("乖離率", d['tech']['bias'])
                    t4.metric("月線價", d['tech']['ma20'])
                    
                    # 第三層：深度財報
                    f1, f2, f3, f4, f5, f6 = st.columns(6)
                    f1.caption(f"毛利: {d['finance']['毛利']}")
                    f2.caption(f"殖利率: {d['finance']['殖利率']}")
                    f3.caption(f"Beta: {d['finance']['Beta']}")
                    f4.caption(f"研發比: {d['finance']['研發比']}")
                    f5.caption(f"外資佔: {d['finance']['外資佔']}")
                    f6.caption(f"現金流: {d['finance']['現金流']}")
                    st.divider()

with st.expander("📝 如何判讀 5 日 K 線？"):
    st.markdown("""
    *   **連續紅棒**：強勢多頭，搭配量能比 > 1.2x 更有利。
    *   **留長上影線**：代表上方壓力大，即使 RSI 低也建議觀察。
    *   **K 線與月線 (MA20) 距離**：若 K 線遠高於月線且 RSI > 75，即為「乖離過大」。
    """)
