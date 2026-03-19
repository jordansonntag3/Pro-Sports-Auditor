import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from io import StringIO

# 1. Page Configuration (MUST BE FIRST)
st.set_page_config(
    page_title="BANG! Button", 
    page_icon="https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/512/emoji_u1f4a5.png", 
    layout="wide"
)

st.title("💥 BANG! Button")

# 2. Secrets Check
if "ODDS_API_KEY" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ Setup Required: Add 'ODDS_API_KEY' and 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION (WITH CACHING) ---
@st.cache_data(ttl=3600) # Remembers results for 1 hour to save your quota
def get_ai_intelligence(matchup, _gemini_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={_gemini_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}] 
    }
    
    try:
        # We only sleep if we aren't using a cached result
        time.sleep(1.2) 
        response = requests.post(url, json=payload, timeout=15).json()
        
        if "error" in response:
            error_msg = response["error"].get("message", "").upper()
            if "QUOTA" in error_msg or "429" in str(response):
                return "QUOTA_EXCEEDED"
            return "⚠️ API ERROR"

        parts = response.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        return parts[0]['text'].strip() if parts else "⚠️ NO INFO"
    except:
        return "⚠️ CONNECTION ERROR"

# --- LIVE DATA LOADING ---
@st.cache_data(ttl=300)
def load_opening_data():
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"} if "GITHUB_TOKEN" in st.secrets else {}
    
    try: 
        response = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if response.status_code == 200:
            return pd.read_csv(StringIO(response.text)), datetime.now().strftime('%I:%M %p')
        return pd.DataFrame(), "Fetch Failed"
    except: 
        return pd.DataFrame(), "Error"

opening_df, last_update = load_opening_data()

# --- TOP STATUS BAR ---
st.markdown(f"**🕒 App Sync:** {last_update} | **📍 Region:** Des Moines (Central)")
st.divider()

# 3. AUDIT SETTINGS (FIXED: expanded=True)
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
    with col2:
        min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 2.0, 0.5, 0.5)
        leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
        selected_sports = st.multiselect("Leagues:", list(leagues.keys()), default=["NBA"])

# 4. ENGINE
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    status_msg = st.empty()
    ai_blocked = False # Short-circuit if quota is hit
    
    now_utc = datetime.utcnow()
    time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    time_to = (now_utc + timedelta(hours=18 if horizon=="Today" else 48 if horizon=="Next 48 Hours" else 24)).strftime('%Y-%m-%dT%H:%M:%SZ')

    with st.spinner("Analyzing Markets..."):
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
                            
                            # AI LOGIC with Quota Protection
                            if not ai_blocked:
                                intel_report = get_ai_intelligence(f"{away_team} vs {home_team}", gemini_key)
                                if intel_report == "QUOTA_EXCEEDED":
                                    ai_blocked = True
                                    intel_report = "🛑 Quota Full (Resets 2AM)"
                            else:
                                intel_report = "⏭️ Skipped (Quota Exceeded)"

                            move_str = "No Morning Data"
                            if not opening_df.empty:
                                hist = opening_df[opening_df['Matchup'] == matchup_key]
                                if not hist.empty:
                                    move_str = f"Move: {pin_away - hist.iloc[0]['Open_Pinnacle']:+.1f} pts"

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            all_results.append({
                                "Status": "🔴" if any(x in intel_report.upper() for x in ["🛑", "HARD PASS", "OUT"]) else "🟢",
                                "Target": f"{away_team if fd_away > pin_away else home_team} {fmt(fd_away if fd_away > pin_away else -fd_away)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Move": move_str, "FD": fmt(fd_away), "PIN": fmt(pin_away), "Edge": f"{edge_val:.1f} pts", "Intel": intel_report
                            })
            except: pass

    status_msg.empty()
    if all_results:
        st.success(f"🚨 Found {len(all_results)} targets!")
        for res in all_results:
            with st.container(border=True):
                st.subheader(f"{res['Status']} {res['Target']}")
                st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
                colA, colB = st.columns(2)
                colA.metric("Edge", res['Edge'], res['Move'] if "No" not in res['Move'] else None)
                colB.metric("FD/PIN", f"{res['FD']}/{res['PIN']}")
                st.info(f"**Report:** {res['Intel']}")
    else: st.warning("No discrepancies found.")
