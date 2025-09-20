# 🎯 FlightRadar Telegram Bot - Complete Project Context Summary

**Last Updated:** September 20, 2025  
**Purpose:** Provide complete project understanding for new conversations  
**Status:** ✅ FULLY OPERATIONAL - All core functions working  

---

## 🚀 **QUICK PROJECT OVERVIEW**

### **What This Project Does:**
A **Telegram bot** that provides **cargo charter flight data analysis** through natural language queries. Users can find operators, routes, aircraft types, and geographic analysis for freight and passenger flights.

### **Core Technology Stack:**
- **Frontend:** Telegram Bot (Python) deployed on Railway
- **Backend:** Supabase Edge Functions (TypeScript/Deno)  
- **Database:** PostgreSQL with 1.28M flight records (Apr 2024 - May 2025)
- **AI:** OpenAI GPT-4 for query analysis
- **Data Source:** FlightRadar24 scraping (12,742 aircraft tracked)

---

## 📱 **WORKING FUNCTIONS (ALL OPERATIONAL)**

### **Function 1: Operators by Destination**
- **Query:** "Who flies to LAX?" 
- **Returns:** All operators serving a destination with freight/passenger breakdown
- **Status:** ✅ Working, 50,000 record limit, complete freighter detection

### **Function 8: Operator Details** 
- **Query:** "Operator details FedEx"
- **Returns:** Complete fleet breakdown + route analysis + geographic filtering buttons
- **Status:** ✅ Working, geographic filtering fixed (Icelandair issue resolved)
- **Features:** Clickable buttons, country/continent filtering, operator profiles

### **Function 9: Multi-Destination Operators**
- **Query:** "Operators to both JFK and LAX"
- **Returns:** Operators serving multiple specified airports
- **Status:** ✅ Working, 50,000 record limit

### **Function 10: Geographic Operators**
- **Query:** "China to SCL operators" or "airport GUM and Continent AS"
- **Returns:** Operators serving between countries/continents/airports
- **Status:** ✅ Working, 50,000 record limit with warning (not error)
- **Recent Fix:** Now processes 50,000 records + shows warning instead of error

### **Function 12: Aircraft-to-Destination Search**
- **Query:** "A330 B777 to China Japan" 
- **Returns:** Operators with specific aircraft types to destinations
- **Status:** ✅ Working, 50,000 record limit, pagination fixed

---

## 🎯 **CRITICAL TECHNICAL DETAILS**

### **Data Accuracy Standards (HIGHEST PRIORITY):**
- **Core Principle:** ACCURACY OVER SPEED
- **Record Limits:** 50,000 for search functions, reasonable limits for display
- **Freighter Detection:** Complete logic with 15+ aircraft classification rules
- **Coverage:** Complete time range (Apr 2024 - May 2025), all operators, no data loss

### **Recent Major Issues Resolved:**
1. **Icelandair Geographic Filtering Crisis (Sep 20, 2025)** - ✅ RESOLVED
   - Root cause: Operator name corruption (`"Icel&air"` vs `"Icelandair"`)
   - Solution: Added operator name cleaning in geographic filter handler
   - Status: All geographic filtering now works for all operators

2. **50,000 Record Limit Behavior** - ✅ IMPROVED  
   - Before: Showed error when hitting 50,000 records
   - After: Processes 50,000 records + shows warning about potential additional data

3. **Function 12 Pagination** - ✅ FIXED
   - Issue: Only 1 page visible, operator buttons not accessible
   - Solution: Separate main content from operator buttons in different messages

4. **Special Characters in Operator Names** - ✅ FIXED
   - Issue: Operators with `&` characters causing callback data corruption
   - Solution: URL encoding/decoding + operator name cleaning

5. **Callback System Implementation** - ✅ RESOLVED (Sep 20, 2025)
   - Issue: Multiple callback handling errors (read-only attributes, text length, object types)
   - Solution: MockMessage/MockUpdate pattern to reuse existing message handlers
   - Note: Large datasets in callbacks remain challenging (use direct function for 100+ operators)

---

## 🏗️ **SYSTEM ARCHITECTURE**

### **File Structure:**
```
/Users/sai/Flightradar crawling/
├── telegram_bot.py                 # Main bot (Railway deployment)
├── supabase/functions/             # Backend functions (Supabase)
│   ├── get-operators-by-destination/
│   ├── get-operator-details/       # Function 8 (most complex)
│   ├── get-operators-by-multi-destinations/
│   ├── get-operators-by-geographic-locations/  # Function 10
│   └── aircraft-to-destination-search/         # Function 12
├── requirements.txt                # Python dependencies
├── Procfile                       # Railway deployment config
└── flightradar_scraper/           # Legacy directory with docs
```

### **Deployment Workflow:**
1. **Code Changes:** Edit files locally
2. **Supabase Functions:** Deploy with `npx supabase functions deploy FUNCTION_NAME`
3. **Telegram Bot:** Auto-deploys to Railway on `git push origin main`
4. **Testing:** Use live Telegram bot (no local testing needed per user preference)

---

## 🔧 **DEVELOPMENT ENVIRONMENT SETUP**

### **Required Environment Variables:**
```bash
# In Railway dashboard (for telegram bot):
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key  
SUPABASE_URL=https://prcnxrkyjnpljoqiazkp.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key

# In Supabase function environment:
DATABASE_URL=postgresql://connection_string
```

