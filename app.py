import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from io import StringIO

# 1. Page Configuration
st.set_page_config(
    page_title="BANG! Button", 
    page_icon="💥", 
    layout="wide"
)

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
    **Confidence Tiers:**
    * 🚀 **1.5+**: SMASH
    * 🟢 **1.0**: STRONG
    * 🟡 **0.5**: VALUE
    """)

st.title("💥 BANG! Button")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION (CACHE REMOVED FOR TESTING) ---
def get_ai_intelligence(matchup, _key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] 
    }
    
    try:
        # We increase timeout to 30s because Search tools can be slow
        response = requests.post(url, json=payload, timeout=30).json()
        
        if "error" in response:
            err_msg = response["error"].get("message", "").upper()
            if "QUOTA" in err_msg:
                return "🛑 API Quota Full: Google is throttling this key/project."
            return f"⚠️ API Error: {err_msg[:25]}"

        candidates = response.get('candidates', [{}])
        parts = candidates[0].get('content', {}).get('parts', [])
        
        if parts:
            return parts[0]['text'].strip()
        
        return "🔍 No fresh injury news found for this matchup."
        
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)[:20]}"

# --- LIVE DATA LOADING (CST) ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"} if "GITHUB_TOKEN" in st.secrets else {}
    try: 
        resp = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            file_date = "N/A"
            if not df.empty and 'Recorded_At' in df.columns:
                utc_dt = pd.to_datetime(df['Recorded_At'].iloc[-1])
                file_date = (utc_dt - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')
            return df, file_date
        return pd.DataFrame(), "File Not Found"
    except: return pd.DataFrame(), "Connection Error"

opening_df, csv_timestamp = load_opening_data()
st.markdown(f"**🕒 Market Snapshot (CST):** `{csv_timestamp}`")
st.divider()

# 4. AUDIT SETTINGS
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    c_set1, c_set2 = st.columns([1, 1])
    with c_set1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_edge = st.slider("Min. Price Edge (Hard Floor):", 0.5, 2.0, 0.5, 0.5)

    with c_set2:
        st.write("**Leagues to Scan:**")
        leagues_master = {
            "NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab",
            "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"
        }
        c1, c2, c3 = st.columns(3)
        # ALL CHECKED BY DEFAULT
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
    t_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    t_to = (now_utc + timedelta(hours=18 if horizon=="Today" else 48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    for display_name, sport_key in selected_keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": t_from, "commenceTimeTo": t_to}
        
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            
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
                    if fd_away > pin_away:
                        target_team, edge, side = away_t, fd_away - pin_away, "away"
                    else:
                        target_team, edge, side = home_t, pin_away - fd_away, "home"

                    # --- THE IRONCLAD FLOOR ---
                    if edge < (min_edge - 0.01):
                        continue

                    matchup_key = f"{sorted([away_t, home_t])[0]} vs {sorted([away_t, home_t])[1]}"
                    
                    # Velocity Math
                    vel_val = 0.0
                    if not opening_df.empty:
                        hist = opening_df[opening_df['Matchup'] == matchup_key]
                        if not hist.empty:
                            pin_open_away = hist.iloc[0]['Open_Pinnacle']
                            away_move = pin_away - pin_open_away
                            vel_val = away_move if side == "away" else -away_move

                    total_score = edge + vel_val
                    
                    if total_score >= 0.49:
                        if total_score >= 1.45: verdict, v_color, emoji = "SMASH PLAY", "red", "🚀"
                        elif total_score >= 0.95: verdict, v_color, emoji = "STRONG PLAY", "green", "🟢"
                        else: verdict, v_color, emoji = "VALUE PLAY", "orange", "🟡"

                        steam = " 🔥" if abs(vel_val) >= 0.95 else ""
                        def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                        
                        new_results.append({
                            "Target": f"{target_team} {fmt(fd_away if side=='away' else -fd_away)}",
                            "Matchup": f"{away_t} @ {home_t}",
                            "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                            "Velocity": f"{vel_val:+.1f}{steam}", "Edge": f"{edge:.1f}", "Score": f"{total_score:.1f}",
                            "Verdict": f"{emoji} {verdict}", "V_Color": v_color
                        })
        except:
            continue
            
    st.session_state.scan_results = new_results

# 6. DISPLAY ENGINE
if st.session_state.scan_results:
    st.success(f"🚨 Found {len(st.session_state.scan_results)} Targets")
    for res in st.session_state.scan_results:
        with st.container(border=True):
            st.subheader(f"{res['Target']}")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Current Edge", f"{res['Edge']} pts")
            m2.metric("Market Velocity", f"{res['Velocity']} pts")
            m3.markdown(f"**Score: {res['Score']}**\n### :{res['V_Color']}[{res['Verdict']}]")
            
            if st.button(f"🔍 Analyze Roster", key=f"intel_{res['Matchup']}"):
                with st.spinner("Talking to Google..."):
                    report = get_ai_intelligence(res['Matchup'], gemini_key)
                    st.session_state[f"report_{res['Matchup']}"] = report
            if f"report_{res['Matchup']}" in st.session_state:
                st.info(f"**Roster Intel:** {st.session_state[f'report_{res['Matchup']}']}")
else:
    st.info(f"No games meet the {min_edge} Edge Floor.")
