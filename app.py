import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from io import StringIO

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. Sidebar Controls
with st.sidebar:
    st.header("⚙️ System Controls")
    if st.button("🔄 Clear System Cache", use_container_width=True):
        st.cache_data.clear()
        st.session_state.scan_results = []
        st.success("Strategic Logic Reset.")
        st.rerun()
    st.divider()
    st.markdown("""
    **The Intelligence Core:**
    * 🔍 **CATALYST**: The 1-sentence 'Why'.
    * 📊 **SCORECARD**: Star vs. Replacement Math.
    * 🧠 **GEMINI'S ANALYSIS**: Tactical Synthesis.
    * 🏁 **VERDICT**: Pass, Neutral, Play, or Smash Play.
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- MASTER INTELLIGENCE CORE ---
def get_unified_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    
    edge_label = "points" if market_type == "spreads" else "cents (Price Gap)"
    
    # Unified Prompt: Forces deep thinking regardless of output size
    prompt = f"""
    SYSTEM ROLE: You are a Strategic Betting Analyst.
    MATCHUP: {matchup} ({sport}) | TARGET: {target_team} {fd_p} (vs Pinnacle {pin_p})
    MATH EDGE: {edge} {edge_label}

    TASK:
    1. Perform a deep-dive tactical audit of this game. 
    2. Analyze the 'Production Gap' (Star vs. Replacement Volume Stats: NBA/NCAA B: Usage/PPG; NHL: SOG/TOI; NFL/NCAA F: EPA/Targets).
    3. Synthesize the tactical matchup (depth, coaching, and 'Backdoor' potential for large spreads).
    4. Reach a final Verdict: 🛑 PASS, ⚪ NEUTRAL, 🟢 PLAY, or ⚡ SMASH PLAY.

    OUTPUT INSTRUCTIONS:
    - MODE: {mode.upper()}
    - IF mode is 'QUICK': Provide a high-density summary (1-2 sentences per pillar). You MUST include the Verdict.
    - IF mode is 'DETAILED': Provide the full, unsummarized strategic breakdown. You MUST include the Verdict.

    FORMAT:
    1. THE CATALYST
    2. THE VIBE
    3. THE SCORECARD
    4. GEMINI'S ANALYSIS
    5. CONCLUSION VERDICT
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] 
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30).json()
        if "error" in response: return "🛑 API Limit Reached."
        parts = response.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        return parts[0]['text'].strip() if parts else "🔍 No strategic data found."
    except: return "⚠️ CONNECTION ERROR"

