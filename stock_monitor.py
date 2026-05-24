import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="完美股票分析系統 v3.4", page_icon="📈", layout="wide")

# ==================== AI 產業分類（已完整更新） ====================
AI_INDUSTRY_GROUPS = {
    "1. 晶圓代工與先進封裝製造": {
        "description": "AI 晶片及高階封裝技術",
        "stocks": [
            ("2330", "台積電"), ("2303", "聯電"), ("3711", "日月光投控"), ("2449", "京元電子"),
            ("6515", "穎崴"), ("3189", "景碩"), ("3374", "精材"), ("6770", "力積電"),
            ("5347", "世界先進"), ("3450", "聯鈞"),
            ("6187", "萬潤"), ("6525", "捷敏")   # ← 新增
        ]
    },
    "2. AI 晶片與矽智財": {
        "description": "AI 運算架構設計與矽智財授權",
        "stocks": [
            ("2454", "聯發科"), ("3443", "創意"), ("3661", "世芯-KY"), ("6531", "愛普*"),
            ("3529", "力旺"), ("6643", "M31"), ("8016", "矽創"), ("3034", "聯詠"),
            ("2379", "瑞昱"), ("3014", "聯陽"),
            ("3035", "智原")   # ← 新增
        ]
    },
    "3. AI 伺服器組裝": {
        "description": "AI 伺服器系統組裝與代工製造",
        "stocks": [
            ("2317", "鴻海"), ("2382", "廣達"), ("3231", "緯創"), ("6669", "緯穎"),
            ("2356", "英業達"), ("2324", "仁寶"), ("3706", "神達"), ("2395", "研華"),
            ("6414", "樺漢"), ("4938", "和碩")
        ]
    },
    "4. 散熱模組與液冷解決": {
        "description": "AI 伺服器高耗能與發熱問題",
        "stocks": [
            ("3324", "雙鴻"), ("3017", "奇鋐"), ("2421", "建準"), ("3653", "健策"),
            ("8996", "高力"), ("3483", "力致"), ("6230", "超眾"), ("3338", "泰碩"),
            ("2486", "一詮"), ("6125", "廣運")
        ]
    },
    "5. 網通與光通訊": {
        "description": "高速傳輸交換器、光模組與設備",
        "stocks": [
            ("2345", "智邦"), ("3363", "智易"), ("5388", "中磊"), ("3163", "波若威"),
            ("4979", "華星光"), ("3234", "光環"), ("4908", "前鼎"), ("6442", "光聖"),
            ("3380", "明泰"), ("3416", "融程電")
        ]
    },
    "6. 記憶體與儲存": {
        "description": "提供 AI 運算所需的高頻寬記憶體",
        "stocks": [
            ("3260", "威剛"), ("2408", "南亞科"), ("2344", "華邦電"), ("2337", "旺宏"),
            ("8299", "群聯"), ("4966", "譜瑞-KY"), ("2451", "創見"), ("8088", "品安"),
            ("4967", "十銓"), ("3006", "晶豪科")
        ]
    },
    "7. 銅箔基板與 PCBA": {
        "description": "AI 伺服器主機板與高速運算電路板",
        "stocks": [
            ("2383", "台光電"), ("6274", "台燿"), ("6213", "聯茂"), ("2368", "金像電"),
            ("3037", "欣興"), ("8046", "南電"), ("2313", "華通"), ("6153", "嘉聯益"),
            ("5469", "瀚宇博"), ("2367", "燿華"),
            ("2327", "國巨"), ("2492", "華新科")   # ← 新增
        ]
    },
    "8. 機殼與滑軌零組件": {
        "description": "伺服器專用機殼設計與耐重滑軌",
        "stocks": [
            ("2059", "川湖"), ("3693", "營邦"), ("8210", "勤誠"), ("2354", "鴻準"),
            ("6117", "迎廣"), ("3013", "晟銘電"), ("8114", "振樺電"), ("3023", "信邦"),
            ("3533", "嘉澤"), ("3665", "貿聯-KY"),
            ("2392", "正崴"), ("2328", "廣宇")   # ← 新增
        ]
    },
    "9. 邊緣 AI 與 AI PC": {
        "description": "終端 AI 設備、高階運算筆電與工業電腦",
        "stocks": [
            ("2357", "華碩"), ("2376", "技嘉"), ("2377", "微星"), ("2353", "宏碁"),
            ("6206", "飛捷"), ("3022", "威強電"), ("2352", "佳世達"), ("2397", "友通"),
            ("3413", "京鼎"), ("6166", "凌華"),
            ("6202", "盛群"), ("3008", "大立光")   # ← 新增
        ]
    },
    "10. 雲端服務與軟體": {
        "description": "AI 應用軟體開發與雲端系統建置整合",
        "stocks": [
            ("6811", "宏碁資訊"), ("6689", "伊雲谷"), ("2453", "凌群"), ("2471", "資通"),
            ("3029", "零壹"), ("6214", "精誠"), ("6183", "關貿"), ("5203", "訊連"),
            ("4953", "緯軟"), ("3130", "一零四"),
            ("3036", "文曄")   # ← 新增
        ]
    }
}

