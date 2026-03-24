import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
from io import StringIO
import pytz

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. Sidebar & System Controls
with st.sidebar:
    st.header("⚙️ Command Center")
    grounding_mode = st.radio("Grounding Mode:", ["Live Search", "Session Cache Only", "Math Only"], index=1)
    
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            if key not in ["sent_alerts"]: del st.session_state[key]
        st.rerun()
    st.divider()
    st.markdown("**Vibe Guide:** 🚀 Velocity | ⚓ Stable | 🌊 Drift")

st.title("💥 BANG! Button")

# 3. Session State
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "sent_alerts" not in st.session_state: st.session_state.sent_alerts = set()
if "bet_history" not in st.session_state: st.session_state.bet_history = []
if "last_sync" not in st.session_state: st.session_state.last_sync = 0
if "debug_report" not in st.session_state: st.session_state.debug_report = {}

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]
discord_live_url = st.secrets.get("DISCORD_LIVE_URL")
github_token = st.secrets.get("GITHUB_TOKEN")

# --- UTILITIES ---
def to_american(decimal):
    try:
        val = float(decimal)
        if val >= 2.0: return f"+{int((val - 1) * 100)}"
        else: return f"{int(-100 / (val - 1))}"
    except: return str(decimal)

def log_to_github_ledger(new_data, overwrite_df=None):
    repo = "jordansonntag3/Pro-Sports-Auditor"; path = "bet_ledger.csv"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_data = r.json(); sha = content_data['sha']
        df = overwrite_df if overwrite_df is not None else pd.concat([pd.read_csv(StringIO(base64.b64decode(content_data['content']).decode('utf-8'))), pd.DataFrame([new_data])], ignore_index=True)
        new_csv = df.to_csv(index=False)
        encoded_content = base64.b64encode(new_csv.encode('utf-8')).decode('utf-8')
        payload = {"message": "Update Ledger", "content": encoded_content, "sha": sha, "branch": "main"}
        return requests.put(url, headers=headers, json=payload).status_code in [200, 201]
    return False

def sync_ledger():
    LEDGER_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/bet_ledger.csv"
    try:
        df = pd.read_csv(f"{LEDGER_URL}?v={time.time()}")
        st.session_state.bet_history = df.to_dict('records')
        st.session_state.last_sync = time.time()
        return True
    except: return False

if time.time() - st.session_state.last_sync > 60: sync_ledger()

# --- TABS ---
tab1, tab2 = st.tabs(["🚀 Strategic Scanner", "📊 Performance Ledger"])

with tab1:
    st.markdown("### 🛠️ Scan Settings")
    col1, col2 = st.columns([1, 1.2])
    with col1:
        # Added "Next 3 Days" to catch full Thursday slate
        horizon = st.radio("Window:", ["Today", "Next 48 Hours", "Next 3 Days"], horizontal=True)
        min_pt_edge = st.slider("Min Spread Edge (pts):", 0.0, 1.0, 0.5, 0.1)
        min_ml_edge = st.slider("Min NHL ML Edge (cents):", 0, 20, 5, 1)
    with col2:
        st.write("**Leagues:**")
        c1, c2, c3 = st.columns(3); selected_leagues = []
        l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
        for league in leagues_list:
            if c1.checkbox(league, value=st.session_state[f"active_{league}"], key=f"cb_{league}"):
                selected_leagues.append(league)

    if st.button("🚀 RUN SCAN", use_container_width=True):
        new_res = []; debug = {"Total": 0, "Started": 0, "Time_Filtered": 0, "Missing_Odds": 0, "Low_Value": 0}
        now_central = datetime.now(pytz.timezone('US/Central'))
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Generous Windowing
        if horizon == "Today": max_time = now_central.replace(hour=23, minute=59)
        elif horizon == "Next 48 Hours": max_time = now_central + timedelta(hours=48)
        else: max_time = now_central + timedelta(hours=72)

        logged_today = [str(b['Team']) for b in st.session_state.bet_history if today_str in str(b['Date'])]

        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    debug["Total"] += 1
                    comm_utc = pd.to_datetime(game['commence_time']).tz_convert('UTC')
                    comm_c = comm_utc.astimezone(pytz.timezone('US/Central'))
                    
                    if comm_c < now_central: debug["Started"] += 1; continue
                    if comm_c > max_time: debug["Time_Filtered"] += 1; continue
                    
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        outcomes = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            v = o.get('point') if mkt == 'spreads' else o.get('price')
                            if o['name'] == game['away_team']:
                                if b['key'] == 'fanduel': fd_a = v
                                elif b['key'] == 'pinnacle': pin_a = v
                            elif o['name'] == game['home_team']:
                                if b['key'] == 'fanduel': fd_h = v
                                elif b['key'] == 'pinnacle': pin_h = v
                    
                    if any(v is None for v in [fd_a, pin_a, fd_h, pin_h]):
                        debug["Missing_Odds"] += 1; continue
                    
                    edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                    if mkt == 'h2h': edge_a, edge_h = edge_a * 100, edge_h * 100
                    
                    floor = (min_ml_edge if mkt == 'h2h' else min_pt_edge) - 0.01
                    if edge_a >= floor or edge_h >= floor:
                        t_team, edge, price = (game['away_team'], edge_a, fd_a) if edge_a > edge_h else (game['home_team'], edge_h, fd_h)
                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": price, "Edge": edge, "Matchup": f"{game['away_team']} @ {game['home_team']}", "Start": comm_c.strftime('%m/%d %I:%M %p')})
                    else: debug["Low_Value"] += 1
            except: continue
        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Edge'], reverse=True)
        st.session_state.debug_report = debug

    if st.session_state.debug_report:
        d = st.session_state.debug_report
        st.write(f"📊 **Raw Pulse:** Found {d['Total']} games. (Skipped: {d['Started']} Started | {d['Time_Filtered']} Future | {d['Missing_Odds']} Odds Missing | {d['Low_Value']} Low Edge)")

    for res in st.session_state.scan_results:
        with st.container(border=True):
            st.subheader(f"{res['Target']} ({to_american(res['FD']) if res['Market']=='h2h' else res['FD']})")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            st.metric("Edge", f"{res['Edge']:.1f} {'cents' if res['Market']=='h2h' else 'pts'}")
            if st.button(f"✅ LOG", key=f"log_{res['Matchup']}"):
                log_to_github_ledger({"Date": today_str, "Team": res['Target'], "Sport": res['Sport'], "Line": res['FD'], "Edge": res['Edge'], "Result": "Pending"})
                st.toast("Logged!"); time.sleep(0.5); st.rerun()

with tab2:
    st.header("📈 Performance Ledger")
    if st.session_state.bet_history:
        display_df = pd.DataFrame(st.session_state.bet_history).iloc[::-1]
        display_df.index = range(1, len(display_df) + 1)
        st.dataframe(display_df, use_container_width=True)
