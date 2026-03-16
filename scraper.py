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
                    all_results.