CHINESE_NAMES = {code: name for group in AI_INDUSTRY_GROUPS.values() for code, name in group["stocks"]}

# ==================== 以下為 v3.2 核心功能（保持不變） ====================
def normalize_taiwan_code(code: str) -> str:
    return code.upper().replace(' ', '').replace('.TW', '').replace('.TWO', '')

def resolve_chinese_name_to_codes(name: str) -> list[str]:
    name = name.strip()
    if not name: return []
    exact = {v: k for k, v in CHINESE_NAMES.items()}
    if name in exact: return [exact[name]]
    return [k for k, v in CHINESE_NAMES.items() if name in v]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_taiwan_stock_data(code: str, period=None, start=None, end=None):
    base = normalize_taiwan_code(code)
    candidates = [code] if code.endswith(('.TW', '.TWO')) else [f"{base}.TW", f"{base}.TWO", base]
    for sym in candidates:
        try:
            ticker = yf.Ticker(sym)
            if start and end:
                hist = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)
            else:
                hist = ticker.history(period=period or "6mo", interval="1d", auto_adjust=True)
            if not hist.empty and len(hist) >= 5:
                info = ticker.info or {}
                return sym, hist, info
        except:
            continue
    return f"{base}.TW", pd.DataFrame(), {}

def calculate_indicators(df: pd.DataFrame):
    df = df.copy()
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['RSV'] = df['RSV'].fillna(50)
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()

    k_period, smooth_k, d_period = 14, 3, 3
    low_min14 = df['Low'].rolling(k_period).min()
    high_max14 = df['High'].rolling(k_period).max()
    df['%K'] = 100 * (df['Close'] - low_min14) / (high_max14 - low_min14)
    df['%K'] = df['%K'].rolling(smooth_k).mean()
    df['%D'] = df['%K'].rolling(d_period).mean()
    df['%J'] = 3 * df['%K'] - 2 * df['%D']

    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['UpperBand'] = df['MA20'] + 2 * df['STD20']
    df['LowerBand'] = df['MA20'] - 2 * df['STD20']
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()

    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    latest = {
        'K': round(df['K'].iloc[-1], 2),
        '%K': round(df['%K'].iloc[-1], 2),
        '%D': round(df['%D'].iloc[-1], 2),
        '%J': round(df['%J'].iloc[-1], 2),
        'RSI': round(df['RSI'].iloc[-1], 2) if not np.isnan(df['RSI'].iloc[-1]) else 50,
        'MA20': round(df['MA20'].iloc[-1], 2),
        'SMA50': round(df['SMA50'].iloc[-1], 2),
        'SMA200': round(df['SMA200'].iloc[-1], 2),
        'MACD': round(df['MACD'].iloc[-1], 2),
        'Hist': round(df['Hist'].iloc[-1], 2),
        'Hist_prev': round(df['Hist'].iloc[-2], 2) if len(df) > 1 else 0,
        'UpperBand': round(df['UpperBand'].iloc[-1], 2),
        'LowerBand': round(df['LowerBand'].iloc[-1], 2),
        'ATR': round((df['High'] - df['Low']).rolling(14).mean().iloc[-1], 2)
    }
    return latest, df

