import os
import requests
import pandas as pd
from datetime import datetime, timezone

# 1. Configuration
API_KEY = os.environ.get("ODDS_API_KEY")
FILE_NAME = "opening_lines.csv"
LEAGUES = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NFL": "americanfootball_nfl"}

def fetch_opening_lines():
    all_results = []
    for name, slug in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{slug}/odds/"
        params = {"apiKey": API_KEY, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle"}
        
        try:
            r = requests.get(url, params=params)
            data = r.json()
            for game in data:
                fd_away, pin_away = None, None
                for book in game.get('bookmakers', []):
                    markets = book.get('markets', [])
                    if not markets: continue
                    outcomes = markets[0].get('outcomes', [])
                    for o in outcomes:
                        if o.get('name') == game.get('away_team'):
                            if book['key'] == 'fanduel': fd_away = o.get('point')
                            if book['key'] == 'pinnacle': pin_away = o.get('point')
                
                if fd_away is not None and pin_away is not None:
                    all_results.append({
                        "Matchup": f"{game.get('away_team')} @ {game.get('home_team')}",
                        "Sport": name,
                        "Open_FanDuel": fd_away,
                        "Open_Pinnacle": pin_away,
                        "Start_Time": game.get('commence_time'),
                        "Recorded_At": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                    })
        except: pass
    return pd.DataFrame(all_results)

def main():
    df = fetch_opening_lines()
    
    # If we found real games, the "Test" row is no longer needed
    if df.empty:
        df = pd.DataFrame([{"Matchup": "Test Connection", "Sport": "TEST", "Open_FanDuel": 0, "Open_Pinnacle": 0, "Start_Time": "2099-01-01T00:00:00Z", "Recorded_At": "NOW"}])

    # Save the fresh opening lines
    df.to_csv(FILE_NAME, index=False)
    print(f"Success! {len(df)} rows saved.")

if __name__ == "__main__":
    main()
