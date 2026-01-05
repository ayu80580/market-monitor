import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import streamlit.components.v1 as components
import feedparser
import json
import random
from datetime import datetime, timezone
import time
import urllib.parse
import textwrap

# --- 1. CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Market Monitor", initial_sidebar_state="expanded")

# --- 2. STYLING ---
st.markdown("""
<style>
    .block-container {padding-top: 3rem; padding-bottom: 5rem;}
    .stApp {background-color: #0d1117;}
    
    /* STICKY HEADER CONTAINER */
    .sticky-header {
        position: sticky; top: 0; z-index: 999; background-color: #0d1117;
        border-bottom: 1px solid #30363d; padding-top: 10px; padding-bottom: 10px; margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }
    
    /* MARKET TICKER (NIFTY) */
    .market-ticker {
        display: flex; gap: 20px; font-family: 'Segoe UI', sans-serif; font-size: 14px;
        border-bottom: 1px solid #21262d; padding-bottom: 8px; margin-bottom: 8px;
    }
    .index-item { display: flex; align-items: center; gap: 8px; }
    .index-name { color: #8b949e; font-weight: 600; }
    .index-val { font-weight: 700; font-family: monospace; }
    
    /* STOCK HEADER */
    .stock-title { font-size: 30px; font-weight: 800; color: #ffffff; margin: 0; line-height: 1.2; }
    .stock-sub { font-size: 14px; color: #8b949e; font-weight: 400; vertical-align: middle; margin-left: 10px; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {background-color: #161b22; border-right: 1px solid #30363d; padding-top: 20px;}
    div.stButton > button {
        width: 100%; background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d;
        text-align: left; margin-bottom: 4px;
    }
    div.stButton > button:hover {border-color: #8b949e; color: #ffffff;}
    div[data-testid="column"] + div[data-testid="column"] div.stButton > button {
        text-align: center; color: #ff5252; border-left: none;
    }

    /* Analyst Report */
    .report-box { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 6px; }
    .report-list { list-style-type: none; padding: 0; margin: 0; }
    .report-item { margin-bottom: 4px; font-size: 13px; color: #c9d1d9; }
    .score-badge { background-color: #238636; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .score-badge-red { background-color: #da3633; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .score-badge-yellow { background-color: #d29922; color: black; padding: 2px 8px; border-radius: 4px; font-weight: bold; }

    /* News */
    .news-card {
        background-color: #1e222d; padding: 10px; border-radius: 4px; margin-bottom: 8px; 
        border-left: 3px solid #58a6ff;
    }
    .news-time { font-size: 11px; color: #58a6ff; font-weight: bold; margin-bottom: 2px; }
    .news-title { font-size: 13px; color: #e6edf3; font-weight: 600; text-decoration: none; }
    .news-title:hover { color: #58a6ff; text-decoration: underline; }
    
    div[data-testid="stMetricValue"] {font-size: 20px !important; color: #e6edf3 !important;}
</style>
""", unsafe_allow_html=True)

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["RELIANCE", "TCS", "INFY", "BSE", "CDSL", "TMCV"]
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = "RELIANCE"

# --- 3. HELPER FUNCTIONS ---
def time_ago(published_parsed):
    if not published_parsed: return "Just now"
    now = datetime.now(timezone.utc)
    pub_dt = datetime.fromtimestamp(time.mktime(published_parsed), timezone.utc)
    diff = now - pub_dt
    seconds = diff.total_seconds()
    if seconds < 60: return "Just now"
    if seconds < 3600: return f"{int(seconds // 60)}m ago"
    if seconds < 86400: return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"

def fetch_news(query):
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en&t={int(time.time())}"
    feed = feedparser.parse(url)
    news_data = []
    for entry in feed.entries[:6]:
        news_data.append({
            "title": entry.title,
            "link": entry.link,
            "source": entry.source.title,
            "time_str": time_ago(entry.published_parsed)
        })
    return news_data

def get_market_indices():
    """Fetches Live NIFTY 50 and NIFTY BANK"""
    try:
        tickers = yf.Tickers("^NSEI ^NSEBANK")
        n50 = tickers.tickers['^NSEI'].fast_info
        n50_obj = {"price": n50.last_price, "change": n50.last_price - n50.previous_close, "pct": (n50.last_price - n50.previous_close)/n50.previous_close*100}
        nb = tickers.tickers['^NSEBANK'].fast_info
        nb_obj = {"price": nb.last_price, "change": nb.last_price - nb.previous_close, "pct": (nb.last_price - nb.previous_close)/nb.previous_close*100}
        return n50_obj, nb_obj
    except: return None, None

