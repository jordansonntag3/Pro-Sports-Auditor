import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
from io import StringIO
import pytz
importimport streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
from io import StringIO
import pytz
import urllib.parse

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. SESSION STATE (The App's Memory)
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "intel_results" not in st.session_state: st.session_state.intel_results = []
if "sent_alerts" not in st.session_state: st.session_state.sent_alerts = set()
if "bet_history" not in st.session_state: st.session_state.bet_history = []
if "last_sync" not in st.session_state: st.session_state.last_sync = 0

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

# SECRETS
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

def make_scout_link(matchup, sport):
    """The 'Alright' Discord Link: Uses the command query for detailed roster/fatigue news."""
    query = f"Analyze {matchup} {sport} injuries rotation impact schedule fatigue rest days"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.google.com/search?q={encoded_query}"

def log_to_github_ledger(new_data=None, overwrite_df=None):
    """Saves to GitHub. Handles appends and full table overwrites for grading."""
    repo = "jordansonntag3/Pro-Sports-Auditor"; path = "bet_ledger.csv"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_data = r.json(); sha = content_data['sha']
        if overwrite_df is not None:
            df = overwrite_df
        else:
            current_csv = base64.b64decode(content_data['content']).decode('utf-8')
            df = pd.read_csv(StringIO(current_csv))
            if new_data:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        
        new_csv = df.to_csv(index=False)
        encoded_content = base64.b64encode(new_csv.encode('utf-8')).decode('utf-8')
        payload = {"message": "Ledger Sync", "content": encoded_content, "sha": sha, "branch": "main"}
        res = requests.put(url, headers=headers, json=payload)
        return res.status_code in [200, 201]
    return False

def sync_ledger():
    """Pulls current ledger from GitHub into the app memory."""
    LEDGER_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/bet_ledger.csv"
    try:
        df = pd.read_csv(f"{LEDGER_URL}?v={time.time()}")
        if 'Result' not in df.columns: df['Result'] = 'Pending'
        st.session_state.bet_history = df.to_dict('records')
        st.session_state.last_sync = time.time()
        return True
    except: return False

def auto_grade_ledger():
    """Settlement Engine: Fixed spread math and partial name matching (Auburn Tigers)."""
    if not st.session_state.bet_history: return False
    df = pd.DataFrame(st.session_state.bet_history)
    pending_bets = df[df['Result'] == 'Pending']
    if pending_bets.empty: return False

    l_map_rev = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
    updated = False

    for idx, row in pending_bets.iterrows():
        sport_key = l_map_rev.get(row['Sport'])
        if not sport_key: continue
        try:
            scores = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={api_key}&daysFrom=3").json()
            for game in scores:
                # MATCHING: Checks if the logged team name is part of the API name
                game_teams = [game['home_team'].lower(), game['away_team'].lower()]
                target_team = str(row['Team']).lower()
                
                if any(target_team in t for t in game_teams) and game.get('completed'):
                    h_score = next((s['score'] for s in game['scores'] if s['name'] == game['home_team']), 0)
                    a_score = next((s['score'] for s in game['scores'] if s['name'] == game['away_team']), 0)
                    
                    is_home = target_team in game['home_team'].lower()
                    target_s = h_score if is_home else a_score
                    opp_s = a_score if is_home else h_score
                    
                    # MATH: Strip '+' and convert to float for spread addition
                    line_val = float(str(row['Line']).replace('+', ''))
                    
                    if (target_s + line_val) > opp_s: df.at[idx, 'Result'] = "Win"
                    elif (target_s + line_val) < opp_s: df.at[idx, 'Result'] = "Loss"
                    else: df.at[idx, 'Result'] = "Push"
                    updated = True
        except: continue
    
    if updated:
        if log_to_github_ledger(overwrite_df=df):
            st.session_state.bet_history = df.to_dict('records')
            return True
    return False

def get_master_intel(matchup, sport, target, fd_p, edge, _key):
    """Internal Scout: The deep-dive math for your eyes only."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    prompt = (
        f"Professional Scout Report for {matchup} ({sport}). Target: {target} at {fd_p}. "
        f"Analyze injuries and fatigue. Provide a QUANTITATIVE breakdown: "
        f"1. ON/OFF SPLITS: Points per possession (PPP) impact of missing players. "
        f"2. REPLACEMENT VALUE: Statistics for the next man up. "
        f"3. FINAL VERDICT: 🟢 PLAY, 🟡 WAIT, or 🛑 PASS."
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]}
    try:
        time.sleep(1) # Prevent rate limiting
        res = requests.post(url, json=payload, timeout=30).json()
        return res.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No data.')
    except: return "⚠️ Intel Timeout. Try again."

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Command Center")
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            if key not in ["sent_alerts", "bet_history"]: del st.session_state[key]
        st.rerun()

if time.time() - st.session_state.last_sync > 60: sync_ledger()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Strategic Scanner", "🧠 Intel Scout", "📊 Performance Ledger"])

# --- TAB 1: SCANNER ---
with tab1:
    st.markdown("### 🛠️ Scan Settings")
    col1, col2 = st.columns([1, 1.2])
    with col1:
        horizon = st.radio("Window:", ["Today", "Tomorrow"], horizontal=True)
        min_pt_edge = st.slider("Min Spread Edge:", 0.5, 1.5, 0.5, 0.1)
        min_ml_edge = st.slider("Min NHL ML Edge (cents):", 10, 30, 10, 1)
    with col2:
        selected_leagues = []
        l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads")}
        for league in l_map.keys():
            if st.checkbox(f"✅ {league}", value=True): selected_leagues.append(league)

    if st.button("🚀 RUN MATH SCAN", use_container_width=True):
        new_res = []; discord_msg_list = []
        now_c = datetime.now(pytz.timezone('US/Central'))
        today_str = now_c.strftime("%Y-%m-%d")
        
        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    comm_c = pd.to_datetime(game['commence_time']).tz_convert('UTC').astimezone(pytz.timezone('US/Central'))
                    if comm_c < now_c: continue
                    
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
                        t_team, edge, price, pin_p = (game['away_team'], edge_a, fd_a, pin_a) if edge_a >= edge_h else (game['home_team'], edge_h, fd_h, pin_h)
                        
                        alert_fp = f"{t_team}_{today_str}"
                        if discord_live_url and alert_fp not in st.session_state.sent_alerts:
                            line_str = to_american(price) if mkt == 'h2h' else f"{'+' if price > 0 else ''}{price}"
                            scout_url = make_scout_link(f"{game['away_team']} @ {game['home_team']}", name)
                            discord_msg_list.append(f"**{name} | {t_team} ({line_str})** vs PIN {pin_p}\n* Matchup: {game['away_team']} @ {game['home_team']}\n[🔎 **DETAILED SCOUTING**]({scout_url})")
                            st.session_state.sent_alerts.add(alert_fp)
                        
                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": price, "PIN": pin_p, "Edge": edge, "Matchup": f"{game['away_team']} @ {game['home_team']}", "Start": comm_c.strftime('%I:%M %p')})
            except: continue
        
        if discord_msg_list:
            requests.post(discord_live_url, json={"content": "**💥 LIVE VALUE ALERTS**\n" + "\n".join(discord_msg_list)})
        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Edge'], reverse=True)
        st.rerun()

    for res in st.session_state.scan_results:
        with st.container(border=True):
            price_str = to_american(res['FD']) if res['Market'] == 'h2h' else f"{'+' if res['FD'] > 0 else ''}{res['FD']}"
            st.subheader(f"{res['Target']} ({price_str})")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
            c1, c2 = st.columns(2); c1.metric("Market Edge", f"{res['Edge']:.1f}"); c2.metric("Pinnacle", to_american(res['PIN']) if res['Market']=='h2h' else res['PIN'])
            if st.button(f"🔎 GET QUANTITATIVE INTEL", key=f"t1d_{res['Matchup']}", use_container_width=True):
                st.session_state[f"id_{res['Matchup']}"] = get_master_intel(res['Matchup'], res['Sport'], res['Target'], price_str, res['Edge'], gemini_key)
            if f"id_{res['Matchup']}" in st.session_state: st.success(st.session_state[f"id_{res['Matchup']}"])
            units = st.number_input("Units", 0.5, 5.0, 1.0, 0.5, key=f"t1u_{res['Matchup']}")
            if st.button(f"✅ LOG BET", key=f"t1l_{res['Matchup']}", type="primary"):
                log_to_github_ledger({"Date": datetime.now().strftime("%m/%d"), "Team": res['Target'], "Sport": res['Sport'], "Line": price_str, "Edge": f"{res['Edge']:.1f}", "Units": units, "Result": "Pending"})
                st.toast("Logged!"); time.sleep(0.5); st.rerun()

# --- TAB 3: LEDGER ---
with tab3:
    st.header("📈 Performance Ledger")
    c1, c2 = st.columns(2)
    if c1.button("🔄 AUTO-SETTLE", use_container_width=True, type="primary"):
        if auto_grade_ledger(): st.success("Updated!"); st.rerun()
    if c2.button("🔄 REFRESH GITHUB", use_container_width=True):
        if sync_ledger(): st.rerun()

    if st.session_state.bet_history:
        df = pd.DataFrame(st.session_state.bet_history)
        df.index = range(1, len(df) + 1)
        
        with st.expander("📝 MANUAL GRADE (Hard Commit)", expanded=False):
            edited = st.data_editor(df.iloc[::-1], column_config={"Result": st.column_config.SelectboxColumn(options=["Pending", "Win", "Loss", "Push"])}, use_container_width=True)
            if st.button("💾 PUSH GRADES TO GITHUB"):
                # HARD COMMIT: Update local memory first for instant screen update
                st.session_state.bet_history = edited.iloc[::-1].to_dict('records')
                if log_to_github_ledger(overwrite_df=edited.iloc[::-1]):
                    st.success("GitHub Updated!"); time.sleep(0.5); st.rerun()
        
        st.dataframe(df.iloc[::-1], use_container_width=True) urllib.parse

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. SESSION STATE INITIALIZATION
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "intel_results" not in st.session_state: st.session_state.intel_results = []
if "sent_alerts" not in st.session_state: st.session_state.sent_alerts = set()
if "bet_history" not in st.session_state: st.session_state.bet_history = []
if "last_sync" not in st.session_state: st.session_state.last_sync = 0
if "audit_data" not in st.session_state: st.session_state.audit_data = {}

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

# SECRETS
api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]
discord_live_url = st.secrets.get("DISCORD_LIVE_URL")
github_token = st.secrets.get("GITHUB_TOKEN")

# --- UTILITIES & ENGINES ---

def to_american(decimal):
    """Converts decimal odds to American (+/-) format."""
    try:
        val = float(decimal)
        if val >= 2.0: return f"+{int((val - 1) * 100)}"
        else: return f"{int(-100 / (val - 1))}"
    except: return str(decimal)

def make_gemini_link(matchup, sport, target, price, edge):
    """Generates a Google Search link to trigger an AI Overview (Gemini)."""
    query = (
        f"Detailed scouting report for {matchup} {sport}. "
        f"Analyze injuries and schedule fatigue for {target} at {price}. "
        f"Is this a 🟢 PLAY, 🟡 WAIT, or 🛑 PASS?"
    )
    # quote() handles parentheses better than quote_plus() for Discord Markdown
    encoded_query = urllib.parse.quote(query)
    return f"https://www.google.com/search?q={encoded_query}"

def log_to_github_ledger(new_data=None, overwrite_df=None):
    """Saves data to GitHub. Handles both single appends and full table overwrites."""
    repo = "jordansonntag3/Pro-Sports-Auditor"; path = "bet_ledger.csv"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_data = r.json(); sha = content_data['sha']
        if overwrite_df is not None:
            df = overwrite_df
        else:
            current_csv = base64.b64decode(content_data['content']).decode('utf-8')
            df = pd.read_csv(StringIO(current_csv))
            if new_data:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        
        new_csv = df.to_csv(index=False)
        encoded_content = base64.b64encode(new_csv.encode('utf-8')).decode('utf-8')
        payload = {"message": "Ledger Sync", "content": encoded_content, "sha": sha, "branch": "main"}
        res = requests.put(url, headers=headers, json=payload)
        return res.status_code in [200, 201]
    return False

def sync_ledger():
    """Pulls current ledger from GitHub into the app."""
    LEDGER_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/bet_ledger.csv"
    try:
        df = pd.read_csv(f"{LEDGER_URL}?v={time.time()}")
        if 'Result' not in df.columns: df['Result'] = 'Pending'
        st.session_state.bet_history = df.to_dict('records')
        st.session_state.last_sync = time.time()
        return True
    except: return False

def auto_grade_ledger():
    """Automatically settles Win/Loss/Push based on live scores and handicaps."""
    if not st.session_state.bet_history: return False
    df = pd.DataFrame(st.session_state.bet_history)
    pending_bets = df[df['Result'] == 'Pending']
    if pending_bets.empty: return False

    l_map_rev = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
    updated = False

    for idx, row in pending_bets.iterrows():
        sport_key = l_map_rev.get(row['Sport'])
        if not sport_key: continue
        try:
            scores = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={api_key}&daysFrom=3").json()
            for game in scores:
                # REFINED MATCHING: Checks for team name overlap (e.g. 'Auburn' in 'Auburn Tigers')
                game_teams = [game['home_team'].lower(), game['away_team'].lower()]
                target_team = row['Team'].lower()
                
                if any(target_team in t for t in game_teams) and game.get('completed'):
                    h_score = next((s['score'] for s in game['scores'] if s['name'] == game['home_team']), 0)
                    a_score = next((s['score'] for s in game['scores'] if s['name'] == game['away_team']), 0)
                    
                    is_home = target_team in game['home_team'].lower()
                    target_s = h_score if is_home else a_score
                    opp_s = a_score if is_home else h_score
                    
                    # SPREAD MATH: Strips '+' and converts to float
                    line_val = float(str(row['Line']).replace('+', ''))
                    
                    if (target_s + line_val) > opp_s: df.at[idx, 'Result'] = "Win"
                    elif (target_s + line_val) < opp_s: df.at[idx, 'Result'] = "Loss"
                    else: df.at[idx, 'Result'] = "Push"
                    updated = True
        except: continue
    
    if updated:
        if log_to_github_ledger(overwrite_df=df):
            st.session_state.bet_history = df.to_dict('records')
            return True
    return False

def get_master_intel(matchup, sport, mkt, target, fd_p, pin_p, edge, _key):
    """On-app AI analysis."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    pin_ctx = f"vs Pinnacle {pin_p}" if pin_p else "(Locked)"
    prompt = f"Expert Scout: {matchup} ({sport}) Target {target} {fd_p} {pin_ctx}. Provide PROS, CONS, VERDICT."
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if grounding_mode == "Live Search": payload["tools"] = [{"google_search": {}}]; time.sleep(1.2)
    try:
        res = requests.post(url, json=payload, timeout=25).json()
        return res.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No data.')
    except: return "⚠️ API ERROR"

# --- SIDEBAR & GLOBAL SYNC ---
with st.sidebar:
    st.header("⚙️ Command Center")
    grounding_mode = st.radio("Grounding Mode:", ["Live Search", "Session Cache Only", "Math Only"], index=1)
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            if key not in ["sent_alerts", "bet_history"]: del st.session_state[key]
        st.rerun()

if time.time() - st.session_state.last_sync > 60: sync_ledger()

# --- MAIN TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Strategic Scanner", "🧠 Intel Scout", "📊 Performance Ledger"])

# --- TAB 1: MATH SCANNER ---
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
            if btn_cols[i].button(f"{'✅' if active else '⬜'} {league}", key=f"t1_{league}", use_container_width=True):
                st.session_state[f"active_{league}"] = not active; st.rerun()
            if active: selected_leagues.append(league)

    if st.button("🚀 RUN MATH SCAN", use_container_width=True):
        new_res = []; discord_msg_list = []; audit = {"Total": 0, "Started": 0, "Horizon": 0, "NoLines": 0, "Efficient": 0, "Hits": 0}
        now_c = datetime.now(pytz.timezone('US/Central'))
        today_str = now_c.strftime("%Y-%m-%d")
        max_time = now_c.replace(hour=23, minute=59) if horizon == "Today" else (now_c + timedelta(days=1)).replace(hour=23, minute=59) if horizon == "Tomorrow" else now_c + timedelta(hours=48)

        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    audit["Total"] += 1
                    comm_c = pd.to_datetime(game['commence_time']).tz_convert('UTC').astimezone(pytz.timezone('US/Central'))
                    if comm_c < now_c: audit["Started"] += 1; continue
                    if comm_c > max_time: audit["Horizon"] += 1; continue
                    
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
                    
                    if any(v is None for v in [fd_a, pin_a, fd_h, pin_h]): audit["NoLines"] += 1; continue
                    edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                    if mkt == 'h2h': edge_a, edge_h = edge_a * 100, edge_h * 100
                    floor = (min_ml_edge if mkt == 'h2h' else min_pt_edge) - 0.01
                    
                    if edge_a >= floor or edge_h >= floor:
                        audit["Hits"] += 1
                        t_team, edge, price, pin_p = (game['away_team'], edge_a, fd_a, pin_a) if edge_a >= edge_h else (game['home_team'], edge_h, fd_h, pin_h)
                        matchup_str = f"{game['away_team']} @ {game['home_team']}"
                        
                        alert_fp = f"{t_team}_{today_str}"
                        if discord_live_url and alert_fp not in st.session_state.sent_alerts:
                            emoji = "🏒" if name == "NHL" else "🏀" if "NBA" in name or "NCAA B" in name else "🏈"
                            line_str = to_american(price) if mkt == 'h2h' else f"{'+' if price > 0 else ''}{price}"
                            scout_url = make_gemini_link(matchup_str, name, t_team, line_str, edge)
                            discord_msg_list.append(f"{emoji} **{name} | {t_team} ({line_str})**\n* Matchup: {matchup_str}\n* Edge: {edge:.1f} {'cents' if mkt=='h2h' else 'pts'}\n[🔎 **DETAILED INTEL**]({scout_url})")
                            st.session_state.sent_alerts.add(alert_fp)
                        
                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": price, "PIN": pin_p, "Edge": edge, "Matchup": matchup_str, "Start": comm_c.strftime('%m/%d %I:%M %p')})
                    else: audit["Efficient"] += 1
            except: continue
        
        if discord_msg_list:
            requests.post(discord_live_url, json={"content": "**💥 BANG! Button Live Value Feed**\n***\n" + "\n".join(discord_msg_list) + "\n***"})
        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Edge'], reverse=True)
        st.session_state.audit_data = audit; st.rerun()

    if st.session_state.get("audit_data"):
        a = st.session_state.audit_data
        with st.container(border=True):
            c1, c2, c3 = st.columns(3); c1.metric("Total Scanned", a['Total']); c2.metric("Value Hits", a['Hits']); c3.metric("Discarded", a['Total'] - a['Hits'])

    for res in st.session_state.scan_results:
        with st.container(border=True):
            price_str = to_american(res['FD']) if res['Market'] == 'h2h' else f"{'+' if res['FD'] > 0 else ''}{res['FD']}"
            st.subheader(f"{res['Target']} ({price_str})")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            c1, c2 = st.columns(2); c1.metric("Market Edge", f"{res['Edge']:.1f} {'pts' if res['Market']=='spreads' else 'cents'}"); c2.metric("Pinnacle", to_american(res['PIN']) if res['Market']=='h2h' else res['PIN'])
            ca, cb, cc, cd = st.columns([1, 1, 0.4, 0.5])
            if ca.button(f"⚡ Quick Intel", key=f"t1q_{res['Matchup']}"): st.session_state[f"iq_{res['Matchup']}"] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key)
            if cb.button(f"🔎 Detailed Intel", key=f"t1d_{res['Matchup']}"): st.session_state[f"id_{res['Matchup']}"] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key)
            units = cc.number_input("Units", 0.1, 10.0, 1.0, 0.5, key=f"t1u_{res['Matchup']}")
            if cd.button(f"✅ LOG", key=f"t1l_{res['Matchup']}", type="primary"):
                if log_to_github_ledger({"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Team": res['Target'], "Sport": res['Sport'], "Line": price_str, "Edge": f"{res['Edge']:.1f}", "Units": units, "Result": "Pending"}): st.toast("Logged!"); time.sleep(0.5); st.rerun()
            if f"iq_{res['Matchup']}" in st.session_state: st.info(st.session_state[f"iq_{res['Matchup']}"])
            if f"id_{res['Matchup']}" in st.session_state: st.success(st.session_state[f"id_{res['Matchup']}"])

