import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings

# 忽略警告以保持畫面乾淨
warnings.filterwarnings('ignore')

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

# 💡 中文名稱對照字典 (你以後想查新股票，可以自己加進這裡)
CHINESE_NAMES = {
    '3131': '弘塑', '3583': '辛耘', '6187': '萬潤', '1560': '中砂',
    '3680': '家登', '3413': '京鼎', '2404': '漢唐', '6196': '帆宣',
    '6640': '均華', '6667': '信紘科', '6515': '穎崴', '3402': '漢科',
    '2330': '台積電', '3260': '威剛', '1802': '台玻', '2345': '智邦',
    '2317': '鴻海', '2454': '聯發科', '0050': '元大台灣50'
}

# 專屬：半導體設備與先進封裝概念股觀測池
EQUIPMENT_POOL = [
    '3131', '3583', '6187', '1560', '3680', '3413', 
    '2404', '6196', '6640', '6667', '6515', '3402'
]

def format_pct(val):
    """將小數轉換為百分比格式，並處理空值"""
    if val is None or val == 'N/A' or pd.isna(val):
        return 'N/A'
    return f"{round(val * 100, 2)}%"

def print_interpretation_guide():
    print("\n" + "📊 【股市數據判讀指南】 ".center(80, "-"))
    print("""
[1] 最新一季財報 (基本面防護網)
  • 毛利率：越高越好，代表產品競爭力強、難以被取代。
  • 營益率：本業獲利能力，若毛利高但營益率負數，代表營業費用(如推銷/管理)花太兇。
  • 營收年增：> 0 代表公司正在成長擴張；< 0 代表步入衰退。

[2] 估值指標 (長線位階)
  • P/E (本益比)：> 20 偏貴 | < 15 偏便宜 (成長型科技股可放寬)。
  • P/B (淨值比)：< 1.2 長線底層價值浮現 (適合傳產、金融)。

[3] 技術與動能 (短線進出點)
  • RSI：> 70 過熱易拉回 | < 30 超賣易反彈。
  • 布林：⚠️觸上軌(過熱注意) | 🟢觸下軌(超跌反彈點)。
  • MACD：📈紅柱放大(強攻) | 📉紅柱縮(轉弱) | 🩸綠柱放大(殺盤) | 🟢醞釀反彈(殺盤衰竭)。
""")
    print("-" * 85)

