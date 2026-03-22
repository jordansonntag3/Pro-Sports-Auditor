import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
from io import StringIO

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. Sidebar & System Controls
with st.sidebar:
    st.header("⚙️ Command Center")
    grounding_mode = st.radio("Grounding Mode:", ["Live Search", "Session Cache Only", "Math Only"], index=1)
    
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("System Cleared. Re-syncing...")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    st.markdown("**Vibe Guide:** 🚀 Velocity | ⚓ Stable | 🌊 Drift")

st.title("💥 BANG! Button")

# 3. Session State Initialization
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "sent_alerts" not in st.session_state: st.session_state.sent_alerts = set()
if "bet_history" not in st.session_state: st.session_state.bet_history = []

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

# Secrets
api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]
discord_live_url = st.secrets.get("DISCORD_LIVE_URL")
github_token = st.secrets.get("GITHUB_TOKEN")

# --- UTILITY: ODDS CONVERTER ---
def to_american(decimal):
    try:
        val = float(decimal)
        if val >= 2.0: return f"+{int((val - 1) * 100)}"
        else: return f"{int(-100 / (val - 1))}"
    except: return str(decimal)

# --- UTILITY: PERMANENT GITHUB LEDGER ---
def log_to_github_ledger(new_data):
    repo = "jordansonntag3/Pro-Sports-Auditor"
    path = "bet_ledger.csv"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_data = r.json(); sha = content_data['sha']
        df = pd.read_csv(StringIO(base64.b64decode(content_data['content']).decode('utf-8')))
    else:
        sha = None
        df = pd.DataFrame(columns=["Date", "Team", "Sport", "Line", "Edge", "Vibe", "Units"])

    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    new_csv = df.to_csv(index=False)
    encoded_content = base64.b64encode(new_csv.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Log Play: {new_data['Team']}", "content": encoded_content, "branch": "main"}
    if sha: payload["sha"] = sha
    return requests.put(url, headers=headers, json=payload).status_code in [200, 201]

def delete_last_from_github_ledger():
    repo = "jordansonntag3/Pro-Sports-Auditor"
    path = "bet_ledger.csv"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_data = r.json(); sha = content_data['sha']
        df = pd.read_csv(StringIO(base64.b64decode(content_data['content']).decode('utf-8')))
        if not df.empty:
            df = df.drop(df.index[-1])
            encoded_content = base64.b64encode(df.to_csv(index=False).encode('utf-8')).decode('utf-8')
            payload = {"message": "Delete Last Entry", "content": encoded_content, "sha": sha, "branch": "main"}
            return requests.put(url, headers=headers, json=payload).status_code in [200, 201]
    return False

# --- SYNC LEDGER ON STARTUP ---
if not st.session_state.bet_history:
    LEDGER_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/bet_ledger.csv"
    try:
        master_df = pd.read_csv(f"{LEDGER_URL}?v={time.time()}")
        st.session_state.bet_history = master_df.to_dict('records')
    except: pass

def send_discord_live(messages):
    if discord_live_url and messages:
        requests.post(discord_live_url, json={"content": "📢 **LIVE VALUE FOUND:**\n" + "\n".join(messages)})

# --- MASTER INTELLIGENCE (Wait Category Logic) ---
def get_master_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    edge_label = "cents" if sport == "NHL" else "points"
    cached_news = st.session_state.search_ledger.get(matchup)
    should_search = (grounding_mode == "Live Search") or (grounding_mode == "Session Cache Only" and not cached_news)
    
    verdict_rules = f"1. Key player on TARGET ({target_team}) is 'Q' -> **🟡 WAIT**. 2. Key player on OPPOSING is 'Q' -> NO WAIT. 3. Standard: **🛑 PASS**, **⚪ NEUTRAL**, **🟢 PLAY**, **⚡ SMASH**."
    prompt = f"ROLE: Strategic Betting Analyst. GAME: {matchup} ({sport}) | TARGET: {target_team} {fd_p} (vs Pin {pin_p}). MATH EDGE: {edge} {edge_label}. FORMAT: {verdict_rules}. End with bold verdict."
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
    if should_search: 
        payload["tools"] = [{"google_search": {}}]; time.sleep(1.5)
    try:
        response = requests.post(url, json=payload, timeout=30).json()
        candidate = response.get('candidates', [{}])[0]
        if 'groundingMetadata' in candidate and not cached_news:
            st.session_state.search_ledger[matchup] = str(candidate['groundingMetadata'].get('searchEntryPoint', ''))
        return candidate.get('content', {}).get('parts', [{}])[0].get('text', '🔍 No Data.').strip()
    except: return "⚠️ API ERROR"

# --- TABS ---
tab1, tab2 = st.tabs(["🚀 Strategic Scanner", "📊 Performance Ledger"])

with tab1:
    with st.expander("🛠️ Settings", expanded=True):
        col1, col2 = st.columns([1, 1.2])
        with col1:
            horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
            min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 1.0, 0.5, 0.5)
            min_ml_edge = st.slider("Min NHL ML Edge (cents):", 10, 20, 10, 5)
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
        new_res = []; discord_messages = []; now_utc = datetime.utcnow(); today_str = datetime.now().strftime("%Y-%m-%d")
        logged_today = [str(b['Team']) for b in st.session_state.bet_history if today_str in str(b['Date'])]
        
        for name in selected_leagues:
            s_key, mkt = l_map[name]
            url = f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/"
            try:
                data = requests.get(url, params={"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}).json()
                for game in data:
                    # Filter already started games
                    if pd.to_datetime(game['commence_time']).replace(tzinfo=None) < now_utc: continue
                    
                    away_t, home_t = game['away_team'], game['home_team']
                    fd_a, pin_a, fd_h, pin_h = None, None, None, None
                    for b in game.get('bookmakers', []):
                        mkts = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in mkts:
                            v = o.get('point') if mkt == 'spreads' else o.get('price')
                            if o['name'] == away_t:
                                if b['key'] == 'fanduel': fd_a = v
                                elif b['key'] == 'pinnacle': pin_a = v
                            elif o['name'] == home_t:
                                if b['key'] == 'fanduel': fd_h = v
                                elif b['key'] == 'pinnacle': pin_h = v

                    if all(v is not None for v in [fd_a, pin_a, fd_h, pin_h]):
                        if mkt == 'h2h':
                            edge_a, edge_h = (fd_a - pin_a) * 100, (fd_h - pin_h) * 100
                            floor = min_ml_edge - 0.01
                        else:
                            edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h); floor = min_pt_edge - 0.01

                        if edge_a > edge_h and edge_a >= floor: t_team, edge, fd_p, pin_p = away_t, edge_a, fd_a, pin_a
                        elif edge_h >= floor: t_team, edge, fd_p, pin_p = home_t, edge_h, fd_h, pin_h
                        else: continue
                        
                        # ANTI-SPAM: Skip if already alerted this session or already in the Ledger for today
                        alert_fingerprint = f"{t_team}_{today_str}"
                        is_duplicate = (alert_fingerprint in st.session_state.sent_alerts) or (t_team in logged_today)
                        
                        if edge >= (20 if mkt=='h2h' else 1.0) and not is_duplicate:
                            line_str = to_american(fd_p) if mkt == 'h2h' else f"{'+' if fd_p > 0 else ''}{fd_p}"
                            discord_messages.append(f"- **{t_team}** {line_str} | Edge: {edge:.1f} ({name})")
                            st.session_state.sent_alerts.add(alert_fingerprint)

                        new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": fd_p, "PIN": pin_p, "Edge": edge, "Priority": (edge if mkt == 'h2h' else edge * 15), "Matchup": f"{away_t} @ {home_t}", "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')})
            except: continue
        st.session_state.scan_results = sorted(new_res, key=lambda x: x['Priority'], reverse=True)
        if discord_messages: send_discord_live(discord_messages)

    if st.session_state.scan_results:
        for res in st.session_state.scan_results:
            with st.container(border=True):
                display_price = to_american(res['FD']) if res['Market'] == 'h2h' else f"{'+' if res['FD'] > 0 else ''}{res['FD']}"
                st.subheader(f"{res['Target']} ({display_price})")
                st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
                c1, c2 = st.columns(2)
                c1.metric("Market Edge", f"{res['Edge']:.1f} {'pts' if res['Market']=='spreads' else 'cents'}")
                if res['Market'] == 'h2h': c2.metric("Pinnacle Price", to_american(res['PIN']))
                ca, cb, cc, cd = st.columns([1, 1, 0.4, 0.5]); q_k, d_k = f"q_{res['Matchup']}", f"d_{res['Matchup']}"
                if ca.button(f"⚡ Quick Intel", key=f"btn_{q_k}", use_container_width=True):
                    st.session_state[q_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="quick")
                if cb.button(f"🔎 Detailed Intel", key=f"btn_{d_k}", use_container_width=True):
                    st.session_state[d_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res['Edge'], gemini_key, mode="detailed")
                units = cc.number_input("Units", 0.1, 10.0, 1.0, 0.5, key=f"u_{res['Matchup']}")
                if cd.button(f"✅ LOG PLAY", key=f"log_{res['Matchup']}", use_container_width=True, type="primary"):
                    with st.spinner("Saving..."):
                        bet_data = {"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Team": res['Target'], "Sport": res['Sport'], "Line": display_price, "Edge": f"{res['Edge']:.1f}", "Units": units}
                        if log_to_github_ledger(bet_data):
                            st.session_state.bet_history.append(bet_data); st.toast("✅ Saved!"); time.sleep(0.5); st.rerun()
                if q_k in st.session_state: st.info(st.session_state[q_k])
                if d_k in st.session_state: st.success(st.session_state[d_k])

with tab2:
    st.header("📈 Performance Ledger")
    if st.button("🗑️ DELETE LAST", use_container_width=True):
        if delete_last_from_github_ledger():
            st.toast("Deleted."); st.session_state.bet_history = []; time.sleep(1); st.rerun()
    if st.session_state.bet_history:
        display_df = pd.DataFrame(st.session_state.bet_history).iloc[::-1].reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)
