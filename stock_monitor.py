import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="台美股研究情報站", page_icon="📈", layout="wide")


TAIWAN_AI_GROUPS = {
    "半導體製造與封測": {
        "description": "先進製程、成熟製程、封裝測試與晶圓代工，是台股 AI 供應鏈的核心底盤。",
        "stocks": [
            ("2330", "台積電"), ("2303", "聯電"), ("3711", "日月光投控"), ("2449", "京元電子"),
            ("6515", "穎崴"), ("3189", "景碩"), ("3374", "精材"), ("6770", "力積電"),
            ("5347", "世界"), ("3450", "聯鈞"), ("6187", "萬潤"), ("6525", "捷敏-KY"),
        ],
    },
    "IC 設計與矽智財": {
        "description": "AI ASIC、邊緣 AI、通訊晶片、IP 與設計服務，是觀察新商機滲透率的前哨。",
        "stocks": [
            ("2454", "聯發科"), ("3443", "創意"), ("3661", "世芯-KY"), ("6531", "愛普*"),
            ("3529", "力旺"), ("6643", "M31"), ("8016", "矽創"), ("3034", "聯詠"),
            ("2379", "瑞昱"), ("3014", "聯陽"), ("3035", "智原"),
        ],
    },
    "伺服器與系統組裝": {
        "description": "AI 伺服器、雲端資料中心、整機代工與系統整合，受 CSP 資本支出牽動最大。",
        "stocks": [
            ("2317", "鴻海"), ("2382", "廣達"), ("3231", "緯創"), ("6669", "緯穎"),
            ("2356", "英業達"), ("2324", "仁寶"), ("3706", "神達"), ("2395", "研華"),
            ("6414", "樺漢"), ("4938", "和碩"),
        ],
    },
    "散熱、機殼與電源": {
        "description": "高功耗 GPU/ASIC 推升液冷、機構件、電源供應與高階材料規格。",
        "stocks": [
            ("3324", "雙鴻"), ("3017", "奇鋐"), ("2421", "建準"), ("3653", "健策"),
            ("8996", "高力"), ("3483", "力致"), ("6230", "尼得科超眾"), ("3338", "泰碩"),
            ("2486", "一詮"), ("6125", "廣運"),
        ],
    },
    "網通與光通訊": {
        "description": "資料中心網路升級、交換器、光收發模組與 CPO 相關題材，是 AI 基建第二層機會。",
        "stocks": [
            ("2345", "智邦"), ("3363", "上詮"), ("5388", "中磊"), ("3163", "波若威"),
            ("4979", "華星光"), ("3234", "光環"), ("4908", "前鼎"), ("6442", "光聖"),
            ("3380", "明泰"), ("3416", "融程電"),
        ],
    },
    "記憶體與儲存": {
        "description": "HBM、DDR、NAND、SSD 控制晶片與模組，受 AI 伺服器容量與價格循環影響。",
        "stocks": [
            ("3260", "威剛"), ("2408", "南亞科"), ("2344", "華邦電"), ("2337", "旺宏"),
            ("8299", "群聯"), ("4966", "譜瑞-KY"), ("2451", "創見"), ("8088", "品安"),
            ("4967", "十銓"), ("3006", "晶豪科"),
        ],
    },
    "PCB 與載板": {
        "description": "高速運算板材、ABF 載板、HDI 與高階 PCB，常領先反映伺服器規格升級。",
        "stocks": [
            ("2383", "台光電"), ("6274", "台燿"), ("6213", "聯茂"), ("2368", "金像電"),
            ("3037", "欣興"), ("8046", "南電"), ("2313", "華通"), ("6153", "嘉聯益"),
            ("5469", "瀚宇博"), ("2367", "燿華"), ("2327", "國巨"), ("2492", "華新科"),
        ],
    },
    "AI PC 與品牌通路": {
        "description": "AI PC、NB、品牌、通路與周邊，是端側 AI 需求擴散的重要觀察面。",
        "stocks": [
            ("2357", "華碩"), ("2376", "技嘉"), ("2377", "微星"), ("2353", "宏碁"),
            ("6206", "飛捷"), ("3022", "威強電"), ("2352", "佳世達"), ("2397", "友通"),
            ("3413", "京鼎"), ("6166", "凌華"),
        ],
    },
}

US_WATCHLIST = {
    "AI 晶片": ["NVDA", "AMD", "AVGO", "MRVL", "ARM"],
    "雲端與軟體": ["MSFT", "GOOGL", "AMZN", "META", "ORCL", "SNOW"],
    "半導體設備": ["ASML", "AMAT", "LRCX", "KLAC", "TER"],
    "電動車與能源": ["TSLA", "ENPH", "FSLR", "GEV"],
}

