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
        index=1,
        help="Math Only saves API tokens by skipping the Google Search step."
    )
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.markdown("""
    **Vibe Speedometer:**
    * 🚀 **Velocity**: Big movement (>2.0 pts).
    * ⚓ **Stable**: Sharp/FanDuel Alignment (<0.5).
    * 🌊 **Drift**: Standard market noise.
    """)

st.title("💥 BANG! Button")

# 3. Session State Initialization
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []

# Big Button League Toggles
leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state:
        st.session_state[f"active_{league}"] = True

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- MASTER INTELLIGENCE CORE (Deep-to-Brief) ---
def get_master_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    edge_label = "cents" if sport == "NHL" else "points"
    
    cached_news = st.session_state.search_ledger.get(matchup)
    should_search = (grounding_mode == "Live Search") or (grounding_mode == "Session Cache Only" and not cached_news)

    prompt = f"""
    SYSTEM ROLE: Strategic Betting Analyst.
    MATCHUP: {matchup} ({sport}) | TARGET: {target_team} {fd_p} (vs Pin {pin_p})
    MATH EDGE: {edge} {edge_label}

    TASK:
    1. Perform tactical audit & calculate 'Production Gap'.
    2. Reach a Verdict: 🛑 PASS, ⚪ NEUTRAL, 🟢 PLAY, or ⚡ SMASH PLAY.
    
    OUTPUT: {mode.upper()} mode. 
    Quick: High-density 1-2 sentence summary + Verdict.
    Detailed: Full, unsummarized strategic deep dive + Verdict.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
    if should_search: payload["tools"] = [{"google_search": {}}]; time.sleep(1.5)

    try:
        response = requests.post(url, json=payload, timeout=30).json()
        candidate = response.get('candidates', [{}])[0]
        grounding = candidate.get('groundingMetadata', {})
        if grounding and not cached_news:
            st.session_state.search_ledger[matchup] = str(grounding.get('searchEntryPoint', ''))
        return candidate.get('content', {}).get('parts', [{}])[0].get('text', '🔍 No Analysis Found.').strip()
    except: return "⚠️ API LIMIT REACHED - TAKE A BREATHER"

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
st.markdown(f"**🕒 Market Snapshot (CST):** `{csv_timestamp}`")

# --- AUDIT SETTINGS (Big Buttons & Tight Sliders) ---
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col_set1, col_set2 = st.columns([1, 1.2])
    
    with col_set1:
        horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        # Precision Capped: 1.0 Spread / 20 Cents ML
        min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 1.0, 0.5, 0.5)
        min_ml_edge = st.slider("Min NHL ML Edge (cents):", 10, 20, 10, 5)
    
    with col_set2:
        st.write("**League Toggles (Active Targets):**")
        c1, c2, c3 = st.columns(3)
        btn_cols = [c1, c2, c3, c1, c2]
        
        selected_leagues = []
        l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
        
        for i, league in enumerate(leagues_list):
            active = st.session_state[f"active_{league}"]
            if btn_cols[i].button(f"{'✅' if active else '⬜'} {league}", key=f"t_{league}", use_container_width=True):
                st.session_state[f"active_{league}"] = not active
                st.rerun()
            if st.session_state[f"active_{league}"]: selected_leagues.append(league)

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

    for name in selected_leagues:
        s_key, mkt = l_map[name]
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
                        
                        vibe = "🌊"
                        if not opening_df.empty:
                            try:
                                opening_row = opening_df[opening_df['Team'] == t_team].iloc[-1]
                                mov = abs(fd_p - opening_row['Opening_Line'])
                                if mov >= 2.0: vibe = "🚀"
                                elif mov <= 0.5: vibe = "⚓"
                            except: pass

                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": fd_p, "PIN": pin_p, "Edge": edge, "Vibe": vibe, "Matchup": f"{away_t} @ {home_t}", "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')})
        except: continue
    st.session_state.scan_results = new_res

# --- DISPLAY ENGINE ---
if st.session_state.scan_results:
    for res in st.session_state.scan_results:
        with st.container(border=True):
            # SAFETY GET: Prevents KeyError if session is stale
            v = res.get('Vibe', '🌊')
            h = f"{v} {res['Target']} ({'+' if res['Market']=='spreads' and res['FD'] > 0 else ''}{res['FD']})" if res['Market']=='spreads' else f"{v} {res['Target']} (ML)"
            st.subheader(h)
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            
            c1, c2 = st.columns(2)
            c1.metric("Market Edge", f"{res.get('Edge', 0):.1f} {'pts' if res['Market']=='spreads' else 'cents'}")
            if res['Market'] == 'h2h': c2.metric("Pinnacle Price", f"{res['PIN']}")
            
            ca, cb = st.columns(2)
            q_k, d_k = f"q_{res['Matchup']}", f"d_{res['Matchup']}"
            if ca.button(f"⚡ Quick Intel", key=f"btn_{q_k}"):
                st.session_state[q_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res.get('Edge', 0), gemini_key, mode="quick")
            if cb.button(f"🔎 Detailed Intel", key=f"btn_{d_k}"):
                st.session_state[d_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res.get('Edge', 0), gemini_key, mode="detailed")
            
            if q_k in st.session_state and isinstance(st.session_state[q_k], str): st.info(st.session_state[q_k])
            if d_k in st.session_state and isinstance(st.session_state[d_k], str): st.success(st.session_state[d_k])
else:
    st.info("No games meet your precision requirements for this window.")
