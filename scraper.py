import os
import requests
import pandas as pd
from datetime import datetime, timezone

# 1. Configuration - Securely grab the API key from GitHub Secrets
API_KEY = os.environ.get("ODDS_API_KEY")
FILE_NAME = "opening_lines.csv"
LEAGUES = {"NBA": "basketball_nba", "NHL": "icehockey_nhl"}

def fetch_opening_lines():
    """Reaches out to the Odds API to grab current market spreads."""
    all_results = []
    for name, slug in LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{slug}/odds/"
        params = {
            "apiKey": API_KEY, 
            "regions": "us,eu", 
            "markets": "spreads", 
            "bookmakers": "fanduel,pinnacle"
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            for game in data:
                away_team = game.get('away_team')
                fd_away, pin_away = None, None
                
                for book in game.get('bookmakers', []):
                    markets = book.get('markets', [])
                    if not markets: continue
                    
                    outcomes = markets[0].get('outcomes', [])
                    for outcome in outcomes:
                        # We track the 'Away' line as our baseline for comparison
                        if outcome.get('name') == away_team:
                            if book['key'] == 'fanduel':
                                fd_away = outcome.get('point')
                            elif book['key'] == 'pinnacle':
                                pin_away = outcome.get('point')
                
                if fd_away is not None and pin_away is not None:
                    all_results.append({
                        "Matchup": f"{away_team} @ {game.get('home_team')}",
                        "Sport": name,
                        "Open_FanDuel": fd_away,
                        "Open_Pinnacle": pin_away,
                        "Start_Time": game.get('commence_time'), # Keep UTC for the janitor
                        "Recorded_At": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                    })
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            
    return pd.DataFrame(all_results)

def main():
    # Fetch fresh data
    new_data = fetch_opening_lines()
    if new_data.empty:
        print("No data found. Skipping update.")
        return

    # Load existing data if it exists
    if os.path.exists(FILE_NAME):
        existing_df = pd.read_csv(FILE_NAME)
        # Combine new scans with old records
        df = pd.concat([existing_df, new_data])
    else:
        df = new_data

    # --- THE JANITOR: SELF-CLEANING LOGIC ---
    # Delete any games where the start time is in the past
    current_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    df = df[df['Start_Time'] > current_utc]

    # Remove duplicates: If a game is already in the list, keep the earliest (Opening) line
    df = df.drop_duplicates(subset=['Matchup'], keep='first')

    # Save the cleaned, updated list back to GitHub
    df.to_csv(FILE_NAME, index=False)
    print(f"Successfully updated {FILE_NAME}. Total active games tracked: {len(df)}")

if __name__ == "__main__":
    main()
