import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from io import StringIO

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="💥", layout="wide")

# 2. Sidebar & System Controls
with st.sidebar:
    st.header("⚙️ Command Center")
    grounding_mode = st.radio("Grounding Mode:", ["Live Search", "Session Cache Only", "Math Only"], index=1)
    if st.button("🔄 FULL SYSTEM RESET", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.markdown("**Vibe Guide:** 🚀 Velocity | ⚓ Stable | 🌊 Drift")

st.title("💥 BANG! Button")

# 3. Session State Initialization
if "search_ledger" not in st.session_state: st.session_state.search_ledger = {}
if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "bet_history" not in st.session_state: st.session_state.bet_history = []

leagues_list = ["NBA", "NHL", "NCAA B", "NFL", "NCAA F"]
for league in leagues_list:
    if f"active_{league}" not in st.session_state: st.session_state[f"active_{league}"] = True

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- MASTER INTELLIGENCE ---
def get_master_intel(matchup, sport, market_type, target_team, fd_p, pin_p, edge, _key, mode="detailed"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={_key}"
    edge_label = "cents" if sport == "NHL" else "points"
    cached_news = st.session_state.search_ledger.get(matchup)
    should_search = (grounding_mode == "Live Search") or (grounding_mode == "Session Cache Only" and not cached_news)

    prompt = f"""
    SYSTEM ROLE: Strategic Betting Analyst.
    GAME: {matchup} ({sport}) | TARGET: {target_team} {fd_p} (vs Pin {pin_p})
    MATH EDGE: {edge} {edge_label}
    INSTRUCTIONS: 1. Identify goalie status (NHL) or fatigue (NBA). 2. Check if the line movement has already priced this in. 3. Reach a Verdict.
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]}
    if should_search: payload["tools"] = [{"google_search": {}}]; time.sleep(1.5)

    try:
        response = requests.post(url, json=payload, timeout=30).json()
        candidate = response.get('candidates', [{}])[0]
        grounding = candidate.get('groundingMetadata', {})
        if grounding and not cached_news:
            st.session_state.search_ledger[matchup] = str(grounding.get('searchEntryPoint', ''))
        return candidate.get('content', {}).get('parts', [{}])[0].get('text', '🔍 No Data.').strip()
    except: return "⚠️ API ERROR"

# --- TABS: SCANNER VS LEDGER ---
tab1, tab2 = st.tabs(["🚀 Strategic Scanner", "📊 Performance Ledger"])

with tab1:
    # --- AUDIT SETTINGS ---
    with st.expander("🛠️ Audit & Display Settings", expanded=True):
        col_set1, col_set2 = st.columns([1, 1.2])
        with col_set1:
            horizon = st.radio("Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
            min_pt_edge = st.slider("Min Spread Edge (pts):", 0.5, 1.0, 0.5, 0.5)
            min_ml_edge = st.slider("Min NHL ML Edge (cents):", 10, 20, 10, 5)
        with col_set2:
            st.write("**League Toggles:**")
            c1, c2, c3 = st.columns(3)
            btn_cols = [c1, c2, c3, c1, c2]
            selected_leagues = []
            l_map = {"NBA": ("basketball_nba", "spreads"), "NHL": ("icehockey_nhl", "h2h"), "NCAA B": ("basketball_ncaab", "spreads"), "NFL": ("americanfootball_nfl", "spreads"), "NCAA F": ("americanfootball_ncaaf", "spreads")}
            for i, league in enumerate(leagues_list):
                active = st.session_state[f"active_{league}"]
                if btn_cols[i].button(f"{'✅' if active else '⬜'} {league}", key=f"t_{league}", use_container_width=True):
                    st.session_state[f"active_{league}"] = not active
                    st.rerun()
                if st.session_state[f"active_{league}"]: selected_leagues.append(league)

    # --- SCANNING ENGINE ---
    if st.button("🚀 RUN STRATEGIC SCAN", use_container_width=True):
        new_res = []
        now_utc = datetime.utcnow()
        # Opening Line Data
        RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
        try: op_df = pd.read_csv(f"{RAW_URL}?v={time.time()}")
        except: op_df = pd.DataFrame()

        for name in selected_leagues:
            s_key, mkt = l_map[name]
            url = f"https://api.the-odds-api.com/v4/sports/{s_key}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "markets": mkt, "bookmakers": "fanduel,pinnacle"}
            try:
                data = requests.get(url, params=params).json()
                if isinstance(data, list):
                    for game in data:
                        away_t, home_t = game.get('away_team'), game.get('home_team')
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
                                edge_a, edge_h = (fd_a - pin_a), (fd_h - pin_h)
                                floor = min_pt_edge - 0.01

                            if edge_a > edge_h and edge_a >= floor:
                                t_team, edge, fd_p, pin_p = away_t, edge_a, fd_a, pin_a
                            elif edge_h >= floor:
                                t_team, edge, fd_p, pin_p = home_t, edge_h, fd_h, pin_h
                            else: continue
                            
                            vibe = "🌊"
                            if not op_df.empty:
                                try:
                                    opening_row = op_df[op_df['Team'] == t_team].iloc[-1]
                                    mov = abs(fd_p - opening_row['Opening_Line'])
                                    if mov > 1.0: vibe = "🚀"
                                    elif mov < 0.5: vibe = "⚓"
                                except: pass

                            new_res.append({"Target": t_team, "Sport": name, "Market": mkt, "FD": fd_p, "PIN": pin_p, "Edge": edge, "Vibe": vibe, "Matchup": f"{away_t} @ {home_t}", "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p')})
            except: continue
        st.session_state.scan_results = new_res

    # --- DISPLAY ENGINE ---
    if st.session_state.scan_results:
        for res in st.session_state.scan_results:
            with st.container(border=True):
                v = res.get('Vibe', '🌊')
                h = f"{v} {res['Target']} ({res['FD']})"
                st.subheader(h)
                st.caption(f"🕒 {res['Start']} | {res['Matchup']} ({res['Sport']})")
                
                c1, c2 = st.columns(2)
                c1.metric("Market Edge", f"{res.get('Edge', 0):.1f} {'pts' if res['Market']=='spreads' else 'cents'}")
                if res['Market'] == 'h2h': c2.metric("Pinnacle Price", f"{res['PIN']}")
                
                ca, cb, cc = st.columns([1, 1, 0.5]) # CC is the new Log Button Column
                q_k, d_k = f"q_{res['Matchup']}", f"d_{res['Matchup']}"
                
                if ca.button(f"⚡ Quick Intel", key=f"btn_{q_k}", use_container_width=True):
                    st.session_state[q_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res.get('Edge', 0), gemini_key, mode="quick")
                if cb.button(f"🔎 Detailed Intel", key=f"btn_{d_k}", use_container_width=True):
                    st.session_state[d_k] = get_master_intel(res['Matchup'], res['Sport'], res['Market'], res['Target'], res['FD'], res['PIN'], res.get('Edge', 0), gemini_key, mode="detailed")
                if cc.button(f"✅ LOG", key=f"log_{res['Matchup']}", use_container_width=True, type="primary"):
                    st.session_state.bet_history.append({"Date": datetime.now().strftime("%m/%d"), "Team": res['Target'], "Line": res['FD'], "Edge": f"{res['Edge']:.1f}", "Vibe": v})
                    st.toast(f"Logged {res['Target']} to Ledger!")

                if q_k in st.session_state: st.info(st.session_state[q_k])
                if d_k in st.session_state: st.success(st.session_state[d_k])

with tab2:
    st.header("📊 Performance Ledger")
    if st.session_state.bet_history:
        st.dataframe(pd.DataFrame(st.session_state.bet_history), use_container_width=True)
    else:
        st.info("No plays logged yet. Use the ✅ LOG button on the scanner to track your picks.")
