import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from io import StringIO

# 1. Page Configuration
st.set_page_config(
    page_title="BANG! Button", 
    page_icon="https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/512/emoji_u1f4a5.png", 
    layout="wide"
)

# 2. Sidebar Controls
with st.sidebar:
    st.header("⚙️ System Controls")
    if st.button("🔄 Clear System Cache", use_container_width=True):
        st.cache_data.clear()
        st.session_state.scan_results = [] # Wipes the current view
        st.success("System Reset!")
        st.rerun()
    st.divider()
    st.info("Tip: Use 'Analyze' on specific games to save your Google AI quota.")

st.title("💥 BANG! Button")

# Initialize Session State for results persistence
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

# 3. Secrets Check
if "ODDS_API_KEY" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ Setup Required: Add 'ODDS_API_KEY' and 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION ---
@st.cache_data(ttl=86400) # Remember injury reports for 24 hours
def get_ai_intelligence(matchup, _key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] 
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20).json()
        if "error" in response:
            msg = response["error"].get("message", "").upper()
            if "QUOTA" in msg: return "🛑 Daily Quota Full (Resets 2AM)"
            return "⚠️ API ERROR"

        parts = response.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        return parts[0]['text'].strip() if parts else "⚠️ NO INFO FOUND"
    except:
        return "⚠️ CONNECTION ERROR"

# --- LIVE DATA LOADING ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"} if "GITHUB_TOKEN" in st.secrets else {}
    
    try: 
        resp = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            file_date = df['Recorded_At'].iloc[-1] if not df.empty and 'Recorded_At' in df.columns else "N/A"
            return df, file_date
        return pd.DataFrame(), "File Not Found"
    except: 
        return pd.DataFrame(), "Connection Error"

opening_df, csv_timestamp = load_opening_data()

# --- TOP STATUS BAR ---
st.markdown(f"**🕒 Snapshot Database Updated:** `{csv_timestamp}`")
st.divider()

# 4. AUDIT SETTINGS
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
    with col2:
        min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 2.0, 0.5, 0.5)
        leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
        selected_sports = st.multiselect("Leagues:", list(leagues.keys()), default=["NBA", "NHL"])

# 5. ENGINE: The Scan Button
if st.button("🚀 RUN SCAN", use_container_width=True):
    new_results = []
    status_msg = st.empty()
    
    now_utc = datetime.utcnow()
    time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    if horizon == "Today":
        time_to = (now_utc + timedelta(hours=18)).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif horizon == "Tomorrow":
        time_to = (now_utc + timedelta(hours=42)).strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        time_to = (now_utc + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    with st.spinner("Calculating Edges..."):
        for name in selected_sports:
            status_msg.info(f"Scanning {name}...")
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": time_from, "commenceTimeTo": time_to}
            
            try:
                data = requests.get(url, params=params).json()
                for game in data:
                    away_team, home_team = game.get('away_team'), game.get('home_team')
                    fd_away, pin_away = None, None
                    for book in game.get('bookmakers', []):
                        outcomes = book.get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            if o.get('name') == away_team:
                                if book['key'] == 'fanduel': fd_away = o.get('point')
                                elif book['key'] == 'pinnacle': pin_away = o.get('point')

                    if fd_away is not None and pin_away is not None:
                        edge_val = abs(fd_away - pin_away)
                        if edge_val >= (min_edge - 0.01):
                            matchup_key = f"{sorted([away_team, home_team])[0]} vs {sorted([away_team, home_team])[1]}"
                            
                            move_val = "MISSING"
                            if not opening_df.empty:
                                hist = opening_df[opening_df['Matchup'] == matchup_key]
                                if not hist.empty:
                                    move_val = f"{pin_away - hist.iloc[0]['Open_Pinnacle']:+.1f} pts"

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            new_results.append({
                                "Target": f"{away_team if fd_away > pin_away else home_team} {fmt(fd_away if fd_away > pin_away else -fd_away)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Move": move_val, "FD": fmt(fd_away), "PIN": fmt(pin_away), "Edge": f"{edge_val:.1f} pts"
                            })
            except: pass

    status_msg.empty()
    st.session_state.scan_results = new_results # Persist findings

# 6. DISPLAY ENGINE
if st.session_state.scan_results:
    st.success(f"🚨 Found {len(st.session_state.scan_results)} targets!")
    
    if view_mode == "Mobile Cards":
        for res in st.session_state.scan_results:
            with st.container(border=True):
                st.subheader(f"{res['Target']}")
                st.write(f"📊 **2:00 AM Drift:** `{res['Move']}`")
                st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
                
                colA, colB, colC = st.columns([1, 1, 2])
                colA.metric("Edge", res['Edge'])
                colB.metric("FD/PIN", f"{res['FD']}/{res['PIN']}")
                
                # --- INDIVIDUAL INTEL BUTTON ---
                with colC:
                    if st.button(f"🔍 Analyze Roster", key=f"intel_{res['Matchup']}"):
                        with st.spinner("Consulting Gemini..."):
                            report = get_ai_intelligence(res['Matchup'], gemini_key)
                            st.info(f"**Report:** {report}")
    else:
        st.dataframe(pd.DataFrame(st.session_state.scan_results), use_container_width=True, hide_index=True)
else:
    if "scan_results" in st.session_state:
        st.info("Hit 'Run Scan' to search for market discrepancies.")
