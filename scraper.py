import requests
import pandas as pd
import os
from datetime import datetime

# 1. Configuration
API_KEY = os.getenv('ODDS_API_KEY')
DISCORD_URL = os.getenv('DISCORD_WEBHOOK_URL') # Add this to GitHub Secrets!
REGIONS = 'us'
MARKETS = 'spreads' 
LEAGUES = ['basketball_nba', 'basketball_ncaab', 'americanfootball_nfl', 'icehockey_nhl']

# Thresholds for the Sentinel Alert
SMASH_SPREAD = 1.5  # 1.5 point gap
SMASH_ML = 25       # 25 cent moneyline gap

def send_discord_alert(msg):
    if DISCORD_URL:
        requests.post(DISCORD_URL, json={"content": msg})

def get_opening_lines():
    all_data = []
    alerts = []
    recorded_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    for league in LEAGUES:
        # NHL uses h2h (moneyline), others use spreads
        mkt_type = 'h2h' if 'nhl' in league else 'spreads'
        url = f'https://api.the-odds-api.com/v4/sports/{league}/odds/'
        params = {
            'apiKey': API_KEY,
            'regions': REGIONS,
            'markets': mkt_type,
            'bookmakers': 'fanduel,pinnacle',
        }
        
        try:
            response = requests.get(url, params=params).json()
            if isinstance(response, list):
                for game in response:
                    # Logic to compare FD and PIN during the scrape
                    fd_val, pin_val = None, None
                    away_t, home_t = game['away_team'], game['home_team']
                    
                    for b in game.get('bookmakers', []):
                        outcomes = b.get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            val = o.get('point') if mkt_type == 'spreads' else o.get('price')
                            if b['key'] == 'fanduel': fd_val = val
                            if b['key'] == 'pinnacle': pin_val = val
                            
                            # Log for the CSV
                            if b['key'] == 'fanduel':
                                all_data.append({
                                    'Team': o['name'],
                                    'Opening_Line': val,
                                    'Recorded_At': recorded_at,
                                    'Sport': league
                                })
                    
                    # SENTINEL CHECK: If we have both prices, check for a SMASH
                    if fd_val and pin_val:
                        edge = abs(fd_val - pin_val)
                        if mkt_type == 'h2h': edge *= 100 # Convert to cents
                        
                        threshold = SMASH_ML if mkt_type == 'h2h' else SMASH_SPREAD
                        if edge >= threshold:
                            alerts.append(f"💥 **4AM SMASH ALERT**: {away_t}@{home_t} | Edge: {edge:.1f} | FD: {fd_val} vs PIN: {pin_val}")

        except Exception as e:
            print(f"Error fetching {league}: {e}")

    # Fire off alerts to Discord
    if alerts:
        send_discord_alert("\n".join(alerts))
    
    return pd.DataFrame(all_data)

if __name__ == "__main__":
    new_df = get_opening_lines()
    if not new_df.empty:
        new_df.to_csv('opening_lines.csv', index=False)
        print("Scrape and Sentinel Audit Complete.")
