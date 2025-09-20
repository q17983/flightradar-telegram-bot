# 📁 FlightRadar Telegram Bot - Directory Structure

**Last Updated:** September 20, 2025  
**Purpose:** Clear organization of all project files  
**Status:** ✅ REORGANIZED - Clean structure implemented  

---

## 🏗️ **CLEAN PROJECT STRUCTURE**

```
/Users/sai/Flightradar crawling/  (ROOT - ACTIVE PROJECT)
│
├── 📱 ACTIVE CODE (CORE FUNCTIONALITY)
│   ├── telegram_bot.py              # Main Telegram bot (Railway deployment)
│   ├── requirements.txt             # Python dependencies
│   ├── Procfile                     # Railway deployment configuration
│   └── supabase/                    # Backend Edge Functions (Supabase)
│       ├── config.toml              # Supabase configuration
│       └── functions/               # All backend functions
│           ├── get-operators-by-destination/        # Function 1
│           ├── get-operator-details/                # Function 8 (most complex)
│           ├── get-operators-by-multi-destinations/ # Function 9
│           ├── get-operators-by-geographic-locations/ # Function 10
│           ├── aircraft-to-destination-search/      # Function 12
│           └── [other functions]/
│
├── 📚 DOCUMENTATION (ORGANIZED BY IMPORTANCE)
│   ├── PROJECT_CONTEXT_SUMMARY.md          # ⭐ START HERE - Complete project overview
│   ├── PROJECT_DEVELOPMENT_RULES.md        # ⭐ Development protocols & debugging
│   ├── DATA_ACCURACY_STANDARDS.md          # ⭐ Data quality requirements
│   ├── ENVIRONMENT_SETUP.md                # Environment configuration
│   ├── TELEGRAM_BOT_SETUP.md               # Bot setup guide
│   ├── README.md                           # Project overview
│   │
│   ├── checkpoints/                        # Recent major milestones
│   │   ├── CHECKPOINT_018_ICELANDAIR_CRISIS.md  # ⭐ Latest debugging crisis
│   │   ├── CHECKPOINT_017_FUNCTION_12.md        # Function 12 completion
│   │   ├── CHECKPOINT_016_FUNCTION_8.md         # Function 8 enhancement
│   │   └── CHECKPOINT_SYSTEM.md                 # Checkpoint methodology
│   │
│   └── archives/                           # Older documentation
│       ├── FUNCTION_8_*.md                 # Function 8 development docs
│       ├── FREIGHTER_CLASSIFICATION.md    # Classification improvement
│       ├── PERFECT_DEVELOPMENT_FRAMEWORK.md
│       └── [other archived docs]/
│
├── 🗄️ DATA & RESOURCES
│   ├── airport_data/                       # CSV data files
│   │   ├── airports_geography.csv          # Airport location data
│   │   ├── airports.csv                    # Airport details
│   │   ├── countries.csv                   # Country mapping
│   │   └── sync_log.json                   # Data sync logs
│   │
│   └── sql_queries/                        # SQL test files
│       ├── analyze_china_airports.sql      # China airport analysis
│       └── test_aircraft_types.sql         # Aircraft type testing
│
├── 🔧 SCRIPTS & UTILITIES
│   ├── airport_sync_script.py              # Airport data synchronization
│   ├── scraper/                            # Current scraping tools
│   │   └── scraper.py                      # Active scraper
│   └── archives/                           # Old scraper versions
│       ├── scraper_back1_beforeFR.py       # Backup versions
│       ├── scraper_back2_can_login.py      # Development history
│       ├── scraper_Final_v5_11APR.py       # Final version
│       └── [other backup versions]/
│
└── 🗃️ LEGACY (PRESERVED BUT INACTIVE)
    ├── flightradar_scraper_legacy/         # Complete old directory structure
    │   └── [entire old structure preserved]
    └── unused_files/                       # Old/unused files
        ├── flight_chatbot/                 # Old bot attempt
        ├── history_*.html                  # FlightRadar HTML files
        ├── test_*.js                       # Old test files
        ├── CHINA_AIRPORTS_*.md             # Old airport docs
        ├── CLOUD_DEPLOYMENT_GUIDE.md       # Old deployment docs
        └── [other unused files]/
```

---

## 🎯 **KEY FILE LOCATIONS**

### **⭐ FOR NEW CONVERSATIONS:**
- **`docs/PROJECT_CONTEXT_SUMMARY.md`** - Complete project understanding
- **`docs/PROJECT_DEVELOPMENT_RULES.md`** - Development protocols
- **`docs/checkpoints/CHECKPOINT_018_ICELANDAIR_CRISIS.md`** - Latest status

### **🔧 FOR DEVELOPMENT:**
- **`telegram_bot.py`** - Main bot code
- **`supabase/functions/`** - All backend functions
- **`requirements.txt`** - Dependencies
- **`Procfile`** - Railway deployment

### **📊 FOR DATA ANALYSIS:**
- **`data/airport_data/`** - CSV data files
- **`data/sql_queries/`** - SQL test files
- **`scripts/scraper/`** - Data collection tools

### **🗃️ FOR REFERENCE:**
- **`legacy/flightradar_scraper_legacy/`** - Complete old structure
- **`docs/archives/`** - Historical documentation
- **`legacy/unused_files/`** - Preserved but inactive files

---

## ✅ **REORGANIZATION BENEFITS**

### **🎯 Clear Structure:**
- **Active code** clearly separated from documentation
- **Documentation** organized by importance and recency
- **Legacy files** preserved but out of the way
- **No files deleted** - everything preserved safely

### **📱 Improved Navigation:**
- Essential files easily findable in `/docs/`
- Current code clearly in root directory
- Historical files organized in `/legacy/`
- Data files organized in `/data/`

### **🔧 Development Efficiency:**
- New conversations can quickly find `PROJECT_CONTEXT_SUMMARY.md`
- Development rules easily accessible
- Active code not cluttered with old documentation
- Clear separation of concerns

---

**This structure provides clear organization while preserving all historical files for reference.**

**Created:** September 20, 2025  
**Backup Available:** `../BACKUP_BEFORE_REORGANIZATION_20250920_143900/`  
**Recovery:** If issues arise, restore from backup directory
