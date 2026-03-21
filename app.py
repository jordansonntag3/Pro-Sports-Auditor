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
        st.success("Audit Logic & Cache Reset.")
        st.rerun()
    st.divider()
    st.markdown("""
    **The Intel Audit Framework:**
    * 🔍 **THE CATALYST**: The 1-sentence 'Why'.
    * 🌊 **THE VIBE**: Market Stability Check.
    * 📊 **THE SCORECARD**: Star vs. Replacement Math.
    * 🧠 **GEMINI'S DEEP DIVE**: Bracket-style game synthesis.
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE (The Strategic Deep Dive) ---
def get_intel_audit(matchup, sport, target_team, fd_p, pin_p, edge, _key):
    # Using Lite for 1,000 RPD quota stability
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    
    prompt = f"""
    STRATEGIC INTEL AUDIT: {matchup} ({sport})
    TARGET: {target_team} {fd_p} (vs Pinnacle {pin_p})
    MATH EDGE: {edge} points
    DATE: March 20, 2026
    
    You are a Strategic Betting Analyst. Provide a deep-dive audit using these 4 pillars:
    
    1. THE CATALYST: In 1 sentence, identify the 'News Anchor' (injury, rest, or move) driving the market today.
    2. THE VIBE: Is the market 'Stable' (priced in) or 'Fluid' (active move)?
    3. THE SCORECARD: Identify the star player out and their LIKELY REPLACEMENT. 
       Calculate the 'Production Gap' using volume metrics:
       - NBA/NCAA B: Usage Rate & PPG.
       - NHL: Shots on Goal (SOG) & TOI.
       - NFL/NCAA F: EPA per Play (QBs) or Targets/Air Yards (Skill).
       Compare Star vs. Replacement stats.
    4. GEMINI'S DEEP DIVE: Perform a synthesis of the spread and the news. Does the {edge}-point math edge 
       adequately cover the 'Production Gap' found in Pillar 3? Provide a bracket-style analytical 
       breakdown of the matchup (e.g., coaching, depth, or situational edge).
    
    Format as 4 clear sections. Be cold, analytical, and highly detailed in Pillar 4.
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
        return parts[0]['text'].strip() if parts else "🔍 No audit found."
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

# 4. AUDIT SETTINGS
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col_set1, col_set2 = st.columns([1, 1])
    with col_set1:
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_edge = st.slider("Min. Price Edge (Hard Floor):", 0.5, 2.0, 0.5, 0.5)
    with col_set2:
        st.write("**Leagues to Scan:**")
        leagues_master = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab", "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"}
        c1, c2, c3 = st.columns(3)
        do_nba = c1.checkbox("NBA", value=True)
        do_nhl = c2.checkbox("NHL", value=True)
        do_ncaab = c3.checkbox("NCAA B", value=True)
        do_nfl = c1.checkbox("NFL", value=True)
        do_ncaaf = c2.checkbox("NCAA F", value=True)
        
        selected_keys = []
        if do_nba: selected_keys.append(("NBA", leagues_master["NBA"]))
        if do_nhl: selected_keys.append(("NHL", leagues_master["NHL"]))
        if do_ncaab: selected_keys.append(("NCAA B", leagues_master["NCAA B"]))
        if do_nfl: selected_keys.append(("NFL", leagues_master["NFL"]))
        if do_ncaaf: selected_keys.append(("NCAA F", leagues_master["NCAA F"]))

# 5. ENGINE
if st.button("🚀 RUN SCAN", use_container_width=True):
    new_results = []
    now_utc = datetime.utcnow()
    t_from, t_to = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), (now_utc + timedelta(hours=18 if horizon=="Today" else 48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    for display_name, sport_key in selected_keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": t_from, "commenceTimeTo": t_to}
        try:
            data = requests.get(url, params=params).json()
            if isinstance(data, list):
                for game in data:
                    away_t, home_t = game.get('away_team'), game.get('home_team')
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        for o in b.get('markets', [{}])[0].get('outcomes', []) or []:
                            if o['name'] == away_t:
                                if b['key'] == 'fanduel': fd_a = o['point']
                                elif b['key'] == 'pinnacle': pin_a = o['point']
                            if o['name'] == home_t:
                                if b['key'] == 'fanduel': fd_h = o['point']
                                elif b['key'] == 'pinnacle': pin_h = o['point']

                    if all(v is not None for v in [fd_a, pin_a, fd_h, pin_h]):
                        edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                        if edge_a > edge_h and edge_a >= (min_edge - 0.01):
                            t_team, edge, side, fd_p, pin_p = away_t, edge_a, "away", fd_a, pin_a
                        elif edge_h >= (min_edge - 0.01):
                            t_team, edge, side, home_t, edge_h, "home", fd_h, pin_h
                        else: continue
                        
                        m_key = f"{sorted([away_t, home_t])[0]} vs {sorted([away_t, home_t])[1]}"
                        vel_val = 0.0
                        if not opening_df.empty:
                            hist = opening_df[opening_df['Matchup'] == m_key]
                            if not hist.empty:
                                pin_open_away = hist.iloc[0]['Open_Pinnacle']
                                vel_val = (pin_a - pin_open_away) if side == "away" else -(pin_a - pin_open_away)

                        new_results.append({
                            "Target": f"{t_team} {'+' if fd_p > 0 else ''}{fd_p}",
                            "Target_Raw": t_team, "FD_Price": fd_p, "PIN_Price": pin_p,
                            "Edge_Raw": edge, "Vel_Raw": vel_val, "Matchup": f"{away_t} @ {home_t}", 
                            "Sport": display_name, "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                            "Velocity": f"{vel_val:+.1f}", "Edge": f"{edge:.1f}", "Score": f"{(edge + vel_val):.1f}"
                        })
        except: continue
    st.session_state.scan_results = new_results

# 6. DISPLAY ENGINE
if st.session_state.scan_results:
    for res in st.session_state.scan_results:
        with st.container(border=True):
            st.subheader(f"{res['Target']}")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Price Edge", f"{res['Edge']} pts")
            m2.metric("Market Velocity", f"{res['Velocity']} pts")
            m3.metric("Combined Score", f"{res['Score']}")
            
            btn_key = f"audit_{res['Matchup']}_{res['Target_Raw']}"
            if st.button(f"🔎 Run Intel Audit", key=btn_key):
                with st.spinner(f"Analyzing {res['Sport']} Strategic Matchups..."):
                    audit = get_intel_audit(res['Matchup'], res['Sport'], res['Target_Raw'], res['FD_Price'], res['PIN_Price'], res['Edge_Raw'], gemini_key)
                    st.session_state[f"audit_text_{btn_key}"] = audit
            
            if f"audit_text_{btn_key}" in st.session_state:
                st.markdown("### 📋 The Intel Audit")
                st.write(st.session_state[f"audit_text_{btn_key}"])
else:
    st.info(f"No games currently meet the {min_edge} requirement.")
