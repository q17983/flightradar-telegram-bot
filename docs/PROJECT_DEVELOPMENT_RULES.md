# 🎯 FlightRadar Scraper - Complete Project Development Rules & Reference

**Last Updated:** September 20, 2025  
**Status:** Comprehensive Development Guide  
**Purpose:** Ensure smooth, stable, and effective future development

---

## 🏗️ **SYSTEM ARCHITECTURE OVERVIEW**

### **Core Components:**
1. **Telegram Bot** (`telegram_bot.py`) - User interface on Railway
2. **Supabase Edge Functions** - Backend API processing (TypeScript/Deno)
3. **PostgreSQL Database** - Flight data storage via Supabase
4. **OpenAI Integration** - Query analysis and enhancement
5. **FlightRadar24 Scraper** (`scraper.py`) - Data collection

### **Infrastructure Stack:**
- **Frontend:** Telegram Bot API (Python)
- **Backend:** Supabase Edge Functions (TypeScript/Deno)
- **Database:** PostgreSQL with connection pooling
- **AI:** OpenAI GPT-4 for query analysis
- **Deployment:** Railway (bot) + Supabase (functions)
- **Version Control:** GitHub with automated Railway deployment

---

## 🎯 **DATA ACCURACY STANDARDS (HIGHEST PRIORITY)**

### **Core Principle: ACCURACY OVER SPEED**
**"We would rather increase waiting time than sacrifice data accuracy"**

All functions must prioritize complete and accurate data over performance optimizations. Users prefer to wait longer for complete results rather than receive fast but incomplete data.

### **Mandatory Data Accuracy Rules:**
1. **No Data Loss Through Filtering**
   - ❌ NEVER use `HAVING COUNT(*) > 1` (eliminates single-flight operations)
   - ❌ NEVER reduce LIMIT below complete coverage needs
   - ✅ ALWAYS include ALL operators, aircraft, and routes
   - ✅ ALWAYS use `HAVING COUNT(*) >= 1` or remove HAVING clause

2. **Complete Aircraft Classification**
   - ✅ ALWAYS use complete freighter detection logic (FREIGHTER, CARGO, BCF, BDSF, SF, -F, F patterns)
   - ✅ ALWAYS include exclusions (FK, TANKER, VIP, FIRST, FLEX patterns)
   - ❌ NEVER use simplified detection that misses aircraft types

3. **Timeout Management Strategy**
   - ✅ Alert user when data exceeds 50,000 records
   - ✅ Suggest specific time frame reductions
   - ✅ Maintain full accuracy within suggested time frames
   - ❌ NEVER silently truncate results

4. **Complete Coverage Requirements**
   - ✅ ALL operators serving routes/destinations
   - ✅ ALL aircraft types and registrations
   - ✅ ALL geographic locations matching criteria
   - ✅ Exact time range adherence

**📋 See `DATA_ACCURACY_STANDARDS.md` for complete requirements**

---

## 🔐 **REQUIRED ENVIRONMENT SETTINGS**

### **1. Core Environment Variables (MANDATORY)**

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather

# OpenAI Integration
OPENAI_API_KEY=your_openai_api_key_from_platform

# Supabase Configuration
SUPABASE_URL=https://prcnxrkyjnpljoqiazkp.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key

# Database Connection (for scrapers)
DB_HOST=your_db_host
DB_PORT=6543
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# FlightRadar24 Credentials (optional)
FR24_USERNAME=your_fr24_username
FR24_PASSWORD=your_fr24_password
```

### **2. Environment Setup Process**

#### **Local Development:**
```bash
# 1. Create .env file in project root
cd "/Users/sai/Flightradar crawling"
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_key_here
SUPABASE_URL=https://prcnxrkyjnpljoqiazkp.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
EOF