def get_macd_text(latest):
    if latest['Hist'] > 0:
        return "🔴 紅柱放大（多頭動能增強）" if latest['Hist'] > latest['Hist_prev'] else "🔴 紅柱縮小（多頭動能減弱）"
    else:
        return "🟢 綠柱放大（空頭動能增強）" if abs(latest['Hist']) > abs(latest['Hist_prev']) else "🟢 綠柱縮小（空頭動能減弱）"

def get_kd_text(latest):
    k, d = latest['%K'], latest['%D']
    if k > d:
        return "🟢 黃金交叉（短線轉強）" + ("＋ 短線過熱" if k > 80 else "")
    else:
        return "🔴 死亡交叉（短線轉弱）" + ("＋ 超賣區" if k < 20 else "")

def get_overall_recommendation(latest, close_price):
    score = 50
    reasons = []
    if latest['SMA200'] > 0 and latest['SMA50'] > 0:
        if close_price > latest['SMA50'] > latest['SMA200']:
            score += 20
            reasons.append("✅ 多頭排列")
        elif close_price < latest['SMA50'] < latest['SMA200']:
            score -= 15
            reasons.append("⚠️ 空頭排列")
    if latest['Hist'] > 0:
        score += 12
        if latest['Hist'] > latest['Hist_prev']:
            score += 8
    else:
        score -= 8
    if 35 <= latest['RSI'] <= 65:
        score += 10
    elif latest['RSI'] > 70:
        score -= 12
    if latest['%K'] > latest['%D']:
        score += 10
        if latest['%K'] > 80:
            score -= 5
    else:
        score -= 5
    if close_price > latest['MA20']:
        score += 7
    else:
        score -= 5

    score = max(0, min(100, score))
    if score >= 80:
        return "★★★★★", "強勢多頭", "積極進場，拉回加碼", score, reasons
    elif score >= 65:
        return "★★★★☆", "偏多格局", "等回測月線再布局", score, reasons
    elif score >= 50:
        return "★★★☆☆", "震盪整理", "觀望為主", score, reasons
    elif score >= 35:
        return "★★☆☆☆", "偏空格局", "保守操作", score, reasons
    else:
        return "★☆☆☆☆", "弱勢空頭", "暫時避開", score, reasons

# ==================== 主介面 ====================
st.title("📈 完美股票分析系統 v3.4（AI 供應鏈完整版）")
st.caption("台股專用 | 10 大 AI 產業分類（已更新 10 檔重要股票）")

# AI 產業快速選擇
st.markdown("## 🔥 AI 供應鏈快速選擇（點擊即可分析）")

for group_name, group_data in AI_INDUSTRY_GROUPS.items():
    with st.expander(f"📁 {group_name}"):
        st.caption(group_data["description"])
        cols = st.columns(5)
        for i, (code, name) in enumerate(group_data["stocks"]):
            col = cols[i % 5]
            if col.button(f"{name}\n{code}", key=f"ai_{group_name}_{code}", use_container_width=True):
                st.session_state.codes_input = code
                st.rerun()

st.markdown("---")

if "codes_input" not in st.session_state:
    st.session_state.codes_input = "2330"

codes_input = st.text_input("或手動輸入股票代號 / 名稱（逗號分隔）", 
                           value=st.session_state.codes_input, key="codes_input")