def scan_rebound_candidates():
    print(f"\n🔍 系統啟動中... 正在掃描 {len(EQUIPMENT_POOL)} 檔【設備股】尋找反彈契機，請稍候...")
    candidates = []
    
    for code in EQUIPMENT_POOL:
        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty:
                ticker = f"{code}.TWO"
                stock = yf.Ticker(ticker)
                hist = stock.history(period="3mo")
                if hist.empty: continue
                
            # 優先使用我們的中文翻譯字典，找不到才用 Yahoo 預設的英文名
            name = CHINESE_NAMES.get(code, stock.info.get('shortName', code))
            last_price = round(hist['Close'].iloc[-1], 2)
            
            delta = hist['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 0
            rsi = round(100 - (100 / (1 + rs)), 2) if loss != 0 else 100
            
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            hist_macd = (macd - signal).iloc[-1]
            hist_macd_prev = (macd - signal).iloc[-2]
            
            if hist_macd < 0 and hist_macd > hist_macd_prev:
                candidates.append({
                    "代號": code, "名稱": name, "收盤價": last_price,
                    "RSI": rsi, "MACD狀態": "🟢綠柱縮小(醞釀反彈)"
                })
        except Exception:
            pass

    if candidates:
        sorted_candidates = sorted(candidates, key=lambda x: x['RSI'])[:5]
        df = pd.DataFrame(sorted_candidates)
        print("\n" + "🎯 【設備股：準備反彈 TOP 5 嚴選】 ".center(60, "="))
        print(df.to_string(index=False))
        print("=" * 66)
    else:
        print("\n目前設備股觀測池中沒有符合「殺盤衰竭」條件的股票，可能處於強勢多頭或全面下殺中。")

def fetch_ultimate_data(stock_codes):
    print(f"\n🚀 個股全方位健檢 | 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 110)
    
    data_list = []
    
    for code in stock_codes:
        valid_stock = False
        for suffix in ['.TW', '.TWO']:
            ticker = f"{code}{suffix}"
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty:
                valid_stock = True
                try:
                    info = stock.info
                    # 優先使用中文字典
                    name = CHINESE_NAMES.get(code, info.get('shortName', code))
                    last_price = round(hist['Close'].iloc[-1], 2)
                    
                    # 財報數據
                    gross_margin = format_pct(info.get('grossMargins'))
                    op_margin = format_pct(info.get('operatingMargins'))
                    rev_growth = format_pct(info.get('revenueGrowth'))
                    
                    # 估值
                    pe = info.get('trailingPE', 'N/A')
                    pe = round(pe, 2) if isinstance(pe, float) else pe
                    pb = info.get('priceToBook', 'N/A')
                    pb = round(pb, 2) if isinstance(pb, float) else pb

                    # RSI
                    delta = hist['Close'].diff()
                    gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
                    rs = gain / loss if loss != 0 else 0
                    rsi = round(100 - (100 / (1 + rs)), 2) if loss != 0 else 100
                    
                    # 布林通道
                    ma20 = hist['Close'].rolling(window=20).mean()
                    std20 = hist['Close'].rolling(window=20).std()
                    upper_band = round((ma20 + 2 * std20).iloc[-1], 2)
                    lower_band = round((ma20 - 2 * std20).iloc[-1], 2)
                    
                    if last_price >= upper_band:
                        bb_status = "⚠️觸及上軌"
                    elif last_price <= lower_band:
                        bb_status = "🟢觸及下軌"
                    else:
                        bb_status = "⚪通道內"

                    # MACD
                    exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
                    exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
                    macd = exp1 - exp2
                    signal = macd.ewm(span=9, adjust=False).mean()
                    hist_macd = (macd - signal).iloc[-1]
                    hist_macd_prev = (macd - signal).iloc[-2]
                    
                    if hist_macd > 0 and hist_macd > hist_macd_prev:
                        macd_status = "📈紅柱放大"
                    elif hist_macd > 0 and hist_macd < hist_macd_prev:
                        macd_status = "📉紅柱縮小"
                    elif hist_macd < 0 and hist_macd < hist_macd_prev:
                        macd_status = "🩸綠柱放大"
                    else:
                        macd_status = "🟢反彈醞釀"
                    
                    data_list.append({
                        "代號": code,
                        "名稱": name,
                        "收盤價": last_price,
                        "毛利率": gross_margin,
                        "營益率": op_margin,
                        "營收年增": rev_growth,
                        "P/E": pe,
                        "P/B": pb,
                        "RSI": rsi,
                        "布林位階": bb_status,
                        "MACD": macd_status
                    })
                except Exception as e:
                    print(f"⚠️ 獲取 {code} 數據時出錯。")
                break
        
        if not valid_stock:
            print(f"❌ 找不到 {code}，請確認代號。")

    if data_list:
        df = pd.DataFrame(data_list)
        print("\n" + "=" * 110)
        print(df.to_string(index=False))
        print("=" * 110)
        print_interpretation_guide()

if __name__ == "__main__":
    scan_rebound_candidates()
    
    while True:
        user_input = input("\n👉 請輸入股票代號 (如: 2330, 3260) 或輸入『q』離開: ")
        
        if user_input.strip().lower() in ['q', 'quit', 'exit']:
            print("\n✅ 系統已關閉，祝你投資順利！")
            break 
            
        elif user_input.strip() == "":
            print("⚠️ 您沒有輸入任何代號，請重新輸入！")
            continue 
            
        codes = [code.strip() for code in user_input.split(',')]
        fetch_ultimate_data(codes)