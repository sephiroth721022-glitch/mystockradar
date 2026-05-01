import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="投資決策雷達", layout="wide")

CHINESE_NAMES = {
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2454': '聯發科', '3711': '日月光', '3189': '景碩', '8028': '昇陽半',
    '3661': '世芯-KY', '4576': '大銀微', '6285': '啟碁', '8064': '東捷',
    '3028': '增你強', '6147': '紘康', '3289': '宜特', '6830': '汎銓',
    '3163': '波若威', '3587': '閎康', '3066': '珍寶', '6515': '穎崴'
}

TRACKING_LIST = ['2454', '3711', '3189', '8028', '3661', '4576', '6285', '8064', '2345', '3028', '6147', '3289', '6830', '3163', '3587', '3066']

def get_advice(rsi, m_val, m_prev, price, upper, lower):
    """綜合評估買賣建議"""
    if rsi < 35 and m_val > m_prev: return "🔥 超跌反彈 (分批布局)"
    if price <= lower: return "🟢 觸及布林下軌 (支撐測試)"
    if rsi > 75: return "⚠️ 極度過熱 (不宜追高)"
    if price >= upper: return "🍎 觸及布林上軌 (壓力區)"
    if m_val > 0 and m_val > m_prev: return "📈 多頭攻擊 (偏多看)"
    return "⚪ 震盪整理"

st.title("🛡️ 17 檔核心持股決策雷達")

if st.button("🔄 執行全數據掃描"):
    all_data = []
    with st.spinner("正在進行深度量化運算..."):
        for code in TRACKING_LIST:
            for suffix in ['.TW', '.TWO']:
                t = yf.Ticker(f"{code}{suffix}")
                h = t.history(period="6mo")
                if not h.empty:
                    try:
                        info = t.info
                        p = round(h['Close'].iloc[-1], 2)
                        
                        # 技術指標：RSI
                        delta = h['Close'].diff()
                        gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                        rsi = round(100 - (100 / (1 + (gain/loss))), 2) if loss != 0 else 100
                        
                        # 技術指標：布林通道
                        ma20 = h['Close'].rolling(20).mean()
                        std20 = h['Close'].rolling(20).std()
                        upper = ma20.iloc[-1] + 2 * std20.iloc[-1]
                        lower = ma20.iloc[-1] - 2 * std20.iloc[-1]
                        
                        # 技術指標：MACD
                        e1 = h['Close'].ewm(span=12, adjust=False).mean()
                        e2 = h['Close'].ewm(span=26, adjust=False).mean()
                        m = e1 - e2
                        s = m.ewm(span=9, adjust=False).mean()
                        m_v, m_p = (m-s).iloc[-1], (m-s).iloc[-2]

                        all_data.append({
                            "名稱": CHINESE_NAMES.get(code, code), "現價": p,
                            "RSI": rsi, "P/E": info.get('trailingPE', 'N/A'), "P/B": info.get('priceToBook', 'N/A'),
                            "毛利": f"{round(info.get('grossMargins', 0)*100, 2)}%",
                            "決策建議": get_advice(rsi, m_v, m_p, p, upper, lower)
                        })
                    except: pass
                    break
    st.dataframe(pd.DataFrame(all_data), use_container_width=True)

st.divider()

with st.expander("📖 投資決策指標與 K 線白話解析"):
    st.markdown("""
    ### 1. K 線的靈魂：開高低收
    *   **紅棒 (陽線)**：收盤高於開盤。代表多頭（買方）獲勝，氣勢轉強。
    *   **長下影線**：股價曾重摔但被打撈上來。這通常是「止跌」或「測支撐」的訊號。

    ### 2. 買點判斷：如何評估「要買了」？
    *   **RSI < 30 (超賣區)**：就像彈簧被壓到極限，隨時會強烈反彈。
    *   **布林下軌 (支撐線)**：股價跌到這裡通常會有護盤力道，適合分批布局。
    *   **MACD 綠柱縮小**：代表賣壓吐完了，動能準備轉正。

    ### 3. 安全邊際：財報輔助
    *   **P/E < 15 & 毛利 > 30%**：這代表公司有賺錢能力且股價不貴，買起來心裡比較踏實。
    """)