def get_sector_map(ticker):
    """Maps Stock to Sector Index"""
    sector_map = {
        "RELIANCE": "^CNXENERGY", "ONGC": "^CNXENERGY", "POWERGRID": "^CNXENERGY",
        "TCS": "^CNXIT", "INFY": "^CNXIT", "WIPRO": "^CNXIT", "HCLTECH": "^CNXIT",
        "HDFCBANK": "^NSEBANK", "SBIN": "^NSEBANK", "ICICIBANK": "^NSEBANK",
        "TATASTEEL": "^CNXMETAL", "JINDALSTEL": "^CNXMETAL",
        "TATAMOTORS": "^CNXAUTO", "M&M": "^CNXAUTO", "TMCV": "^CNXAUTO",
        "ITC": "^CNXFMCG", "HUL": "^CNXFMCG", "SUNPHARMA": "^CNXPHARMA",
        "BSE": "^CNXFIN", "CDSL": "^CNXFIN", "ZOMATO": "^CNXIT"
    }
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "").upper()
    return sector_map.get(clean_ticker, "^NSEI")

def get_quant_analysis(ticker):
    try:
        yf_symbol = ticker if ".NS" in ticker else f"{ticker}.NS"
        df = yf.download(yf_symbol, period="5d", interval="1m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # --- FIX FOR VWAP ERROR: Force Sort Index ---
        df = df.sort_index()

        # Sector Data
        sector_symbol = get_sector_map(ticker)
        try:
            sector_df = yf.download(sector_symbol, period="1d", interval="1d", progress=False)
            if not sector_df.empty:
                if isinstance(sector_df.columns, pd.MultiIndex): sector_df.columns = sector_df.columns.get_level_values(0)
                sec_change = (sector_df['Close'].iloc[-1] - sector_df['Open'].iloc[-1])
                sec_pct = (sec_change / sector_df['Open'].iloc[-1]) * 100
                sector_name = sector_symbol.replace("^CNX", "").replace("^NSE", "").replace("I", "")
            else:
                sec_pct = 0
                sector_name = "MARKET"
        except:
            sec_pct = 0
            sector_name = "MARKET"

        # --- INDICATORS ---
        df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df = df.join(macd)
        st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=7, multiplier=3)
        if st_data is not None: df = df.join(st_data)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = df.join(bb)
        df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        df = df.join(adx)
        ichimoku = ta.ichimoku(df['High'], df['Low'], df['Close'])[0]
        df = df.join(ichimoku)
        df['CCI'] = ta.cci(df['High'], df['Low'], df['Close'], length=20)
        df['WILLR'] = ta.willr(df['High'], df['Low'], df['Close'], length=14)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        st_dir = [c for c in df.columns if 'SUPERTd' in c][0]
        st_val = [c for c in df.columns if 'SUPERT' in c and 'd' not in c][0]
        
        # Values
        close = latest['Close']
        vwap = latest.get('VWAP', close)
        rsi = latest.get('RSI_14', 50)
        macd_line = latest.get('MACD_12_26_9', 0)
        macd_sig = latest.get('MACDs_12_26_9', 0)
        mfi = latest.get('MFI_14', 50)
        adx_val = latest.get('ADX_14', 0)
        cci = latest.get('CCI_20_0.015', 0)
        willr = latest.get('WILLR_14', -50)
        span_a = latest.get('ISA_9', 0)
        span_b = latest.get('ISB_26', 0)
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)
        bb_upper = latest.get('BBU_20_2.0', 0)
        bb_lower = latest.get('BBL_20_2.0', 0)

        # --- SCORING ---
        score = 50
        reasons = []

        if sec_pct > 0.2: 
            score += 5
            reasons.append(f"🌍 **Sector ({sector_name}):** Bullish ({sec_pct:.2f}%)")
        elif sec_pct < -0.2:
            score -= 5
            reasons.append(f"🌍 **Sector ({sector_name}):** Bearish ({sec_pct:.2f}%)")

        if latest[st_dir] == 1: score += 10; reasons.append("📈 **SuperTrend:** Bullish")
        else: score -= 10; reasons.append("📉 **SuperTrend:** Bearish")

        if close > vwap: score += 10; reasons.append("🏦 **VWAP:** Price > Inst. Avg")
        else: score -= 10; reasons.append("🏦 **VWAP:** Price < Inst. Avg")

        if rsi < 30: score += 5; reasons.append(f"🟢 **RSI:** Oversold ({rsi:.0f})")
        elif rsi > 70: score -= 5; reasons.append(f"🔴 **RSI:** Overbought ({rsi:.0f})")

        if macd_line > macd_sig: score += 5; reasons.append("🟢 **MACD:** Bullish Cross")
        else: score -= 5; reasons.append("🔴 **MACD:** Bearish Cross")
            
        if mfi < 20: score += 5; reasons.append("💰 **MFI:** Accumulation")
        elif mfi > 80: score -= 5; reasons.append("💰 **MFI:** Distribution")

        if adx_val > 25: score += 5; reasons.append(f"💪 **ADX:** Strong Trend")
        
        if close > cloud_top: score += 10; reasons.append("☁️ **Ichimoku:** Above Cloud")
        elif close < cloud_bottom: score -= 10; reasons.append("☁️ **Ichimoku:** Below Cloud")

        if close > bb_upper: score -= 5; reasons.append("💥 **BBands:** Upper Pierce")
        elif close < bb_lower: score += 5; reasons.append("💥 **BBands:** Lower Pierce")

        if cci > 100: score += 5; reasons.append("🔄 **CCI:** Upside Momentum")
        elif cci < -100: score -= 5; reasons.append("🔄 **CCI:** Downside Momentum")

        if willr < -80: score += 5; reasons.append("📉 **Will%R:** Oversold")
        elif willr > -20: score -= 5; reasons.append("📈 **Will%R:** Overbought")

        score = max(0, min(100, score))
        signal = "NEUTRAL"
        if score >= 75: signal = "STRONG BUY"
        elif score >= 60: signal = "BUY"
        elif score <= 25: signal = "STRONG SELL"
        elif score <= 40: signal = "SELL"
        
        news = fetch_news(f"{ticker} stock news")
        
        return {
            "price": close, "vwap": vwap, "signal": signal, "score": score, "reasons": reasons, 
            "stop_loss": latest[st_val], "change": close - prev['Close'],
            "pct": (close - prev['Close']) / prev['Close'] * 100,
            "news": news
        }
    except Exception as e: return None

