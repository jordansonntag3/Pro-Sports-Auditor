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
        st.success("Global Cache Wiped.")
        st.rerun()
    st.divider()
    st.markdown("""
    **Signal Strength Definitions:**
    * 🟢 **PURE VALUE**: FD is a price outlier on a stable market.
    * 🟡 **CAUTION**: News is fresh; FD is likely in the process of moving.
    * 🔴 **STALE / TRAP**: The market has moved; the edge is a 'falling knife'.
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE (The "Anchored" Price Audit) ---
def get_forensic_audit(matchup, target_team, fd_price, pin_price, edge, velocity, _key):
    # Using Lite for 1,000 RPD quota stability
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    
    prompt = f"""
    PRICE INTEGRITY AUDIT: {matchup}
    DATE: March 20, 2026
    
    LIVE MARKET DATA (Source of Truth):
    - FANDUEL: {target_team} {fd_price}
    - PINNACLE: {target_team} {pin_price}
    - CURRENT EDGE: {edge} points of value at FanDuel.
    
    TASK: You are a Quantitative Market Analyst. 
    CRITICAL: Do not use Google Search to find current lines. Use the LIVE MARKET DATA above as the absolute truth. Use Google Search ONLY to find the 'News Anchor' (the reason the market is moving).
    
    1. NEWS ANCHOR: Search for roster news for {matchup} today. Does the news explain why Pinnacle is at {pin_price}?
    2. PRICE OUTLIER: Since FanDuel is giving a {edge}-point advantage at {fd_price}, is this a 'lazy book' lag or a 'news trap'?
    3. MARKET FLOOR: Based on the news, is the Pinnacle price of {pin_price} likely the 'final' number, or is the market still crashing?
    
    FINAL SIGNAL: 🟢 PURE VALUE, 🟡 CAUTION, or 🔴 STALE.
    Be concise, cold, and strictly focused on the spread math.
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
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_edge = st.slider("Min. Price Edge (Hard Floor):", 0.5, 2.0, 0.5, 0.5)
    with col_set2:
        st.write("**Leagues to Scan:**")
        leagues_master = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab", "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"}
        c1, c2, c3 = st.columns(3)
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
                        # Which team are we betting on?
                        if fd_away > pin_away:
                            t_team, edge, side = away_t, fd_away - pin_away, "away"
                            fd_p, pin_p = fd_away, pin_away
                        else:
                            t_team, edge, side = home_t, pin_away - fd_away, "home"
                            fd_p, pin_p = fd_away if side=="away" else -fd_away, pin_away if side=="away" else -pin_away
                            # Correction for display logic:
                            if side == "home":
                                fd_p, pin_p = outcomes_p = [o.get('point') for book in game['bookmakers'] for o in book['markets'][0]['outcomes'] if o['name'] == home_t]
                                fd_p = next(o.get('point') for b in game['bookmakers'] if b['key']=='fanduel' for o in b['markets'][0]['outcomes'] if o['name'] == home_t)
                                pin_p = next(o.get('point') for b in game['bookmakers'] if b['key']=='pinnacle' for o in b['markets'][0]['outcomes'] if o['name'] == home_t)

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
                                "Target": f"{t_team} {'+' if fd_p > 0 else ''}{fd_p}",
                                "Target_Raw": t_team, "FD_Price": fd_p, "PIN_Price": pin_p,
                                "Edge_Raw": edge, "Vel_Raw": vel_val,
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
            
            if st.button(f"🔎 Run Price Audit", key=f"intel_{res['Matchup']}"):
                with st.spinner("Analyzing Market Alignment..."):
                    audit = get_forensic_audit(res['Matchup'], res['Target_Raw'], res['FD_Price'], res['PIN_Price'], res['Edge_Raw'], res['Vel_Raw'], gemini_key)
                    st.session_state[f"audit_{res['Matchup']}"] = audit
            
            if f"audit_{res['Matchup']}" in st.session_state:
                st.markdown("### 🕵️ Price Integrity Audit")
                st.write(st.session_state[f"audit_{res['Matchup']}"])
else:
    st.info(f"No games meet the {min_edge} Edge requirement.")
