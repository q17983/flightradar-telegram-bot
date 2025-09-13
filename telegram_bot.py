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
import google.generativeai as genai
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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

if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env file.")
    exit()

if not SUPABASE_ANON_KEY:
    print("❌ Error: SUPABASE_ANON_KEY not found in .env file.")
    exit()

# Initialize Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("✅ Gemini AI initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing Gemini: {e}")
    exit()

# Function mapping for Supabase Edge Functions
FUNCTION_MAP = {
    "get_operator_frequency": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-frequency",
        "params": ["origin_code", "destination_code", "start_time", "end_time"],
        "description": "Get frequency of operators flying a specific route"
    },
    "get_operators_by_destination": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-destination",
        "params": ["destination_code", "start_time", "end_time"],
        "description": "Get operators flying TO a destination"
    },
    "get_operators_by_origin": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operators-by-origin",
        "params": ["origin_code", "start_time", "end_time"],
        "description": "Get operators flying FROM an origin"
    },
    "get_operator_route_summary": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-route-summary",
        "params": ["operator_name", "start_time", "end_time"],
        "description": "Get route summary for a specific operator"
    },
    "get_route_details": {
        "url": f"{SUPABASE_URL}/functions/v1/get-route-details",
        "params": ["origin_code", "destination_code", "start_time", "end_time"],
        "description": "Get detailed route information"
    },
    "get_operator_details": {
        "url": f"{SUPABASE_URL}/functions/v1/get-operator-details",
        "params": ["search_query", "operator_selection"],
        "description": "Search for operator details with fleet and route analysis"
    }
}