# 2. Verify .env is in .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo ".specstory/" >> .gitignore
```

#### **Railway Cloud Deployment:**
- Add all variables in Railway Dashboard → Variables tab
- No quotes needed in Railway variables
- Use exact variable names from list above

#### **Supabase Local Development:**
```bash
# Create supabase/.env.local for local function testing
cd supabase
cat > .env.local << 'EOF'
DATABASE_URL=your_supabase_database_url
EOF
```

### **3. Connection Verification**

```bash
# Test local environment
cd "/Users/sai/Flightradar crawling"
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('✅ TELEGRAM_BOT_TOKEN:', 'TELEGRAM_BOT_TOKEN' in os.environ)
print('✅ OPENAI_API_KEY:', 'OPENAI_API_KEY' in os.environ)
print('✅ SUPABASE_ANON_KEY:', 'SUPABASE_ANON_KEY' in os.environ)
"
```

---

## 🚨 **CRITICAL MISTAKES TO NEVER REPEAT**

### **1. API Key Security Breaches**

#### **❌ What Went Wrong:**
- OpenAI API key accidentally committed to `.specstory/` conversation history
- GitHub detected and blocked push with `GH013: Repository rule violations`
- OpenAI automatically revoked the leaked key
- ALL functions stopped working (not just new ones)

#### **✅ Prevention Rules:**
```bash
# BEFORE EVERY git commit:
grep -r "sk-" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules
grep -r "AIza" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules
grep -r "API_KEY" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules

# Verify .gitignore protection:
cat .gitignore | grep -E "(\.env|\.specstory|secret|key)"
```

#### **🚨 If API Key Leaked:**
1. **IMMEDIATELY** create new API key at provider
2. **Update ALL environments** (local + Railway)
3. **Use GitHub bypass URLs** if needed for emergency deployment
4. **Never delete** `.specstory/` - move temporarily, then restore

### **2. Directory and Runtime Errors**

#### **❌ Common Mistakes:**
- Running bot from `/flightradar_scraper/` instead of `/Users/sai/Flightradar crawling/`
- Can't access OpenAI API key in parent `.env` file
- Multiple bot instances causing conflicts

#### **✅ Correct Patterns:**
```bash
# ALWAYS run from parent directory
cd "/Users/sai/Flightradar crawling"
python telegram_bot.py

# ALWAYS kill local instances before Railway deployment
pkill -f "python telegram_bot.py"
ps aux | grep telegram_bot  # Verify none running

# ALWAYS check working directory for Supabase commands
cd "/Users/sai/Flightradar crawling"
npx supabase functions serve [function-name] --env-file supabase/.env.local
```

### **3. Database and Function Development Errors**

#### **❌ Function Development Mistakes:**
- Using wrong table names (`flight_data` instead of `movements`)
- Mixed Supabase client imports with PostgreSQL direct connection
- BigInt type conversion errors in JavaScript
- Missing result formatting for new functions
- Assuming JWT errors mean broken functionality

#### **✅ Correct Patterns:**
```typescript
// ALWAYS use these exact imports
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

// ALWAYS use correct table names
FROM movements m JOIN aircraft a ON m.registration = a.registration

// ALWAYS convert BigInt to Number
operator.total_flights += Number(flight.frequency)

// ALWAYS add result formatting for new functions
function format_function_X_results(data) { ... }
```

### **4. Deployment and Testing Errors**

#### **❌ Deployment Mistakes:**
- Making multiple changes at once without incremental testing
- Not testing locally before cloud deployment
- Forgetting to implement message splitting for large results
- Not creating checkpoints before major changes

#### **✅ Safe Deployment Process:**
1. **Test locally first** with `npx supabase functions serve`
2. **One change at a time** with immediate testing
3. **Create checkpoints** before major changes
4. **Deploy Supabase functions first**, then Telegram bot
5. **Always implement message splitting** for complex functions

---

## 🎯 **PROVEN DEVELOPMENT WORKFLOW**

### **Phase 1: Foundation Setup (SAFE)**
```bash
# 1. Create checkpoint
git add . && git commit -m "CHECKPOINT: Before Function X development"

# 2. Add to FUNCTION_MAP in telegram_bot.py
"function_name": {
    "url": f"{SUPABASE_URL}/functions/v1/function-name",
    "params": ["param1", "param2"],
    "description": "Function X: Clear description"
}

# 3. Add button to selectfunction_command
InlineKeyboardButton("🎯 Function X", callback_data="select_func_X")

# 4. Add callback handler
elif callback_data.startswith("select_func_X"):
    # Implementation here

# 5. Test: Button appears and responds
```

### **Phase 2: Query Detection (SAFE)**
```python
# 1. Add detection functions
def is_function_X_query(query: str) -> bool:
    # Implementation

def extract_function_X_from_query(query: str) -> dict:
    # Implementation

