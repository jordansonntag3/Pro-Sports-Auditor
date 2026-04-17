import streamlit as st
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

# 2. SESSION STATE INITIALIZATION
if 'lock_until' not in st.session_state: st.session_state.lock_until = 0
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

# --- UTILITIES ---

def is_locked():
    return time.time() < st.session_state.lock_until

def to_american(decimal):
    try:
        val = float(decimal)
        if val >= 2.0: return f"+{int((val - 1) * 100)}"
        else: return f"{int(-100 / (val - 1))}"
    except: return str(decimal)

def make_scout_link(matchup, sport):
    query = f"Analyze {matchup} {sport} injuries rotation impact schedule fatigue rest days"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.google.com/search?q={encoded_query}"

def log_to_github_ledger(new_data=None, overwrite_df=None):
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
    LEDGER_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/bet_ledger.csv"
    try:
        df = pd.read_csv(f"{LEDGER_URL}?v={time.time()}")
        if 'Result' not in df.columns: df['Result'] = 'Pending'
        st.session_state.bet_history = df.to_dict('records')
        st.session_state.last_sync = time.time()
        return True
    except: return False

def auto_grade_ledger():
    if not st.session_state.bet_history: return False
    df = pd.DataFrame(st.session_state.bet_history)
    pending_bets = df[df['Result'] == 'Pending']
    if pending_bets.empty: return False

    l_map_rev = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab", "NFL": "americanfootball_nfl", "NCAA F": "americanfootball_ncaaf"}
    updated = False

    for idx, row in pending_bets.iterrows():
        sport_key = l_map_rev.get(row['Sport'])
        if not sport_key: continue
        try:
            scores = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={api_key}&daysFrom=3").json()
            for game in scores:
                game_teams = [game['home_team'].lower(), game['away_team'].lower()]
                target_team = str(row['Team']).lower()
                match_found = any(target_team in t or t in target_team for t in game_teams)
                
                if match_found and game.get('completed'):
                    h_score = next((s['score'] for s in game['scores'] if s['name'] == game['home_team']), 0)
                    a_score = next((s['score'] for s in game['scores'] if s['name'] == game['away_team']), 0)
                    is_home = any(target_team in t or t in target_team for t in [game['home_team'].lower()])
                    target_s, opp_s = (int(h_score), int(a_score)) if is_home else (int(a_score), int(h_score))
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

# --- GEMINI INTELLIGENCE ENGINES ---

def get_analyst_opinions(matchup, sport, target, fd_p, _key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={_key}"
    prompt = (
        f"ACT AS A SPORTS MARKET ANALYST. AUDIT THE MARKET CONSENSUS FOR: {matchup} ({sport}).\n"
        f"BENCHMARK: {target} {fd_p}.\n"
        "TASK: Search for 10 distinct sources (betting previews, sharp action trackers).\n"
        "Create a Markdown table: **Source**, **Spread Stance**, **Primary Logic**.\n"
        "End with '🏁 MARKET CONVERGENCE'."
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.1}}
    try:
        res = requests.post(url, json=payload, timeout=50).json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"⚠️ Error: {str(e)}"

def get_math_breakdown(matchup, sport, target, fd_p, _key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={_key}"
    prompt = (
        f"ACT AS A PROFESSIONAL PERSONNEL SCOUT. AUDIT: {matchup} ({sport}).\n"
        f"BENCHMARK: {target} {fd_p}.\n"
        "OUTPUT: ### 🏥 Roster Health & Fatigue, ### ⚖️ The Mismatch Verdict, ### 🏁 Final Intelligence Action (🟢 PLAY or 🛑 HARD PASS)."
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.1}}
    try:
        res = requests.post(url, json=payload, timeout=50).json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"⚠️ Error: {str(e)}"

# --- UI START ---

st.title("💥 BANG! Button Value Scanner")

# Cooldown Timer Display
locked = is_locked()
if locked:
    timer_placeholder = st.empty()
    remaining = int(st.session_state.lock_until - time.time())
    if remaining > 0:
        timer_placeholder.warning(f"⏳ API Cooldown: System ready in {remaining}s...")
    else:
        st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Command Center")
    grounding_mode = st.radio("Grounding Mode:", ["Live Search", "Session Cache Only", "Math Only"], index=0)
    mute_alerts = st.checkbox("🔇 Mute Discord during testing", value=False)
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            if key not in ["sent_alerts", "bet_history"]: del st.session_state[key]
        st.rerun()

if time.time() - st.session_state.last_sync > 60: sync_ledger()

