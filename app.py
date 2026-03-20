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
        st.session_state.scan_results = []
        st.success("System Reset!")
        st.rerun()
    st.divider()
    st.markdown("""
    **Confidence Tiers:**
    * 🚀 **1.5+**: SMASH PLAY
    * 🟢 **1.0**: STRONG PLAY
    * 🟡 **0.5**: VALUE PLAY
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

# 3. Secrets Check
api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION ---
@st.cache_data(ttl=86400)
def get_ai_intelligence(matchup, _key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={_key}"
    payload = {
        "contents": [{"parts": [{"text": f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] 
    }
    try:
        response = requests.post(url, json=payload, timeout=20).json()
        parts = response.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        return parts[0]['text'].strip() if parts else "⚠️ NO INFO FOUND"
    except: return "⚠️ CONNECTION ERROR"

# --- LIVE DATA LOADING (Updated for Local Time) ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"} if "GITHUB_TOKEN" in st.secrets else {}
    try: 
        resp = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            
            # --- LOCAL TIME CONVERSION ---
            file_date = "N/A"
            if not df.empty and 'Recorded_At' in df.columns:
                try:
                    # Parse the UTC time from GitHub and shift to Central Time (-5h)
                    utc_dt = pd.to_datetime(df['Recorded_At'].iloc[-1])
                    local_dt = utc_dt - pd.Timedelta(hours=5) 
                    file_date = local_dt.strftime('%m/%d %I:%M %p')
                except:
                    file_date = df['Recorded_At'].iloc[-1]
            
            return df, file_date
        return pd.DataFrame(), "File Not Found"
    except: return pd.DataFrame(), "Connection Error"

opening_df, csv_timestamp = load_opening_data()

# --- TOP STATUS BAR ---
st.markdown(f"**🕒 Snapshot Database Updated:** `{csv_timestamp} (Central Time)`")
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

# 5. ENGINE
if st.button("🚀 RUN SCAN", use_container_width=True):
    new_results = []
    now_utc = datetime.utcnow()
    time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    time_to = (now_utc + timedelta(hours=18 if horizon=="Today" else 48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    for name in selected_sports:
        url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
        params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": time_from, "commenceTimeTo": time_to}
        try:
            data = requests.get(url, params=params).json()
            for game in data:
                away_t, home_t = game.get('away_team'), game.get('home_team')
                fd_away, pin_away = None, None
                for book in game.get('bookmakers', []):
                    outcomes = book.get('markets', [{}])[0].get('outcomes', [])
                    for o in outcomes:
                        if o.get('name') == away_t:
                            if book['key'] == 'fanduel': fd_away = o.get('point')
                            elif book['key'] == 'pinnacle': pin_away = o.get('point')

                if fd_away is not None and pin_away is not None:
                    # Determine target team and current edge
                    if fd_away > pin_away:
                        target_team, edge, side = away_t, fd_away - pin_away, "away"
                    else:
                        target_team, edge, side = home_t, pin_away - fd_away, "home"

                    matchup_key = f"{sorted([away_t, home_t])[0]} vs {sorted([away_t, home_t])[1]}"
                    
                    # DRIFT LOGIC
                    drift_val = 0.0
                    if not opening_df.empty:
                        hist = opening_df[opening_df['Matchup'] == matchup_key]
                        if not hist.empty:
                            pin_open_away = hist.iloc[0]['Open_Pinnacle']
                            away_drift = pin_away - pin_open_away
                            drift_val = away_drift if side == "away" else -away_drift

                    # ADDITIVE SCORE MATH (Min. Total of 0.5)
                    total_score = edge + drift_val
                    
                    if total_score >= 0.49:
                        if total_score >= 1.45:
                            verdict, v_color, emoji = "SMASH PLAY", "red", "🚀"
                        elif total_score >= 0.95:
                            verdict, v_color, emoji = "STRONG PLAY", "green", "🟢"
                        else:
                            verdict, v_color, emoji = "VALUE PLAY", "orange", "🟡"

                        def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                        new_results.append({
                            "Target": f"{target_team} {fmt(fd_away if side=='away' else -fd_away)}",
                            "Matchup": f"{away_t} @ {home_t}",
                            "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                            "Drift": f"{drift_val:+.1f}",
                            "Edge": f"{edge:.1f}",
                            "Score": f"{total_score:.1f}",
                            "Verdict": f"{emoji} {verdict}",
                            "V_Color": v_color
                        })
        except: pass
    st.session_state.scan_results = new_results

# 6. DISPLAY ENGINE
if st.session_state.scan_results:
    st.success(f"🚨 Found {len(st.session_state.scan_results)} high-confidence targets!")
    for res in st.session_state.scan_results:
        with st.container(border=True):
            st.subheader(f"{res['Target']}")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Current Edge", f"{res['Edge']} pts")
            m2.metric("2:00 AM Drift", f"{res['Drift']} pts")
            m3.markdown(f"**Confidence Score: {res['Score']}**\n### :{res['V_Color']}[{res['Verdict']}]")
            
            if st.button(f"🔍 Analyze Roster", key=f"intel_{res['Matchup']}"):
                with st.spinner("Consulting Gemini..."):
                    report = get_ai_intelligence(res['Matchup'], gemini_key)
                    st.info(f"**Report:** {report}")
else:
    st.info("No games currently meet the 0.5 Combined Confidence threshold.")
