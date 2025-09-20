#!/usr/bin/env python3
"""
FlightRadar Cargo Charter Broker - Telegram Bot
Mobile access to flight data through Telegram chat interface.
"""

import os
import json
import logging
import asyncio
import requests
import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://prcnxrkyjnpljoqiazkp.supabase.co"
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Clean up the ANON key (remove quotes if present)
if SUPABASE_ANON_KEY and SUPABASE_ANON_KEY.startswith('"') and SUPABASE_ANON_KEY.endswith('"'):
    SUPABASE_ANON_KEY = SUPABASE_ANON_KEY[1:-1]

# Check required environment variables
if not TELEGRAM_BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file.")
    print("   1. Message @BotFather on Telegram")
    print("   2. Use /newbot command")
    print("   3. Add token to .env file: TELEGRAM_BOT_TOKEN=your_token")
    exit()

if not OPENAI_API_KEY:
    print("❌ Error: OPENAI_API_KEY not found in .env file.")
    exit()

if not SUPABASE_ANON_KEY:
    print("❌ Error: SUPABASE_ANON_KEY not found in .env file.")
    exit()

# Initialize OpenAI
try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing OpenAI: {e}")
    exit()

# Core Function mapping for Supabase Edge Functions (Primary 4 Functions)
FUNCTION_MAP = {
    "get_operators_by_destination": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-destination",
        "params": ["destination_code", "start_time", "end_time"],
        "description": "Function 1: Get operators flying TO a specific airport"
    },
    "get_operator_details": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-details",
        "params": ["search_query", "operator_selection"],
        "description": "Function 8: Search for operator details with fleet and route analysis"
    },
    "get_operators_by_multi_destinations": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-multi-destinations",
        "params": ["destination_codes", "start_time", "end_time"],
        "description": "Function 9: Find operators that serve multiple specified airports"
    },
    "get_operators_by_geographic_locations": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-geographic-locations",
        "params": ["first_location_type", "first_location_value", "second_location_type", "second_location_value", "start_time", "end_time"],
        "description": "Function 10: Find operators serving between countries/continents/airports"
    },
    "aircraft-to-destination-search": {
        "url": f"{SUPABASE_URL}/functions/v1/aircraft-to-destination-search",
        "params": ["mode", "aircraft_types", "destinations", "start_time", "end_time"],
        "description": "Function 12: Find operators with specific aircraft types to destinations"
    }
}

# Backup Functions (Functions 2-7) - Available but not actively promoted
BACKUP_FUNCTION_MAP = {
    "get_operator_frequency": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-frequency",
        "params": ["origin_code", "destination_code", "start_time", "end_time"],
        "description": "Function 5: Get frequency of operators flying a specific route"
    },
    "get_operators_by_origin": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-origin",
        "params": ["origin_code", "start_time", "end_time"],
        "description": "Function 2: Get operators flying FROM an origin"
    },
    "get_operator_route_summary": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-route-summary",
        "params": ["operator_name", "start_time", "end_time"],
        "description": "Function 3: Get route summary for a specific operator"
    },
    "get_route_details": {
        "url": f"{SUPABASE_URL}/functions/v1/get-route-details",
        "params": ["origin_code", "destination_code", "start_time", "end_time"],
        "description": "Function 4: Get detailed route information"
    }
}

async def analyze_query_with_openai(user_query: str, time_frame: dict = None) -> dict:
    """Use OpenAI to analyze user query and determine intent with universal location intelligence."""
    
    # Set default time frame if not provided
    if not time_frame:
        time_frame = {"start_time": "2024-04-01", "end_time": "2025-05-31"}
    
    prompt = f"""
You are a flight data assistant for a cargo charter broker with UNIVERSAL LOCATION INTELLIGENCE. Analyze this query and return the best function to call from the 4 CORE FUNCTIONS only.

CORE FUNCTIONS ONLY:
{json.dumps(FUNCTION_MAP, indent=2)}

User query: "{user_query}"

CRITICAL RULES:
- Use time range: start_time: "{time_frame['start_time']}", end_time: "{time_frame['end_time']}"
- Apply UNIVERSAL LOCATION INTELLIGENCE with typo correction
- Use EXACT airport codes (3-letter IATA) like LAX, JFK, LHR, DXB, SCL
- Use EXACT country names - DO NOT TRANSLATE: "Korea" stays "Korea", "Korean" refers to "Korea"

COUNTRY/CONTINENT MAPPING (DO NOT TRANSLATE):
- Korea/Korean → "South Korea" (NOT Japan/JPN, NOT "Korea")
- Taiwan/Taiwanese → "Taiwan" 
- China/Chinese → "China"
- Japan/Japanese → "Japan"  
- Thailand/Thai → "Thailand"
- Germany/German → "Germany"

UNIVERSAL LOCATION INTELLIGENCE (with typo correction):

CONTINENT CODES (Use these exact codes):
- Asia/asia/ASIA/Aisa/Asai → "AS"
- North America/north america/Noth America/Nroth America/North Amreica → "NA" 
- Europe/europe/EUROPE/Eruope/Europ → "EU"
- South America/south america/South Amreica → "SA"
- Africa/africa/AFRICA/Afirca → "AF"
- Oceania/oceania/OCEANIA → "OC"
- Antarctica/antarctica → "AN"

AIRPORT CODE RECOGNITION (case-insensitive):
- 3-letter codes: JFK/jfk/Jfk → "JFK", NRT/nrt → "NRT", TPE/tpe → "TPE"
- Always convert to uppercase for processing

CONJUNCTION HANDLING:
- "AND"/"and"/"&"/"+"/"," → multiple locations
- "NRT AND TPE" → ["NRT", "TPE"] (both airports)
- "Asia and JFK" → ["AS", "JFK"] (continent + airport)
- "NRT, TPE" → ["NRT", "TPE"] (comma-separated airports)

SMART FUNCTION SELECTION LOGIC:
1. "who flies to [AIRPORT]" → get_operators_by_destination
   Example: "who flies to LAX" → destination_code: "LAX"

2. "operator details [NAME]" or "show operator [NAME]" → get_operator_details
   Example: "operator details FedEx" → search_query: "FedEx"

3. "operators to both [X] and [Y]" → SMART ROUTING based on location types:
   - Both airports: get_operators_by_multi_destinations
     Example: "operators to both JFK and LAX" → destination_codes: ["JFK", "LAX"]
   - Mixed types: get_operators_by_geographic_locations  
     Example: "operators to both AS and JFK" → first_location_type: "continent", first_location_value: "AS", second_location_type: "airport", second_location_value: "JFK"

4. "[LOCATION] to [LOCATION] operators" or geographic queries → get_operators_by_geographic_locations
   Example: "Korea to Japan operators" → first_location_type: "country", first_location_value: "South Korea", second_location_type: "country", second_location_value: "Japan"
   Example: "China to SCL operators" → first_location_type: "country", first_location_value: "China", second_location_type: "airport", second_location_value: "SCL"
   Example: "Thailand to North America operators" → first_location_type: "country", first_location_value: "Thailand", second_location_type: "continent", second_location_value: "NA"

5. "[AIRCRAFT TYPES] to [DESTINATIONS]" or aircraft-destination queries → aircraft_to_destination_search
   Example: "A330 B777 to China" → aircraft_types: ["A330", "B777"], destinations: ["China"]
   Example: "B747 to JFK LAX" → aircraft_types: ["B747"], destinations: ["JFK", "LAX"]
   Example: "IL76 A330 to Europe Asia" → aircraft_types: ["IL76", "A330"], destinations: ["Europe", "Asia"]

Return JSON:
{{
    "function_name": "function_name",
    "parameters": {{"param": "value"}},
    "reasoning": "explanation"
}}
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a flight data assistant for a cargo charter broker. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Handle code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.rfind("```")
            response_text = response_text[start:end].strip()
        
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"Error with OpenAI: {e}")
        return None

def get_time_frame_options() -> dict:
    """Generate time frame options for user selection."""
    from datetime import datetime, timedelta
    
    end_date = datetime(2025, 5, 31)  # Database end date
    
    time_frames = {
        "1_month": {
            "start_time": "2025-04-01",
            "end_time": "2025-05-31", 
            "label": "📅 Last 1 Month (Apr-May 2025)",
            "description": "Most recent data"
        },
        "3_months": {
            "start_time": "2025-02-01", 
            "end_time": "2025-05-31",
            "label": "📅 Last 3 Months (Feb-May 2025)",
            "description": "Recent quarter"
        },
        "6_months": {
            "start_time": "2024-11-01",
            "end_time": "2025-05-31", 
            "label": "📅 Last 6 Months (Nov 2024-May 2025)",
            "description": "Half-year analysis"
        },
        "12_months": {
            "start_time": "2024-04-01",
            "end_time": "2025-05-31",
            "label": "📅 Full Period (Apr 2024-May 2025)", 
            "description": "Complete dataset (408 days)"
        }
    }
    
    return time_frames

def preprocess_locations(query: str) -> dict:
    """Universal location intelligence with typo correction."""
    
    # Typo correction mapping
    typo_corrections = {
        # Continents (case-insensitive)
        "noth america": "North America", "nroth america": "North America", "north amreica": "North America",
        "aisa": "Asia", "asai": "Asia", "eruope": "Europe", "europ": "Europe",
        "south amreica": "South America", "afirca": "Africa",
        # Countries  
        "germny": "Germany", "grmany": "Germany", "chna": "China", "jpan": "Japan",
        # Conjunctions
        "&": " and ", "+": " and ", ",": " and "
    }
    
    # Apply corrections (case-insensitive)
    corrected_query = query.lower()
    for typo, correction in typo_corrections.items():
        corrected_query = corrected_query.replace(typo, correction)
    
    # Remove common conjunctions to avoid detecting them as airports
    corrected_query = corrected_query.replace(" and ", " ").replace(" & ", " ").replace(" + ", " ")
    
    # Extract locations and classify them
    locations = []
    words = corrected_query.split()
    
    # Enhanced location detection with both codes and names
    continent_codes_map = {
        # Continent codes
        "as": ("AS", "continent"), "na": ("NA", "continent"), "eu": ("EU", "continent"),
        "sa": ("SA", "continent"), "af": ("AF", "continent"), "oc": ("OC", "continent"), "an": ("AN", "continent"),
        # Continent names
        "asia": ("AS", "continent"), "north america": ("NA", "continent"), "europe": ("EU", "continent"),
        "south america": ("SA", "continent"), "africa": ("AF", "continent"), "oceania": ("OC", "continent"), "antarctica": ("AN", "continent")
    }
    
    # Common country names (can be expanded)
    country_names = ["china", "japan", "germany", "thailand", "korea", "south korea", "taiwan"]
    
    # Words to exclude from airport detection
    excluded_words = ["and", "or", "to", "from", "the", "in", "on", "at", "by", "for", "with"]
    
    for word in words:
        word_lower = word.lower()
        word_upper = word.upper()
        
        # Skip excluded words
        if word_lower in excluded_words:
            continue
            
        # Check continent codes/names first
        if word_lower in continent_codes_map:
            code, type_name = continent_codes_map[word_lower]
            locations.append((code, type_name))
        # Check if it's a 3-letter airport code (but not excluded words)
        elif len(word_upper) == 3 and word_upper.isalpha() and word_lower not in continent_codes_map:
            locations.append((word_upper, "airport"))
        # Check if it's a country name
        elif word_lower in country_names:
            locations.append((word, "country"))
    
    result = {
        "original_query": query,
        "corrected_query": corrected_query,
        "locations": locations,
        "location_types": [loc[1] for loc in locations]
    }
    
    # Debug logging
    logger.info(f"🔍 Location preprocessing: '{query}' → {locations} → types: {result['location_types']}")
    
    return result

def check_function_compatibility(selected_function: str, natural_function: str, processed_query: dict) -> dict:
    """Check compatibility between selected function and natural query analysis."""
    
    location_types = processed_query.get("location_types", [])
    
    compatibility_rules = {
        "get_operators_by_destination": {
            "compatible": len(location_types) == 1 and "airport" in location_types,
            "reason": "Single airport destination queries"
        },
        "get_operator_details": {
            "compatible": len(location_types) == 0,  # No locations = operator name
            "reason": "Operator name queries without locations"
        },
        "get_operators_by_multi_destinations": {
            "compatible": len(location_types) >= 2 and all(t == "airport" for t in location_types),
            "reason": "Multiple airport destinations (same type)"
        },
        "get_operators_by_geographic_locations": {
            "compatible": len(location_types) >= 2,  # Any multiple locations
            "reason": "Geographic queries between locations"
        }
    }
    
    selected_rule = compatibility_rules.get(selected_function, {"compatible": False, "reason": "Unknown function"})
    
    result = {
        "is_compatible": selected_rule["compatible"],
        "selected_function": selected_function,
        "natural_function": natural_function,
        "reason": selected_rule["reason"],
        "location_types": location_types,
        "suggestion": "switch" if not selected_rule["compatible"] else "proceed"
    }
    
    # Debug logging
    logger.info(f"🔍 Compatibility check: {selected_function} vs {natural_function} | Types: {location_types} | Compatible: {result['is_compatible']} | Reason: {selected_rule['reason']}")
    
    return result

async def analyze_geographic_query_with_openai(query: str, time_frame: dict = None) -> dict:
    """Analyze user query as geographic query (Function 10) using OpenAI with universal location intelligence."""
    
    # Set default time frame if not provided
    if not time_frame:
        time_frame = {"start_time": "2024-04-01", "end_time": "2025-05-31"}
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a flight data analysis assistant with UNIVERSAL LOCATION INTELLIGENCE. Analyze user queries as GEOGRAPHIC QUERIES for Function 10.

FUNCTION: get_operators_by_geographic_locations
PURPOSE: Find operators serving between countries/continents/airports

IMPORTANT RULES:
- Use time range: start_time: "{time_frame['start_time']}", end_time: "{time_frame['end_time']}"
- Apply UNIVERSAL LOCATION INTELLIGENCE with typo correction
- Use EXACT airport codes (3-letter IATA) like LAX, JFK, LHR, DXB, SCL, TLV
- Use EXACT country names - DO NOT TRANSLATE: "Korea" stays "Korea", "Korean" refers to "Korea"

COUNTRY/CONTINENT MAPPING (DO NOT TRANSLATE):
- Korea/Korean → "South Korea" (NOT Japan/JPN, NOT "Korea")
- Taiwan/Taiwanese → "Taiwan" 
- China/Chinese → "China"
- Japan/Japanese → "Japan"  
- Thailand/Thai → "Thailand"
- Germany/German → "Germany"

UNIVERSAL LOCATION INTELLIGENCE (with typo correction):

CONTINENT CODES (Use these exact codes):
- Asia/asia/ASIA/Aisa/Asai → "AS"
- North America/north america/Noth America/Nroth America/North Amreica → "NA" 
- Europe/europe/EUROPE/Eruope/Europ → "EU"
- South America/south america/South Amreica → "SA"
- Africa/africa/AFRICA/Afirca → "AF"
- Oceania/oceania/OCEANIA → "OC"
- Antarctica/antarctica → "AN"

AIRPORT CODE RECOGNITION (case-insensitive):
- 3-letter codes: JFK/jfk/Jfk → "JFK", NRT/nrt → "NRT", TPE/tpe → "TPE"
- Always convert to uppercase for processing

CONJUNCTION HANDLING:
- "AND"/"and"/"&"/"+"/"," → multiple locations
- "Asia and JFK" → continent + airport (geographic query)
- "NRT and TPE" → airport + airport (should be multi-destinations, but force as geographic if preset)

GEOGRAPHIC QUERY PATTERNS:
- "China to TLV" → first_location_type: "country", first_location_value: "China", second_location_type: "airport", second_location_value: "TLV"
- "Korea to Japan operators" → first_location_type: "country", first_location_value: "South Korea", second_location_type: "country", second_location_value: "Japan"
- "Thailand to North America operators" → first_location_type: "country", first_location_value: "Thailand", second_location_type: "continent", second_location_value: "NA"
- "JFK to Asia carriers" → first_location_type: "airport", first_location_value: "JFK", second_location_type: "continent", second_location_value: "AS"

LOCATION TYPE DETECTION:
- 3-letter codes (LAX, JFK, TLV) → "airport"
- Country names (China, Japan, Thailand) → "country"  
- Continent names (Asia, North America, Europe) → "continent"

Return JSON:
{{
    "function_name": "get_operators_by_geographic_locations",
    "parameters": {{
        "first_location_type": "airport|country|continent",
        "first_location_value": "exact_value",
        "second_location_type": "airport|country|continent", 
        "second_location_value": "exact_value",
        "start_time": "2024-04-01",
        "end_time": "2025-05-31"
    }},
    "reasoning": "Brief explanation of geographic analysis"
}}"""
                },
                {
                    "role": "user", 
                    "content": query
                }
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"OpenAI geographic analysis response: {content}")
        
        # Handle code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.rfind("```")
            content = content[start:end].strip()
        
        # Parse JSON response
        analysis = json.loads(content)
        return analysis
        
    except Exception as e:
        logger.error(f"OpenAI geographic analysis failed: {e}")
        return None

