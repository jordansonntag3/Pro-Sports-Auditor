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

# 3. Session State Initialization
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "sent_alerts" not in st.session_state: st.session_state.sent_alerts = set()
if "bet_history" not in st.session_state: st.session_state.bet_history = []
if "last_sync" not in st.session_state: st.session_state.last_sync = 0

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

# Secrets
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
        if "Result" not in df.columns: df["Result"] = "Pending"
        st.session_state.bet_history = df.to_dict('records')
        st.session_state.last_sync = time.time()
        return True
    except: return False

if time.time() - st.session_state.last_sync > 60: sync_ledger()

def auto_grade_ledger():
    if not st.session_state.bet_history: return "No history found."
    df = pd.DataFrame(st.session_state.bet_history)
    pending_mask = df['Result'] == 'Pending'
    if not pending_mask.any(): return "No pending plays."
    l_map = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab", "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"}
    unique_sports = df.loc[pending_mask, 'Sport'].unique()
    scores_db = {}
    for sport in unique_sports:
        s_key = l_map.get(sport)
        if s_key:
            url = f"https://api.the-odds-api.com/v4/sports/{s_key}/scores/?daysFrom=3&apiKey={api_key}"
            try:
                res = requests.get(url).json()
                for match in res:
                    if match.get('completed'):
                        scores_db[match['home_team']] = match['scores']
                        scores_db[match['away_team']] = match['scores']
            except: continue
    updated = False
    for idx, row in df.loc[pending_mask].iterrows():
        team = row['Team']
        if team in scores_db:
            scores = scores_db[team]
            my_s = next(int(s['score']) for s in scores if s['name'] == team)
            opp_s = next(int(s['score']) for s in scores if s['name'] != team)
            line = row['Line']
            try:
                if any(x in str(line) for x in ['+', '-']) and '.' in str(line):
                    net = my_s + float(line)
                    res = "Win" if net > opp_s else ("Loss" if net < opp_s else "Push")
                else: res = "Win" if my_s > opp_s else "Loss"
                df.at[idx, 'Result'] = res
                updated = True
            except: continue
    if updated:
        log_to_github_ledger({}, overwrite_df=df)
        st.session_state.bet_history = df.to_dict('records')
        return "Grades applied!"
    return "Scores not available yet."