# 2. Update OpenAI prompt with examples
# 3. Add to message handling logic
# 4. Test: Query detection works
```

### **Phase 3: Backend Development (INCREMENTAL)**
```typescript
// 1. Create Supabase function using EXACT template from working functions
// 2. Test locally first
npx supabase functions serve function-name --env-file supabase/.env.local

// 3. Test with curl
curl -X POST "http://localhost:54321/functions/v1/function-name" \
  -H "Content-Type: application/json" \
  -d '{"param": "value"}'

// 4. Deploy to cloud only after local success
npx supabase functions deploy function-name

// 5. Test cloud deployment
```

### **Phase 4: Integration & Polish (CAREFUL)**
```python
# 1. Implement result formatting with message splitting
def format_function_X_results(data):
    # Handle Telegram 4096 character limit
    
# 2. Add advanced UI features one by one
# 3. Deploy directly to Railway for user testing (skip local bot testing)
# 4. Create final checkpoint when complete
```

### **Testing Protocol:**
- ✅ **Supabase Functions:** Test locally with `npx supabase functions serve`
- ✅ **Database Queries:** Test with curl or direct database connection
- ✅ **Telegram Bot:** Deploy directly to Railway - user will test functionality
- ❌ **Skip Local Bot Testing:** No need to run telegram_bot.py locally for testing

---

## 🛡️ **MANDATORY TECHNICAL STANDARDS**

### **Database Query Standards:**
```sql
-- ALWAYS include these in complex queries:
LIMIT 10000  -- Prevent timeouts
AND a.operator != ''  -- Filter empty operators
HAVING COUNT(*) >= 1  -- Group filtering

-- ALWAYS use standard freighter detection:
CASE 
    WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
      OR UPPER(a.aircraft_details) LIKE '%-F%'
      OR UPPER(a.aircraft_details) LIKE '%CARGO%'
      OR UPPER(a.aircraft_details) LIKE '%BCF%'
      OR UPPER(a.aircraft_details) LIKE '%SF%'
    THEN 'Freighter'
    ELSE 'Passenger'
