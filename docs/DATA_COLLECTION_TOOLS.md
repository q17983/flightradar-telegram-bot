# 🛠️ Data Collection Tools - FlightRadar Project

**Last Updated:** September 20, 2025  
**Purpose:** Documentation for core data collection scripts  
**Location:** Root directory for easy access  

---

## 🎯 **OVERVIEW**

The FlightRadar project uses two critical data collection scripts located in the root directory for easy access and execution:

### **📍 Core Data Collection Scripts:**
1. **`airport_sync_script.py`** - Airport & country data synchronization
2. **`scraper_Final_v5_11APR.py`** - FlightRadar24 flight data scraper

---

## ✈️ **AIRPORT_SYNC_SCRIPT.PY**

### **Purpose:**
Downloads and synchronizes airport and country data from OurAirports.com to Supabase database every 6 months for continent/region analysis.

### **Key Features:**
- **Data Sources:** 
  - `https://davidmegginson.github.io/ourairports-data/airports.csv`
  - `https://davidmegginson.github.io/ourairports-data/countries.csv`
- **Automatic Sync:** Checks for updates every 6 months
- **Progress Tracking:** Maintains sync logs in `data/airport_data/sync_log.json`
- **Database Integration:** Direct Supabase PostgreSQL connection

### **Data Tables Updated:**
- `airports_geography` - Airport location data with continent/country mapping
- Country reference data for geographic analysis

### **Usage:**
```bash
python airport_sync_script.py
```

### **Environment Variables Required:**
```bash
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=your_database_port
```

---

## 🛩️ **SCRAPER_FINAL_V5_11APR.PY**

### **Purpose:**
Complete FlightRadar24 data scraper that collects flight movement data and aircraft details for the cargo charter analysis system.

### **Key Features:**
- **FlightRadar24 Login:** Authenticated access for extended flight history
- **Aircraft Registration Extraction:** Discovers new aircraft registrations
- **Flight History Collection:** Comprehensive movement data
- **Aircraft Details:** Operator, type, and classification information
- **Progress Tracking:** Resumes from last processed aircraft
- **Error Handling:** Robust retry mechanisms and logging

### **Data Collection Process:**
1. **Login to FlightRadar24** using credentials
2. **Extract Aircraft Registrations** from various sources
3. **Collect Flight History** for each aircraft
4. **Gather Aircraft Details** (operator, type, etc.)
5. **Store in Database** with proper data validation

### **Database Tables Populated:**
- `aircraft` - Aircraft details with operator information
- `movements` - Flight movement records (1.28M+ records)

### **Usage:**
```bash
python scraper_Final_v5_11APR.py
```

### **Environment Variables Required:**
```bash
# Database connection (same as airport sync)
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=your_database_port

# FlightRadar24 credentials
FR24_USERNAME=your_flightradar24_username
FR24_PASSWORD=your_flightradar24_password
```

### **Progress Tracking:**
- Creates `scraper_progress.txt` to track last processed aircraft
- Resumes from interruption point
- Comprehensive logging to monitor collection progress

---

## 🔧 **TECHNICAL SPECIFICATIONS**

### **Dependencies (All in requirements.txt):**
- **Common:** `psycopg2-binary`, `python-dotenv`, `requests`, `logging`
- **Airport Sync:** `pandas` for CSV processing
- **Scraper:** `beautifulsoup4` for HTML parsing, `datetime`, `re` for data processing

### **File Locations:**
```
/Users/sai/Flightradar crawling/
├── airport_sync_script.py          # Airport data synchronization
├── scraper_Final_v5_11APR.py       # FlightRadar24 data collection
├── data/airport_data/              # Airport sync output
│   ├── airports_geography.csv      # Downloaded airport data
│   ├── countries.csv               # Downloaded country data
│   └── sync_log.json              # Sync tracking
└── scraper_progress.txt           # Scraper progress tracking
```

---

## 🚨 **IMPORTANT NOTES**

### **Security:**
- **Never commit credentials** to version control
- Use `.env` file for all sensitive information
- FlightRadar24 credentials required for full functionality

### **Data Quality:**
- **Airport Sync:** Updates every 6 months to maintain accuracy
- **Scraper:** Collects comprehensive flight data (Apr 2024 - May 2025)
- **Validation:** Both scripts include data validation and error handling

### **Operational:**
- **Run airport sync** when geographic analysis needs updates
- **Run scraper** to collect new flight movement data
- **Monitor logs** for any collection issues
- **Check progress files** to resume interrupted operations

---

## 📊 **DATA IMPACT**

### **Current Database Status:**
- **Aircraft Records:** 12,742 aircraft tracked
- **Flight Movements:** 1.28M+ movement records
- **Geographic Coverage:** Complete airport and country mapping
- **Time Range:** April 2024 - May 2025

### **System Integration:**
These scripts feed data directly into the Telegram bot analysis functions:
- **Function 1:** Operators by destination
- **Function 8:** Operator details with geographic filtering
- **Function 10:** Geographic location analysis
- **Function 12:** Aircraft-to-destination search

---

**These tools are the foundation of the FlightRadar project's data collection and analysis capabilities.**

**Created:** September 20, 2025  
**Maintainer:** FlightRadar Development Team  
**Status:** Production-ready, actively maintained