# --- LIVE DATA LOADING ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"} if "GITHUB_TOKEN" in st.secrets else {}
    try: 
        resp = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            file_date = (pd.to_datetime(df['Recorded_At'].iloc[-1]) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p') if not df.empty else "N/A"
            return df, file_date
        return pd.DataFrame(), "File Not Found"
    except: return pd.DataFrame(), "Connection Error"

opening_df, csv_timestamp = load_opening_data()
st.markdown(f"**🕒 Market Snapshot (CST):** `{csv_timestamp}`")
st.divider()

# 4. AUDIT SETTINGS (Specialized Markets & 10-Cent Base)
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col_set1, col_set2 = st.columns([1, 1])
    with col_set1:
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_pt_edge = st.slider("Min. Spread Edge (Points):", 0.5, 2.0, 0.5, 0.5)
        min_ml_edge = st.slider("Min. NHL Moneyline Edge (Cents):", 10, 50, 10, 5)
    with col_set2:
        st.write("**Leagues & Specialized Markets:**")
        leagues_config = {
            "NBA": {"key": "basketball_nba", "market": "spreads"},
            "NHL": {"key": "icehockey_nhl", "market": "h2h"},
            "NCAA B": {"key": "basketball_ncaab", "market": "spreads"},
            "NFL": {"key": "americanfootball_nfl", "market": "spreads"},
            "NCAA F": {"key": "americanfootball_ncaaf", "market": "spreads"}
        }
        active_leagues = []
        c1, c2, c3 = st.columns(3)
        if c1.checkbox("NBA", value=True): active_leagues.append("NBA")
        if c2.checkbox("NHL", value=True): active_leagues.append("NHL")
        if c3.checkbox("NCAA B", value=True): active_leagues.append("NCAA B")
        if c1.checkbox("NFL", value=True): active_leagues.append("NFL")
        if c2.checkbox("NCAA F", value=True): active_leagues.append("NCAA F")

# 5. ENGINE
if st.button("🚀 RUN STRATEGIC SCAN", use_container_width=True):
    new_results = []
    now_utc = datetime.utcnow()
    t_from, t_to = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), (now_utc + timedelta(hours=18 if horizon=="Today" else 48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    for name in active_leagues:
        conf = leagues_config[name]
        url = f"https://api.the-odds-api.com/v4/sports/{conf['key']}/odds/"
        params = {"apiKey": api_key, "regions": "us,eu", "markets": conf['market'], "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": t_from, "commenceTimeTo": t_to}
        try:
            data = requests.get(url, params=params).json()
            if isinstance(data, list):
                for game in data:
                    away_t, home_t = game.get('away_team'), game.get('home_team')
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        mkts = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            p = o.get('point') if conf['market'] == 'spreads' else o.get('price')
                            if o['name'] == away_t:
                                if b['key'] == 'fanduel': fd_a = p
                                elif b['key'] == 'pinnacle': pin_a = p
                            if o['name'] == home_t:
                                if b['key'] == 'fanduel': fd_h = p
                                elif b['key'] == 'pinnacle': pin_h = p

                    if all(v is not None for v in [fd_a, pin_a, fd_h, pin_h]):
                        edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                        floor = (min_pt_edge if conf['market'] == 'spreads' else min_ml_edge) - 0.01

                        if edge_a > edge_h and edge_a >= floor:
                            t_team, edge, fd_p, pin_p = away_t, edge_a, fd_a, pin_a
                        elif edge_h >= floor:
                            t_team, edge, fd_p, pin_p = home_t, edge_h, fd_h, pin_h
                        else: continue

                        new_results.append({
                            "Target": f"{t_team} ({'+' if conf['market']=='spreads' and fd_p > 0 else ''}{fd_p})",
                            "Target_Raw": t_team, "FD_Price": fd_p, "PIN_Price": pin_p,
                            "Edge_Raw": edge, "Matchup": f"{away_t} @ {home_t}", 
                            "Sport": name, "Market": conf['market'],
                            "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                            "Edge_Label": "pts" if conf['market'] == 'spreads' else "cents"
                        })
        except: continue
    st.session_state.scan_results = new_results

# 6. DISPLAY ENGINE
if st.session_state.scan_results:
    for res in st.session_state.scan_results:
        with st.container(border=True):
            st.subheader(f"{res['Target']}")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
            m1, m2 = st.columns(2)
            m1.metric(f"{'Spread' if res['Market']=='spreads' else 'Price'} Edge", f"{res['Edge_Raw']} {res['Edge_Label']}")
            m2.metric("Pinnacle Price", f"{res['PIN_Price']}")
            
            # --- TWO BUTTON SYSTEM (UNIFIED LOGIC) ---
            col_a, col_b = st.columns(2)
            
            if col_a.button(f"⚡ Quick Intel", key=f"q_{res['Matchup']}"):
                with st.spinner("Summarizing Deep Dive..."):
                    res_text = get_unified_intel(res['Matchup'], res['Sport'], res['Market'], res['Target_Raw'], res['FD_Price'], res['PIN_Price'], res['Edge_Raw'], gemini_key, mode="quick")
                    st.session_state[f"q_{res['Matchup']}"] = res_text
            
            if col_b.button(f"🔎 Detailed Intel", key=f"d_{res['Matchup']}"):
                with st.spinner("Executing Strategic Deep Dive..."):
                    res_text = get_unified_intel(res['Matchup'], res['Sport'], res['Market'], res['Target_Raw'], res['FD_Price'], res['PIN_Price'], res['Edge_Raw'], gemini_key, mode="detailed")
                    st.session_state[f"d_{res['Matchup']}"] = res_text
            
            if f"q_{res['Matchup']}" in st.session_state:
                st.info(f"⚡ **Quick Audit Summary:**\n\n{st.session_state[f'q_{res['Matchup']}']}")
            if f"d_{res['Matchup']}" in st.session_state:
                st.success(f"🔎 **Full Strategic Audit:**\n\n{st.session_state[f'd_{res['Matchup']}']}")
else:
    st.info("No games meet your Edge requirements.")
