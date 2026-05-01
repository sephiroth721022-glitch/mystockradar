import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

# 網頁配置：設定寬版面模式
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

st.title("🚀 半導體設備股雷達與全方位健檢")

# --- 自動掃描反彈功能 ---
st.subheader("🎯 設備股：今日準備反彈 TOP 5 嚴選")
if st.button("啟動雷達掃描 🔍"):
    candidates = []
    with st.spinner("正在掃描設備股動能..."):
        for code in EQUIPMENT_POOL:
            # 自動偵測上市(.TW)或上櫃(.TWO)
            for suffix in ['.TW', '.TWO']:
                ticker = f"{code}{suffix}"
                stock = yf.Ticker(ticker)
                hist = stock.history(period="6mo")
                if not hist.empty:
                    try:
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
                        
                        # 判定反彈條件 (綠柱縮小)
                        if hist_macd < 0 and hist_macd > hist_macd_prev:
                            candidates.append({
                                "代號": code, "名稱": name, "收盤價": last_price, 
                                "RSI": rsi, "動能狀態": "🟢綠柱縮小(醞釀反彈)"
                            })
                    except Exception:
                        pass
                    break
        
        if candidates:
            # 依 RSI 由低到高排序，顯示最超跌的前五名
            res_df = pd.DataFrame(sorted(candidates, key=lambda x: x['RSI'])[:5])
            st.dataframe(res_df, use_container_width=True)
        else:
            st.info("目前設備股中尚無符合「殺盤衰竭」條件的標的。")

st.divider()

# --- 手動查詢功能 ---
st.subheader("🔍 個股全方位深度健檢")
user_codes = st.text_input("👉 請輸入股票代號 (用逗號隔開，例如: 2330, 3260, 6515)", "")

if user_codes:
    codes = [c.strip() for c in user_codes.split(',')]
    full_data = []
    with st.spinner("抓取數據中..."):
        for code in codes:
            valid = False
            for suffix in ['.TW', '.TWO']:
                ticker = f"{code}{suffix}"
                stock = yf.Ticker(ticker)
                hist = stock.history(period="6mo")
                if not hist.empty:
                    valid = True
                    try:
                        info = stock.info
                        name = CHINESE_NAMES.get(code, info.get('shortName', code))
                        last_price = round(hist['Close'].iloc[-1], 2)
                        
                        # 計算技術指標
                        ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                        
                        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
                        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
                        macd = exp1 - exp2
                        signal = macd.ewm(span=9, adjust=False).mean()
                        m_val = (macd - signal).iloc[-1]
                        m_prev = (macd - signal).iloc[-2]
                        
                        if m_val > 0:
                            m_status = "📈紅柱放大" if m_val > m_prev else "📉紅柱縮小"
                        else:
                            m_status = "🩸綠柱放大" if m_val < m_prev else "🟢反彈醞釀"

                        full_data.append({
                            "名稱": name, "代號": code, "現價": last_price,
                            "毛利率": format_pct(info.get('grossMargins')),
                            "營收年增": format_pct(info.get('revenueGrowth')),
                            "P/E(本益比)": info.get('trailingPE', 'N/A'),
                            "P/B(淨值比)": info.get('priceToBook', 'N/A'),
                            "MACD動能": m_status,
                            "月線位階": "🔴站上" if last_price > ma20 else "🟢跌破"
                        })
                    except Exception:
                        pass
                    break
            if not valid:
                st.error(f"找不到代號: {code}")
    
    if full_data:
        st.dataframe(pd.DataFrame(full_data), use_container_width=True)

# --- 完整版解說指南 ---
with st.expander("📊 點我看【數據判讀詳細指南】"):
    st.markdown("""
    ### [1] 財報指標 (基本面防護網)
    *   **毛利率**：數值越高，代表產品競爭力越強，不容易被取代（如台積電通常高於 50%）。
    *   **營收年增**：大於 0 代表公司正在擴張；小於 0 需留意衰退。
    *   **P/E (本益比)**：通常 < 15 為便宜，> 20 偏貴；高成長科技股可放寬標準。
    *   **P/B (淨值比)**：適合傳產或金融股，< 1.2 通常具備長線底層價值。

    ### [2] 技術指標 (短線進出參考)
    *   **RSI (14)**：< 30 為極度超跌（易反彈）；> 70 為過熱（易拉回）。
    *   **MACD 狀態**：
        *   📈 **紅柱放大**：多頭強攻中。
        *   🩸 **綠柱放大**：殺盤中，不宜接刀。
        *   🟢 **反彈醞釀**：綠柱開始縮短，殺盤力道衰竭，是短線準備反彈的訊號。
    *   **月線位階**：站上月線代表中期趨勢轉強，跌破則轉弱。
    """)
