import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="AI 行動決策雷達 2.0", layout="wide")

# 核心字典
CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

if 'my_list' not in st.session_state:
    st.session_state.my_list = ['2454', '3711', '3189', '8028', '3587', '4576']

def analyze_k_logic(h):
    """AI 自動判讀 5 日 K 線行為"""
    if len(h) < 5: return "⌛ 資料不足"
    last_5 = h.tail(5)
    c, o, hi, lo = last_5['Close'], last_5['Open'], last_5['High'], last_5['Low']
    
    # 趨勢判定
    is_rising = all(hi.diff().dropna() > 0)
    is_falling = all(lo.diff().dropna() < 0)
    
    curr_body = abs(c.iloc[-1] - o.iloc[-1])
    upper_s = hi.iloc[-1] - max(c.iloc[-1], o.iloc[-1])
    lower_s = min(c.iloc[-1], o.iloc[-1]) - lo.iloc[-1]
    
    if is_rising: return "📈 強勢多頭 (階梯式上漲)"
    if is_falling: return "📉 弱勢空頭 (逐波探底)"
    if lower_s > curr_body * 1.2: return "🛡️ 下影支撐 (低檔有守)"
    if upper_s > curr_body * 1.2: return "⚠️ 上影壓力 (高檔拋售)"
    return "⚖️ 區間震盪"

def plot_mini_candle(df):
    """5日簡約 K 線"""
    last_5 = df.tail(5)
    fig = go.Figure(data=[go.Candlestick(
        x=last_5.index.strftime('%m/%d'),
        open=last_5['Open'], high=last_5['High'],
        low=last_5['Low'], close=last_5['Close'],
        increasing_line_color='#FF4B4B', decreasing_line_color='#00CC96'
    )])
    fig.update_layout(height=200, margin=dict(l=5, r=5, t=5, b=5),
                      xaxis_rangeslider_visible=False, template="plotly_white")
    return fig

def fetch_data(code):
    # 嘗試兩種後綴
    for suffix in ['.TW', '.TWO']:
        ticker_str = f"{code}{suffix}"
        t = yf.Ticker(ticker_str)
        # period 改為 1個月，確保留有足夠計算空間
        h = t.history(period="1mo") 
        if not h.empty and len(h) >= 5:
            try:
                p = round(h['Close'].iloc[-1], 2)
                prev_p = h['Close'].iloc[-2]
                change = round(p - prev_p, 2)
                
                # 指標計算
                vol_avg5 = h['Volume'].rolling(5).mean().iloc[-1]
                vol_ratio = round(h['Volume'].iloc[-1] / vol_avg5, 2) if vol_avg5 > 0 else 1.0
                ma20 = h['Close'].rolling(20).mean().iloc[-1] if len(h) >= 20 else h['Close'].mean()
                
                return {
                    "name": CHINESE_NAMES.get(code, code),
                    "id": code, "p": p, "change": change,
                    "v_ratio": vol_ratio, "ma20": round(ma20, 1),
                    "k_text": analyze_k_logic(h),
                    "df": h
                }
            except Exception as e:
                continue
    return None

# --- UI 介面 ---
st.title("🚀 AI 行動投資決策雷達")

# 側邊欄
with st.sidebar:
    st.header("清單管理")
    new_id = st.text_input("新增代號 (如: 2330):")
    if st.button("加入"):
        if new_id and new_id not in st.session_state.my_list:
            st.session_state.my_list.append(new_id)
            st.rerun()
    
    del_id = st.selectbox("刪除代號:", ["---"] + st.session_state.my_list)
    if st.button("確認刪除") and del_id != "---":
        st.session_state.my_list.remove(del_id)
        st.rerun()

# 主畫面
if st.button("🔄 刷新即時數據"):
    with st.spinner("正在讀取市場數據..."):
        # 建立容器顯示結果
        for code in st.session_state.my_list:
            data = fetch_data(code)
            if data:
                with st.container():
                    c1, c2 = st.columns([3, 2])
                    color = "red" if data['change'] >= 0 else "green"
                    c1.subheader(f"{data['name']} ({data['id']})")
                    c2.markdown(f"### :{color}[${data['p']} ({data['change']})]")
                    
                    col_left, col_right = st.columns([1.5, 1])
                    with col_left:
                        st.plotly_chart(plot_mini_candle(data['df']), use_container_width=True, config={'displayModeBar': False})
                    with col_right:
                        st.success(f"**AI 型態判讀**\n\n{data['k_text']}")
                        st.metric("量能爆發比", f"{data['v_ratio']}x")
                    
                    m1, m2, m3 = st.columns(3)
                    m1.caption(f"支撐位(MA20): {data['ma20']}")
                    m2.caption(f"乖離率: {round(((data['p']-data['ma20'])/data['ma20'])*100, 2)}%")
                    m3.caption(f"狀態: {'多頭' if data['p'] > data['ma20'] else '空頭'}")
                    st.divider()
            else:
                st.warning(f"無法取得代號 {code} 的資料，請確認代號是否正確或稍後再試。")