if st.button("🚀 執行分析", type="primary", use_container_width=True):
    items = [i.strip() for i in codes_input.split(',') if i.strip()]
    for item in items:
        code_list = resolve_chinese_name_to_codes(item) if any(ord(c) > 127 for c in item) else [item]
        for code in code_list:
            with st.spinner(f"分析 {code} 中..."):
                symbol, hist, info = fetch_taiwan_stock_data(code, period="6mo")

            if hist.empty:
                st.error(f"❌ {code} 無法取得數據")
                continue

            latest, hist = calculate_indicators(hist)
            close_price = round(float(hist['Close'].iloc[-1]), 2)
            stock_name = CHINESE_NAMES.get(code, code)
            stars, trend, strategy, score, reasons = get_overall_recommendation(latest, close_price)

            with st.expander(f"📊 {stock_name} ({symbol}) | 健康分數 {score}/100 | {trend}", expanded=True):
                # 即時報價
                st.markdown("### ⚡ 即時報價")
                try:
                    rt = yf.Ticker(symbol)
                    fi = rt.fast_info
                    last_price = fi.get('lastPrice', close_price)
                    prev = fi.get('previousClose', close_price)
                    chg_pct = ((last_price - prev) / prev * 100) if prev > 0 else 0
                    st.metric("最新成交價", f"{last_price:.2f} TWD", f"{chg_pct:+.2f}%")
                except:
                    st.info("即時報價暫時無法取得")

                # 綜合評分
                st.markdown(f"<h2 style='text-align:center;color:#FFD700'>{stars}</h2>", unsafe_allow_html=True)
                st.write(f"**趨勢**：{trend}　**策略**：{strategy}")
                for r in reasons:
                    st.write(f"- {r}")

                # 技術訊號
                st.markdown("### ❷ 技術訊號總覽（文字說明）")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**MACD**：{get_macd_text(latest)}")
                    st.metric("MACD柱狀體", latest['Hist'])
                with col2:
                    st.markdown(f"**KD**：{get_kd_text(latest)}")
                    st.metric("完整KD", f"%K {latest['%K']} / %D {latest['%D']} / %J {latest['%J']}")
                st.metric("RSI", latest['RSI'])
                st.metric("月線 (MA20)", latest['MA20'])

                # 風險控管與進場計劃
                st.markdown("### ❹ 風險控管與進場計劃")
                atr = latest['ATR']
                buy_low = round(latest['MA20'] * 0.97, 1)
                buy_high = round(latest['MA20'] * 1.03, 1)
                stop_loss = round(close_price - atr * 1.5, 1)
                target = round(close_price + atr * 3, 1)
                risk_reward = round((target - close_price) / (close_price - stop_loss), 2) if (close_price - stop_loss) > 0 else 0

                st.markdown(f"""
                - **建議買點區間**：`{buy_low} ~ {buy_high}`
                - **嚴格停損點**：`{stop_loss}`（1.5倍 ATR）
                - **目標價（第一檔）**：`{target}`（3倍 ATR）
                - **風險報酬比**：`1 : {risk_reward}`
                - **建議部位**：每筆風險控制在總資金 **2% 以內**
                """)

                # 公司基本面
                st.markdown("### ❺ 公司基本面摘要")
                if info:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        pe = info.get('trailingPE') or info.get('forwardPE')
                        if pe: st.metric("本益比 (PE)", f"{pe:.1f}")
                    with c2:
                        eps = info.get('trailingEps')
                        if eps: st.metric("EPS", f"{eps:.2f}")
                    with c3:
                        div = info.get('dividendYield')
                        if div: st.metric("殖利率", f"{div*100:.2f}%")
                    st.caption(f"產業：{info.get('sector', '未提供')} / {info.get('industry', '未提供')}")
                else:
                    st.caption("基本面資料有限")

                csv = hist.to_csv(index=True).encode('utf-8-sig')
                st.download_button("📥 下載完整技術數據 CSV", csv, f"{symbol}_v3.4_analysis.csv", "text/csv")

st.markdown("---")
st.caption("免責聲明：本系統僅供參考，投資有風險。數據來源 Yahoo Finance。")
