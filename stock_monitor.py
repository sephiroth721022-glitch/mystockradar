import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="AI 行動決策雷達 2.0", layout="wide")

CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3587': '閎康', '4576': '大銀微', '6830': '汎銓'
}

if 'my_list' not in st.session_state:
    st.session_state.my_list = ['2454', '3711', '8028', '3587', '4576']

# --- 左側邊欄：名單管理 + 深度名詞解釋 ---
with st.sidebar:
    st.header("⚙️ 清單管理")
    new_id = st.text_input("新增代號:")
    if st.button("加入清單") and new_id:
        if new_id not in st.session_state.my_list:
            st.session_state.my_list.append(new_id)
            st.rerun()
    
    del_id = st.selectbox("移除代號:", ["---"] + st.session_state.my_list)
    if st.button("確認移除") and del_id != "---":
        st.session_state.my_list.remove(del_id)
        st.rerun()

    st.divider()
    st.header("📚 投資名詞百科")
    with st.expander("📈 什麼是「多頭 / 空頭」？"):
        st.write("**多頭 (Bullish)**：市場樂觀，股價低點不斷墊高，像公牛向上頂。")
        st.write("**空頭 (Bearish)**：市場悲觀，股價高點不斷下移，像黑熊向下拍。")
    
    with st.expander("🛡️ 什麼是「下影支撐」？"):
        st.write("代表股價跌下去後被強力拉回。若發生在**月線附近**且**帶量**，通常是買點訊號。")
        
    with st.expander("🚀 什麼是「量能爆發比」？"):
        st.write("今日成交量 ÷ 過去5日平均量。")
        st.write("> 1.5x：代表有人在裡面大殺大砍或狂買，必有大事。")
        st.write("< 0.7x：代表窒息量，市場沒人理，股價難動。")

    with st.expander("📏 什麼是「乖離率」？"):
        st.write("股價跟月線的距離。")
        st.write("> 10%：漲太兇，小心回檔。")
        st.write("< -10%：跌太深，可能反彈。")

# --- 核心邏輯與畫面 ---
def analyze_k_logic(h):
    if len(h) < 5: return "資料讀取中"
    last_5 = h.tail(5)
    c, o, hi, lo = last_5['Close'], last_5['Open'], last_5['High'], last_5['Low']
    vol_ratio = h['Volume'].iloc[-1] / h['Volume'].rolling(5).mean().iloc[-1]
    
    is_rising = all(hi.diff().dropna() > 0)
    curr_body = abs(c.iloc[-1] - o.iloc[-1])
    lower_s = min(c.iloc[-1], o.iloc[-1]) - lo.iloc[-1]
    upper_s = hi.iloc[-1] - max(c.iloc[-1], o.iloc[-1])
    
    # 結合量能的判讀
    if is_rising and vol_ratio > 1.2: return "🚀 強勢進攻 (量價齊揚，續抱)"
    if lower_s > curr_body * 1.3:
        return "🛡️ 下影支撐 (低檔有守，若在月線旁可考慮)" if vol_ratio > 1 else "🛡️ 下影線 (量不足，再觀察)"
    if upper_s > curr_body * 1.3: return "⚠️ 上影壓力 (高檔有人拋售，先別買)"
    if c.iloc[-1] > o.iloc[-1] and vol_ratio > 2: return "🔥 爆量長紅 (主力發動，追蹤焦點)"
    return "⚖️ 區間震盪 (等待表態)"

def fetch_data(code):
    for suffix in ['.TW', '.TWO']:
        t = yf.Ticker(f"{code}{suffix}")
        h = t.history(period="1mo")
        if not h.empty and len(h) >= 5:
            p = round(h['Close'].iloc[-1], 2)
            change = round(p - h['Close'].iloc[-2], 2)
            vol_ratio = round(h['Volume'].iloc[-1] / h['Volume'].rolling(5).mean().iloc[-1], 2)
            ma20 = h['Close'].rolling(20).mean().iloc[-1]
            return {"name": CHINESE_NAMES.get(code, code), "id": code, "p": p, "change": change, "v_ratio": vol_ratio, "ma20": round(ma20, 1), "k_text": analyze_k_logic(h), "df": h}
    return None

st.title("📱 AI 行動決策雷達 2.0")

if st.button("🔄 刷新即時 AI 判讀"):
    for code in st.session_state.my_list:
        data = fetch_data(code)
        if data:
            with st.container():
                c1, c2 = st.columns([3, 2])
                color = "#FF4B4B" if data['change'] >= 0 else "#00CC96"
                c1.subheader(f"{data['name']} ({data['id']})")
                c2.markdown(f"### <span style='color:{color}'>${data['p']} ({data['change']})</span>", unsafe_allow_html=True)
                
                col_l, col_r = st.columns([1.5, 1])
                with col_l:
                    fig = go.Figure(data=[go.Candlestick(x=data['df'].tail(5).index.strftime('%m/%d'), open=data['df'].tail(5)['Open'], high=data['df'].tail(5)['High'], low=data['df'].tail(5)['Low'], close=data['df'].tail(5)['Close'], increasing_line_color='#FF4B4B', decreasing_line_color='#00CC96')])
                    fig.update_layout(height=180, margin=dict(l=5, r=5, t=5, b=5), xaxis_rangeslider_visible=False, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                with col_r:
                    st.success(f"**AI 建議**\n\n{data['k_text']}")
                    st.metric("量能爆發比", f"{data['v_ratio']}x", delta=f"{round(data['v_ratio']-1,2)}x")
                
                st.divider()
