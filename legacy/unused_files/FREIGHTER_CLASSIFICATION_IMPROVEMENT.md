# 🛩️ Freighter Classification Logic Improvement

## 📊 Current Classification Issues

### **Examples Not Caught by Current Logic:**
- `Boeing 747-428F(ER)` → Pattern: `428F` (number+F)
- `Boeing 747-8HVF` → Pattern: `8HVF` (number+letters+F)
- `Airbus A330-243F` → Pattern: `243F` (number+F)

### **Current Rules:**
```sql
WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
  OR UPPER(a.aircraft_details) LIKE '%-F%'        -- Only dash-F
  OR UPPER(a.aircraft_details) LIKE '%CARGO%'
  OR UPPER(a.aircraft_details) LIKE '%BCF%'       -- Boeing Converted Freighter
  OR UPPER(a.aircraft_details) LIKE '%SF%'        -- Special Freighter
THEN 'Freighter'
```

## 🎯 Improved Classification Logic

### **Enhanced Rules (More Comprehensive):**
```sql
CASE 
  -- Explicit freighter keywords
  WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
    OR UPPER(a.aircraft_details) LIKE '%CARGO%'
    
  -- Boeing freighter designations
    OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
    OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
    OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
    
  -- General F patterns (with safeguards)
    OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F (e.g., 737-400F)
    OR UPPER(a.aircraft_details) LIKE '%F)'        -- F before closing bracket (e.g., 747-428F(ER))
    OR UPPER(a.aircraft_details) LIKE '%F '%       -- F followed by space
    OR UPPER(a.aircraft_details) LIKE '%F,'        -- F followed by comma
    
  -- Specific freighter model patterns
    OR UPPER(a.aircraft_details) LIKE '%[0-9]F%'   -- Number followed by F (PostgreSQL regex)
    
  -- Additional cargo designations
    OR UPPER(a.aircraft_details) LIKE '%COMBI%'    -- Passenger/Cargo combination
    OR UPPER(a.aircraft_details) LIKE '%QUICK CHANGE%'  -- Quick Change (QC)
    OR UPPER(a.aircraft_details) LIKE '%QC%'       -- Quick Change abbreviation
    
  THEN 'Freighter'
  ELSE 'Passenger'
END as aircraft_category
```

### **Alternative Safer Approach:**
Since PostgreSQL LIKE doesn't support regex, here's a safer approach:

```sql
CASE 
  -- Explicit freighter keywords
  WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
    OR UPPER(a.aircraft_details) LIKE '%CARGO%'
    
  -- Boeing freighter designations
    OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
    OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
    OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
    
  -- F patterns with context
    OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F (e.g., 737-400F)
    OR UPPER(a.aircraft_details) LIKE '%0F%'       -- 0F, 1F, 2F, etc.
    OR UPPER(a.aircraft_details) LIKE '%1F%'
    OR UPPER(a.aircraft_details) LIKE '%2F%'
    OR UPPER(a.aircraft_details) LIKE '%3F%'
    OR UPPER(a.aircraft_details) LIKE '%4F%'
    OR UPPER(a.aircraft_details) LIKE '%5F%'
    OR UPPER(a.aircraft_details) LIKE '%6F%'
    OR UPPER(a.aircraft_details) LIKE '%7F%'
    OR UPPER(a.aircraft_details) LIKE '%8F%'
    OR UPPER(a.aircraft_details) LIKE '%9F%'
    OR UPPER(a.aircraft_details) LIKE '%F)'        -- F before closing bracket
    
  -- Additional cargo designations
    OR UPPER(a.aircraft_details) LIKE '%COMBI%'    -- Passenger/Cargo combination
    OR UPPER(a.aircraft_details) LIKE '%QC%'       -- Quick Change
    
  THEN 'Freighter'
  ELSE 'Passenger'
END as aircraft_category
```

## 🔍 Examples That Will Now Be Caught

### **✅ Previously Missed, Now Caught:**
- `Boeing 747-428F(ER)` → Matches `%8F%` and `%F)`
- `Boeing 747-4H6(BCF)` → Matches `%BCF%` (should already work)
- `Airbus A330-243F` → Matches `%3F%`
- `Boeing 777-F28` → Matches `%-F%` (already worked)

### **✅ Additional Patterns Caught:**
- `ATR 72-212F` → Matches `%2F%`
- `Boeing 757-236F` → Matches `%6F%`
- `Boeing 747-8HVF` → Matches `%F)` if formatted as `747-8HVF)`

## 🚨 Potential False Positives to Watch

### **Patterns to be careful with:**
- Aircraft with `F` in registration (not model)
- Airlines with `F` in name
- Equipment codes with `F`

### **Safeguards Applied:**
- Using specific patterns rather than general `%F%`
- Context-aware matching (F after numbers, F before brackets)
- Avoiding overly broad matches

## 🧪 Testing Strategy

### **Test Cases:**
1. **Known Freighters:** Verify all catch correctly
2. **Known Passengers:** Verify none are misclassified
3. **Edge Cases:** Manual review of borderline aircraft

### **Implementation Plan:**
1. Update all Supabase functions with new logic
2. Test with sample queries
3. Compare before/after classifications
4. Monitor for false positives