async def analyze_query_with_gemini(user_query: str) -> dict:
    """Use Gemini to analyze user query and determine intent."""
    
    prompt = f"""
You are a flight data assistant for a cargo charter broker. Analyze this query and return the best function to call.

Available functions:
{json.dumps(FUNCTION_MAP, indent=2)}

User query: "{user_query}"

Rules:
- Use IATA airport codes (3-letter) like LAX, JFK, LHR, DXB
- CRITICAL: ALWAYS use the full database range: start_time: "2024-04-01", end_time: "2025-05-31"
- IGNORE any specific dates mentioned by user - always use the full 408-day period
- The database contains Apr 2024 - May 2025 data, so ALWAYS query the complete range
- For "who flies to X" → get_operators_by_destination
- For "routes from X" → get_operators_by_origin  
- For "[airline] routes" → get_operator_route_summary
- For "X to Y details" → get_route_details
- For "X Y frequency" → get_operator_frequency
- For "[airline] regional origins" → get_operator_origins_by_region
- For "multi-leg" or "complex routing" → calculate_multi_leg_route_metrics

Return JSON:
{{
    "function_name": "function_name",
    "parameters": {{"param": "value"}},
    "reasoning": "explanation"
}}
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
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
        logger.error(f"Error with Gemini: {e}")
        return None

async def call_supabase_function(function_name: str, parameters: dict) -> dict:
    """Call Supabase Edge Function."""
    
    if function_name not in FUNCTION_MAP:
        return {"error": f"Unknown function: {function_name}"}
    
    # FORCE the correct date range regardless of what Gemini suggests
    parameters["start_time"] = "2024-04-01"
    parameters["end_time"] = "2025-05-31"
    
    # Debug: Log the credentials being used
    logger.info(f"Using SUPABASE_URL: {SUPABASE_URL}")
    logger.info(f"Using ANON_KEY (first 20 chars): {SUPABASE_ANON_KEY[:20] if SUPABASE_ANON_KEY else 'None'}...")
    
    url = FUNCTION_MAP[function_name]["url"]
    headers = {
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, json=parameters, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
            
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

def format_results_for_telegram(results: dict, function_name: str) -> str:
    """Format results for Telegram message."""
    
    if "error" in results:
        return f"❌ Error: {results['error']}"
    
    # Handle enhanced Function 1 format (with freighter/passenger breakdown)
    if function_name == "get_operators_by_destination" and "freighter_operators" in results:
        return format_enhanced_destination_results(results)
    
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
🆘 *HELP - Complete Function Guide*

📊 *Available Functions (Apr 2024 - May 2025):*

🎯 *1. Find Carriers by Destination*
• "Who flies to LAX?"
• "Carriers to Dubai"
• "Hong Kong flights"
*Gets all airlines serving a destination*

🛫 *2. Find Routes from Origin*
• "Routes from JFK"
• "London departures"  
• "Tokyo flights"
*Gets all destinations from an origin*

✈️ *3. Airline Route Analysis*
• "Emirates routes"
• "FedEx destinations"
• "Cathay Pacific"
*Gets complete route map for an airline*

🔍 *4. Specific Route Details*
• "JFK to LAX route details"
• "London to New York flights"
• "Dubai to Frankfurt details"
*Gets carriers & frequencies for specific routes*

📈 *5. Route Frequency Analysis*
• "JFK LAX frequency"
• "Dubai London frequency"
*Gets detailed frequency data between two airports*

🌍 *6. Regional Origin Analysis*
• "Emirates origins by region"
• "FedEx regional origins"
*Gets airline origins grouped by geographic regions*

⚡ *7. Multi-leg Route Metrics*
• "Multi-leg route via Dubai"
• "Complex routing analysis"
*Advanced routing calculations for multiple stops*

💡 *Usage Tips:*
• Use 3-letter IATA codes (LAX, JFK, LHR, DXB)
• Data covers Apr 2024 - May 2025 (408 days)
• Shows up to 50 results per query
• Be specific about airlines and airports
• Type /examples for more query examples
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
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Check if this is an operator search query (Function 8)
        if is_operator_search_query(user_query):
            search_term = extract_operator_from_query(user_query)
            if search_term:
                await handle_operator_search(update, context, search_term)
                return
        
        # Analyze query with Gemini for other functions
        analysis = await analyze_query_with_gemini(user_query)
        
        if not analysis:
            await update.message.reply_text(
                "❌ Sorry, I couldn't understand your query. Please try rephrasing it or use /help for examples."
            )
            return
        
        # Debug: Log the analysis result
        logger.info(f"Gemini analysis: {analysis}")
        
        # Call Supabase function
        results = await call_supabase_function(
            analysis["function_name"], 
            analysis["parameters"]
        )
        
        # Debug: Log the results
        logger.info(f"Supabase results: {results}")
        
        # Format and send results
        response_text = format_results_for_telegram(results, analysis["function_name"])
        
        # Split long messages (Telegram has 4096 char limit)
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
    await query.answer()  # Acknowledge the button click
    
    try:
        callback_data = query.data
        
        if callback_data.startswith("select_operator_"):
            # Extract operator selection
            parts = callback_data.split("_", 3)
            if len(parts) >= 4:
                selection_id = parts[2]
                operator_name = parts[3]
                
                # Get full operator details
                results = await call_supabase_function("get_operator_details", {"operator_selection": operator_name})
                
                # Format and display results
                response_text = format_operator_details(results)
                
                # Edit the message to show full details
                await query.edit_message_text(
                    text=response_text,
                    parse_mode='Markdown',
                    reply_markup=create_details_keyboard()
                )
            
        elif callback_data == "search_again":
            await query.edit_message_text("🔍 Enter operator name, IATA, or ICAO code to search:")
            
        elif callback_data == "cancel":
            await query.edit_message_text("❌ Search cancelled.")
            
        elif callback_data == "new_search":
            await query.edit_message_text("🔍 Enter operator name, IATA, or ICAO code for new search:")
            
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
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
    return any(keyword in query_lower for keyword in operator_keywords)

def extract_operator_from_query(query: str) -> str:
    """Extract operator search term from query."""
    # Remove common prefixes
    prefixes_to_remove = [
        "operator details", "operator info", "fleet breakdown", "show operator",
        "operator profile", "airline details", "carrier details", "airline info",
        "details for", "info for", "show", "get"
    ]
    
    query_clean = query.lower()
    for prefix in prefixes_to_remove:
        if query_clean.startswith(prefix):
            query_clean = query_clean[len(prefix):].strip()
            break
    
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