END as aircraft_category
```

### **Supabase Function Template (MANDATORY):**
```typescript
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3
console.log(`Function "[function-name]" up and running!`)

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection;
  try {
    const requestData = await req.json()
    
    const databaseUrl = Deno.env.get('DATABASE_URL')!
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    connection = await pool.connect()
    
    // Function logic here
    
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
    
  } catch (error) {
    console.error("Function error:", error)
    return new Response(JSON.stringify({
      error: 'Internal server error',
      details: error.message
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  } finally {
    if (connection) connection.release()
  }
})
```

### **Error Handling Standards:**
- **Connection release:** Always in finally block
- **Parameter validation:** Clear error messages
- **Status codes:** 400 for user errors, 500 for server errors
- **CORS headers:** On all responses
- **BigInt conversion:** Always convert PostgreSQL numbers to JavaScript numbers

---

## 📋 **PRE-DEVELOPMENT CHECKLIST**

### **Environment Verification:**
- [ ] **Working Directory:** `/Users/sai/Flightradar crawling/` (NOT subfolder)
- [ ] **API Keys:** OpenAI API key accessible via environment test
- [ ] **Git Status:** Clean working tree with all changes committed
- [ ] **Existing Functions:** All core functions tested and working

### **Baseline Function Tests:**
- [ ] **Function 1:** "Who flies to LAX" → Returns operator breakdown
- [ ] **Function 8:** "FedEx details" → Returns fleet and route analysis
- [ ] **Function 10:** "China to Taiwan operators" → Returns geographic analysis
- [ ] **Function 12:** "Boeing 777 to Europe" → Returns aircraft-destination search

### **Security Checks:**
- [ ] **API Key Scan:** No API keys in code or git history
- [ ] **Gitignore Protection:** `.env`, `.specstory/` properly ignored
- [ ] **Environment Access:** All required variables accessible

---

## 🚀 **DEPLOYMENT SAFETY PROTOCOLS**

### **Before ANY Change:**
1. ✅ **Commit current working state**
2. ✅ **Test all existing functions still work**
3. ✅ **Make ONE change at a time**
4. ✅ **Test immediately after each change**

### **Never Touch:**
- ✅ **OpenAI API key configuration** (unless replacing compromised key)
- ✅ **Working function logic** (unless enhancing with backup)
- ✅ **Database connection setup** (proven stable pattern)
- ✅ **Existing callback handlers** (unless adding new ones)

### **Safe Deployment Sequence:**
```bash
# 1. Local development and testing
cd "/Users/sai/Flightradar crawling"
# Make changes, test locally

# 2. Security check
grep -r "sk-" . --exclude-dir=.git --exclude-dir=venv
git diff --cached  # Review what will be committed

# 3. Commit and deploy Supabase functions
git add . && git commit -m "ENHANCE: Function X - Description"
npx supabase functions deploy function-name

# 4. Kill local bot instances
pkill -f "python telegram_bot.py"

# 5. Deploy to Railway
git push origin main

# 6. Wait and test
# Wait 30-60 seconds for Railway deployment
# Test via Telegram bot
```

---

## 📊 **CHECKPOINT SYSTEM USAGE**

### **When to Create Checkpoints:**
- ✅ **Before major development** (new function, significant changes)
- ✅ **After successful completion** (working function, stable state)
- ✅ **Before risky operations** (API key changes, major refactoring)
- ✅ **At stable milestones** (multiple functions working)

### **Checkpoint Creation:**
```bash
# 1. Update CHECKPOINT_SYSTEM.md
# Add new checkpoint entry

# 2. Create checkpoint documentation
# Create CHECKPOINT_XXX_DESCRIPTION.md file

# 3. Commit with checkpoint message
git add . && git commit -m "CHECKPOINT_XXX: Description"
git push origin main

# 4. Note commit hash for future reference
git log --oneline -1
```

### **Checkpoint Restoration:**
```bash
# Find checkpoint commit
git log --oneline | grep "CHECKPOINT"

# Restore to checkpoint
git reset --hard <commit_hash>
git push --force origin main

# Redeploy if needed
npx supabase functions deploy --all
```

---

## 🎯 **FUNCTION DEVELOPMENT SUCCESS PATTERNS**

### **Proven Working Functions:**
1. **Function 1** (`get-operators-by-destination`) - Enhanced with freighter/passenger breakdown
2. **Function 8** (`get-operator-details`) - Cross-field search, fleet analysis, route analysis
3. **Function 10** (`get-operators-by-geographic-locations`) - Geographic analysis with OpenAI
4. **Function 12** (`aircraft-to-destination-search`) - Aircraft type to destination matching

### **Common Success Elements:**
- ✅ **Clear Purpose:** Well-defined function objective
- ✅ **Simple Parameters:** Easy to understand and validate
- ✅ **Enhanced Data:** Rich information beyond basic queries
- ✅ **Structured Output:** Consistent JSON format with summary + details
- ✅ **Telegram Integration:** Button selection + OpenAI detection
- ✅ **Performance Optimization:** Query limits and efficient SQL
- ✅ **Error Handling:** Graceful degradation and clear messages

---

## 🔧 **TROUBLESHOOTING GUIDE**

### **Common Issues & Solutions:**

#### **"BOOT_ERROR" in Supabase Functions:**
- **Cause:** Mixed import types or syntax errors
- **Solution:** Use exact imports from working functions
- **Test:** `npx supabase functions serve` locally first

#### **"Cannot mix BigInt and other types":**
- **Cause:** PostgreSQL COUNT() returns BigInt
- **Solution:** Convert with `Number(value)` before arithmetic

#### **"Conflict: terminated by other getUpdates request":**
- **Cause:** Multiple bot instances running
- **Solution:** `pkill -f "python telegram_bot.py"` before deployment

#### **"Message too long" in Telegram:**
- **Cause:** Response exceeds 4096 characters
- **Solution:** Implement message splitting in formatting function

#### **"No results found" despite function returning data:**
- **Cause:** Missing or incorrect result formatting
- **Solution:** Add specific formatting function for new data structure

#### **JWT Token Warnings:**
- **Cause:** Supabase authentication issues (cosmetic)
- **Solution:** Ignore - functions work despite warnings

---

## 📚 **PROJECT RULES FOR CURSOR IDE**

### **Cursor Project Rules Format:**
Create `.cursor-rules` file in project root:

```markdown
# FlightRadar Scraper Development Rules

## Directory Structure
- Always work from `/Users/sai/Flightradar crawling/` for bot operations
- Supabase functions in `supabase/functions/[function-name]/`
- Use `flightradar_scraper/` for scraper-related files only

## Environment Variables
- Never commit API keys or secrets
- Use .env file for local development
- Railway dashboard for production variables
- Always check .gitignore before commits

## Function Development
- Copy structure from working functions (1, 8, 10, 12)
- Use exact imports: serve from std@0.177.0, Pool from postgres@v0.17.0
- Always include CORS handling and connection cleanup
- Convert PostgreSQL BigInt to Number before arithmetic

## Database Queries
- Always use LIMIT 10000 to prevent timeouts
- Filter empty operators: AND a.operator != ''
- Use standard freighter detection pattern
- Include HAVING COUNT(*) >= 1 for group filtering

## Testing & Deployment
- Test locally before cloud deployment
- Kill local bot instances before Railway deployment
- Create checkpoints before major changes
- One change at a time with immediate testing

## Security
- Scan for API keys before every commit
- Protect .specstory/ and .env files in .gitignore
- Use GitHub bypass URLs for emergency deployments
- Immediately replace compromised API keys
```

### **Alternative: Documentation-Based Approach**

Since Cursor project rules might have limitations, maintain this comprehensive `PROJECT_DEVELOPMENT_RULES.md` file as the single source of truth and:

1. **Reference before every development session**
2. **Update after learning new patterns**
3. **Share with team members**
4. **Use as checklist for code reviews**

---

## 🎯 **QUICK REFERENCE COMMANDS**

### **Daily Development Commands:**
```bash
# Start development session
cd "/Users/sai/Flightradar crawling"
git status  # Check clean state
git pull origin main  # Get latest changes

# Test existing functions
python telegram_bot.py  # Quick test, then Ctrl+C

# Security check before commit
grep -r "sk-" . --exclude-dir=.git --exclude-dir=venv
git diff --cached

# Safe deployment
pkill -f "python telegram_bot.py"
git push origin main
```

### **Function Development Commands:**
```bash
# Local Supabase function testing
npx supabase functions serve [function-name] --env-file supabase/.env.local

# Deploy Supabase function
npx supabase functions deploy [function-name]

# Test function endpoint
curl -X POST "http://localhost:54321/functions/v1/[function-name]" \
  -H "Content-Type: application/json" \
  -d '{"param": "value"}'
```

### **Emergency Recovery Commands:**
```bash
# Restore to checkpoint
git log --oneline | grep "CHECKPOINT"
git reset --hard <commit_hash>
git push --force origin main

# Replace compromised API key
# 1. Create new key at provider
# 2. Update .env file
# 3. Update Railway variables
# 4. Test functionality
```

---

## 🏆 **SUCCESS METRICS & GOALS**

### **Development Success Criteria:**
- ✅ **No regressions:** Existing functions continue working
- ✅ **Security maintained:** No API keys leaked
- ✅ **Performance acceptable:** < 10 second response times
- ✅ **User experience smooth:** Clear, intuitive interactions
- ✅ **Code quality high:** Following established patterns

### **Project Stability Goals:**
- ✅ **Zero downtime deployments**
- ✅ **Consistent development patterns**
- ✅ **Comprehensive error handling**
- ✅ **Maintainable codebase**
- ✅ **Documented development process**

---

## 🔥 **CRITICAL DEBUGGING LESSONS LEARNED**

### **The Icelandair Geographic Filtering Crisis - September 20, 2025**

**Crisis Summary:** Extended debugging session to fix geographic filtering that worked at 12:09 but broke afterward. Root cause: operator name corruption + missing cleaning logic in geographic filter code path.

### **🎯 MANDATORY DEBUGGING PROTOCOL**

When encountering regressions or mysterious failures:

#### **Step 1: SYSTEMATIC COMPARISON (ALWAYS DO FIRST)**
```bash
# Compare exact code differences between working vs broken versions
git show WORKING_COMMIT:file.ext | diff - CURRENT_FILE
git log --oneline WORKING_COMMIT..HEAD  # Show all changes since working version
```

#### **Step 2: IDENTIFY ALL CODE PATHS**
- ❌ **CRITICAL MISTAKE:** Fixing issue in one code path but missing others
- ✅ **SOLUTION:** Map ALL functions that handle the same data type
- **Example:** Operator name used in both `handle_callback_query` AND `handle_geographic_filter`

#### **Step 3: TRACE DATA FLOW**
```
Source → Processing → Transformation → Destination
- Where does data originate? (Database, API, user input)
- What transformations happen? (Encoding, cleaning, validation)
- Which functions handle the same data differently?
```

#### **Step 4: VERIFY ASSUMPTIONS**
- ❌ **Don't assume:** "Database contains corrupted data"
- ✅ **Verify:** Check actual database content vs processed data
- ❌ **Don't assume:** "Error message indicates real problem"
- ✅ **Verify:** Add detailed logging to see actual data flow

### **🚨 IMMEDIATE RED FLAGS**

**Stop and investigate immediately when you see:**
- ❌ Generic error messages (`"Message is too long"`, `"Error processing"`)
- ❌ Same functionality works in one place, fails in another
- ❌ Data corruption patterns (special characters, encoding issues)
- ❌ Missing functions being called without obvious errors
- ❌ Field name mismatches between function responses

### **🛡️ PREVENTION RULES**

#### **A. CODE PATH CONSISTENCY**
```python
# ❌ BAD: Duplicate logic in multiple places
def handle_callback_query():
    if "icel&air" in name.lower():
        name = "Icelandair"  # Only fixes callback path!

def handle_geographic_filter():
    # Missing the same cleaning logic!
```

```python
# ✅ GOOD: Centralized data processing
def clean_operator_name(name: str) -> str:
    """Centralized operator name cleaning logic."""
    if "icel&air" in name.lower():
        return "Icelandair"
    return name

# Use in ALL code paths that handle operator names
```

#### **B. ATOMIC COMMITS**
- ✅ **One logical change per commit** (easier to debug/revert)
- ❌ **Multiple unrelated changes** (hard to isolate issues)
- **Example:** Don't combine function creation + message handling changes

#### **C. DATA INTEGRITY CHECKS**
```python
# Add validation at entry points
def handle_geographic_filter(operator_name: str, ...):
    # Validate and clean data immediately
    cleaned_name = clean_operator_name(operator_name)
    logger.debug(f"Original: {operator_name}, Cleaned: {cleaned_name}")
```

#### **D. EXPLICIT ERROR HANDLING**
```python
# ❌ BAD: Generic error messages
except Exception as e:
    logger.error(f"Error in geographic filter: {e}")

# ✅ GOOD: Specific, actionable error messages  
except Exception as e:
    logger.error(f"Geographic filter failed for operator '{operator_name}' "
                f"in {geography_input} ({filter_type}): {e}")
    logger.error(f"Debug: Function 8 parameters were {parameters}")
```

### **📋 MANDATORY CODE REVIEW CHECKLIST**

Before deploying ANY changes that modify data processing:

- [ ] **All Code Paths Updated:** Are ALL functions that handle this data type updated consistently?
- [ ] **Data Transformations Centralized:** Is the logic in a shared utility function?
- [ ] **Error Messages Specific:** Can someone debug this from the error message alone?
- [ ] **Atomic Changes:** Can this commit be easily reverted if it causes issues?
- [ ] **Debug Information Added:** Is there enough logging to troubleshoot issues?
- [ ] **Integration Testing:** Have you tested the complete user flow, not just the function?

### **🎯 TECHNICAL DEBT PREVENTION**

#### **Immediate Actions for Any Data Processing Change:**
1. **Create shared utilities** for common data transformations
2. **Standardize field names** across all function responses
3. **Add data validation** at all function entry points
4. **Replace generic errors** with specific, actionable messages
5. **Add integration tests** for complete user workflows

#### **Architecture Improvements:**
1. **Document data flow paths** - map all transformations
2. **Consistent logging format** across all functions
3. **Error handling patterns** - define standard approaches
4. **Field naming conventions** - prevent mismatches like `destinations` vs `geographic_destinations`

### **✅ SUCCESS FACTORS**

**What worked in the Icelandair crisis:**
- ✅ Detailed Supabase function logs (crucial for diagnosis)
- ✅ User's hypothesis testing (`send_large_message()` theory)
- ✅ Systematic version comparison methodology
- ✅ Persistent debugging until root cause found

**Key Insight:** Combination of detailed logging + systematic comparison solved the mystery.

---

**This document represents the complete knowledge base for FlightRadar Scraper development. Follow these rules religiously to ensure smooth, stable, and effective development.**

**Last Updated:** September 20, 2025  
**Next Review:** After next function development  
**Maintainer:** FlightRadar Development Team
