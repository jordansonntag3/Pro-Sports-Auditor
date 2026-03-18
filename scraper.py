import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# 1. Configuration
API_KEY = os.environ.get("ODDS_API_KEY")
FILE_NAME = "opening_lines.csv"
LEAGUES = {
    "NBA": "basketball_nba", 
    "NHL": "icehockey_nhl", 
    "NCAA B": "basketball_ncaab"
}

def fetch_current_snapshot():
    all_results = []
    now_utc = datetime.now(timezone.utc)
    # Scan for games starting in the next 48 hours
    future_utc = now_utc + timedelta(hours=48)
    
    time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    time_to = future_utc.strftime('%Y-%m-%dT%H:%M:%SZ')

    for name, slug in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{slug}/odds/"
        params = {
            "apiKey": API_KEY, 
            "regions": "us,eu", 
            "markets": "spreads", 
            "bookmakers": "fanduel,pinnacle", 
            "commenceTimeFrom": time_from, 
            "commenceTimeTo": time_to
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            for game in data:
                away_team = game.get('away_team')
                home_team = game.get('home_team')
                fd_away, pin_away = None, None
                
                for book in game.get('bookmakers', []):
                    markets = book.get('markets', [])
                    if not markets: continue
                    outcomes = markets[0].get('outcomes', [])
                    for o in outcomes:
                        if o.get('name') == away_team:
                            if book['key'] == 'fanduel': fd_away = o.get('point')
                            if book['key'] == 'pinnacle': pin_away = o.get('point')
                
                if fd_away is not None and pin_away is not None:
                    # Matchup-Proofing: Alphabetical sort so names always match
                    teams = sorted([away_team, home_team])
                    all_results.append({
                        "Matchup": f"{teams[0]} vs {teams[1]}",
                        "Sport": name,
                        "Open_FanDuel": fd_away,
                        "Open_Pinnacle": pin_away,
                        "Start_Time": game.get('commence_time'),
                        "Recorded_At": now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')
                    })
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            
    return pd.DataFrame(all_results)

def main():
    if not API_KEY:
        print("Error: ODDS_API_KEY not found in environment.")
        return

    new_data = fetch_current_snapshot()
    if new_data.empty: 
        print("No new data found.")
        return

    # LEDGER LOGIC: Append new scan to history
    if os.path.exists(FILE_NAME):
        try:
            existing_df = pd.read_csv(FILE_NAME)
            df = pd.concat([existing_df, new_data])
        except:
            df = new_data
    else:
        df = new_data

    # THE JANITOR: Remove games that started > 6 hours ago
    current_utc = datetime.now(timezone.utc)
    cutoff = current_utc - timedelta(hours=6)
    
    df['Start_Time_DT'] = pd.to_datetime(df['Start_Time'])
    df = df[df['Start_Time_DT'] > cutoff]
    df = df.drop(columns=['Start_Time_DT'])

    df.to_csv(FILE_NAME, index=False)
    print(f"Success! Ledger updated. File now contains {len(df)} rows.")

if __name__ == "__main__":
    main()