### **Key Commands:**
```bash
# Deploy specific function to Supabase
npx supabase functions deploy FUNCTION_NAME

# Deploy bot to Railway (automatic on git push)
git add . && git commit -m "message" && git push origin main

# Check function logs
# Go to: https://supabase.com/dashboard → Functions → FUNCTION_NAME → Logs
```

---

## 📊 **DATA STRUCTURE & BUSINESS LOGIC**

### **Core Database Tables:**
- **movements:** Flight movement records (1.28M records)
- **aircraft:** Aircraft details with operator information (12,742 aircraft)
- **airports_geography:** Airport location data with country/continent mapping

### **Key Data Relationships:**
```sql
movements.registration → aircraft.registration → aircraft.operator
movements.destination_code → airports_geography.iata_code → country/continent
```

### **Freighter Detection Logic (CRITICAL):**
Complex CASE statement with 15+ rules to classify aircraft as 'Freighter' vs 'Passenger':
- Explicit terms: FREIGHTER, CARGO, BCF, BDSF, SF
- Pattern matching: -F patterns, F variants
- Exclusions: Military (FK), VIP, Tanker variants
- **Status:** Complete logic implemented in all functions

---

## 🚨 **KNOWN ISSUES & SOLUTIONS**

### **Operator Name Corruption (RESOLVED):**
- **Issue:** `"Icelandair"` becomes `"Icel&air"` in callback data
- **Solution:** Operator name cleaning in both callback handler AND geographic filter handler
- **Code Location:** `telegram_bot.py` lines ~1574 and ~1901

### **Message Length Handling:**
- **Tool:** `send_large_message()` function for splitting long messages
- **Usage:** Used for operator profiles, search results, geographic analysis
- **Telegram Limit:** 4096 characters, we use 4000 for safety

### **Special Characters in Callback Data:**
- **Solution:** URL encoding with `urllib.parse.quote()` and `urllib.parse.unquote()`
- **Applied:** All operator button creation and handling

---

## 🎯 **USER PREFERENCES & REQUIREMENTS**

### **Explicit User Preferences:**
1. **Data Accuracy Over Speed:** Willing to wait longer for complete data
2. **No Local Bot Testing:** Deploy directly to Railway for testing
3. **50,000 Record Processing:** Process data + show warning, don't show error
4. **Complete Coverage:** Prefer comprehensive results over fast incomplete results

### **Data Quality Standards:**
- **No Data Loss:** `HAVING COUNT(*) >= 1` (not >= 2)
- **Complete Time Range:** Full Apr 2024 - May 2025 coverage
- **All Operators:** No arbitrary filtering that could miss operators
- **Accurate Classification:** Complete freighter detection logic

---

## 🔍 **DEBUGGING PROTOCOLS (LEARNED FROM CRISIS)**

### **For Regression Issues:**
1. **Compare exact code** between working vs broken versions
2. **Map ALL code paths** that handle the same data type  
3. **Add detailed logging** to trace data flow
4. **Verify assumptions** with actual database/API data
5. **Make atomic commits** for easier debugging

### **Red Flags to Investigate:**
- Generic error messages without specific context
- Same functionality works in one place, fails in another
- Data corruption patterns (special characters, encoding)
- Field name mismatches between functions
- Telegram API object attribute errors (read-only properties)
- Callback context behaving differently than normal messages
- Function name corruption after replace_all operations

---

## 📋 **CURRENT DEVELOPMENT PRIORITIES**

### **Next Major Enhancement (Planned):**
**Time Frame Selection for All Functions**
- Allow users to select search time periods (1, 3, 6, 12 months)
- Apply to Functions 1, 8, 10, 12
- Improve query performance and data relevance

### **Technical Debt (Priority):**
1. **Centralize operator name cleaning** into shared utility function
2. **Remove debug logging** from Function 8 (temporary debug code)
3. **Standardize field names** across all function responses
4. **Add integration tests** for complete user workflows
5. **Callback system large dataset handling** - investigate pagination for 100+ operator results
6. **Function name safety** - avoid replace_all operations that can corrupt names

---

## ✅ **CURRENT SYSTEM STATUS**

### **All Functions:** ✅ FULLY OPERATIONAL
### **Geographic Filtering:** ✅ Working for all operators (Icelandair crisis resolved)
### **50,000 Record Handling:** ✅ Processes data + shows warning (no more errors)
### **Message Pagination:** ✅ Working for all long messages
### **Operator Buttons:** ✅ Working with special character handling
### **Data Accuracy:** ✅ Maintained across all functions

---

## 🎯 **FOR NEW CONVERSATIONS: QUICK START**

### **To Continue Development:**
1. **Read this document** for complete context
2. **Check CHECKPOINT_018** for latest crisis resolution details
3. **Review PROJECT_DEVELOPMENT_RULES.md** for development protocols
4. **Check current TODO status** in conversation history
5. **Verify system status** by testing core functions

### **Key Files to Understand:**
- **`telegram_bot.py`:** Main bot logic, all user interaction handling
- **`supabase/functions/get-operator-details/index.ts`:** Function 8 (most complex)
- **`PROJECT_DEVELOPMENT_RULES.md`:** Complete development protocols
- **`DATA_ACCURACY_STANDARDS.md`:** Data quality requirements

### **Testing Approach:**
- **No local testing required** (per user preference)
- **Deploy directly to Railway/Supabase** for testing
- **Use live Telegram bot** for validation
- **Check Supabase function logs** for debugging

---

**This document provides complete project context for seamless continuation of development in new conversations.**

**Last Updated:** September 20, 2025  
**Next Update:** After next major feature development  
**Maintainer:** FlightRadar Development Team