# --- MAIN TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Strategic Scanner", "🧠 Intel Scout", "📊 Performance Ledger"])

with tab1:
    st.markdown("### 🛠️ Scan Settings")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
        min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 1.5, 0.5, 0.1)
        min_ml_edge = st.slider("Min NHL ML Edge (cents):", 5, 10, 5, 1)
    with c2:
        st.write("**Leagues:**")
        c1a, c1b, c1c = st.columns(3); selected_leagues = []
        l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
        btn_cols = [c1a, c1b, c1c, c1a, c1b]
        for i, (league, (s_key, mkt)) in enumerate(l_map.items()):
            active = st.session_state.get(f"active_{league}", True)
            if btn_cols[i].button(f"{'✅' if active else '⬜'} {league}", key=f"t1_btn_{league}", use_container_width=True):
                st.session_state[f"active_{league}"] = not active; st.rerun()
            if active: selected_leagues.append(league)

    if st.button("🚀 RUN SCAN", use_container_width=True):
        new_res, discord_msg_list, now_c = [], [], datetime.now(pytz.timezone('US/Central'))
        today_str = now_c.strftime("%m/%d/%Y")
        if horizon == "Today": max_time = now_c.replace(hour=23, minute=59, second=59)
        elif horizon == "Tomorrow": max_time = (now_c + timedelta(days=1)).replace(hour=23, minute=59, second=59)
        else: max_time = now_c + timedelta(hours=48)
        
        audit = {"Total": 0, "Time": 0, "Missing": 0, "Math": 0, "Hits": 0}

        for name in selected_leagues:
            s_key, mkt = l_map[name]
            try:
                data = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/", params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    audit["Total"] += 1
                    comm_c = pd.to_datetime(game['commence_time']).tz_convert('UTC').astimezone(pytz.timezone('US/Central'))
                    if comm_c < now_c or comm_c > max_time: 
                        audit["Time"] += 1; continue
                    
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
                    
                    if any(v is None for v in [fd_a, pin_a, fd_h, pin_h]): 
                        audit["Missing"] += 1; continue
                        
                    edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                    if mkt == 'h2h': edge_a, edge_h = edge_a * 100, edge_h * 100
                    floor = (min_ml_edge if mkt == 'h2h' else min_pt_edge) - 0.01
                    
                    if edge_a >= floor or edge_h >= floor:
                        audit["Hits"] += 1
                        t_team, edge, price, pin_p = (game['away_team'], edge_a, fd_a, pin_a) if edge_a >= edge_h else (game['home_team'], edge_h, fd_h, pin_h)
                        if discord_live_url and not mute_alerts and f"{t_team}_{today_str}" not in st.session_state.sent_alerts:
                            line_str = to_american(price) if mkt == 'h2h' else f"{'+' if price > 0 else ''}{price}"
                            scout_url = make_scout_link(f"{game['away_team']} @ {game['home_team']}", name)
                            discord_msg_list.append(f"**{name} | {t_team} ({line_str})** vs PIN {pin_p}\n[🔎 **SCOUTING**](<{scout_url}>)")
                            st.session_state.sent_alerts.add(f"{t_team}_{today_str}")
                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": price, "PIN": pin_p, "Edge": edge, "Matchup": f"{game['away_team']} @ {game['home_team']}", "Start": comm_c.strftime('%I:%M %p')})
                    else: audit["Math"] += 1
            except: continue

        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Edge'], reverse=True)
        st.session_state.audit_data = audit
        if discord_msg_list:
            requests.post(discord_live_url, json={"content": "**💥 LIVE VALUE FEED**\n" + "\n".join(discord_msg_list)})
        st.rerun()

    if st.session_state.get("audit_data"):
        a = st.session_state.audit_data
        with st.container(border=True):
            cols = st.columns(5)
            cols[0].metric("Total Scanned", a.get('Total', 0))
            cols[1].metric("Out of Window", a.get('Time', 0))
            cols[2].metric("Missing Line", a.get('Missing', 0))
            cols[3].metric("No Math Edge", a.get('Math', 0))
            cols[4].metric("Value Hits", a.get('Hits', 0))

    for i, res in enumerate(st.session_state.scan_results):
        with st.container(border=True):
            price_str = to_american(res['FD']) if res['Market'] == 'h2h' else f"{'+' if res['FD'] > 0 else ''}{res['FD']}"
            st.subheader(f"{res['Target']} ({price_str})")
            st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
            c1, c2 = st.columns(2); c1.metric("Market Edge", f"{res['Edge']:.1f}"); c2.metric("Pinnacle", to_american(res['PIN']) if res['Market']=='h2h' else res['PIN'])
            
            ca, cb = st.columns(2)
            if ca.button("📊 Analyst Opinions", key=f"t1_opin_{i}", disabled=locked, use_container_width=True):
                st.session_state.lock_until = time.time() + 30
                with st.spinner("Consulting sources..."):
                    st.session_state[f"t1_res_{i}_opin"] = get_analyst_opinions(res['Matchup'], res['Sport'], res['Target'], price_str, gemini_key)
                st.rerun()

            if cb.button("🧮 Math Breakdown", key=f"t1_math_{i}", disabled=locked, use_container_width=True):
                st.session_state.lock_until = time.time() + 30
                with st.spinner("Analyzing personnel..."):
                    st.session_state[f"t1_res_{i}_math"] = get_math_breakdown(res['Matchup'], res['Sport'], res['Target'], price_str, gemini_key)
                st.rerun()

            if f"t1_res_{i}_opin" in st.session_state: st.info(st.session_state[f"t1_res_{i}_opin"])
            if f"t1_res_{i}_math" in st.session_state: st.success(st.session_state[f"t1_res_{i}_math"])
            
            if st.button(f"✅ LOG BET", key=f"t1l_{res['Matchup']}_{i}", type="primary", use_container_width=True):
                log_to_github_ledger({"Date": datetime.now().strftime("%m/%d/%Y"), "Team": res['Target'], "Sport": res['Sport'], "Line": price_str, "Edge": f"{res['Edge']:.1f}", "Units": 1.0, "Result": "Pending"})
                st.toast("Logged!"); st.rerun()

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
                    all_intel.append({"Matchup": f"{game['away_team']} @ {game['home_team']}", "Target": game['away_team'], "Sport": name, "Start": comm_c.strftime('%I:%M %p')})
            except: continue
        st.session_state.intel_results = all_intel; st.rerun()

    for i, game in enumerate(st.session_state.intel_results):
        with st.container(border=True):
            st.subheader(game['Matchup']); st.caption(f"🕒 {game['Start']} | {game['Sport']}")
            qa, qb = st.columns(2)
            
            if qa.button("📊 Analyst Opinions", key=f"t2_opin_{i}", disabled=locked, use_container_width=True):
                st.session_state.lock_until = time.time() + 30
                with st.spinner("Analyzing market..."):
                    st.session_state[f"t2_res_{i}_opin"] = get_analyst_opinions(game['Matchup'], game['Sport'], game['Target'], "N/A", gemini_key)
                st.rerun()
            
            if qb.button("🧮 Math Breakdown", key=f"t2_math_{i}", disabled=locked, use_container_width=True):
                st.session_state.lock_until = time.time() + 30
                with st.spinner("Scouting personnel..."):
                    st.session_state[f"t2_res_{i}_math"] = get_math_breakdown(game['Matchup'], game['Sport'], game['Target'], "N/A", gemini_key)
                st.rerun()

            # DISPLAY LOGIC MOVED INSIDE THE LOOP
            if f"t2_res_{i}_opin" in st.session_state: st.info(st.session_state[f"t2_res_{i}_opin"])
            if f"t2_res_{i}_math" in st.session_state: st.success(st.session_state[f"t2_res_{i}_math"])

with tab3:
    st.header("📈 Performance Ledger")
    c1, c2 = st.columns(2)
    if c1.button("🔄 AUTO-SETTLE PENDING", use_container_width=True, type="primary"):
        if auto_grade_ledger(): st.rerun()
    if c2.button("🔄 REFRESH GITHUB", use_container_width=True):
        if sync_ledger(): st.rerun()

    if st.session_state.get('bet_history'):
        df = pd.DataFrame(st.session_state.bet_history)
        df.index = range(1, len(df) + 1)
        with st.expander("📝 MANUAL GRADE (Hard Commit)", expanded=False):
            edited = st.data_editor(df.iloc[::-1], use_container_width=True)
            if st.button("💾 PUSH TO GITHUB"):
                st.session_state.bet_history = edited.iloc[::-1].to_dict('records')
                if log_to_github_ledger(overwrite_df=edited.iloc[::-1]): 
                    st.success("Updated!"); st.rerun()
        st.dataframe(df.iloc[::-1], use_container_width=True)
    else:
        st.warning("No bet history found. Hit 'Refresh GitHub' to pull your data.")
