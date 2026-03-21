import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from io import StringIO

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. Sidebar - Quota & System Controls
with st.sidebar:
    st.header("⚙️ System Controls")
    grounding_mode = st.radio(
        "Grounding Mode:",
        ["Live Search", "Session Cache Only", "Math Only"],
        index=1
    )
    if st.button("🔄 Clear All Cache", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.markdown("**Verdicts:** 🛑 Pass | ⚪ Neutral | 🟢 Play | ⚡ Smash")

st.title("💥 BANG! Button")

# 3. Session State Initialization
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- MASTER INTELLIGENCE CORE ---
def get_master_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    edge_label = "cents" if sport == "NHL" else "points"
    
    cached_news = st.session_state.search_ledger.get(matchup)
    should_search = (grounding_mode == "Live Search") or (grounding_mode == "Session Cache Only" and not cached_news)

    prompt = f"""
    SYSTEM ROLE: Strategic Betting Analyst.
    MATCHUP: {matchup} ({sport}) | TARGET: {target_team} {fd_p} (vs Pin {pin_p})
    MATH EDGE: {edge} {edge_label}
    
    CONTEXT: {f'Use these Search Results: {cached_news}' if cached_news else 'Identify roster news and injuries for this game.'}

    TASK:
    1. Perform tactical audit & calculate 'Production Gap'.
    2. Reach a Verdict: 🛑 PASS, ⚪ NEUTRAL, 🟢 PLAY, or ⚡ SMASH PLAY.
    
    OUTPUT: {mode.upper()} mode. 
    Quick: Summary + Verdict. Detailed: Deep Dive + Verdict.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
    if should_search: payload["tools"] = [{"google_search": {}}]; time.sleep(1.5)

    try:
        response = requests.post(url, json=payload, timeout=30).json()
        candidate = response.get('candidates', [{}])[0]
        grounding = candidate.get('groundingMetadata', {})
        if grounding and not cached_news:
            st.session_state.search_ledger[matchup] = str(grounding.get('searchEntryPoint', ''))
        return candidate.get('content', {}).get('parts', [{}])[0].get('text', '🔍 No Data.').strip()
    except: return "⚠️ API LIMIT OR CONNECTION ERROR"

# --- DATA LOADING ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    try: 
        resp = requests.get(f"{RAW_URL}?v={time.time()}")
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            f_date = (pd.to_datetime(df['Recorded_At'].iloc[-1]) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')
            return df, f_date
        return pd.DataFrame(), "N/A"
    except: return pd.DataFrame(), "Error"

opening_df, csv_timestamp = load_opening_data()
st.markdown(f"**🕒 Market Snapshot:** `{csv_timestamp}`")

# --- AUDIT SETTINGS ---
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col_a, col_b = st.columns([1, 1])
    with col_a:
        horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 2.0, 0.5, 0.5)
        min_ml_edge = st.slider("Min NHL Moneyline Edge (cents):", 5, 50, 10, 5)
    with col_b:
        l_config = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
        selected = []
        c1, c2, c3 = st.columns(3)
        if c1.checkbox("NBA", value=True): selected.append("NBA")
        if c2.checkbox("NHL", value=True): selected.append("NHL")
        if c3.checkbox("NCAA B", value=True): selected.append("NCAA B")
        if c1.checkbox("NFL", value=True): selected.append("NFL")
        if c2.checkbox("NCAA F", value=True): selected.append("NCAA F")

# --- SCANNING ENGINE ---
if st.button("🚀 RUN STRATEGIC SCAN", use_container_width=True):
    new_res = []
    now_utc = datetime.utcnow()
    
    if horizon == "Today":
        t_from, t_to = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), (now_utc + timedelta(hours=18)).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif horizon == "Tomorrow":
        t_from, t_to = (now_utc + timedelta(hours=18)).strftime('%Y-%m-%dT%H:%M:%SZ'), (now_utc + timedelta(hours=42)).strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        t_from, t_to = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), (now_utc + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    status_text = st.empty()
    
    for name in selected:
        s_key, mkt = l_config[name]
        status_text.text(f"Scanning {name} Board...")
        url = f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/"
        params = {"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": t_from, "commenceTimeTo": t_to}
        try:
            data = requests.get(url, params=params).json()
            if isinstance(data, list):
                for game in data:
                    away_t, home_t = game.get('away_team'), game.get('home_team')
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        mkts = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            v = o.get('point') if mkt == 'spreads' else o.get('price')
                            if o['name'] == away_t:
                                if b['key'] == 'fanduel': fd_a = v
                                elif b['key'] == 'pinnacle': pin_a = v
                            elif o['name'] == home_t:
                                if b['key'] == 'fanduel': fd_h = v
                                elif b['key'] == 'pinnacle': pin_h = v

                    if all(v is not None for v in [fd_a, pin_a, fd_h, pin_h]):
                        # NHL CENTS CONVERSION: (Decimal - Decimal) * 100
                        if mkt == 'h2h':
                            edge_a, edge_h = (fd_a - pin_a) * 100, (fd_h - pin_h) * 100
                            floor = min_ml_edge - 0.01
                        else:
                            edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                            floor = min_pt_edge - 0.01

                        if edge_a > edge_h and edge_a >= floor:
                            t_team, edge, fd_p, pin_p = away_t, edge_a, fd_a, pin_a
                        elif edge_h >= floor:
                            t_team, edge, fd_p, pin_p = home_t, edge_h, fd_h, pin_h
                        else: continue

                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": fd_p, "PIN": pin_p, "Edge": edge, "Matchup": f"{away_t} @ {home_t}", "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')})
        except Exception as e:
            st.error(f"Error scanning {name}: {e}")
            continue
    st.session_state.scan_results = new_res
    status_text.text(f"Scan Complete: Found {len(new_res)} Value Plays.")

# --- DISPLAY ENGINE ---
if st.session_state.scan_results:
    for res in st.session_state.scan_results:
        with st.container(border=True):
            header = f"{res['Target']} ({'+' if res['Market']=='spreads' and res['FD'] > 0 else ''}{res['FD']})" if res['Market']=='spreads' else f"{res['Target']} (ML)"
            st.subheader(header)
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            
            c1, c2 = st.columns(2)
            c1.metric("Market Edge", f"{res['Edge']:.1f} {'pts' if res['Market']=='spreads' else 'cents'}")
            c2.metric("Pinnacle Price", f"{res['PIN']}")
            
            ca, cb = st.columns(2)
            q_key, d_key = f"q_{res['Matchup']}", f"d_{res['Matchup']}"
            if ca.button(f"⚡ Quick Intel", key=f"btn_{q_key}"):
                st.session_state[q_key] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="quick")
            if cb.button(f"🔎 Detailed Intel", key=f"btn_{d_key}"):
                st.session_state[d_key] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="detailed")
            
            if q_key in st.session_state and isinstance(st.session_state[q_key], str): st.info(st.session_state[q_key])
            if d_key in st.session_state and isinstance(st.session_state[d_key], str): st.success(st.session_state[d_key])
else:
    st.info("No games currently meet your Edge requirements.")