# --- TAB 2: INTEL SCOUT ---
with tab2:
    st.markdown("### 🧠 Master Scout Board")
    if st.button("🚀 REFRESH ALL UPCOMING GAMES", use_container_width=True):
        all_intel = []; now_c = datetime.now(pytz.timezone('US/Central'))
        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us", "markets": mkt}).json()
                for game in data:
                    comm_c = pd.to_datetime(game['commence_time']).tz_convert('UTC').astimezone(pytz.timezone('US/Central'))
                    if comm_c < now_c: continue 
                    fd_a, pin_a = None, None
                    for b in game.get('bookmakers', []):
                        mkts = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            if o['name'] == game['away_team']:
                                if b['key'] == 'fanduel': fd_a = o.get('point') if mkt == 'spreads' else o.get('price')
                                if b['key'] == 'pinnacle': pin_a = o.get('point') if mkt == 'spreads' else o.get('price')
                    all_intel.append({"Matchup": f"{game['away_team']} @ {game['home_team']}", "Target": game['away_team'], "FD": fd_a, "PIN": pin_a, "Sport": name, "Market": mkt, "Start": comm_c.strftime('%I:%M %p')})
            except: continue
        st.session_state.intel_results = all_intel; st.rerun()

    for game in st.session_state.intel_results:
        with st.container(border=True):
            st.subheader(game['Matchup']); st.caption(f"🕒 {game['Start']} | {game['Sport']}")
            c1, c2 = st.columns(2)
            if c1.button(f"⚡ Quick Intel", key=f"t2q_{game['Matchup']}"): st.session_state[f"iq_{game['Matchup']}"] = get_master_intel(game['Matchup'], game['Sport'], game['Market'], game['Target'], game['FD'], game['PIN'], 0.0, gemini_key)
            if c2.button(f"🔎 Detailed Intel", key=f"t2d_{game['Matchup']}"): st.session_state[f"id_{game['Matchup']}"] = get_master_intel(game['Matchup'], game['Sport'], game['Market'], game['Target'], game['FD'], game['PIN'], 0.0, gemini_key)
            if f"iq_{game['Matchup']}" in st.session_state: st.info(st.session_state[f"iq_{game['Matchup']}"])
            if f"id_{game['Matchup']}" in st.session_state: st.success(st.session_state[f"id_{game['Matchup']}"])

