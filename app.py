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
        st.success("Logic & Cache Wiped!")
        st.rerun()
    st.divider()
    st.markdown("""
    **Signal Strength Definitions:**
    * 🟢 **PURE VALUE**: Stable market, FanDuel is simply lagging.
    * 🟡 **CAUTION**: News is fresh, line is moving, edge is thin.
    * 🔴 **STALE / TRAP**: Line is crashing; news is worse than the points.
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE (The 3-Question Forensic Audit) ---
def get_forensic_audit(matchup, target_team, edge, velocity, _key):
    # Using the Lite model for high-quota stability as discussed
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    
    prompt = f"""
    MARKET AUDIT: {matchup}
    TARGET: {target_team} | MATH EDGE: {edge} pts | VELOCITY: {velocity} pts
    
    As a professional market analyst for March 20, 2026, answer these 3 questions:
    1. NEWS ANCHOR: What specific news (injuries, rest, or sharp action) is driving the {velocity} point move?
    2. VALUE INTEGRITY: Does the {edge} point math edge actually compensate for the roster news found in #1?
    3. MARKET FLOOR: Is this line stable at FanDuel's current price, or is it still 'accelerating' (crashing) toward a new price?
    
    FINAL SIGNAL: Categorize as 🟢 PURE VALUE, 🟡 CAUTION, or 🔴 STALE/TRAP.
    Format your response as a clean bulleted list. Be concise.
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
        return parts[0]['text'].strip() if parts else "🔍 No forensic data found."
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
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_edge = st.slider("Min. Price Edge (Hard Floor):", 0.5, 2.0, 0.5, 0.5)
    with col_set2:
        st.write("**Leagues to Scan:**")
        leagues_master = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab", "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"}
        c1, c2, c3 = st.columns(3)
        # ALL CHECKED BY DEFAULT
        do_nba, do_nhl, do_ncaab = c1.checkbox("NBA", value=True), c2.checkbox("NHL", value=True), c3.checkbox("NCAA B", value=True)
        do_nfl, do_ncaaf = c1.checkbox("NFL", value=True), c2.checkbox("NCAA F", value=True)
        
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
                    fd_away, pin_away = None, None
                    for book in game.get('bookmakers', []):
                        mkts = book.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            if o.get('name') == away_t:
                                if book['key'] == 'fanduel': fd_away = o.get('point')
                                elif book['key'] == 'pinnacle': pin_away = o.get('point')

                    if fd_away is not None and pin_away is not None:
                        t_team, edge, side = (away_t, fd_away - pin_away, "away") if fd_away > pin_away else (home_t, pin_away - fd_away, "home")
                        if edge < (min_edge - 0.01): continue
                        
                        m_key = f"{sorted([away_t, home_t])[0]} vs {sorted([away_t, home_t])[1]}"
                        vel_val = 0.0
                        if not opening_df.empty:
                            hist = opening_df[opening_df['Matchup'] == m_key]
                            if not hist.empty:
                                pin_open_away = hist.iloc[0]['Open_Pinnacle']
                                vel_val = (pin_away - pin_open_away) if side == "away" else -(pin_away - pin_open_away)

                        total_score = edge + vel_val
                        if total_score >= 0.49:
                            new_results.append({
                                "Target": f"{t_team} {'+' if fd_away > 0 else ''}{fd_away if side=='away' else -fd_away}",
                                "Target_Raw": t_team, "Edge_Raw": edge, "Vel_Raw": vel_val,
                                "Matchup": f"{away_t} @ {home_t}", "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Velocity": f"{vel_val:+.1f}", "Edge": f"{edge:.1f}", "Score": f"{total_score:.1f}"
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
            
            if st.button(f"🔎 Run Forensic Audit", key=f"intel_{res['Matchup']}"):
                with st.spinner("Analyzing Market Alignment..."):
                    audit = get_forensic_audit(res['Matchup'], res['Target_Raw'], res['Edge_Raw'], res['Vel_Raw'], gemini_key)
                    st.session_state[f"audit_{res['Matchup']}"] = audit
            
            if f"audit_{res['Matchup']}" in st.session_state:
                st.markdown("### 🕵️ Intelligence Audit")
                st.write(st.session_state[f"audit_{res['Matchup']}"])
else:
    st.info(f"No games meet the {min_edge} Edge requirement.")
