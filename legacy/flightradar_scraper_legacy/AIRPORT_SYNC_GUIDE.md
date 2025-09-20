# Airport Geography Sync Guide

## 🎯 **Purpose**
Sync airport and country data from OurAirports to create a lookup table for continent/country analysis of your flight movements.

## 📊 **Database Structure**

### **Separate Tables (No Merge):**
- `movements` - Your existing flight data
- `aircraft` - Your existing aircraft data  
- `airports_geography` - **NEW** lookup table for airport locations

### **Integration via IATA Codes:**
```sql
-- Example: Find continent for each movement
SELECT 
    m.destination_code,
    ag.airport_name,
    ag.country_name,
    ag.continent,
    COUNT(*) as flights
FROM movements m
JOIN airports_geography ag ON m.destination_code = ag.iata_code
GROUP BY m.destination_code, ag.airport_name, ag.country_name, ag.continent
ORDER BY flights DESC;
```

## 🚀 **How to Use (Manual Every 6 Months)**

### **Run the Sync Script:**
```bash
cd "/Users/sai/Flightradar crawling/flightradar_scraper"
./venv/bin/python airport_sync_script.py --force
```

### **What It Does:**
1. ✅ Downloads latest airports.csv and countries.csv from OurAirports
2. ✅ Processes 8,799 airports with IATA codes
3. ✅ Assigns North America (NA) continent to US/Canada/Mexico airports
4. ✅ **UPSERTS** to Supabase (like scraper_final_v5):
   - **New airports** → Inserted
   - **Existing airports** → Updated with latest info
   - **Removed airports** → Remain in database (safe)

## 📋 **Current Data Coverage**

### **Continent Breakdown:**
- **NA (North America)**: 2,758 airports (US, CA, MX, etc.)
- **AS (Asia)**: 1,851 airports
- **OC (Oceania)**: 1,268 airports  
- **AF (Africa)**: 1,069 airports
- **EU (Europe)**: 938 airports
- **SA (South America)**: 913 airports
- **AN (Antarctica)**: 2 airports

### **Major Airports Included:**
- ✅ JFK, LAX, ORD, ATL, DFW (US - NA)
- ✅ LHR, CDG, FRA (Europe - EU)
- ✅ NRT, ICN, SIN (Asia - AS)
- ✅ All airports with IATA codes from your movements

## 🔍 **Usage Examples**

### **1. Flights by Continent:**
```sql
SELECT 
    ag.continent,
    COUNT(*) as total_flights
FROM movements m
JOIN airports_geography ag ON m.destination_code = ag.iata_code
GROUP BY ag.continent
ORDER BY total_flights DESC;
```

### **2. Top Countries by Flight Volume:**
```sql
SELECT 
    ag.country_name,
    ag.continent,
    COUNT(*) as flights
FROM movements m
JOIN airports_geography ag ON m.destination_code = ag.iata_code
GROUP BY ag.country_name, ag.continent
ORDER BY flights DESC
LIMIT 20;
```

### **3. Freighter vs Passenger by Continent:**
```sql
SELECT 
    ag.continent,
    CASE 
        WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
          OR UPPER(a.aircraft_details) LIKE '%-F%'
        THEN 'Freighter'
        ELSE 'Passenger'
    END as aircraft_category,
    COUNT(*) as flights
FROM movements m
JOIN aircraft a ON m.registration = a.registration
JOIN airports_geography ag ON m.destination_code = ag.iata_code
GROUP BY ag.continent, aircraft_category
ORDER BY ag.continent, flights DESC;
```

## ⚙️ **Script Options**

```bash
# Normal run (checks if 6 months passed)
./venv/bin/python airport_sync_script.py

# Force run (manual - use this every 6 months)
./venv/bin/python airport_sync_script.py --force

# Test mode (download and process, no database sync)
./venv/bin/python airport_sync_script.py --test
```

## 📁 **Files Created**
- `airport_data/airports.csv` - Raw airport data
- `airport_data/countries.csv` - Raw country data
- `airport_data/airports_geography.csv` - Processed data
- `airport_data/sync_log.json` - Last sync timestamp
- `airport_sync.log` - Detailed logs

## 🔧 **Maintenance**

### **When to Run:**
- ✅ **Every 6 months** (manual)
- ✅ **When you notice new airports** in your movements data
- ✅ **After major airport code changes** (rare)

### **What Gets Updated:**
- ✅ New airports added to database
- ✅ Airport names updated if changed
- ✅ Country assignments updated
- ✅ Coordinates and elevation updated
- ❌ Old airports remain (safe - no deletions)

## 🚨 **Troubleshooting**

### **Common Issues:**
1. **Missing airports in movements**: Check if they have IATA codes
2. **Null continents**: Script auto-assigns NA to North American countries
3. **Database connection**: Verify .env file has correct Supabase credentials

### **Logs Location:**
- Console output shows progress
- `airport_sync.log` has detailed information
- Check for ERROR or WARNING messages

---

**Last Updated:** September 14, 2025  
**Next Sync Due:** March 2026 (6 months)  
**Total Airports:** 8,799 with IATA codes
