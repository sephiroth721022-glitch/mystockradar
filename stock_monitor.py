import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# 網頁配置
st.set_page_config(page_title="半導體設備雷達", layout="wide")

# 中文翻譯字典
CHINESE_NAMES = {
    '3131': '弘塑', '3583': '辛耘', '6187': '萬潤', '1560': '中砂',
    '3680': '家登', '3413': '京鼎', '2404': '漢唐', '6196': '帆宣',
    '6640': '均華', '6667': '信紘科', '6515': '穎崴', '3402': '漢科',
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦'
}

# 設備股觀測池
EQUIPMENT_POOL = ['3131', '3583', '6187', '1560', '3680', '3413', '2404', '6196', '6640', '6667', '6515', '3402']

def format_pct(val):
    if pd.isna(val) or val is None: return 'N/A'
    return f"{round(val * 100, 2)}%"

st.title("🚀 半導體設備股雷達與全方位分析")

# --- 自動掃描反彈功能 ---
st.subheader("🎯 設備股：今日準備反彈 TOP 5 嚴選")
if st.button("啟動雷達掃描 🔍"):
    candidates = []
    with st.spinner("正在掃描設備股動能..."):
        for code in EQUIPMENT_POOL:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty:
                stock = yf.Ticker(f"{code}.TWO")
                hist = stock.history(period="3mo")
            
            if not hist.empty:
                name = CHINESE_NAMES.get(code, code)
                last_price = round(hist['Close'].iloc[-1], 2)
                
                # 計算 RSI
                delta = hist['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
                rs = gain / loss if loss != 0 else 0
                rsi = round(100 - (100 / (1 + rs)), 2)
                
                # 計算 MACD
                exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
                exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9, adjust=False).mean()
                hist_macd = (macd - signal).iloc[-1]
                hist_macd_prev = (macd - signal).iloc[-2]
                
                if hist_macd < 0 and hist_macd > hist_macd_prev:
                    candidates.append({"代號": code, "名稱": name, "現價": last_price, "RSI": rsi, "動能": "🟢綠柱縮小"})
        
        if candidates:
            res_df = pd.DataFrame(sorted(candidates, key=lambda x: x['RSI'])[:5])
            st.table(res_df)
        else:
            st.info("目前無符合反彈條件之標的。")

st.divider()

# --- 手動查詢功能 ---
user_codes = st.text_input("👉 請輸入代號進行全方位健檢 (例如: 2330, 3260, 6515)", "")
if user_codes:
    codes = [c.strip() for c in user_codes.split(',')]
    full_data = []
    for code in codes:
        ticker = f"{code}.TW"
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        if hist.empty:
            stock = yf.Ticker(f"{code}.TWO")
            hist = stock.history(period="6mo")
        
        if not hist.empty:
            info = stock.info
            name = CHINESE_NAMES.get(code, info.get('shortName', code))
            last_price = round(hist['Close'].iloc[-1], 2)
            
            # 獲取財報與技術指標 (簡化版)
            full_data.append({
                "名稱": name, "現價": last_price,
                "毛利率": format_pct(info.get('grossMargins')),
                "本益比": info.get('trailingPE', 'N/A'),
                "MACD": "📈強勢" if (hist['Close'].iloc[-1] > hist['Close'].rolling(window=20).mean().iloc[-1]) else "📉偏弱"
            })
    st.dataframe(pd.DataFrame(full_data))

with st.expander("📖 數據判讀指南"):
    st.write("本益比 < 15 偏便宜；毛利率越高代表競爭力越強；RSI < 30 為超跌反彈訊號。")