CHINESE_NAMES = {
    code: name for group in TAIWAN_AI_GROUPS.values() for code, name in group["stocks"]
}


NEWS_TASK_PROMPT = """請扮演一位專業股票研究員，擅長蒐集關鍵重要資訊。

任務：整理過去 24 小時台股與美股的重要新聞，台股為主、美股為輔。來源盡量廣泛，包括工商時報、經濟日報、鉅亨網、CNBC、Reuters、Bloomberg、X、Reddit，以及其他重量級新聞媒體。

請依照三大類統整：
1. 總體經濟
2. 地緣政治
3. 產業與個股動態

要求：
- 嚴格檢視事件準確度，標示來源、時間與可信度。
- 產業與個股動態要更廣泛搜尋潛在機會，避免流於庸俗或只有市場已知的大型權值股。
- 優先挖掘市場可能忽略但重要的資訊。
- 除新聞重點外，也要延伸洞見與投資觀點。
- 最後輸出綜合解析，包含所有動態總結、未來一周重要大事、值得關注的潛力產業與個股。
- 請使用繁體中文，內容詳盡、有架構、有邏輯。
"""


@dataclass
class NewsItem:
    category: str
    title: str
    source: str
    published: datetime | None
    link: str
    query: str


def normalize_taiwan_code(code: str) -> str:
    return code.upper().replace(" ", "").replace(".TW", "").replace(".TWO", "")


def resolve_stock_input(text: str) -> list[str]:
    item = text.strip()
    if not item:
        return []
    exact = {name: code for code, name in CHINESE_NAMES.items()}
    if item in exact:
        return [exact[item]]
    fuzzy = [code for code, name in CHINESE_NAMES.items() if item in name]
    return fuzzy or [item]


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_stock_data(code: str, period: str = "1y"):
    base = normalize_taiwan_code(code)
    candidates = [code] if code.endswith((".TW", ".TWO")) else [f"{base}.TW", f"{base}.TWO", base]
    for symbol in candidates:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval="1d", auto_adjust=True)
            if not hist.empty and len(hist) >= 30:
                return symbol, hist, ticker.info or {}
        except Exception:
            continue
    return f"{base}.TW", pd.DataFrame(), {}