# --- UPDATED: THE PRO/CON DEBATE ENGINE ---
def get_master_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    edge_label = "cents" if sport == "NHL" else "points"
    cached_news = st.session_state.search_ledger.get(matchup)
    should_search = (grounding_mode == "Live Search") or (grounding_mode == "Session Cache Only" and not cached_news)
    
    prompt = f"""
    ROLE: Professional Sports Analyst & Scout.
    GAME: {matchup} ({sport}) | TARGET BET: {target_team} {fd_p} (Math Edge: {edge} {edge_label}).
    
    TASK: Provide a balanced, no-nonsense analysis of this specific bet. 
    STRUCTURE:
    - **PROS**: List the reasons why this bet should win (e.g., math edge, favorable matchup, home court, opponent fatigue, return of players).
    - **CONS**: List the reasons why this bet is dangerous (e.g., key injuries to target, situational trap, sharp money movement, schedule fatigue).
    - **THE CASE**: Synthesize the pros and cons. Acknowledge that beating Vegas is extremely difficult and focus on making an informed decision.
    - **VERDICT**: End with a bold final verdict (🟢 PLAY, 🟡 WAIT, or 🛑 PASS).
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
    if should_search: payload["tools"] = [{"google_search": {}}]; time.sleep(1.5)
    try:
        response = requests.post(url, json=payload, timeout=30).json()
        return response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '🔍 No Data.').strip()
    except: return "⚠️ API ERROR"

# --- TABS ---
tab1, tab2 = st.tabs(["🚀 Strategic Scanner", "📊 Performance Ledger"])

with tab1:
    st.markdown("### 🛠️ Scan Settings")
    col1, col2 = st.columns([1, 1.2])
    with col1:
        horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 1.5, 0.5, 0.1)
        min_ml_edge = st.slider("Min NHL ML Edge (cents):", 10, 30, 10, 1)
    with col2:
        st.write("**Leagues:**")
        c1, c2, c3 = st.columns(3); btn_cols = [c1, c2, c3, c1, c2]; selected_leagues = []
        l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
        for i, league in enumerate(leagues_list):
            active = st.session_state[f"active_{league}"]
            if btn_cols[i].button(f"{'✅' if active else '⬜'} {league}", key=f"t_{league}", use_container_width=True):
                st.session_state[f"active_{league}"] = not active; st.rerun()
            if st.session_state[f"active_{league}"]: selected_leagues.append(league)

    if st.button("🚀 RUN SCAN", use_container_width=True):
        new_res = []; discord_messages = []; today_str = datetime.now().strftime("%Y-%m-%d")
        now_central = datetime.now(pytz.timezone('US/Central'))
        if horizon == "Today": max_time = now_central.replace(hour=23, minute=59)
        elif horizon == "Tomorrow": max_time = (now_central + timedelta(days=1)).replace(hour=23, minute=59)
        else: max_time = now_central + timedelta(hours=48)

        logged_today = [str(b['Team']) for b in st.session_state.bet_history if today_str in str(b['Date'])]
        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    comm_utc = pd.to_datetime(game['commence_time']).tz_convert('UTC')
                    comm_c = comm_utc.astimezone(pytz.timezone('US/Central'))
                    if comm_c < now_central: continue
                    if comm_c > max_time: continue
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        mkts = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            v = o.get('point') if mkt == 'spreads' else o.get('price')
                            if o['name'] == game['away_team']:
                                if b['key'] == 'fanduel': fd_a = v
                                elif b['key'] == 'pinnacle': pin_a = v
                            elif o['name'] == game['home_team']:
                                if b['key'] == 'fanduel': fd_h = v
                                elif b['key'] == 'pinnacle': pin_h = v
                    if any(v is None for v in [fd_a, pin_a, fd_h, pin_h]): continue
                    edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                    if mkt == 'h2h': edge_a, edge_h = edge_a * 100, edge_h * 100
                    floor = (min_ml_edge if mkt == 'h2h' else min_pt_edge) - 0.01
                    if edge_a >= floor or edge_h >= floor:
                        t_team, edge, price = (game['away_team'], edge_a, fd_a) if edge_a > edge_h else (game['home_team'], edge_h, fd_h)
                        alert_fp = f"{t_team}_{today_str}"
                        if edge >= (20 if mkt=='h2h' else 1.0) and alert_fp not in st.session_state.sent_alerts and t_team not in logged_today:
                            line_str = to_american(price) if mkt == 'h2h' else f"{'+' if price > 0 else ''}{price}"
                            discord_messages.append(f"- **{t_team}** {line_str} | Edge: {edge:.1f} ({name})")
                            st.session_state.sent_alerts.add(alert_fp)
                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": price, "PIN": (pin_a if t_team==game['away_team'] else pin_h), "Edge": edge, "Matchup": f"{game['away_team']} @ {game['home_team']}", "Start": comm_c.strftime('%m/%d %I:%M %p')})
            except: continue
        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Edge'], reverse=True)
        if discord_messages and discord_live_url: requests.post(discord_live_url, json={"content": "📢 **LIVE VALUE FOUND:**\n" + "\n".join(discord_messages)})

    for res in st.session_state.scan_results:
        with st.container(border=True):
            display_price = to_american(res['FD']) if res['Market'] == 'h2h' else f"{'+' if res['FD'] > 0 else ''}{res['FD']}"
            st.subheader(f"{res['Target']} ({display_price})")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            c1, c2 = st.columns(2)
            c1.metric("Market Edge", f"{res['Edge']:.1f} {'pts' if res['Market']=='spreads' else 'cents'}")
            if res['Market'] == 'h2h': c2.metric("Pinnacle Price", to_american(res['PIN']))
            ca, cb, cc, cd = st.columns([1, 1, 0.4, 0.5])
            if ca.button(f"⚡ Quick Intel", key=f"q_{res['Matchup']}", use_container_width=True):
                st.session_state[f"iq_{res['Matchup']}"] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="quick")
            if cb.button(f"🔎 Detailed Intel", key=f"d_{res['Matchup']}", use_container_width=True):
                st.session_state[f"id_{res['Matchup']}"] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="detailed")
            units = cc.number_input("Units", 0.1, 10.0, 1.0, 0.5, key=f"u_{res['Matchup']}")
            if cd.button(f"✅ LOG", key=f"l_{res['Matchup']}", type="primary", use_container_width=True):
                if log_to_github_ledger({"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Team": res['Target'], "Sport": res['Sport'], "Line": display_price, "Edge": f"{res['Edge']:.1f}", "Units": units, "Result": "Pending"}):
                    st.toast("Saved!"); time.sleep(0.5); st.rerun()
            if f"iq_{res['Matchup']}" in st.session_state: st.info(st.session_state[f"iq_{res['Matchup']}"])
            if f"id_{res['Matchup']}" in st.session_state: st.success(st.session_state[f"id_{res['Matchup']}"])

with tab2:
    st.header("📈 Performance Ledger")
    col_a, col_b = st.columns(2)
    if col_a.button("🔄 REFRESH FROM GITHUB", use_container_width=True):
        if sync_ledger(): st.toast("Synced!")
        st.rerun()
    if col_b.button("🤖 AUTO-GRADE PENDING", use_container_width=True, type="primary"):
        with st.spinner("Checking scores..."): st.toast(auto_grade_ledger()); time.sleep(1); st.rerun()
    if st.session_state.bet_history:
        df = pd.DataFrame(st.session_state.bet_history)
        with st.expander("📝 MANUAL ADJUSTMENTS", expanded=False):
            # FIXED: SelectboxColumn used correctly
            edited = st.data_editor(df.iloc[::-1], column_config={"Result": st.column_config.SelectboxColumn(options=["Pending", "Win", "Loss", "Push"])}, use_container_width=True, hide_index=False)
            if st.button("💾 SAVE MANUAL GRADES"):
                if log_to_github_ledger({}, overwrite_df=edited.iloc[::-1]): st.success("Updated!"); time.sleep(1); st.rerun()
        display_df = df.iloc[::-1].copy(); display_df.index = range(1, len(display_df) + 1)
        st.dataframe(display_df, use_container_width=True)