async def handle_function_mismatch(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 selected_function: str, natural_analysis: dict, user_query: str) -> None:
    """Handle function mismatch with user guidance."""
    
    natural_function = natural_analysis.get('function_name', 'unknown')
    
    # Function name mapping for user-friendly display
    function_names = {
        "get_operators_by_destination": "🛬 Operators by Destination",
        "get_operator_details": "👤 Operator Details", 
        "get_operators_by_multi_destinations": "🗺️ Multi-Destination Operators",
        "get_operators_by_geographic_locations": "🌍 Geographic Operators",
        "aircraft_to_destination_search": "✈️ Aircraft-to-Destination Search"
    }
    
    selected_name = function_names.get(selected_function, selected_function)
    natural_name = function_names.get(natural_function, natural_function)
    
    message = f"""⚠️ **Function Mismatch Detected**

You have **{selected_name}** selected, but your query "{user_query}" looks like a **{natural_name}** search.

🤔 **What would you like to do?**"""

    # Create buttons for user choice
    keyboard = [
        [InlineKeyboardButton(f"🔄 Switch to {natural_name}", callback_data=f"switch_to_{natural_function}")],
        [InlineKeyboardButton(f"📝 Keep {selected_name}", callback_data=f"keep_{selected_function}")],
        [InlineKeyboardButton("🏠 Clear Selection (Auto-detect)", callback_data="clear_selection")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the analysis for later use
    context.user_data['pending_analysis'] = natural_analysis
    context.user_data['pending_query'] = user_query
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def call_supabase_function(function_name: str, parameters: dict) -> dict:
    """Call Supabase Edge Function."""
    
    # Log ALL function calls to see what's being called
    logger.info(f"🚀 CALLING FUNCTION: {function_name} with parameters: {parameters}")
    
    # TEMPORARY: Add debug info to help user see what function is being called
    print(f"DEBUG: About to call {function_name} with {parameters}")
    
    # Check both core and backup functions
    if function_name in FUNCTION_MAP:
        function_config = FUNCTION_MAP[function_name]
    elif function_name in BACKUP_FUNCTION_MAP:
        function_config = BACKUP_FUNCTION_MAP[function_name]
    else:
        return {"error": f"Unknown function: {function_name}"}
    
    # FORCE the correct date range regardless of what Gemini suggests
    parameters["start_time"] = "2024-04-01"
    parameters["end_time"] = "2025-05-31"
    
    # Debug: Log the credentials being used
    logger.info(f"Using SUPABASE_URL: {SUPABASE_URL}")
    logger.info(f"Using ANON_KEY (first 20 chars): {SUPABASE_ANON_KEY[:20] if SUPABASE_ANON_KEY else 'None'}...")
    
    # Special debug logging for Function 9
    if function_name == "get_operators_by_multi_destinations":
        logger.info(f"🔍 Function 9 Debug - Parameters received: {parameters}")
        logger.info(f"🔍 Function 9 Debug - Parameter types: {[(k, type(v)) for k, v in parameters.items()]}")
    
    url = function_config["url"]
    headers = {
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=parameters, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            # Add debug info to error message
            debug_info = f"[DEBUG: Called {function_name} with {list(parameters.keys())}]"
            return {"error": f"HTTP {response.status_code}: {response.text} {debug_info}"}
            
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

def format_enhanced_destination_results(results: dict) -> str:
    """Format enhanced Function 1 results with freighter/passenger breakdown."""
    dest = results.get("destination_code", "Unknown")
    summary = results.get("summary", {})
    
    message = f"🛬 **OPERATORS TO {dest}**\n"
    message += f"📅 *Period: {results.get('period_start')} to {results.get('period_end')}*\n"
    message += f"📊 *Total: {summary.get('total_flights', 0):,} flights ({summary.get('freighter_percentage', 0)}% freight, {summary.get('passenger_percentage', 0)}% passenger)*\n\n"
    
    # Freighter operators - Show ALL
    freighter_ops = results.get("freighter_operators", [])
    if freighter_ops:
        message += f"🚛 **FREIGHTER ({len(freighter_ops)} operators)**:\n"
        for i, op in enumerate(freighter_ops, 1):  # Show ALL freighter operators
            iata = op.get('operator_iata_code') or 'N/A'
            icao = op.get('operator_icao_code') or 'N/A'
            message += f"{i}. **{op['operator']}** ({iata}/{icao}): {op['total_frequency']:,} flights\n"
            # Show top aircraft types for this operator
            for aircraft in op['aircraft_types'][:2]:  # Show top 2 aircraft types
                message += f"   • {aircraft['aircraft_type']}: {aircraft['frequency']:,} flights\n"
        message += "\n"
    
    # Passenger operators - Show at least 25
    passenger_ops = results.get("passenger_operators", [])
    if passenger_ops:
        passenger_limit = max(25, len(passenger_ops))  # At least 25, or all if fewer
        message += f"✈️ **PASSENGER ({len(passenger_ops)} operators)**:\n"
        for i, op in enumerate(passenger_ops[:passenger_limit], 1):  # Show at least 25
            iata = op.get('operator_iata_code') or 'N/A'
            icao = op.get('operator_icao_code') or 'N/A'
            message += f"{i}. **{op['operator']}** ({iata}/{icao}): {op['total_frequency']:,} flights\n"
            # Show top aircraft types for this operator
            for aircraft in op['aircraft_types'][:2]:  # Show top 2 aircraft types
                message += f"   • {aircraft['aircraft_type']}: {aircraft['frequency']:,} flights\n"
        message += "\n"
        
        if len(passenger_ops) > passenger_limit:
            message += f"💡 *Note: Showing top {passenger_limit} passenger operators (out of {len(passenger_ops)} total)*\n"
    
    return message

def format_multi_destination_results(results: dict) -> list:
    """Format Function 9 multi-destination operator results. Returns list of messages for splitting."""
    
    if "error" in results:
        return [f"❌ Error: {results['error']}"]
    
    operators = results.get("operators", [])
    destination_codes = results.get("destination_codes", [])
    summary = results.get("summary", {})
    
    if not operators:
        dest_str = " and ".join(destination_codes)
        return [f"📭 No operators found serving both {dest_str}."]
    
    dest_str = " and ".join(destination_codes)
    
    # Create header message
    header = f"🛬 **OPERATORS SERVING BOTH {dest_str}**\n"
    header += f"📅 *Period: {results.get('time_range', {}).get('start_time')} to {results.get('time_range', {}).get('end_time')}*\n"
    header += f"📊 *Found: {summary.get('total_operators', 0)} operators*\n\n"
    
    messages = []
    current_message = header
    
    # Show ALL operators, splitting into multiple messages as needed
    for i, op in enumerate(operators, 1):
        operator_name = op.get('operator_name', 'Unknown')
        operator_iata = op.get('operator_iata') or 'N/A'
        total_flights = op.get('total_flights', 0)
        destinations_served = op.get('destinations_served', [])
        aircraft_types = op.get('aircraft_types', [])
        
        # Get enhanced data if available
        freighter_flights = op.get('freighter_flights', 0)
        passenger_flights = op.get('passenger_flights', 0)
        freighter_percentage = op.get('freighter_percentage', 0)
        passenger_percentage = op.get('passenger_percentage', 0)
        freighter_aircraft = op.get('freighter_aircraft', [])
        passenger_aircraft = op.get('passenger_aircraft', [])
        
        operator_text = f"{i}. **{operator_name}** ({operator_iata})\n"
        operator_text += f"   ✈️ Total: {total_flights:,} flights ({freighter_percentage}% freight, {passenger_percentage}% pax)\n"
        
        # Show freighter breakdown if available
        if freighter_flights > 0:
            operator_text += f"   🚛 Freight: {freighter_flights:,} flights"
            if freighter_aircraft:
                operator_text += f" ({', '.join(freighter_aircraft[:3])})\n"
            else:
                operator_text += "\n"
        
        # Show passenger breakdown if available  
        if passenger_flights > 0:
            operator_text += f"   ✈️ Passenger: {passenger_flights:,} flights"
            if passenger_aircraft:
                operator_text += f" ({', '.join(passenger_aircraft[:3])})\n"
            else:
                operator_text += "\n"
        
        operator_text += f"   🌍 Destinations: {', '.join(destinations_served[:5])}\n"  # Show up to 5 destinations
        operator_text += "\n"
        
        # Check if adding this operator would exceed Telegram's 4096 character limit
        if len(current_message + operator_text) > 3800:  # Leave some buffer
            messages.append(current_message)
            current_message = f"🛬 **OPERATORS SERVING BOTH {dest_str}** (continued)\n\n" + operator_text
        else:
            current_message += operator_text
    
    # Add the last message
    if current_message.strip():
        messages.append(current_message)
    
    # Add summary to last message
    if len(messages) > 1:
        messages[-1] += f"\n✅ *Showing all {len(operators)} operators across {len(messages)} messages*"
    
    return messages

def format_geographic_operator_results(results: dict) -> dict:
    """Format Function 10 geographic operator results with detailed aircraft breakdown.
    
    Returns:
        dict: Contains 'messages' (list) and 'operators' (list) for keyboard creation
    """
    
    if "error" in results:
        return {"messages": [f"❌ Error: {results['error']}"], "operators": []}
    
    operators = results.get("operators", [])
    search_criteria = results.get("search_criteria", {})
    summary = results.get("summary", {})
    
    if not operators:
        first_loc = search_criteria.get("first_location", {})
        second_loc = search_criteria.get("second_location", {})
        return [f"📭 No operators found serving both {first_loc.get('value')} ({first_loc.get('type')}) and {second_loc.get('value')} ({second_loc.get('type')})."]
    
    first_loc = search_criteria.get("first_location", {})
    second_loc = search_criteria.get("second_location", {})
    
    # Create header message with search summary
    header = f"🌍 **GEOGRAPHIC OPERATOR ANALYSIS**\n"
    header += f"📍 **{first_loc.get('value')}** ({first_loc.get('type')}) ↔ **{second_loc.get('value')}** ({second_loc.get('type')})\n"
    header += f"📅 *Period: {results.get('time_range', {}).get('start_time')} to {results.get('time_range', {}).get('end_time')}*\n\n"
    
    header += f"📊 **SUMMARY:**\n"
    header += f"• {summary.get('total_operators', 0)} operators found\n"
    header += f"• {summary.get('total_flights', 0):,} total flights\n"
    header += f"• {summary.get('freighter_flights', 0):,} freighter ({round(summary.get('freighter_flights', 0) / max(summary.get('total_flights', 1), 1) * 100)}%)\n"
    header += f"• {summary.get('passenger_flights', 0):,} passenger ({round(summary.get('passenger_flights', 0) / max(summary.get('total_flights', 1), 1) * 100)}%)\n\n"
    
    # Add limit warning if present
    limit_warning = results.get("limit_warning")
    if limit_warning:
        header += f"⚠️ **DATA LIMIT NOTICE:**\n"
        header += f"• {limit_warning.get('message', 'Showing results from first 50,000 records.')}\n"
        header += f"• {limit_warning.get('suggestion', 'Consider narrowing your search for complete coverage.')}\n\n"
    
    messages = []
    
    # Message 1: Summary only
    messages.append(header)
    
    # Message 2: ALL Operators with Fleet Details
    if len(operators) > 0:
        message2 = f"🛩️ **ALL OPERATORS - FLEET BREAKDOWN**\n\n"
        
        for i, op in enumerate(operators, 1):
            operator_name = op.get('operator', 'Unknown')
            operator_iata = op.get('operator_iata_code') or 'N/A'
            total_flights = op.get('total_flights', 0)
            
            message2 += f"**{i}. {operator_name}** ({operator_iata}) - {total_flights:,} flights\n"
            
            # Show detailed fleet breakdown
            fleet_breakdown = op.get('fleet_breakdown', {})
            freighter_aircraft = fleet_breakdown.get('freighter_aircraft', [])
            passenger_aircraft = fleet_breakdown.get('passenger_aircraft', [])
            
            # Show freighter aircraft with airport details
            if freighter_aircraft:
                message2 += f"   🚛 **Freighter Fleet:**\n"
                for aircraft in freighter_aircraft[:3]:  # Top 3 freighter types
                    aircraft_type = aircraft.get('aircraft_type', 'Unknown')
                    flights = aircraft.get('flights', 0)
                    destinations = aircraft.get('destinations', [])
                    
                    message2 += f"      • {aircraft_type}: {flights:,} flights\n"
                    
                    # Show ALL airports for this aircraft type
                    if destinations:
                        airport_list = []
                        for dest in destinations:  # ALL airports, not just top 5
                            airport_code = dest.get('code', '???')
                            airport_flights = dest.get('flights', 0)
                            airport_list.append(f"{airport_code}: {airport_flights}")
                        message2 += f"        └ Airports: {', '.join(airport_list)}\n"
            
            # Show passenger aircraft  
            if passenger_aircraft:
                message2 += f"   ✈️ **Passenger Fleet:**\n"
                for aircraft in passenger_aircraft[:3]:  # Top 3 passenger types
                    aircraft_type = aircraft.get('aircraft_type', 'Unknown')
                    flights = aircraft.get('flights', 0)
                    message2 += f"      • {aircraft_type}: {flights:,} flights\n"
            
            message2 += "\n"
            
            # Check if message is getting too long, split into multiple messages
            if len(message2) > 3500:
                messages.append(message2)
                message2 = f"🛩️ **OPERATORS - FLEET BREAKDOWN** (continued)\n\n"
        
        # Add the final message if it has content
        if message2.strip() and not message2.endswith("🛩️ **OPERATORS - FLEET BREAKDOWN** (continued)\n\n"):
            messages.append(message2)
    
    # Message 3: Airport Breakdown per Operator
    airport_breakdown = results.get('airport_breakdown_by_operator', [])
    
    if airport_breakdown:
        first_loc = search_criteria.get("first_location", {})
        second_loc = search_criteria.get("second_location", {})
        
        message3 = f"🏢 **AIRPORT BREAKDOWN BY OPERATOR**\n\n"
        
        # Show airport breakdown for each operator
        for op_data in airport_breakdown[:10]:  # Top 10 operators
            operator_name = op_data.get('operator', 'Unknown')
            operator_iata = op_data.get('operator_iata_code', 'N/A')
            first_airports = op_data.get('first_location_airports', [])
            second_airports = op_data.get('second_location_airports', [])
            
            message3 += f"**{operator_name}** ({operator_iata}):\n"
            
            # First location airports
            if first_airports:
                message3 += f"   📍 **{first_loc.get('value')}**: "
                airport_list = []
                for airport in first_airports[:5]:  # Top 5 airports per operator
                    iata = airport.get('iata_code', '???')
                    flights = airport.get('flights', 0)
                    airport_list.append(f"{iata}: {flights:,}")
                message3 += ", ".join(airport_list) + "\n"
            
            # Second location airports  
            if second_airports:
                message3 += f"   📍 **{second_loc.get('value')}**: "
                airport_list = []
                for airport in second_airports[:5]:  # Top 5 airports per operator
                    iata = airport.get('iata_code', '???')
                    flights = airport.get('flights', 0)
                    airport_list.append(f"{iata}: {flights:,}")
                message3 += ", ".join(airport_list) + "\n"
            
            message3 += "\n"
            
            # Check if message is getting too long
            if len(message3) > 3500:
                break
        
        messages.append(message3)
    
    # Collect operator info for clickable buttons (top 10 operators)
    operator_buttons = []
    for i, op in enumerate(operators[:10], 1):
        operator_name = op.get('operator', 'Unknown')
        operator_iata = op.get('operator_iata_code') or 'N/A'
        operator_icao = op.get('operator_icao_code') or 'N/A'
        total_flights = op.get('total_flights', 0)
        
        operator_buttons.append({
            'name': operator_name,
            'iata': operator_iata,
            'icao': operator_icao,
            'flights': total_flights,
            'button_text': f"{i}. {operator_name} ({operator_iata}) - {total_flights:,} flights"
        })
    
    return {
        "messages": messages,
        "operators": operator_buttons
    }

def format_results_for_telegram(results: dict, function_name: str):
    """Format results for Telegram message.
    
    Returns:
        str: For most functions (single message)
        list: For Functions 9 & 10 (multiple messages)
    """
    
    if "error" in results:
        return f"❌ Error: {results['error']}"
    
    # Handle enhanced Function 1 format (with freighter/passenger breakdown)
    if function_name == "get_operators_by_destination" and "freighter_operators" in results:
        return format_enhanced_destination_results(results)
    
    # Handle Function 9 format (multi-destination operators) - returns list for splitting
    if function_name == "get_operators_by_multi_destinations":
        return format_multi_destination_results(results)
    
    # Handle Function 10 format (geographic operators) - returns list for splitting
    if function_name == "get_operators_by_geographic_locations":
        return format_geographic_operator_results(results)
    
    if "results" not in results or not results["results"]:
        return "📭 No results found for your query."
    
    data = results["results"]
    message = f"✅ Found {len(data)} results:\n📅 *Data Period: Apr 2024 - May 2025 (408 days)*\n\n"
    
    # Format results for Telegram (show more for comprehensive view)
    display_limit = min(50, len(data))  # Show up to 50 results or all if fewer
    for i, item in enumerate(data[:display_limit], 1):
        if function_name in ["get_operators_by_destination", "get_operators_by_origin"]:
            operator = item.get("operator", "Unknown")
            frequency = item.get("frequency", 0)
            iata = item.get("operator_iata_code") or "N/A"
            message += f"{i}. {operator}\n   Flights: {frequency} | IATA: {iata}\n\n"
            
        elif function_name == "get_operator_route_summary":
            origin = item.get("origin_code", "???")
            destination = item.get("destination_code", "???")
            frequency = item.get("frequency", 0)
            message += f"{i}. {origin} → {destination}\n   Flights: {frequency}\n\n"
            
        elif function_name == "get_route_details":
            operator = item.get("operator", "Unknown")
            frequency = item.get("frequency", 0)
            registration = item.get("sample_registration", "N/A")
            message += f"{i}. {operator}\n   Flights: {frequency} | Sample Aircraft: {registration}\n\n"
        
        elif function_name == "get_operator_frequency":
            operator = item.get("operator", "Unknown")
            frequency = item.get("frequency", 0)
            route = f"{item.get('origin_code', '???')} → {item.get('destination_code', '???')}"
            message += f"{i}. {operator}\n   Route: {route} | Frequency: {frequency}\n\n"
        
        elif function_name == "get_operator_origins_by_region":
            region = item.get("region", "Unknown")
            origin = item.get("origin_code", "???")
            frequency = item.get("frequency", 0)
            message += f"{i}. {region} - {origin}\n   Flights: {frequency}\n\n"
        
        elif function_name == "calculate_multi_leg_route_metrics":
            metric = item.get("metric_type", "Unknown")
            value = item.get("value", "N/A")
            description = item.get("description", "")
            message += f"{i}. {metric}: {value}\n   {description}\n\n"
        
        else:
            # Generic formatting for any new functions
            key_fields = []
            for key, value in item.items():
                if key not in ['id', 'created_at', 'updated_at'] and value is not None:
                    key_fields.append(f"{key}: {value}")
            message += f"{i}. {' | '.join(key_fields[:3])}\n"
    
    if len(data) > display_limit:
        message += f"\n... and {len(data) - display_limit} more results"
        message += f"\n\n💡 *Tip: For smaller result sets, be more specific (e.g., 'Who flies cargo to CAI?' or specify airline)*"
    
    return message

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    welcome_text = """
🛩️ *FlightRadar Cargo Charter Broker Bot*

I help you find carriers and routes for cargo flights!

*Examples:*
• "Who flies to LAX?"
• "Emirates routes"
• "Carriers to London"
• "Routes from JFK"

*Commands:*
/help - Complete usage guide
/examples - Query examples  
/functions - Technical function details

Just ask me about any destination or airline! 🚀
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information."""
    help_text = """
🆘 *HELP - Core Functions Guide*

📊 *CORE FUNCTIONS (Apr 2024 - May 2025):*

🎯 *Function 1: Find Carriers by Destination*
• "Who flies to LAX?"
• "Carriers to Dubai"
• "Hong Kong flights"
*Gets all airlines serving a destination with freight/passenger breakdown*

🔍 *Function 8: Operator Details*
• "Operator details FedEx"
• "Show operator Emirates"
• "Airline info Lufthansa"
*Complete fleet breakdown + route analysis with clickable buttons*

🌐 *Function 9: Multi-Destination Operators*
• "Operators to both JFK and LAX"
• "Which operators fly to both Dubai and Singapore"
• "Carriers serving multiple destinations"
*Find operators serving multiple specified airports*

🌍 *Function 10: Geographic Operator Analysis*
• "China to SCL operators"
• "Korea to Japan operators"
• "JFK to Asia carriers"
• "Europe to Thailand operators"
*Find operators serving between countries/continents/airports*

💡 *Usage Tips:*
• Use 3-letter IATA codes (LAX, JFK, LHR, DXB, SCL)
• Use exact country names: "Korea" not "Korean", "China" not "Chinese"
• Data covers Apr 2024 - May 2025 (408 days)
• All functions show comprehensive results
• Type /examples for more query examples

🎯 *Function Selection:*
• Use /selectfunction to choose which function to use
• Helpful when queries could match multiple functions
• Example: "PEK to SCL operators" could be Function 1 or 10

🔧 *Advanced Functions:*
Functions 2-7 are available but not actively promoted. Focus on the 4 core functions above for best results.
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show example queries."""
    examples_text = """
💡 *Complete Query Examples*

🎯 *Destination Analysis:*
• "Who flies to LAX?"
• "Which airlines serve Dubai DXB?"
• "Carriers to Hong Kong HKG"
• "London Heathrow LHR flights"
*→ Returns all carriers serving that destination*

🛫 *Origin Analysis:*
• "Routes from JFK"
• "What destinations from Dubai DXB?"
• "Tokyo NRT departures"
• "Frankfurt FRA routes"
*→ Returns all destinations from that origin*

✈️ *Airline Route Maps:*
• "Emirates route map"
• "FedEx destinations"
• "Cathay Pacific routes"
• "Delta cargo flights"
• "Lufthansa network"
*→ Returns complete airline route summary*

🔍 *Specific Route Details:*
• "JFK to LAX route details"
• "London to New York flights"
• "Dubai to Frankfurt details"
• "Hong Kong to LAX carriers"
*→ Returns all carriers on that specific route*

📈 *Route Frequency Analysis:*
• "JFK LAX frequency"
• "Dubai London frequency"
• "Frankfurt Tokyo frequency"
*→ Returns detailed frequency metrics*

🌍 *Regional Analysis:*
• "Emirates origins by region"
• "FedEx regional origins"
• "Lufthansa regional network"
*→ Returns origins grouped by world regions*

⚡ *Advanced Queries:*
• "Multi-leg route analysis"
• "Complex routing metrics"
• "Hub connectivity analysis"
*→ Returns advanced routing calculations*

🏢 *Operator Details (NEW!):*
• "Operator details FX"
• "Fleet breakdown Emirates"
• "Show operator Lufthansa"
• "Airline info EK"
*→ Returns fleet breakdown + route analysis with clickable buttons*

🌍 *Geographic Analysis (NEW!):*
• "China to SCL operators"
• "JFK to Asia carriers"
• "Europe to Japan flights"
• "North America to Thailand operators"
• "Operators from Germany to Singapore"
*→ Returns operators serving countries/continents with aircraft details*

💼 *Business Scenarios:*
• "Cargo options to Mumbai"
• "Freighter routes from Amsterdam"
• "Heavy cargo to São Paulo"
• "Time-sensitive to Singapore"

🌐 *Popular Destinations:*
LAX, JFK, LHR, DXB, FRA, NRT, HKG, SIN, AMS, CDG

Just ask naturally - I understand context! 🤖
"""
    await update.message.reply_text(examples_text, parse_mode='Markdown')

async def functions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed function information."""
    functions_text = """
⚙️ *Technical Function Reference*

*All functions use Apr 2024 - May 2025 data (408 days)*

📊 *Function 1: get-operators-by-destination*
🎯 Purpose: Find all carriers serving a destination
📝 Usage: "Who flies to [AIRPORT]?"
💡 Example: "Who flies to LAX?"
📈 Returns: List of operators + flight frequencies

📊 *Function 2: get-operators-by-origin*  
🎯 Purpose: Find all destinations from an origin
📝 Usage: "Routes from [AIRPORT]"
💡 Example: "Routes from JFK"
📈 Returns: List of destinations + frequencies

📊 *Function 3: get-operator-route-summary*
🎯 Purpose: Complete airline route network
📝 Usage: "[AIRLINE] routes"
💡 Example: "Emirates routes"
📈 Returns: All routes for that airline

📊 *Function 4: get-route-details*
🎯 Purpose: Specific route analysis
📝 Usage: "[ORIGIN] to [DESTINATION] details"
💡 Example: "JFK to LAX details"
📈 Returns: All carriers on that route

📊 *Function 5: get-operator-frequency*
🎯 Purpose: Route frequency analysis
📝 Usage: "[ORIGIN] [DESTINATION] frequency"
💡 Example: "JFK LAX frequency"
📈 Returns: Detailed frequency metrics

📊 *Function 6: get-operator-origins-by-region*
🎯 Purpose: Regional origin analysis
📝 Usage: "[AIRLINE] regional origins"
💡 Example: "Emirates regional origins"
📈 Returns: Origins grouped by regions

📊 *Function 7: calculate-multi-leg-route-metrics*
🎯 Purpose: Complex routing analysis
📝 Usage: "Multi-leg route analysis"
💡 Example: "Complex routing via Dubai"
📈 Returns: Advanced routing calculations

📊 *Function 8: get-operator-details* (NEW!)
🎯 Purpose: Operator fleet & route analysis
📝 Usage: "Operator details [AIRLINE/IATA/ICAO]"
💡 Example: "Operator details FX" or "Fleet breakdown Emirates"
📈 Returns: Fleet breakdown + top destinations with clickable selection
🔥 Features: Multi-search results, interactive buttons, detailed registrations

🔧 *Technical Notes:*
• All queries processed via Gemini AI
• Automatic function selection
• Apr 2024 - May 2025: 1.28M flight records
• 12,742 aircraft tracked
• Shows up to 50 results per query
• Response time: <3 seconds
"""
    await update.message.reply_text(functions_text, parse_mode='Markdown')

async def selectfunction_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show function selection menu and pin it."""
    keyboard = [
        [
            InlineKeyboardButton("🏢 Operators by Destination", callback_data="select_func_1"),
            InlineKeyboardButton("🔍 Operator Details", callback_data="select_func_8")
        ],
        [
            InlineKeyboardButton("🗺️ Multi-Destination Operators", callback_data="select_func_9"),
            InlineKeyboardButton("🌍 Geographic Operators", callback_data="select_func_10")
        ],
        [
            InlineKeyboardButton("✈️ Aircraft-to-Destination Search", callback_data="select_func_12")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_selection"),
            InlineKeyboardButton("📌 Unpin Menu", callback_data="unpin_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the function selection menu
    message = await update.message.reply_text(
        "📌 **FUNCTION SELECTION MENU**\n\n"
        "Choose which type of analysis you want:\n\n"
        "🏢 **Operators by Destination** (Function 1)\n"
        "   *Find operators flying to specific airports*\n"
        "   Example: \"Who flies to LAX?\"\n\n"
        "🔍 **Operator Details** (Function 8)\n"
        "   *Get detailed operator information*\n"
        "   Example: \"FedEx details\"\n\n"
        "🗺️ **Multi-Destination Operators** (Function 9)\n"
        "   *Find operators serving multiple airports*\n" 
        "   Example: \"Operators to both JFK and LAX\"\n\n"
        "🌍 **Geographic Operators** (Function 10)\n"
        "   *Find operators between countries/continents*\n"
        "   Example: \"PEK to SCL operators\"\n\n"
        "✈️ **Aircraft-to-Destination Search** (Function 12)\n"
        "   *Find operators with specific aircraft to destinations*\n"
        "   Example: \"A330 B777 to China\"\n\n"
        "👆 **Click a button above to continue**\n"
        "💡 **Your selection will stay active until you change it**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Pin the message to the top of the chat
    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=message.message_id,
            disable_notification=True
        )
        logger.info("✅ Function selection menu pinned successfully")
    except Exception as e:
        logger.error(f"❌ Failed to pin message: {e}")
        # Continue even if pinning fails

async def send_large_message(message, text: str, reply_markup=None):
    """Split and send large messages that exceed Telegram's 4096 character limit."""
    MAX_MESSAGE_LENGTH = 4000  # Leave some buffer for safety
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        # Message is small enough, send normally
        await message.reply_text(text=text, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Split the message at natural break points
    parts = []
    current_part = ""
    
    lines = text.split('\n')
    
    for line in lines:
        # If adding this line would exceed the limit, save current part and start new one
        if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current_part:
                parts.append(current_part.strip())
                current_part = ""
        
        current_part += line + '\n'
    
    # Add the last part
    if current_part:
        parts.append(current_part.strip())
    
    # Send all parts
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # Last message gets the reply markup (buttons)
            await message.reply_text(text=part, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            # Other messages just get the text with a "continued" indicator
            part_with_indicator = part + f"\n\n*📄 Continued in next message... ({i+1}/{len(parts)})*"
            await message.reply_text(text=part_with_indicator, parse_mode='Markdown')

async def start_aircraft_selection_from_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Start Function 12 from callback query."""
    # Create a mock update object for the existing function
    class MockUpdate:
        def __init__(self, query):
            self.callback_query = query
            self.message = query.message
    
    mock_update = MockUpdate(query)
    await start_aircraft_selection(mock_update, context)

async def start_aircraft_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Function 12 by showing aircraft type selection with clickable buttons."""
    try:
        # Get available aircraft types from database
        await update.message.reply_text(
            "⏳ **Loading available aircraft types from database...**",
            parse_mode='Markdown'
        )
        
        # Call Supabase function to get aircraft types
        results = await call_supabase_function("aircraft-to-destination-search", {
            "mode": "get_aircraft_types"
        })
        
        if results.get("error"):
            await update.message.reply_text(
                f"❌ **Error loading aircraft types**\n\n{results['error']}\n\n"
                "Falling back to known aircraft types...",
                parse_mode='Markdown'
            )
            # Fallback to known types
            aircraft_types = [
                {"aircraft_type": "A330", "aircraft_count": 0, "operator_count": 0},
                {"aircraft_type": "B747", "aircraft_count": 0, "operator_count": 0},
                {"aircraft_type": "B757", "aircraft_count": 0, "operator_count": 0},
                {"aircraft_type": "B767", "aircraft_count": 0, "operator_count": 0},
                {"aircraft_type": "B777", "aircraft_count": 0, "operator_count": 0},
                {"aircraft_type": "IL76", "aircraft_count": 0, "operator_count": 0}
            ]
        else:
            aircraft_types = results.get("aircraft_types", [])
        
        # Initialize selection state
        context.user_data['func12_step'] = 'select_aircraft'
        context.user_data['available_aircraft'] = aircraft_types
        context.user_data['selected_aircraft'] = []
        
        # Create aircraft selection message and keyboard
        await show_aircraft_selection_menu(update, context, aircraft_types)
        
    except Exception as e:
        logger.error(f"Error starting aircraft selection: {e}")
        await update.message.reply_text(
            "❌ **Error starting aircraft selection**\n\n"
            "Please try again later.",
            parse_mode='Markdown'
        )

async def update_aircraft_selection_menu(query, context: ContextTypes.DEFAULT_TYPE, aircraft_types: list):
    """Update aircraft selection menu via callback query."""
    selected_aircraft = context.user_data.get('selected_aircraft', [])
    
    # Create updated message
    message = "✈️ **FUNCTION 12: Aircraft-to-Destination Search**\n\n"
    message += "**Step 1: Select Aircraft Types** (Multiple Selection)\n\n"
    
    if selected_aircraft:
        message += f"**Currently Selected:** {', '.join(selected_aircraft)}\n\n"
    
    message += "Click aircraft types to select/deselect:\n\n"
    
    # Show ALL aircraft types with statistics (sorted: Boeing, Airbus, Others)
    for i, aircraft in enumerate(aircraft_types, 1):  # Show ALL aircraft types
        aircraft_type = aircraft.get("aircraft_type", "Unknown")
        aircraft_count = aircraft.get("aircraft_count", 0)
        operator_count = aircraft.get("operator_count", 0)
        
        # Mark selected aircraft
        status = "✅" if aircraft_type in selected_aircraft else "☐"
        message += f"{status} **{aircraft_type}** ({aircraft_count:,} aircraft, {operator_count} operators)\n"
    
    message += "\n👆 **Click buttons below to select aircraft types**"
    
    # Create keyboard with aircraft buttons
    keyboard = []
    
    # Aircraft selection buttons (2 per row) - Show ALL aircraft types
    for i in range(0, len(aircraft_types), 2):
        row = []
        for j in range(2):
            if i + j < len(aircraft_types):
                aircraft = aircraft_types[i + j]
                aircraft_type = aircraft.get("aircraft_type", "Unknown")
                
                # Show selection status in button
                if aircraft_type in selected_aircraft:
                    button_text = f"✅ {aircraft_type}"
                else:
                    button_text = f"☐ {aircraft_type}"
                
                callback_data = f"func12_aircraft_{aircraft_type}"
                row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        if row:  # Only add non-empty rows
            keyboard.append(row)
    
    # Control buttons
    control_buttons = []
    if len(aircraft_types) > 0:
        control_buttons.append(InlineKeyboardButton("☑️ Select All", callback_data="func12_select_all"))
        control_buttons.append(InlineKeyboardButton("🗑️ Clear All", callback_data="func12_clear_all"))
    
    if control_buttons:
        keyboard.append(control_buttons)
    
    # Action buttons
    action_buttons = []
    if selected_aircraft:
        action_buttons.append(InlineKeyboardButton("➡️ Continue to Destinations", callback_data="func12_continue"))
    action_buttons.append(InlineKeyboardButton("❌ Cancel", callback_data="func12_cancel"))
    
    if action_buttons:
        keyboard.append(action_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Edit the existing message
    await query.edit_message_text(
        text=message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_aircraft_selection_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, aircraft_types: list):
    """Show aircraft selection menu with clickable buttons."""
    selected_aircraft = context.user_data.get('selected_aircraft', [])
    
    # Create message
    message = "✈️ **FUNCTION 12: Aircraft-to-Destination Search**\n\n"
    message += "**Step 1: Select Aircraft Types** (Multiple Selection)\n\n"
    
    if selected_aircraft:
        message += f"**Currently Selected:** {', '.join(selected_aircraft)}\n\n"
    
    message += "Click aircraft types to select/deselect:\n\n"
    
    # Show ALL aircraft types with statistics (sorted: Boeing, Airbus, Others)
    for i, aircraft in enumerate(aircraft_types, 1):  # Show ALL aircraft types
        aircraft_type = aircraft.get("aircraft_type", "Unknown")
        aircraft_count = aircraft.get("aircraft_count", 0)
        operator_count = aircraft.get("operator_count", 0)
        
        # Mark selected aircraft
        status = "✅" if aircraft_type in selected_aircraft else "☐"
        message += f"{status} **{aircraft_type}** ({aircraft_count:,} aircraft, {operator_count} operators)\n"
    
    message += "\n👆 **Click buttons below to select aircraft types**"
    
    # Create keyboard with aircraft buttons
    keyboard = []
    
    # Aircraft selection buttons (2 per row) - Show ALL aircraft types
    for i in range(0, len(aircraft_types), 2):
        row = []
        for j in range(2):
            if i + j < len(aircraft_types):
                aircraft = aircraft_types[i + j]
                aircraft_type = aircraft.get("aircraft_type", "Unknown")
                
                # Show selection status in button
                if aircraft_type in selected_aircraft:
                    button_text = f"✅ {aircraft_type}"
                else:
                    button_text = f"☐ {aircraft_type}"
                
                callback_data = f"func12_aircraft_{aircraft_type}"
                row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        if row:  # Only add non-empty rows
            keyboard.append(row)
    
    # Control buttons
    control_buttons = []
    if len(aircraft_types) > 0:
        control_buttons.append(InlineKeyboardButton("☑️ Select All", callback_data="func12_select_all"))
        control_buttons.append(InlineKeyboardButton("🗑️ Clear All", callback_data="func12_clear_all"))
    
    if control_buttons:
        keyboard.append(control_buttons)
    
    # Action buttons
    action_buttons = []
    if selected_aircraft:
        action_buttons.append(InlineKeyboardButton("➡️ Continue to Destinations", callback_data="func12_continue"))
    action_buttons.append(InlineKeyboardButton("❌ Cancel", callback_data="func12_cancel"))
    
    if action_buttons:
        keyboard.append(action_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Always send new message, never edit
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(
            text=message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_destination_input_step(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_aircraft: list):
    """Show destination input step after aircraft selection."""
    try:
        message = f"✅ **Aircraft Selected:** {', '.join(selected_aircraft)}\n\n"
        message += "**Step 2: Enter Destinations**\n\n"
        message += "Enter one or more destinations separated by spaces:\n\n"
        message += "**Examples:**\n"
        message += "• Airport codes: `JFK LAX LHR`\n"
        message += "• Countries: `China Japan Germany`\n"
        message += "• Continents: `Asia Europe`\n"
        message += "• Mixed: `JFK China Europe`\n\n"
        message += "💬 **Type your destinations and press Enter:**"
        
        # Update user state
        context.user_data['func12_step'] = 'select_destinations'
        context.user_data['selected_aircraft'] = selected_aircraft
        
        # Send new message (don't edit the aircraft selection message)
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing destination input: {e}")
        await update.message.reply_text(
            "❌ **Error proceeding to destinations**\n\nPlease try again.",
            parse_mode='Markdown'
        )

async def handle_destination_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    """Handle destination input and execute search."""
    try:
        selected_aircraft = context.user_data.get('selected_aircraft', [])
        destinations = [dest.strip() for dest in user_input.replace(',', ' ').split() if dest.strip()]
        
        if not destinations:
            await update.message.reply_text(
                "❌ **No destinations entered**\n\n"
                "Please enter at least one destination.",
                parse_mode='Markdown'
            )
            return
        
        # Clear user state
        context.user_data.pop('func12_step', None)
        context.user_data.pop('selected_aircraft', None)
        context.user_data.pop('available_aircraft', None)
        
        # Execute search
        await execute_aircraft_destination_search(update, context, selected_aircraft, destinations)
        
    except Exception as e:
        logger.error(f"Error handling destination input: {e}")
        await update.message.reply_text(
            "❌ **Error processing destinations**\n\nPlease try again.",
            parse_mode='Markdown'
        )

async def execute_aircraft_destination_search(update: Update, context: ContextTypes.DEFAULT_TYPE, aircraft_types: list[str], destinations: list[str]):
    """Execute the actual aircraft-destination search."""
    try:
        # Show processing message
        await update.message.reply_text(
            f"🔍 **Searching operators with {', '.join(aircraft_types)} to {', '.join(destinations)}...**\n\n"
            "⏳ Processing comprehensive database search...",
            parse_mode='Markdown'
        )
        
        # Call Supabase Function 12
        results = await call_supabase_function("aircraft-to-destination-search", {
            "mode": "search",
            "aircraft_types": aircraft_types,
            "destinations": destinations,
            "start_time": "2024-04-01",
            "end_time": "2025-05-31"
        })
        
        # Format and send results
        response_data = format_aircraft_destination_results(results, aircraft_types, destinations)
        
        if response_data["operators"]:
            # Create operator buttons (Function 10 style)
            keyboard = []
            for op in response_data["operators"][:20]:  # Top 20 operators for buttons
                # Encode operator name to handle special characters like &
                encoded_name = urllib.parse.quote(op['name'], safe='')
                callback_data = f"select_operator_func12_{encoded_name}"
                button_text = f"📋 {op['name']} Details"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add additional buttons
            keyboard.append([
                InlineKeyboardButton("🔍 New Search", callback_data="search_again"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ])
            
            # Send the message content first (may be split into multiple messages)
            await send_large_message(update.message, response_data["message"])
            
            # Send operator buttons separately to ensure they're always visible
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔗 **OPERATOR QUICK ACCESS:**\nClick any button below for detailed operator analysis:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(response_data["message"], parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in aircraft-destination search execution: {e}")
        await update.message.reply_text(
            "❌ **Error executing search**\n\n"
            f"Aircraft: {', '.join(aircraft_types)}\n"
            f"Destinations: {', '.join(destinations)}\n\n"
            "Please try again or contact support.",
            parse_mode='Markdown'
        )

async def handle_aircraft_destination_search(update: Update, context: ContextTypes.DEFAULT_TYPE, user_query: str):
    """Handle Function 12: Aircraft-to-Destination Search (Legacy direct query)."""
    try:
        # Parse the query to extract aircraft types and destinations
        aircraft_types, destinations = parse_aircraft_destination_query(user_query)
        
        if not aircraft_types:
            await update.message.reply_text(
                "❌ **Aircraft types not found in query**\n\n"
                "Please specify aircraft types in your query.\n\n"
                "**Examples:**\n"
                "• \"A330 B777 to China\"\n"
                "• \"B747 to JFK LAX\"\n"
                "• \"IL76 to Europe\"\n\n"
                "**Supported aircraft:** A330, B747, B757, B767, B777, IL76, A350, B737, etc.",
                parse_mode='Markdown'
            )
            return
            
        if not destinations:
            await update.message.reply_text(
                "❌ **Destinations not found in query**\n\n"
                "Please specify destinations in your query.\n\n"
                "**Examples:**\n"
                "• Airport codes: JFK, LAX, LHR\n"
                "• Countries: China, Germany, Japan\n"
                "• Continents: Asia, Europe, North America\n\n"
                "**Format:** [Aircraft Types] to [Destinations]",
                parse_mode='Markdown'
            )
            return
        
        # Show processing message
        await update.message.reply_text(
            f"🔍 **Searching operators with {', '.join(aircraft_types)} to {', '.join(destinations)}...**\n\n"
            "⏳ Processing comprehensive database search...",
            parse_mode='Markdown'
        )
        
        # Call Supabase Function 12
        results = await call_supabase_function("aircraft-to-destination-search", {
            "mode": "search",
            "aircraft_types": aircraft_types,
            "destinations": destinations,
            "start_time": "2024-04-01",
            "end_time": "2025-05-31"
        })
        
        # Format and send results
        response_data = format_aircraft_destination_results(results, aircraft_types, destinations)
        
        if response_data["operators"]:
            # Create operator buttons (Function 10 style)
            keyboard = []
            for op in response_data["operators"][:20]:  # Top 20 operators for buttons
                # Encode operator name to handle special characters like &
                encoded_name = urllib.parse.quote(op['name'], safe='')
                callback_data = f"select_operator_func12_{encoded_name}"
                button_text = f"📋 {op['name']} Details"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add additional buttons
            keyboard.append([
                InlineKeyboardButton("🔍 New Search", callback_data="search_again"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await send_large_message(update.message, response_data["message"], reply_markup)
        else:
            await update.message.reply_text(response_data["message"], parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in Function 12: {e}")
        await update.message.reply_text(
            "❌ **Error processing aircraft-destination search**\n\n"
            "Please check your query format and try again.\n\n"
            "**Expected format:** [Aircraft Types] to [Destinations]\n"
            "**Example:** \"A330 B777 to China Japan\"",
            parse_mode='Markdown'
        )

def parse_aircraft_destination_query(query: str) -> tuple[list[str], list[str]]:
    """Parse aircraft-destination query to extract aircraft types and destinations."""
    # Common aircraft types (will be dynamically updated from database in future)
    known_aircraft = ["A330", "A340", "A350", "A380", "B737", "B747", "B757", "B767", "B777", "B787", "IL76", "AN124", "DC8", "MD11"]
    
    # Split query on "to" keyword
    query_lower = query.lower()
    if " to " in query_lower:
        parts = query_lower.split(" to ", 1)
        aircraft_part = parts[0].strip()
        destination_part = parts[1].strip()
    else:
        # Try to detect aircraft types and assume rest are destinations
        words = query.split()
        aircraft_part = ""
        destination_part = ""
        
        # Find aircraft types
        for word in words:
            if word.upper() in known_aircraft:
                aircraft_part += word + " "
            else:
                destination_part += word + " "
        
        aircraft_part = aircraft_part.strip()
        destination_part = destination_part.strip()
    
    # Extract aircraft types
    aircraft_types = []
    aircraft_words = aircraft_part.split()
    for word in aircraft_words:
        word_upper = word.upper()
        if word_upper in known_aircraft:
            aircraft_types.append(word_upper)
    
    # Extract destinations
    destinations = []
    if destination_part:
        # Split by common separators
        dest_words = destination_part.replace(",", " ").replace("and", " ").split()
        destinations = [word.strip() for word in dest_words if word.strip()]
    
    return aircraft_types, destinations

def format_aircraft_destination_results(results: dict, aircraft_types: list[str], destinations: list[str]) -> dict:
    """Format Function 12 results for Telegram display."""
    if results.get("error"):
        return {
            "message": f"❌ {results['error']}",
            "operators": []
        }
    
    search_summary = results.get("search_summary", {})
    operators = results.get("operators", [])
    
    if not operators:
        message = (
            f"❌ **No operators found**\n\n"
            f"**Search criteria:**\n"
            f"• Aircraft: {', '.join(aircraft_types)}\n"
            f"• Destinations: {', '.join(destinations)}\n\n"
            f"**Suggestions:**\n"
            f"• Try different aircraft types\n"
            f"• Use broader destination names\n"
            f"• Check spelling of destinations"
        )
        return {"message": message, "operators": []}
    
    # Build comprehensive results message
    total_operators = search_summary.get("total_operators", len(operators))
    total_flights = search_summary.get("total_flights", 0)
    total_destinations = search_summary.get("total_destinations", 0)
    
    message = f"🎯 **AIRCRAFT-TO-DESTINATION SEARCH RESULTS**\n\n"
    message += f"**Search Criteria:**\n"
    message += f"✈️ Aircraft: {', '.join(aircraft_types)}\n"
    message += f"🌍 Destinations: {', '.join(destinations)}\n\n"
    message += f"📊 **SUMMARY:**\n"
    message += f"• **Total Operators:** {total_operators:,}\n"
    message += f"• **Total Flights:** {total_flights:,}\n"
    message += f"• **Total Destinations:** {total_destinations:,}\n\n"
    message += f"🏢 **ALL MATCHING OPERATORS:**\n\n"
    
    # List all operators (NO LIMITS)
    for i, op in enumerate(operators, 1):
        operator_name = op.get("operator", "Unknown")
        operator_iata = op.get("operator_iata_code") or "N/A"
        matching_fleet = op.get("matching_fleet_size", 0)
        total_fleet = op.get("total_fleet_size", 0)
        total_flights_op = op.get("total_flights", 0)
        destinations_count = op.get("destination_count", 0)
        avg_monthly = op.get("avg_monthly_flights", 0)
        available_types = op.get("available_aircraft_types", [])
        
        message += f"{i}️⃣ **{operator_name}** ({operator_iata})\n"
        message += f"   ✈️ Fleet: {matching_fleet}/{total_fleet} matching aircraft\n"
        message += f"   🌍 Destinations: {destinations_count} airports\n"
        message += f"   📈 Flights: {total_flights_op:,} ({avg_monthly} avg/month)\n"
        
        # Show aircraft types available
        if available_types:
            types_display = ", ".join(available_types[:5])
            if len(available_types) > 5:
                types_display += f" (+{len(available_types) - 5} more)"
            message += f"   🛩️ Aircraft: {types_display}\n"
        
        message += "\n"
    
    message += f"\n🔗 **QUICK ACCESS TO OPERATOR DETAILS:**\n"
    message += f"Use the buttons below to get detailed fleet & route analysis for any operator.\n\n"
    message += f"💡 **Results show ALL {total_operators} operators** - no limits applied!"
    
    # Prepare operator data for buttons
    button_operators = []
    for op in operators:
        button_operators.append({
            "name": op.get("operator", "Unknown"),
            "iata": op.get("operator_iata_code") or "N/A"
        })
    
    return {
        "message": message,
        "operators": button_operators
    }

async def handle_geographic_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  operator_name: str, geography_input: str, filter_type: str) -> None:
    """Handle geographic filtering for Function 8."""
    try:
        # Send loading message
        await update.message.reply_text(f"🔍 Searching {operator_name} destinations in {geography_input}...")
        
        # Clean operator name - fix common issues like Icel&air -> Icelandair
        cleaned_operator_name = operator_name
        if "icel&air" in operator_name.lower():
            # Handle Icelandair specifically - database has 'Icelandair' not 'Icel&air'
            cleaned_operator_name = "Icelandair"  # Fix the corruption
        elif "&" in operator_name and "icel" not in operator_name.lower():
            # Only apply general & replacement for non-Icelandair operators
            cleaned_operator_name = operator_name.replace("&", " and ")
        
        # Call the enhanced Supabase function with geographic filtering
        # Note: This will require the Supabase function to be enhanced in Phase 2
        results = await call_supabase_function("get_operator_details", {
            "operator_selection": cleaned_operator_name,
            "geographic_filter": geography_input,
            "filter_type": filter_type
        })
        
        if results.get("error"):
            await update.message.reply_text(f"❌ {results['error']}")
            return
        
        # Format the geographic results
        response_text = format_geographic_destinations(results, operator_name, geography_input, filter_type)
        
        # Send results with back button
        keyboard = [[InlineKeyboardButton("🔙 Back to Full Details", 
                                        callback_data=f"back_to_operator_{operator_name.replace(' ', '_')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=response_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in geographic filter: {e}")
        await update.message.reply_text("❌ Error processing geographic filter. Please try again.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user_query = update.message.text
    user_name = update.message.from_user.first_name or "User"
    
    logger.info(f"Query from {user_name}: {user_query}")
    
    # ENHANCED: Check if user is entering geographic filter input
    if context.user_data.get('awaiting_country_filter'):
        operator_name = context.user_data.pop('awaiting_country_filter')
        await handle_geographic_filter(update, context, operator_name, user_query, "country")
        return
    
    if context.user_data.get('awaiting_continent_filter'):
        operator_name = context.user_data.pop('awaiting_continent_filter')
        await handle_geographic_filter(update, context, operator_name, user_query, "continent")
        return
    
    # TEMPORARY: Direct test of Function 9
    if user_query.lower() == "test function 9":
        logger.info("🧪 DIRECT FUNCTION 9 TEST ACTIVATED")
        await update.message.reply_text("🧪 Testing Function 9 directly...")
        
        try:
            # Call Function 9 directly with test mode
            result = await call_supabase_function("get_operators_by_multi_destinations", {
                "test_mode": True,
                "destination_codes": ["HKG", "JFK"],
                "start_time": "2024-04-01",
                "end_time": "2025-05-31"
            })
            
            await update.message.reply_text(f"🔬 Function 9 Direct Test Result:\n{result}")
            return
            
        except Exception as e:
            await update.message.reply_text(f"❌ Function 9 Direct Test Failed: {e}")
            return
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Check if user has selected a specific function
        selected_function = context.user_data.get('selected_function')
        
        if selected_function:
            # User has pre-selected a function, force its use
            logger.info(f"🎯 Using pre-selected function: {selected_function}")
            
            if selected_function == 'get_operator_details':
                # Handle as operator search
                search_term = extract_operator_from_query(user_query)
                if search_term:
                    await handle_operator_search(update, context, search_term)
                    # Clear the selection after use
                    context.user_data.pop('selected_function', None)
                    return
            elif selected_function == 'aircraft_to_destination_search':
                # Handle Function 12: Aircraft-to-Destination Search
                # ONLY handle destination input if user is in that specific step
                if context.user_data.get('func12_step') == 'select_destinations':
                    await handle_destination_input(update, context, user_query)
                    return
                else:
                    # Ignore other text input - user should use buttons for aircraft selection
                    await update.message.reply_text(
                        "⚠️ **Please use the aircraft selection buttons**\n\n"
                        "Use `/selectfunction` and click **✈️ Aircraft-to-Destination Search** to start.",
                        parse_mode='Markdown'
                    )
                    return
            else:
                # SMART PRESET SYSTEM: Check compatibility before forcing function
                
                # Step 1: Analyze what the query naturally should be
                natural_analysis = await analyze_query_with_openai(user_query)
                
                if not natural_analysis:
                    await update.message.reply_text(
                        "❌ Sorry, I couldn't understand your query. Please try rephrasing it."
                    )
                    return
                
                # Step 2: Preprocess locations for compatibility check
                processed_query = preprocess_locations(user_query)
                
                # Step 3: Check compatibility
                compatibility = check_function_compatibility(
                    selected_function, 
                    natural_analysis['function_name'], 
                    processed_query
                )
                
                if compatibility['is_compatible'] or selected_function == natural_analysis['function_name']:
                    # ✅ Compatible or same function - proceed with selected function
                    if selected_function == 'get_operators_by_geographic_locations':
                        analysis = await analyze_geographic_query_with_openai(user_query)
                    else:
                        analysis = natural_analysis
                    
                    if analysis:
                        analysis['function_name'] = selected_function
                        logger.info(f"🔄 Using selected function: {selected_function} (compatible)")
                else:
                    # ⚠️ Incompatible - show user guidance
                    await handle_function_mismatch(update, context, selected_function, natural_analysis, user_query)
                    return
            
            # Keep the selection persistent - don't clear it
            # User can change it by using /selectfunction again
        else:
            # Check if this is an operator search query (Function 8)
            if is_operator_search_query(user_query):
                search_term = extract_operator_from_query(user_query)
                if search_term:
                    await handle_operator_search(update, context, search_term)
                    return
            
            # Analyze query with OpenAI for other functions
            analysis = await analyze_query_with_openai(user_query)
        
        if not analysis:
            await update.message.reply_text(
                "❌ Sorry, I couldn't understand your query. Please try rephrasing it or use /help for examples."
            )
            return
        
        # Debug: Log the analysis result
        logger.info(f"OpenAI analysis: {analysis}")
        
        # Call Supabase function
        results = await call_supabase_function(
            analysis["function_name"], 
            analysis["parameters"]
        )
        
        # Debug: Log the results
        logger.info(f"Supabase results: {results}")
        
        # Format and send results
        response_text = format_results_for_telegram_for_telegram(results, analysis["function_name"])
        
        # Handle Function 9 which returns list of messages
        if analysis["function_name"] == "get_operators_by_multi_destinations" and isinstance(response_text, list):
            # Send all messages in sequence
            for i, message in enumerate(response_text):
                if i > 0:
                    # Add small delay between messages to avoid rate limiting
                    import asyncio
                    await asyncio.sleep(0.5)
                await update.message.reply_text(message, parse_mode='Markdown')
        
        # Handle Function 10 which returns dict with messages and operators for clickable buttons
        elif analysis["function_name"] == "get_operators_by_geographic_locations" and isinstance(response_text, dict):
            messages = response_text.get("messages", [])
            operators = response_text.get("operators", [])
            
            # Send all messages in sequence
            for i, message in enumerate(messages):
                if i > 0:
                    # Add small delay between messages to avoid rate limiting
                    import asyncio
                    await asyncio.sleep(0.5)
                
                # Add keyboard to the last message if we have operators
                if i == len(messages) - 1 and operators:
                    keyboard = []
                    for op in operators:
                        # Encode operator name to handle special characters like &
                        encoded_name = urllib.parse.quote(op['name'], safe='')
                        callback_data = f"select_operator_geo_{encoded_name}"
                        keyboard.append([InlineKeyboardButton(op['button_text'], callback_data=callback_data)])
                    
                    # Add additional buttons
                    keyboard.append([
                        InlineKeyboardButton("🔍 Search Again", callback_data="search_again"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await update.message.reply_text(message, parse_mode='Markdown')
        
        # Handle Function 12 which returns dict with operators and clickable buttons
        elif analysis["function_name"] == "aircraft_to_destination_search" and isinstance(response_text, dict):
            message_text = response_text.get("message", "")
            operators = response_text.get("operators", [])
            
            # Create operator buttons (Function 10 style, linking to Function 8)
            if operators:
                keyboard = []
                for op in operators:
                    # Encode operator name to handle special characters like &
                    encoded_name = urllib.parse.quote(op['name'], safe='')
                    callback_data = f"select_operator_func12_{encoded_name}"
                    button_text = f"📋 {op['name']} Details"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                
                # Add additional buttons
                keyboard.append([
                    InlineKeyboardButton("🔍 New Search", callback_data="search_again"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await send_large_message(update.message, message_text, reply_markup)
            else:
                await update.message.reply_text(message_text, parse_mode='Markdown')
        else:
            # Standard message handling - split long messages (Telegram has 4096 char limit)
            if len(response_text) > 4000:
                chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response_text)
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong. Please try again later or contact support."
        )

# ============ Function 8: Operator Details with Clickable Buttons ============

async def handle_operator_search(update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str) -> None:
    """Handle operator search with clickable button interface."""
    try:
        # Call Function 8 in search mode
        results = await call_supabase_function("get_operator_details", {"search_query": search_query})
        
        if results.get("result_type") == "search_results":
            # Multiple operators found - show selection buttons
            operators = results.get("operators_found", [])
            
            if not operators:
                await update.message.reply_text(f"❌ No operators found matching '{search_query}'")
                return
            
            # Create message text
            message_text = f"🔍 **Search results for '{search_query}':**\n\n"
            
            # Create buttons for each operator
            keyboard = []
            for operator in operators:
                # Get appropriate emoji based on operator type
                emoji = get_operator_emoji(operator)
                
                # Create button text
                iata = operator.get('operator_iata_code') or '--'
                icao = operator.get('operator_icao_code') or '--'
                button_text = f"{emoji} {operator['operator']} ({iata}/{icao})"
                
                # Add operator info to message
                message_text += f"{emoji} **{operator['operator']}** ({iata}/{icao})\n"
                message_text += f"   ✈️ {operator['aircraft_count']} aircraft ({operator['freighter_percentage']}% freighter)\n\n"
                
                # Create callback data for button
                callback_data = f"select_operator_{operator['selection_id']}_{operator['operator']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add additional buttons
            keyboard.append([
                InlineKeyboardButton("🔍 Search Again", callback_data="search_again"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ])
            
            # Store search context for callback handling
            context.user_data['operator_search'] = {
                'query': search_query,
                'operators': operators
            }
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            # Single operator or direct details
            response_text = format_operator_details(results)
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in operator search: {e}")
        await update.message.reply_text(f"❌ Error searching for '{search_query}'. Please try again.")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards."""
    query = update.callback_query
    
    try:
        callback_data = query.data
        
        if callback_data.startswith("select_operator_"):
            # Handle regular, geographic, and Function 12 operator selections
            is_geographic_selection = callback_data.startswith("select_operator_geo_")
            is_func12_selection = callback_data.startswith("select_operator_func12_")
            
            if is_geographic_selection:
                # Geographic operator selection (Function 10) - preserve original results
                encoded_name = callback_data.replace("select_operator_geo_", "")
                operator_name = urllib.parse.unquote(encoded_name)
                # Handle HTML entities like &amp; -> &
                operator_name = html.unescape(operator_name)
                logger.info(f"DEBUG: Geographic selection - encoded: {encoded_name}, decoded: {operator_name}")
            elif is_func12_selection:
                # Function 12 operator selection - preserve original results
                encoded_name = callback_data.replace("select_operator_func12_", "")
                operator_name = urllib.parse.unquote(encoded_name)
                # Handle HTML entities like &amp; -> &
                operator_name = html.unescape(operator_name)
                logger.info(f"DEBUG: Function 12 selection - encoded: {encoded_name}, decoded: {operator_name}")
            else:
                # Regular operator selection (Function 8 search) - replace message
                parts = callback_data.split("_", 3)
                if len(parts) >= 4:
                    selection_id = parts[2]
                    operator_name = parts[3]
                else:
                    return
            
            # Clean operator name - try to fix common issues like Icel&air -> Icelandair
            cleaned_operator_name = operator_name
            if "icel&air" in operator_name.lower():
                # Handle Icelandair specifically - database has 'Icelandair' not 'Icel&air'
                cleaned_operator_name = "Icelandair"  # Fix the corruption
            elif "&" in operator_name and "icel" not in operator_name.lower():
                # Only apply general & replacement for non-Icelandair operators
                cleaned_operator_name = operator_name.replace("&", " and ")
            
            logger.info(f"DEBUG: Original operator: {operator_name}, Cleaned: {cleaned_operator_name}")
            
            # Get full operator details using Function 8
            results = await call_supabase_function("get_operator_details", {"operator_selection": cleaned_operator_name})
            
            # Format and display results
            response_text = format_operator_details(results)
            
            if is_geographic_selection or is_func12_selection:
                # For Function 10 and 12: Send new message to preserve original results
                # Use send_large_message to handle long operator profiles
                await send_large_message(query.message, response_text, create_details_keyboard(operator_name))
                # Acknowledge the button click
                await query.answer("✅ Operator details loaded!")
            else:
                # For Function 8: Handle large messages by splitting if needed
                try:
                    await query.edit_message_text(
                        text=response_text,
                        parse_mode='Markdown',
                        reply_markup=create_details_keyboard(operator_name)
                    )
                except Exception as e:
                    if "Message_too_long" in str(e) or "Bad Request" in str(e):
                        # Split large message into multiple parts
                        await send_large_message(query.message, response_text, create_details_keyboard(operator_name))
                    else:
                        raise e
                await query.answer()
            
        # Smart Preset Mismatch Handlers
        elif callback_data.startswith("switch_to_"):
            # User wants to switch to the suggested function
            new_function = callback_data.replace("switch_to_", "")
            pending_query = context.user_data.get('pending_query')
            
            if pending_query:
                # Re-analyze with the correct function
                if new_function == 'get_operators_by_geographic_locations':
                    analysis = await analyze_geographic_query_with_openai(pending_query)
                else:
                    analysis = await analyze_query_with_openai(pending_query)
                
                if analysis:
                    analysis['function_name'] = new_function
                    context.user_data['selected_function'] = new_function
                    
                    results = await call_supabase_function(
                        analysis["function_name"], 
                        analysis["parameters"]
                    )
                    
                    response_text = format_results_for_telegram(results, analysis["function_name"])
                    await send_large_message(query.message.chat.id, response_text, context)
                    
                    # Clean up
                    context.user_data.pop('pending_analysis', None)
                    context.user_data.pop('pending_query', None)
                    
                    await query.edit_message_text("✅ **Switched and executed successfully!**")
                else:
                    await query.edit_message_text("❌ **Error re-analyzing query**")
            
        elif callback_data.startswith("keep_"):
            # User wants to keep their selected function
            selected_function = callback_data.replace("keep_", "")
            pending_query = context.user_data.get('pending_query')
            
            if pending_query:
                # Force execute with selected function (may give unexpected results)
                if selected_function == 'get_operators_by_geographic_locations':
                    analysis = await analyze_geographic_query_with_openai(pending_query)
                else:
                    analysis = await analyze_query_with_openai(pending_query)
                
                if analysis:
                    analysis['function_name'] = selected_function
                    
                    results = await call_supabase_function(
                        analysis["function_name"], 
                        analysis["parameters"]
                    )
                    
                    response_text = format_results_for_telegram(results, analysis["function_name"])
                    await send_large_message(query.message.chat.id, response_text, context)
                    
                    # Clean up
                    context.user_data.pop('pending_analysis', None)
                    context.user_data.pop('pending_query', None)
                    
                    await query.edit_message_text("✅ **Executed with your selected function!**")
                else:
                    await query.edit_message_text("❌ **Error processing with selected function**")
        
        elif callback_data == "clear_selection":
            # User wants to clear selection and use auto-detect
            pending_query = context.user_data.get('pending_query')
            
            if pending_query:
                # Clear selection and execute with natural function
                context.user_data.pop('selected_function', None)
                
                # Re-analyze without preset function
                analysis = await analyze_query_with_openai(pending_query)
                
                if analysis:
                    results = await call_supabase_function(
                        analysis["function_name"], 
                        analysis["parameters"]
                    )
                    
                    response_text = format_results_for_telegram(results, analysis["function_name"])
                    await send_large_message(query.message.chat.id, response_text, context)
                    
                    # Clean up
                    context.user_data.pop('pending_analysis', None)
                    context.user_data.pop('pending_query', None)
                    
                    await query.edit_message_text("✅ **Selection cleared - using auto-detection!**")
                else:
                    await query.edit_message_text("❌ **Error with auto-detection**")

        # Function 12 Aircraft Selection Handlers
        elif callback_data.startswith("func12_aircraft_"):
            # Handle individual aircraft selection toggle
            aircraft_type = callback_data.replace("func12_aircraft_", "")
            selected_aircraft = context.user_data.get('selected_aircraft', [])
            
            if aircraft_type in selected_aircraft:
                selected_aircraft.remove(aircraft_type)
                await query.answer(f"❌ {aircraft_type} removed")
            else:
                selected_aircraft.append(aircraft_type)
                await query.answer(f"✅ {aircraft_type} selected")
            
            context.user_data['selected_aircraft'] = selected_aircraft
            
            # Update the menu display
            available_aircraft = context.user_data.get('available_aircraft', [])
            await update_aircraft_selection_menu(query, context, available_aircraft)
            
        elif callback_data == "func12_select_all":
            # Select all aircraft types
            available_aircraft = context.user_data.get('available_aircraft', [])
            all_types = [a.get('aircraft_type') for a in available_aircraft]
            context.user_data['selected_aircraft'] = all_types
            
            await update_aircraft_selection_menu(query, context, available_aircraft)
            await query.answer("✅ All aircraft selected!")
            
        elif callback_data == "func12_clear_all":
            # Clear all selections
            context.user_data['selected_aircraft'] = []
            available_aircraft = context.user_data.get('available_aircraft', [])
            
            await update_aircraft_selection_menu(query, context, available_aircraft)
            await query.answer("🗑️ All selections cleared!")
            
        elif callback_data == "func12_continue":
            # Continue to destination selection
            selected_aircraft = context.user_data.get('selected_aircraft', [])
            if not selected_aircraft:
                await query.answer("❌ Please select at least one aircraft type!")
                return
            
            # Move to destination input step
            await show_destination_input_step(update, context, selected_aircraft)
            await query.answer()
            
        elif callback_data == "func12_cancel":
            # Cancel Function 12
            context.user_data.pop('func12_step', None)
            context.user_data.pop('selected_aircraft', None)
            context.user_data.pop('available_aircraft', None)
            
            await query.edit_message_text("❌ Aircraft-to-Destination search cancelled.")
            await query.answer()
            
        elif callback_data == "search_again":
            await query.edit_message_text("🔍 Enter operator name, IATA, or ICAO code to search:")
            await query.answer()
            
        elif callback_data == "cancel":
            await query.edit_message_text("❌ Search cancelled.")
            await query.answer()
            
        elif callback_data == "new_search":
            await query.edit_message_text("🔍 Enter operator name, IATA, or ICAO code for new search:")
            await query.answer()
            
        # Function Selection Handlers
        elif callback_data.startswith("select_func_"):
            func_id = callback_data.split("_")[-1]
            
            if func_id == "1":
                # Send new message instead of editing the pinned menu
                await query.message.reply_text(
                    "🏢 **Operators by Destination Selected** ✅\n\n"
                    "Enter your query for finding operators flying to a specific airport.\n\n"
                    "**Examples:**\n"
                    "• \"Who flies to LAX?\"\n"
                    "• \"Operators to SCL\"\n"
                    "• \"Airlines flying to TLV\"\n\n"
                    "💬 **Type your query now:**\n"
                    "💡 **This selection will stay active until you change it**\n\n"
                    "📌 **Function menu remains pinned above for easy switching**"
                )
                context.user_data['selected_function'] = 'get_operators_by_destination'
                
            elif func_id == "8":
                # Send new message instead of editing the pinned menu
                await query.message.reply_text(
                    "🔍 **Operator Details Selected** ✅\n\n"
                    "Enter operator name, IATA, or ICAO code for detailed analysis.\n\n"
                    "**Examples:**\n"
                    "• \"FedEx details\"\n"
                    "• \"Operator details UPS\"\n"
                    "• \"Show operator AA\"\n\n"
                    "💬 **Type your query now:**\n"
                    "💡 **This selection will stay active until you change it**\n\n"
                    "📌 **Function menu remains pinned above for easy switching**"
                )
                context.user_data['selected_function'] = 'get_operator_details'
                
            elif func_id == "9":
                # Send new message instead of editing the pinned menu
                await query.message.reply_text(
                    "🗺️ **Multi-Destination Operators Selected** ✅\n\n"
                    "Enter your query for finding operators serving multiple airports.\n\n"
                    "**Examples:**\n"
                    "• \"Operators to both JFK and LAX\"\n"
                    "• \"Which airlines fly to both HKG and NRT?\"\n\n"
                    "💬 **Type your query now:**\n"
                    "💡 **This selection will stay active until you change it**\n\n"
                    "📌 **Function menu remains pinned above for easy switching**"
                )
                context.user_data['selected_function'] = 'get_operators_by_multi_destinations'
                
            elif func_id == "10":
                # Send new message instead of editing the pinned menu
                await query.message.reply_text(
                    "🌍 **Geographic Operators Selected** ✅\n\n"
                    "Enter your query for finding operators between countries, continents, or airports.\n\n"
                    "**Examples:**\n"
                    "• \"PEK to SCL operators\" (airport to airport)\n"
                    "• \"China to Chile operators\" (country to country)\n"
                    "• \"Korea to Taiwan operators\"\n\n"
                    "💬 **Type your query now:**\n"
                    "💡 **This selection will stay active until you change it**\n\n"
                    "📌 **Function menu remains pinned above for easy switching**"
                )
                context.user_data['selected_function'] = 'get_operators_by_geographic_locations'
                
            elif func_id == "12":
                # Start Function 12 immediately with aircraft selection
                context.user_data['selected_function'] = 'aircraft_to_destination_search'
                
                # Send confirmation message
                await query.message.reply_text(
                    "✈️ **Aircraft-to-Destination Search Selected** ✅\n\n"
                    "Starting aircraft selection menu...",
                    parse_mode='Markdown'
                )
                
                # Immediately start aircraft selection
                await start_aircraft_selection_from_callback(query, context)
            
            await query.answer()
            
        elif callback_data == "cancel_selection":
            # Send new message instead of editing the pinned menu
            await query.message.reply_text("❌ Function selection cancelled. You can type any query or use /selectfunction again.")
            await query.answer()
            
        elif callback_data == "unpin_menu":
            try:
                # Unpin the current message
                await context.bot.unpin_chat_message(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id
                )
                # Send new message instead of editing the pinned menu
                await query.message.reply_text("📌 **Function menu unpinned**\n\nYou can still use /selectfunction to show the menu again.")
                logger.info("✅ Function selection menu unpinned successfully")
            except Exception as e:
                logger.error(f"❌ Failed to unpin message: {e}")
                await query.message.reply_text("❌ Failed to unpin menu. You can still use /selectfunction to show the menu again.")
            await query.answer()
        
        # ENHANCED: Geographic filtering handlers for Function 8
        elif callback_data.startswith("geo_filter_"):
            filter_parts = callback_data.split("_", 3)
            if len(filter_parts) >= 4:
                filter_type = filter_parts[2]  # "country" or "continent"
                operator_name = filter_parts[3].replace("_", " ").replace("and", "&")
                
                if filter_type == "country":
                    await query.message.reply_text(
                        f"🌍 **Country Filter for {operator_name}**\n\n"
                        "Enter the country name to see destinations:\n\n"
                        "**Examples:**\n"
                        "• China\n"
                        "• Germany\n"
                        "• United States\n"
                        "• Japan\n"
                        "• United Kingdom\n\n"
                        "💬 **Type country name:**"
                    )
                    context.user_data['awaiting_country_filter'] = operator_name
                    
                elif filter_type == "continent":
                    await query.message.reply_text(
                        f"🗺️ **Continent Filter for {operator_name}**\n\n"
                        "Enter the continent name to see destinations:\n\n"
                        "**Examples:**\n"
                        "• Asia\n"
                        "• Europe\n"
                        "• North America\n"
                        "• South America\n"
                        "• Africa\n"
                        "• Oceania\n\n"
                        "💬 **Type continent name:**"
                    )
                    context.user_data['awaiting_continent_filter'] = operator_name
                    
            await query.answer()
            
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        await query.answer("❌ Error occurred")
        await query.edit_message_text("❌ Error processing selection. Please try again.")

def get_operator_emoji(operator: dict) -> str:
    """Get appropriate emoji based on operator type."""
    freighter_percentage = operator.get('freighter_percentage', 0)
    
    if freighter_percentage > 80:
        return "🚛"  # Freighter
    elif freighter_percentage > 20:
        return "📦"  # Mixed
    else:
        return "✈️"  # Passenger

def create_details_keyboard(operator_name: str = "") -> InlineKeyboardMarkup:
    """Create enhanced keyboard for operator details view with geographic filtering."""
    keyboard = []
    
    # ENHANCED: Add geographic filtering buttons if we have an operator
    if operator_name:
        # Clean operator name for callback data (remove spaces and special chars)
        clean_operator = operator_name.replace(" ", "_").replace("&", "and")
        
        keyboard.extend([
            [
                InlineKeyboardButton("🌍 Filter by Country", 
                                   callback_data=f"geo_filter_country_{clean_operator}"),
                InlineKeyboardButton("🗺️ Filter by Continent", 
                                   callback_data=f"geo_filter_continent_{clean_operator}")
            ]
        ])
    
    # Standard buttons
    keyboard.append([InlineKeyboardButton("🔄 New Search", callback_data="new_search")])
    
    return InlineKeyboardMarkup(keyboard)

def format_operator_details(results: dict) -> str:
    """Format operator details for Telegram display."""
    if results.get("result_type") != "operator_details":
        return "❌ Invalid operator details format"
    
    operator_details = results.get("operator_details", {})
    fleet_breakdown = results.get("fleet_breakdown", [])
    fleet_summary = results.get("fleet_summary", {})
    top_destinations = results.get("top_destinations", [])
    
    # Header
    operator_name = operator_details.get("operator_name", "Unknown")
    iata = operator_details.get("operator_iata_code") or "--"
    icao = operator_details.get("operator_icao_code") or "--"
    
    message = f"✈️ **OPERATOR PROFILE: {operator_name.upper()} ({iata}/{icao})**\n"
    message += f"📅 *Analysis Period: {operator_details.get('period_start')} to {operator_details.get('period_end')}*\n\n"
    
    # Fleet Summary
    total_aircraft = fleet_summary.get("total_aircraft", 0)
    freighter_pct = fleet_summary.get("freighter_percentage", 0)
    passenger_pct = fleet_summary.get("passenger_percentage", 0)
    unique_types = fleet_summary.get("unique_aircraft_types", 0)
    
    message += f"🚁 **FLEET SUMMARY**:\n"
    message += f"📊 *Total Aircraft: {total_aircraft} ({freighter_pct}% freighter, {passenger_pct}% passenger)*\n"
    message += f"🔢 *Aircraft Types: {unique_types} different models*\n\n"
    
    # ENHANCED: Fleet Breakdown (show ALL aircraft)
    if fleet_breakdown:
        message += f"🛩️ **COMPLETE FLEET BREAKDOWN** (All {len(fleet_breakdown)} Aircraft Types):\n"
        for i, aircraft in enumerate(fleet_breakdown, 1):  # ENHANCED: Show ALL aircraft, no limit
            aircraft_type = aircraft.get("aircraft_type", "Unknown")
            aircraft_details = aircraft.get("aircraft_details", "Unknown")
            count = aircraft.get("count", 0)
            category = aircraft.get("aircraft_category", "Unknown")
            registrations = aircraft.get("registrations", [])
            
            # Show category emoji
            category_emoji = "🚛" if category == "Freighter" else "✈️"
            
            message += f"{i}. **{aircraft_details}** ({count} aircraft) - {category} {category_emoji}\n"
            
            # ENHANCED: Show ALL registrations, no truncation
            if registrations:
                reg_display = ", ".join(registrations)  # Show all registrations
                message += f"   • {reg_display}\n"
        message += "\n"
    
    # ENHANCED: Top Destinations (show top 30)
    if top_destinations:
        message += f"🌍 **TOP 30 DESTINATIONS**:\n"
        for i, dest in enumerate(top_destinations, 1):  # ENHANCED: Show all 30 destinations
            dest_code = dest.get("destination_code", "Unknown")
            total_flights = dest.get("total_flights", 0)
            aircraft_types = dest.get("aircraft_types_used", [])
            avg_monthly = dest.get("avg_flights_per_month", 0)
            
            message += f"{i}. **{dest_code}**: {total_flights:,} flights ({avg_monthly} avg/month)\n"
            if aircraft_types:
                types_display = ", ".join(aircraft_types[:3])  # Show first 3 aircraft types
                message += f"   • Aircraft: {types_display}\n"
        
        # ENHANCED: Add geographic filtering call-to-action
        message += "\n🌍 **GEOGRAPHIC FILTERING AVAILABLE**\n"
        message += "Use the buttons below to filter destinations by country or continent:\n\n"
    
    return message

def format_geographic_destinations(results: dict, operator_name: str, geography_name: str, filter_type: str) -> str:
    """Format geographic destination filtering results."""
    if results.get("error"):
        return f"❌ {results['error']}"
    
    geographic_destinations = results.get("geographic_destinations", [])
    
    if not geographic_destinations:
        return (f"❌ No destinations found for **{operator_name}** in **{geography_name}**\n\n"
                f"This could mean:\n"
                f"• {operator_name} doesn't serve {geography_name}\n"
                f"• Geographic data not available\n"
                f"• Spelling variation (try alternative names)")
    
    # Build the response message
    total_destinations = len(geographic_destinations)
    total_flights = sum(dest.get('total_flights', 0) for dest in geographic_destinations)
    
    flag_emoji = "🌍" if filter_type == "country" else "🗺️"
    message = f"{flag_emoji} **{operator_name} Destinations in {geography_name}**\n\n"
    message += f"📊 **Summary:** {total_destinations} airports, {total_flights:,} total flights\n\n"
    
    # List each destination with aircraft breakdown
    for i, dest in enumerate(geographic_destinations, 1):
        dest_code = dest.get('destination_code', 'Unknown')
        airport_name = dest.get('airport_name', 'Unknown Airport')
        total_flights = dest.get('total_flights', 0)
        aircraft_types = dest.get('aircraft_types_used', [])
        avg_monthly = dest.get('avg_flights_per_month', 0)
        
        message += f"{i}. **{dest_code}** - {airport_name}\n"
        message += f"   🛫 {total_flights:,} flights ({avg_monthly} avg/month)\n"
        
        if aircraft_types:
            aircraft_display = ", ".join(aircraft_types[:4])  # Show first 4 aircraft types
            if len(aircraft_types) > 4:
                aircraft_display += f" (+{len(aircraft_types) - 4} more)"
            message += f"   ✈️ Aircraft: {aircraft_display}\n"
        
        message += "\n"
    
    message += f"🔄 **Use the button below to return to full {operator_name} details**"
    
    return message

def is_operator_search_query(query: str) -> bool:
    """Check if query is asking for operator details."""
    operator_keywords = [
        "operator details", "operator info", "fleet breakdown", "show operator",
        "operator profile", "airline details", "carrier details", "airline info"
    ]
    
    query_lower = query.lower()
    
    # Check for exact phrase matches
    if any(keyword in query_lower for keyword in operator_keywords):
        return True
    
    # Check for flexible patterns: "operator [code] details" or "[code] operator details"
    words = query_lower.split()
    has_operator = "operator" in words
    has_details = any(word in words for word in ["details", "info", "profile", "breakdown"])
    
    return has_operator and has_details

def extract_operator_from_query(query: str) -> str:
    """Extract operator search term from query."""
    # Remove common prefixes
    prefixes_to_remove = [
        "operator details", "operator info", "fleet breakdown", "show operator",
        "operator profile", "airline details", "carrier details", "airline info",
        "details for", "info for", "show", "get"
    ]
    
    query_clean = query.lower()
    
    # Try exact prefix removal first
    for prefix in prefixes_to_remove:
        if query_clean.startswith(prefix):
            query_clean = query_clean[len(prefix):].strip()
            break
    else:
        # Handle flexible patterns like "operator FX details" or "FX operator details"
        words = query_clean.split()
        # Remove operator-related and detail-related words
        words_to_remove = ["operator", "details", "info", "profile", "breakdown", "show", "get", "for"]
        query_clean = " ".join(word for word in words if word not in words_to_remove)
    
    return query_clean.strip()

def format_geographic_destinations(results: dict, operator_name: str, geography_input: str, filter_type: str) -> str:
    """Format geographic destination results for Function 8 geographic filtering."""
    if results.get("error"):
        return f"❌ {results['error']}"
    
    destinations = results.get("geographic_destinations", [])
    
    if not destinations:
        return f"❌ No destinations found for {operator_name} in {geography_input}. Try alternative spelling or check if operator serves this region."
    
    # Create header
    filter_emoji = "🌍" if filter_type == "continent" else "🏳️"
    message = f"{filter_emoji} **{operator_name} Destinations in {geography_input}**\n\n"
    message += f"📊 **Summary:** {len(destinations)} airports, {sum(d.get('total_flights', 0) for d in destinations):,} total flights\n\n"
    
    # List destinations (limit to prevent message too long error)
    display_limit = 25  # Limit to prevent Telegram message length issues
    
    for i, dest in enumerate(destinations[:display_limit], 1):
        airport_name = dest.get('airport_name', 'Unknown')
        iata_code = dest.get('destination_code', '???')
        country = dest.get('country_name', 'Unknown')
        continent = dest.get('continent', 'Unknown')
        total_flights = dest.get('total_flights', 0)
        avg_monthly = dest.get('avg_flights_per_month', 0)
        aircraft_types = dest.get('aircraft_types_used', [])
        
        message += f"{i}. **{airport_name}** ({iata_code})\n"
        message += f"   📍 {country}, {continent}\n"
        message += f"   ✈️ {total_flights:,} flights ({avg_monthly} avg/month)\n"
        
        if aircraft_types:
            types_display = ", ".join(aircraft_types[:3])
            if len(aircraft_types) > 3:
                types_display += f" (+{len(aircraft_types) - 3} more)"
            message += f"   🛩️ Aircraft: {types_display}\n"
        
        message += "\n"
    
    # Add truncation notice if needed
    if len(destinations) > display_limit:
        message += f"... and {len(destinations) - display_limit} more destinations\n\n"
        message += f"💡 *Showing top {display_limit} destinations to prevent message length issues*\n"
    
    return message

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}")

def main() -> None:
    """Start the bot."""
    
    print("🤖 Starting FlightRadar Telegram Bot...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("examples", examples_command))
    application.add_handler(CommandHandler("functions", functions_command))
    application.add_handler(CommandHandler("selectfunction", selectfunction_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))  # Handle button clicks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print("✅ Bot is ready! Send /start to begin.")
    print("📱 Find your bot on Telegram and start chatting!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