def calculate_indicators(df: pd.DataFrame):
    data = df.copy()
    data["MA20"] = data["Close"].rolling(20).mean()
    data["SMA50"] = data["Close"].rolling(50).mean()
    data["SMA200"] = data["Close"].rolling(200).mean()
    data["STD20"] = data["Close"].rolling(20).std()
    data["UpperBand"] = data["MA20"] + 2 * data["STD20"]
    data["LowerBand"] = data["MA20"] - 2 * data["STD20"]

    ema12 = data["Close"].ewm(span=12, adjust=False).mean()
    ema26 = data["Close"].ewm(span=26, adjust=False).mean()
    data["MACD"] = ema12 - ema26
    data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["Hist"] = data["MACD"] - data["Signal"]

    low14 = data["Low"].rolling(14).min()
    high14 = data["High"].rolling(14).max()
    data["%K"] = (100 * (data["Close"] - low14) / (high14 - low14)).rolling(3).mean()
    data["%D"] = data["%K"].rolling(3).mean()
    data["%J"] = 3 * data["%K"] - 2 * data["%D"]

    delta = data["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    data["RSI"] = 100 - (100 / (1 + rs))
    data["ATR"] = (data["High"] - data["Low"]).rolling(14).mean()

    latest = data.iloc[-1]
    prev = data.iloc[-2] if len(data) > 1 else latest
    return {
        "close": float(latest["Close"]),
        "MA20": float(latest.get("MA20", np.nan)),
        "SMA50": float(latest.get("SMA50", np.nan)),
        "SMA200": float(latest.get("SMA200", np.nan)),
        "RSI": float(latest.get("RSI", 50) if not pd.isna(latest.get("RSI", np.nan)) else 50),
        "MACD": float(latest.get("MACD", 0)),
        "Hist": float(latest.get("Hist", 0)),
        "Hist_prev": float(prev.get("Hist", 0)),
        "%K": float(latest.get("%K", 50) if not pd.isna(latest.get("%K", np.nan)) else 50),
        "%D": float(latest.get("%D", 50) if not pd.isna(latest.get("%D", np.nan)) else 50),
        "%J": float(latest.get("%J", 50) if not pd.isna(latest.get("%J", np.nan)) else 50),
        "UpperBand": float(latest.get("UpperBand", np.nan)),
        "LowerBand": float(latest.get("LowerBand", np.nan)),
        "ATR": float(latest.get("ATR", 0) if not pd.isna(latest.get("ATR", np.nan)) else 0),
    }, data


def score_stock(ind: dict):
    score = 50
    reasons = []
    close = ind["close"]
    if close > ind["SMA50"] > ind["SMA200"]:
        score += 20
        reasons.append("價格站上 50 日與 200 日均線，長短期趨勢同步偏多。")
    elif close < ind["SMA50"] < ind["SMA200"]:
        score -= 18
        reasons.append("價格跌破主要均線，趨勢防守優先。")
    if ind["Hist"] > 0:
        score += 10
        reasons.append("MACD 柱體為正，動能仍在多方。")
        if ind["Hist"] > ind["Hist_prev"]:
            score += 6
            reasons.append("MACD 柱體擴大，短線動能加速。")
    else:
        score -= 8
        reasons.append("MACD 柱體為負，需觀察動能是否收斂。")
    if 40 <= ind["RSI"] <= 65:
        score += 8
        reasons.append("RSI 位於健康區間，尚未明顯過熱。")
    elif ind["RSI"] > 72:
        score -= 10
        reasons.append("RSI 偏高，追價風險上升。")
    if ind["%K"] > ind["%D"]:
        score += 8
        reasons.append("KD 呈現黃金交叉或多方排列。")
    else:
        score -= 4
        reasons.append("KD 動能偏弱，短線需等轉強訊號。")

    score = max(0, min(100, score))
    if score >= 78:
        label, action = "強勢偏多", "可列入核心觀察，等待量價確認後分批布局。"
    elif score >= 62:
        label, action = "偏多觀察", "適合逢回觀察，避免急漲後追高。"
    elif score >= 45:
        label, action = "區間整理", "以支撐壓力與消息面催化作為操作依據。"
    else:
        label, action = "偏弱防守", "先控管風險，等待均線與動能修復。"
    return score, label, action, reasons


def parse_date(value: str | None):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def clean_title(title: str):
    title = re.sub(r"\s+", " ", title or "").strip()
    title = re.sub(r" - (工商時報|經濟日報|鉅亨網|CNBC|Reuters|Bloomberg|Yahoo奇摩股市|MoneyDJ).*?$", "", title)
    return title


@st.cache_data(ttl=900, show_spinner=False)
def fetch_google_news_rss(query: str, category: str, hours: int, limit: int):
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(f"{query} when:{hours}h")
        + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        root = ET.fromstring(res.content)
    except Exception:
        return []

    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for item in root.findall(".//item")[: limit * 2]:
        title = clean_title(item.findtext("title", ""))
        link = item.findtext("link", "")
        source_el = item.find("source")
        source = source_el.text if source_el is not None and source_el.text else "Google News"
        published = parse_date(item.findtext("pubDate"))
        if published and published < cutoff:
            continue
        if title and link:
            items.append(NewsItem(category, title, source, published, link, query))
        if len(items) >= limit:
            break
    return items


def collect_news(hours: int, per_query: int):
    queries = {
        "總體經濟": [
            "台股 美股 通膨 利率 Fed 台灣央行",
            "美國 公債殖利率 美元 台幣 匯率 台股",
            "台灣 出口 訂單 PMI 景氣 對策信號",
        ],
        "地緣政治": [
            "台海 美國 中國 半導體 出口管制",
            "中東 油價 航運 紅海 美股 台股",
            "關稅 貿易戰 科技管制 供應鏈 台灣",
        ],
        "產業與個股動態": [
            "台股 AI 伺服器 GB200 ASIC CPO 液冷 PCB",
            "台積電 輝達 AMD Broadcom 供應鏈 台股",
            "記憶體 HBM NAND DRAM 台股 美光 三星 SK海力士",
            "機器人 電動車 電力設備 儲能 台股 美股",
            "小型股 轉機股 訂單 法說 產能 擴產 台股",
        ],
    }
    all_items = []
    for category, category_queries in queries.items():
        for query in category_queries:
            all_items.extend(fetch_google_news_rss(query, category, hours, per_query))
            time.sleep(0.08)

    seen = set()
    deduped = []
    for item in all_items:
        key = re.sub(r"\W+", "", item.title.lower())[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    deduped.sort(key=lambda x: x.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return deduped


def source_quality(source: str):
    premium = ["Reuters", "Bloomberg", "CNBC", "工商時報", "經濟日報", "鉅亨", "MoneyDJ", "中央社"]
    if any(name.lower() in source.lower() for name in premium):
        return "高"
    return "中"


def render_stock_tab():
    st.subheader("台股技術面與題材觀察")
    st.caption("輸入台股代號或名稱，可一次輸入多檔並以逗號分隔。資料來源為 Yahoo Finance，適合做研究起點，不構成投資建議。")

    with st.expander("AI 供應鏈分類觀察", expanded=True):
        for group_name, group_data in TAIWAN_AI_GROUPS.items():
            st.markdown(f"**{group_name}**")
            st.caption(group_data["description"])
            cols = st.columns(6)
            for i, (code, name) in enumerate(group_data["stocks"]):
                if cols[i % 6].button(f"{name}\n{code}", key=f"{group_name}_{code}", use_container_width=True):
                    st.session_state["codes_input"] = code
                    st.rerun()

    default_codes = st.session_state.get("codes_input", "2330, 2382, 3661")
    codes_input = st.text_input("股票代號或名稱", value=default_codes, key="codes_input")
    period = st.selectbox("資料區間", ["6mo", "1y", "2y", "5y"], index=1)

    if st.button("開始分析", type="primary", use_container_width=True):
        items = [x.strip() for x in codes_input.split(",") if x.strip()]
        for item in items:
            for code in resolve_stock_input(item):
                with st.spinner(f"讀取 {code} 資料中..."):
                    symbol, hist, info = fetch_stock_data(code, period)
                if hist.empty:
                    st.error(f"{code} 找不到足夠資料。")
                    continue
                ind, hist = calculate_indicators(hist)
                score, label, action, reasons = score_stock(ind)
                name = CHINESE_NAMES.get(normalize_taiwan_code(code), info.get("shortName", code))

                with st.expander(f"{name} ({symbol}) | 研究分數 {score}/100 | {label}", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else ind["close"]
                    change_pct = (ind["close"] - prev_close) / prev_close * 100 if prev_close else 0
                    c1.metric("收盤價", f"{ind['close']:.2f}", f"{change_pct:+.2f}%")
                    c2.metric("RSI", f"{ind['RSI']:.1f}")
                    c3.metric("MACD 柱體", f"{ind['Hist']:.2f}")
                    c4.metric("KD", f"K {ind['%K']:.1f} / D {ind['%D']:.1f}")

                    st.line_chart(hist[["Close", "MA20", "SMA50"]].dropna())
                    st.markdown(f"**操作觀點：** {action}")
                    for reason in reasons:
                        st.write(f"- {reason}")

                    atr = ind["ATR"]
                    buy_low = ind["MA20"] * 0.97 if not np.isnan(ind["MA20"]) else ind["close"] * 0.97
                    buy_high = ind["MA20"] * 1.03 if not np.isnan(ind["MA20"]) else ind["close"] * 1.03
                    stop_loss = ind["close"] - atr * 1.5 if atr else ind["close"] * 0.92
                    target = ind["close"] + atr * 3 if atr else ind["close"] * 1.15
                    st.markdown(
                        f"**交易框架：** 觀察區間 {buy_low:.1f} 至 {buy_high:.1f}，"
                        f"停損參考 {stop_loss:.1f}，第一目標 {target:.1f}。"
                    )

                    with st.expander("基本面摘要"):
                        cols = st.columns(4)
                        cols[0].metric("本益比", f"{info.get('trailingPE') or info.get('forwardPE') or 'N/A'}")
                        cols[1].metric("EPS", f"{info.get('trailingEps') or 'N/A'}")
                        dividend = info.get("dividendYield")
                        cols[2].metric("殖利率", f"{dividend * 100:.2f}%" if dividend else "N/A")
                        cols[3].metric("產業", info.get("industry", "N/A"))

                    csv = hist.to_csv(index=True).encode("utf-8-sig")
                    st.download_button("下載分析資料 CSV", csv, f"{symbol}_analysis.csv", "text/csv")


def render_news_tab():
    st.subheader("過去 24 小時台美股研究情報")
    st.caption("台股為主、美股為輔；自多組新聞搜尋 RSS 蒐集標題與來源，並提供研究員式整理框架。X、Reddit 與付費媒體內容會以外部查核連結補強。")

    with st.expander("內建研究任務 Prompt", expanded=False):
        st.text_area("可複製到任何 LLM 或研究流程", NEWS_TASK_PROMPT, height=300)

    c1, c2, c3 = st.columns([1, 1, 2])
    hours = c1.slider("回溯小時", min_value=6, max_value=48, value=24, step=6)
    per_query = c2.slider("每組搜尋筆數", min_value=3, max_value=10, value=6)
    c3.info("建議先讀高可信來源，再用 X/Reddit 找市場敘事差異，最後回到公司公告、法說與交易數據交叉驗證。")

    if st.button("更新新聞情報", type="primary", use_container_width=True):
        with st.spinner("蒐集新聞中..."):
            news = collect_news(hours, per_query)
        if not news:
            st.warning("目前抓不到新聞 RSS，可能是網路或來源暫時限制。")
            return

        df = pd.DataFrame(
            [
                {
                    "分類": item.category,
                    "標題": item.title,
                    "來源": item.source,
                    "可信度": source_quality(item.source),
                    "時間": item.published.astimezone().strftime("%Y-%m-%d %H:%M") if item.published else "未標示",
                    "搜尋主題": item.query,
                    "連結": item.link,
                }
                for item in news
            ]
        )

        st.session_state["latest_news_df"] = df
        st.success(f"已整理 {len(df)} 則候選新聞。請點開原文檢查內容後，再形成最終投資結論。")

    df = st.session_state.get("latest_news_df")
    if isinstance(df, pd.DataFrame) and not df.empty:
        for category in ["總體經濟", "地緣政治", "產業與個股動態"]:
            subset = df[df["分類"] == category]
            with st.expander(f"{category} ({len(subset)})", expanded=True):
                for _, row in subset.iterrows():
                    st.markdown(f"**[{row['標題']}]({row['連結']})**")
                    st.caption(f"{row['時間']} | {row['來源']} | 可信度：{row['可信度']} | 主題：{row['搜尋主題']}")

        st.markdown("### 研究員綜合解析框架")
        st.markdown(
            """
- **所有動態總結：** 先把新聞分成政策、資金、需求、供給、財報與估值六條線，避免只看單一熱門標題。
- **未來一周大事：** 關注美國通膨與就業數據、Fed 官員談話、台灣出口與電子供應鏈月營收、重量級科技股法說、地緣政治制裁或關稅更新。
- **潛力產業：** AI 伺服器次供應鏈、CPO/光通訊、液冷散熱、高階 PCB/載板、HBM 與記憶體、電力設備、機器人與工業電腦。
- **個股挖掘原則：** 優先找「訂單能見度變長、報價上修、產能瓶頸解除、客戶結構升級、技術面剛轉強」的中型供應鏈，而不是只追已經擁擠的大型權值股。
            """
        )
        st.download_button(
            "下載新聞候選清單 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            "tw_us_market_news_watchlist.csv",
            "text/csv",
        )

    st.markdown("### X 與 Reddit 查核入口")
    social_queries = [
        ("X 台股 AI 伺服器", "https://x.com/search?q=" + quote_plus("台股 AI 伺服器 since:2026-06-27")),
        ("X Nvidia supply chain", "https://x.com/search?q=" + quote_plus("Nvidia supply chain AI server")),
        ("Reddit stocks", "https://www.reddit.com/r/stocks/search/?q=" + quote_plus("AI semiconductor Taiwan") + "&restrict_sr=1&t=day"),
        ("Reddit investing", "https://www.reddit.com/r/investing/search/?q=" + quote_plus("semiconductor AI capex") + "&restrict_sr=1&t=day"),
    ]
    cols = st.columns(4)
    for i, (label, url) in enumerate(social_queries):
        cols[i].link_button(label, url, use_container_width=True)


def render_watchlist_tab():
    st.subheader("美股輔助觀察清單")
    st.caption("用來輔助判斷台股供應鏈方向，特別是 AI 資本支出、半導體設備與雲端需求。")
    for group, tickers in US_WATCHLIST.items():
        with st.expander(group, expanded=True):
            cols = st.columns(len(tickers))
            for i, ticker in enumerate(tickers):
                try:
                    data = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=True)
                    if data.empty:
                        cols[i].metric(ticker, "N/A")
                    else:
                        close = float(data["Close"].iloc[-1])
                        prev = float(data["Close"].iloc[-2]) if len(data) > 1 else close
                        cols[i].metric(ticker, f"{close:.2f}", f"{(close - prev) / prev * 100:+.2f}%")
                except Exception:
                    cols[i].metric(ticker, "N/A")


st.title("台美股研究情報站")
st.caption("結合台股供應鏈觀察、技術面評分、24 小時新聞情報與美股輔助監控。")

tab_stock, tab_news, tab_us = st.tabs(["台股分析", "24 小時情報", "美股輔助"])
with tab_stock:
    render_stock_tab()
with tab_news:
    render_news_tab()
with tab_us:
    render_watchlist_tab()

st.markdown("---")
st.caption("資料僅供研究與教育用途，不構成投資建議。新聞需回到原文、公司公告與交易數據交叉驗證。")
