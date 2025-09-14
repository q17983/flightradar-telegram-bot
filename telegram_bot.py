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

async def analyze_query_with_openai(user_query: str) -> dict:
    """Use OpenAI to analyze user query and determine intent."""
    
    prompt = f"""
You are a flight data assistant for a cargo charter broker. Analyze this query and return the best function to call from the 4 CORE FUNCTIONS only.

CORE FUNCTIONS ONLY:
{json.dumps(FUNCTION_MAP, indent=2)}

User query: "{user_query}"

CRITICAL RULES:
- ALWAYS use the full database range: start_time: "2024-04-01", end_time: "2025-05-31"
- IGNORE any specific dates mentioned by user - always use the full 408-day period
- Use EXACT airport codes (3-letter IATA) like LAX, JFK, LHR, DXB, SCL
- Use EXACT country names - DO NOT TRANSLATE: "Korea" stays "Korea", "Korean" refers to "Korea"

COUNTRY/CONTINENT MAPPING (DO NOT TRANSLATE):
- Korea/Korean → "South Korea" (NOT Japan/JPN, NOT "Korea")
- Taiwan/Taiwanese → "Taiwan" 
- China/Chinese → "China"
- Japan/Japanese → "Japan"  
- Thailand/Thai → "Thailand"
- Germany/German → "Germany"
- Continents: Asia, Europe, North America, South America, Africa, Oceania

FUNCTION SELECTION LOGIC:
1. "who flies to [AIRPORT]" → get_operators_by_destination
   Example: "who flies to LAX" → destination_code: "LAX"

2. "operator details [NAME]" or "show operator [NAME]" → get_operator_details
   Example: "operator details FedEx" → search_query: "FedEx"

3. "operators to both [X] and [Y]" or "which operators fly to both" → get_operators_by_multi_destinations
   Example: "operators to both JFK and LAX" → destination_codes: ["JFK", "LAX"]

4. "[LOCATION] to [LOCATION] operators" or geographic queries → get_operators_by_geographic_locations
   Example: "Korea to Japan operators" → first_location_type: "country", first_location_value: "South Korea", second_location_type: "country", second_location_value: "Japan"
   Example: "China to SCL operators" → first_location_type: "country", first_location_value: "China", second_location_type: "airport", second_location_value: "SCL"

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user_query = update.message.text
    user_name = update.message.from_user.first_name or "User"
    
    logger.info(f"Query from {user_name}: {user_query}")
    
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
        response_text = format_results_for_telegram(results, analysis["function_name"])
        
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
                        callback_data = f"select_operator_geo_{op['name']}"
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
            # Handle both regular operator selection and geographic operator selection
            is_geographic_selection = callback_data.startswith("select_operator_geo_")
            
            if is_geographic_selection:
                # Geographic operator selection (Function 10) - preserve original results
                operator_name = callback_data.replace("select_operator_geo_", "")
            else:
                # Regular operator selection (Function 8 search) - replace message
                parts = callback_data.split("_", 3)
                if len(parts) >= 4:
                    selection_id = parts[2]
                    operator_name = parts[3]
                else:
                    return
            
            # Get full operator details using Function 8
            results = await call_supabase_function("get_operator_details", {"operator_selection": operator_name})
            
            # Format and display results
            response_text = format_operator_details(results)
            
            if is_geographic_selection:
                # For Function 10: Send new message to preserve original results
                await query.message.reply_text(
                    text=response_text,
                    parse_mode='Markdown',
                    reply_markup=create_details_keyboard()
                )
                # Acknowledge the button click
                await query.answer("✅ Operator details loaded!")
            else:
                # For Function 8: Edit the message to show full details
                await query.edit_message_text(
                    text=response_text,
                    parse_mode='Markdown',
                    reply_markup=create_details_keyboard()
                )
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

def create_details_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for operator details view."""
    keyboard = [
        [InlineKeyboardButton("🔄 New Search", callback_data="new_search")]
    ]
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
    
    # Fleet Breakdown (show top 10)
    if fleet_breakdown:
        message += f"🛩️ **FLEET BREAKDOWN** (Top 10):\n"
        for i, aircraft in enumerate(fleet_breakdown[:10], 1):
            aircraft_type = aircraft.get("aircraft_type", "Unknown")
            aircraft_details = aircraft.get("aircraft_details", "Unknown")
            count = aircraft.get("count", 0)
            category = aircraft.get("aircraft_category", "Unknown")
            registrations = aircraft.get("registrations", [])
            
            # Show category emoji
            category_emoji = "🚛" if category == "Freighter" else "✈️"
            
            message += f"{i}. **{aircraft_details}** ({count} aircraft) - {category} {category_emoji}\n"
            
            # Show first 5 registrations
            if registrations:
                reg_display = ", ".join(registrations[:5])
                if len(registrations) > 5:
                    reg_display += f"... (+{len(registrations) - 5} more)"
                message += f"   • {reg_display}\n"
        message += "\n"
    
    # Top Destinations (show top 10)
    if top_destinations:
        message += f"🌍 **TOP DESTINATIONS** (Top 10):\n"
        for i, dest in enumerate(top_destinations[:10], 1):
            dest_code = dest.get("destination_code", "Unknown")
            total_flights = dest.get("total_flights", 0)
            aircraft_types = dest.get("aircraft_types_used", [])
            avg_monthly = dest.get("avg_flights_per_month", 0)
            
            message += f"{i}. **{dest_code}**: {total_flights:,} flights ({avg_monthly} avg/month)\n"
            if aircraft_types:
                types_display = ", ".join(aircraft_types[:3])  # Show first 3 aircraft types
                message += f"   • Aircraft: {types_display}\n"
        message += "\n"
    
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
    application.add_handler(CallbackQueryHandler(handle_callback_query))  # Handle button clicks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print("✅ Bot is ready! Send /start to begin.")
    print("📱 Find your bot on Telegram and start chatting!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