def get_chart_data(ticker):
    try:
        yf_symbol = ticker if ".NS" in ticker else f"{ticker}.NS"
        df = yf.download(yf_symbol, period="5d", interval="1m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        chart_data = []
        df_sorted = df.sort_index()
        for index, row in df_sorted.iterrows():
            t = int(index.timestamp()) + 19800 
            chart_data.append({
                "time": t, "open": float(row['Open']), "high": float(row['High']),
                "low": float(row['Low']), "close": float(row['Close'])
            })
        return chart_data
    except: return None

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("Watchlist")
    c1, c2 = st.columns([3, 1])
    new_stock = c1.text_input("Add", placeholder="ZOMATO", label_visibility="collapsed").upper()
    if c2.button("➕"):
        if new_stock:
            clean = new_stock.replace(".NS", "").replace(".BO", "").strip()
            if clean not in st.session_state.watchlist:
                st.session_state.watchlist.append(clean)
                st.rerun()
    st.markdown("---")
    for ticker in st.session_state.watchlist:
        col_select, col_delete = st.columns([0.8, 0.2])
        if col_select.button(ticker, key=f"btn_{ticker}"):
            st.session_state.active_ticker = ticker
            st.rerun()
        if col_delete.button("✕", key=f"rem_{ticker}"):
            st.session_state.watchlist.remove(ticker)
            if st.session_state.active_ticker == ticker:
                st.session_state.active_ticker = st.session_state.watchlist[0] if st.session_state.watchlist else ""
            st.rerun()

active = st.session_state.active_ticker
if not active: st.stop()

# --- 5. STICKY HEADER ---
@st.fragment(run_every=10)
def sticky_header_zone():
    data = get_quant_analysis(active)
    n50, nbank = get_market_indices()
    
    if data:
        # Market Ticker HTML
        market_html = ""
        if n50 and nbank:
            n50_c = "#2ea043" if n50['change'] >=0 else "#da3633"
            nb_c = "#2ea043" if nbank['change'] >=0 else "#da3633"
            market_html = f'<div class="market-ticker"><div class="index-item"><span class="index-name">NIFTY 50</span><span class="index-val" style="color:{n50_c};">{n50["price"]:,.0f} ({n50["pct"]:+.2f}%)</span></div><div class="index-item"><span class="index-name">NIFTY BANK</span><span class="index-val" style="color:{nb_c};">{nbank["price"]:,.0f} ({nbank["pct"]:+.2f}%)</span></div></div>'

        # Colors
        p_color = '#2ea043' if data['change'] >= 0 else '#da3633'
        s_color = '#2ea043' if 'BUY' in data['signal'] else '#da3633' if 'SELL' in data['signal'] else '#d29922'

        # Flattened HTML
        header_html = textwrap.dedent(f"""
            <div class="sticky-header">
                {market_html}
                <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                    <div>
                        <div class="stock-title">{active}</div>
                        <div class="stock-sub">NSE • Sector-Aware Quant • {datetime.now().strftime('%H:%M:%S')}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 12px; color: #8b949e;">LTP</div>
                        <div style="font-size: 24px; color: {p_color}; font-weight: bold;">₹{data['price']:.2f}</div>
                        <div style="font-size: 14px; color: {p_color};">{data['change']:.2f} ({data['pct']:.2f}%)</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 12px; color: #8b949e;">SIGNAL</div>
                        <div style="font-size: 18px; color: {s_color}; font-weight: bold;">{data['signal']}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 12px; color: #8b949e;">VWAP</div>
                        <div style="font-size: 18px; color: #58a6ff;">₹{data['vwap']:.2f}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 12px; color: #8b949e;">STOP LOSS</div>
                        <div style="font-size: 18px; color: #e6edf3;">₹{data['stop_loss']:.2f}</div>
                    </div>
                </div>
            </div>
        """)
        st.markdown(header_html, unsafe_allow_html=True)

sticky_header_zone()

# --- 6. WORKSPACE ---
col_chart, col_intel = st.columns([7, 3], gap="medium")

# LEFT: STATIC CHART
with col_chart:
    chart_json = get_chart_data(active)
    if chart_json:
        json_data = json.dumps(chart_json)
        chart_id = f"chart_{active}"
        
        html_code = textwrap.dedent(f"""
        <div style="position: relative; width: 100%; height: 600px;">
            <div id="{chart_id}" style="width: 100%; height: 100%; background-color: #0e1117;"></div>
            <button onclick="resetToLive()" style="position: absolute; bottom: 30px; right: 80px; z-index: 10; background-color: #2962ff; color: white; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-weight: bold;">📍 LIVE</button>
        </div>
        <script src="https://unpkg.com/lightweight-charts@4.0.1/dist/lightweight-charts.standalone.production.js"></script>
        <script>
            (function() {{
                const container = document.getElementById('{chart_id}');
                const chart = LightweightCharts.createChart(container, {{
                    layout: {{ textColor: '#d1d4dc', background: {{ type: 'solid', color: '#0e1117' }} }},
                    grid: {{ vertLines: {{ color: 'rgba(42, 46, 57, 0.4)' }}, horzLines: {{ color: 'rgba(42, 46, 57, 0.4)' }} }},
                    timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '#2B2B43' }},
                    rightPriceScale: {{ borderColor: '#2B2B43' }},
                }});
                const candleSeries = chart.addCandlestickSeries({{ upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350' }});
                candleSeries.setData({json_data});
                new ResizeObserver(entries => {{
                    if (entries.length === 0) return;
                    const newRect = entries[0].contentRect;
                    chart.applyOptions({{ width: newRect.width, height: newRect.height }});
                }}).observe(container);
                window.resetToLive = function() {{ chart.timeScale().scrollToRealTime(); }};
            }})();
        </script>
        """)
        components.html(html_code, height=600)

# RIGHT: LIVE INTEL
with col_intel:
    @st.fragment(run_every=10)
    def live_intel_zone():
        data = get_quant_analysis(active)
        if data:
            color = "score-badge" if data['score'] > 60 else "score-badge-red" if data['score'] < 40 else "score-badge-yellow"
            
            report_html = textwrap.dedent(f"""
            <div class="report-box">
                <div style="margin-bottom:8px; font-size:14px;">
                    <b>QUANT SCORE:</b> <span class="{color}">{data['score']}/100</span>
                </div>
                <div style="height: 250px; overflow-y: auto; padding-right: 5px;">
                    <ul class="report-list">
                        {''.join([f'<li class="report-item">{r}</li>' for r in data['reasons']])}
                    </ul>
                </div>
            </div>
            """)
            st.markdown(report_html, unsafe_allow_html=True)

            st.caption(f"🟢 Live News")
            t1, t2 = st.tabs(["Stock", "Market"])
            with t1:
                if data['news']:
                    for item in data['news']:
                        st.markdown(f"""
                        <div class="news-card">
                            <div class="news-time">{item['time_str']} • {item['source']}</div>
                            <a href="{item['link']}" target="_blank" class="news-title">{item['title']}</a>
                        </div>""", unsafe_allow_html=True)
                else: st.info("No News")
            with t2:
                m_news = fetch_news("Indian Stock Market")
                for item in m_news:
                    st.markdown(f"""
                    <div class="news-card" style="border-left: 3px solid #f9a825;">
                        <div class="news-time">{item['time_str']} • {item['source']}</div>
                        <a href="{item['link']}" target="_blank" class="news-title">{item['title']}</a>
                    </div>""", unsafe_allow_html=True)
    live_intel_zone()

