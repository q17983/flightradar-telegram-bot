#!/usr/bin/env python3
"""
Extract all aircraft types containing 'F' for freighter classification review
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://prcnxrkyjnpljoqiazkp.supabase.co"
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Clean up the ANON key (remove quotes if present)
if SUPABASE_ANON_KEY and SUPABASE_ANON_KEY.startswith('"') and SUPABASE_ANON_KEY.endswith('"'):
    SUPABASE_ANON_KEY = SUPABASE_ANON_KEY[1:-1]

def extract_f_aircraft_types():
    """Call the Supabase function to extract all aircraft types containing 'F'"""
    
    url = f"{SUPABASE_URL}/functions/v1/extract-f-aircraft-types"
    headers = {
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        print("🔍 Extracting all aircraft types containing 'F'...")
        response = requests.post(url, headers=headers, json={}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ SUCCESS: {data['message']}")
            print(f"📊 Summary:")
            print(f"   - Total aircraft types/details: {data['summary']['total_types']}")
            print(f"   - Currently classified as Freighter: {data['summary']['currently_classified_as_freighter']}")
            print(f"   - Currently classified as Passenger: {data['summary']['currently_classified_as_passenger']}")
            
            print(f"\n🚛 CURRENTLY CLASSIFIED AS FREIGHTER ({len(data['freighter_classified'])}):")
            print("=" * 100)
            for item in data['freighter_classified']:
                print(f"{item['aircraft_type']:8} | {item['aircraft_details']:40} | Count: {item['aircraft_count']:4} | Ops: {item['operator_count']:3} | Regs: {item['registration_count']:3}")
            
            print(f"\n✈️  CURRENTLY CLASSIFIED AS PASSENGER ({len(data['passenger_classified'])}):")
            print("=" * 100)
            for item in data['passenger_classified']:
                print(f"{item['aircraft_type']:8} | {item['aircraft_details']:40} | Count: {item['aircraft_count']:4} | Ops: {item['operator_count']:3} | Regs: {item['registration_count']:3}")
            
            # Save to file for detailed review
            with open('f_aircraft_types_analysis.json', 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n💾 Detailed data saved to: f_aircraft_types_analysis.json")
            
            return data
            
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")
        return None

if __name__ == "__main__":
    if not SUPABASE_ANON_KEY:
        print("❌ Error: SUPABASE_ANON_KEY not found in environment variables")
        exit(1)
    
    extract_f_aircraft_types()