# --- TAB 3: PERFORMANCE LEDGER ---
with tab3:
    st.header("📈 Performance Ledger")
    c1, c2 = st.columns(2)
    if c1.button("🔄 AUTO-SETTLE PENDING BETS", use_container_width=True, type="primary"):
        with st.spinner("Auditing scores..."):
            if auto_grade_ledger(): st.success("Updated!"); st.rerun()
            else: st.info("No new game results found.")
    if c2.button("🔄 REFRESH FROM GITHUB", use_container_width=True):
        if sync_ledger(): st.rerun()

    if st.session_state.bet_history:
        df = pd.DataFrame(st.session_state.bet_history)
        if 'Result' not in df.columns: df['Result'] = 'Pending'
        df.index = range(1, len(df) + 1)
        
        with st.expander("📝 MANUAL OVERRIDES", expanded=False):
            edited = st.data_editor(df.iloc[::-1], column_config={"Result": st.column_config.SelectboxColumn(options=["Pending", "Win", "Loss", "Push"])}, use_container_width=True)
            if st.button("💾 SAVE MANUAL UPDATES"):
                if log_to_github_ledger(overwrite_df=edited.iloc[::-1]): st.success("GitHub Updated!"); time.sleep(0.5); st.rerun()
        
        st.subheader("Audit Trail")
        st.dataframe(df.iloc[::-1], use_container_width=True)
