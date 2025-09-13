# Function 8: Unified Search-Then-Select Approach

## 🎯 **How It Works: Simple & Clear**

### **Step 1: User Types Search Query**
```
User: "FX"
```

### **Step 2: System Searches ALL Fields**
The system searches across:
- ✅ **IATA codes** (operator_iata_code)
- ✅ **ICAO codes** (operator_icao_code) 
- ✅ **Operator names** (operator field)

### **Step 3: Show ALL Matches**
```
🔍 **Search results for 'FX':**

1️⃣ **FedEx** 
   📋 IATA: FX | ICAO: FDX
   🌍 Country: United States
   ✈️ Fleet: 367 aircraft (98% freighter, 2% passenger)

2️⃣ **FedEx Feeder** 
   📋 IATA: -- | ICAO: --
   🌍 Country: United States  
   ✈️ Fleet: 234 aircraft (100% freighter)

3️⃣ **Flexjet** 
   📋 IATA: LXJ | ICAO: FLX
   🌍 Country: United States
   ✈️ Fleet: 45 aircraft (100% passenger)

💡 **Select operator:** Reply with number (1-3) or search again
```

### **Step 4: User Selects**
```
User: "1"
```

### **Step 5: Show Full Details**
```
✈️ **OPERATOR PROFILE: FEDEX (FX/FDX)**
📅 *Analysis Period: Jan 2024 - Dec 2024*

🚁 **FLEET SUMMARY**:
📊 *Total Aircraft: 367 (98% freighter, 2% passenger)*
🔢 *Aircraft Types: 12 different models*

🛩️ **FLEET BREAKDOWN**:
1. **Boeing 767-300F** (89 aircraft) - Freighter
   • N102FE, N103FE, N104FE... [show first 5-10]

2. **Boeing 777F** (56 aircraft) - Freighter  
   • N851FD, N852FD, N853FD... [show first 5-10]

🌍 **TOP DESTINATIONS**:
1. **MEM** (Memphis): 2,847 flights [B763F, B77F]
2. **IND** (Indianapolis): 1,234 flights [B767F, A300F]
...
```

---

## 🛠️ **Technical Implementation**

### **Database Query (Cross-Field Search):**
```sql
SELECT DISTINCT
    a.operator,
    a.operator_iata_code,
    a.operator_icao_code,
    COUNT(*) as aircraft_count,
    -- Calculate freighter percentage
    ROUND(
        (COUNT(CASE WHEN 
            UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
            OR UPPER(a.aircraft_details) LIKE '%-F%'
            OR UPPER(a.aircraft_details) LIKE '%CARGO%'
            OR UPPER(a.aircraft_details) LIKE '%BCF%'
            OR UPPER(a.aircraft_details) LIKE '%SF%'
        THEN 1 END) * 100.0 / COUNT(*)), 0
    ) as freighter_percentage
FROM aircraft a
WHERE a.operator IS NOT NULL
  AND (
    -- Search IATA code
    UPPER(COALESCE(a.operator_iata_code, '')) LIKE '%' || UPPER($1) || '%'
    OR
    -- Search ICAO code  
    UPPER(COALESCE(a.operator_icao_code, '')) LIKE '%' || UPPER($1) || '%'
    OR
    -- Search operator name
    UPPER(a.operator) LIKE '%' || UPPER($1) || '%'
  )
GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code
ORDER BY aircraft_count DESC
LIMIT 20;
```

### **Response Structure:**

#### **For Search Results:**
```json
{
  "search_query": "FX",
  "result_type": "search_results",
  "operators_found": [
    {
      "selection_id": "1",
      "operator": "FedEx",
      "operator_iata_code": "FX", 
      "operator_icao_code": "FDX",
      "country": "United States",
      "aircraft_count": 367,
      "freighter_percentage": 98,
      "passenger_percentage": 2,
      "match_reason": "IATA code match"
    },
    {
      "selection_id": "2", 
      "operator": "FedEx Feeder",
      "operator_iata_code": null,
      "operator_icao_code": null, 
      "country": "United States",
      "aircraft_count": 234,
      "freighter_percentage": 100,
      "passenger_percentage": 0,
      "match_reason": "Operator name contains 'FX'"
    }
  ],
  "total_matches": 3,
  "message": "Select operator by number (1-3) or search again"
}
```

#### **For Full Details (after selection):**
```json
{
  "search_query": "FX",
  "selection": "1",
  "result_type": "operator_details",
  "operator_details": {
    // Full operator profile as designed previously
  }
}
```

---

## 🎨 **User Experience Examples**

### **Example 1: "FX" Search**
```
User: "Operator details FX"

Bot: 🔍 **Search results for 'FX':**

     1️⃣ **FedEx** (FX/FDX) 🇺🇸
        ✈️ 367 aircraft (98% freighter)
        
     2️⃣ **FedEx Feeder** (--/--) 🇺🇸  
        ✈️ 234 aircraft (100% freighter)
        
     3️⃣ **Flexjet** (LXJ/FLX) 🇺🇸
        ✈️ 45 aircraft (100% passenger)
        
     💡 Reply with number (1-3)

User: "1"

Bot: [Full FedEx profile with fleet breakdown and top destinations]
```

### **Example 2: "Emirates" Search**
```
User: "Show operator emirates"

Bot: 🔍 **Search results for 'emirates':**

     1️⃣ **Emirates** (EK/UAE) 🇦🇪
        ✈️ 279 aircraft (15% freighter, 85% passenger)
        
     2️⃣ **Emirates SkyCargo** (EK/UAE) 🇦🇪
        ✈️ 89 aircraft (100% freighter)
        
     💡 Reply with number (1-2)

User: "1"

Bot: [Full Emirates profile]
```

### **Example 3: "Lufthansa" Search**
```
User: "luft"

Bot: 🔍 **Search results for 'luft':**

     1️⃣ **Lufthansa** (LH/DLH) 🇩🇪
        ✈️ 278 aircraft (5% freighter, 95% passenger)
        
     2️⃣ **Lufthansa Cargo** (LH/GEC) 🇩🇪
        ✈️ 45 aircraft (100% freighter)
        
     3️⃣ **Lufthansa CityLine** (CL/CLH) 🇩🇪
        ✈️ 67 aircraft (100% passenger)
        
     💡 Reply with number (1-3)
```

---

## 🔍 **Search Matching Logic**

### **What Triggers a Match:**
- ✅ **Exact IATA**: "FX" finds FedEx (FX)
- ✅ **Exact ICAO**: "FDX" finds FedEx (FDX)  
- ✅ **Partial Name**: "fed" finds FedEx, FedEx Feeder
- ✅ **Case Insensitive**: "fx", "FX", "Fx" all work
- ✅ **Substring**: "american" finds American Airlines

### **Match Ranking (Display Order):**
1. **Aircraft Count** (biggest fleets first)
2. **Exact matches** before partial matches
3. **IATA/ICAO matches** before name matches

---

## 📱 **Session Management**

### **Context Tracking:**
- Remember user's last search for 5 minutes
- Allow number selections (1, 2, 3, etc.)
- Clear context on new search
- Handle timeout gracefully

### **User Commands:**
```
✅ "1", "2", "3"           → Select from last search
✅ "operator details LH"   → New search (clears old context)
✅ "search again"          → Clear context, start over
✅ "show more"             → Show next 10 results (if >20 matches)
```

---

## 💡 **Benefits of This Approach**

### **User Benefits:**
- ✅ **Simple**: One search, see all possibilities
- ✅ **Visual**: See fleet size and type at a glance
- ✅ **Flexible**: Works with any partial information
- ✅ **No Memorization**: Don't need to know exact codes

### **Technical Benefits:**
- ✅ **Single Query**: One search across all fields
- ✅ **Clear Logic**: Easy to understand and maintain
- ✅ **Scalable**: Works with any number of operators
- ✅ **Efficient**: Fast database lookup

### **Business Benefits:**
- ✅ **User-Friendly**: Reduces support questions
- ✅ **Comprehensive**: Shows related operators
- ✅ **Discoverable**: Users find operators they didn't know about

---

## 🚀 **Implementation Steps**

### **Phase 1: Search Function**
1. ✅ Create cross-field search query
2. ✅ Build search results formatter
3. ✅ Add session context management
4. ✅ Test with various search terms

### **Phase 2: Selection Function**  
1. ✅ Handle number selections (1, 2, 3)
2. ✅ Retrieve full operator details
3. ✅ Format complete operator profile
4. ✅ Clear context after selection

### **Phase 3: Integration**
1. ✅ Add to Telegram bot
2. ✅ Add command recognition
3. ✅ Test full workflow
4. ✅ Deploy and monitor

---

**This approach is perfect!** It's intuitive, comprehensive, and handles all edge cases. Users get exactly what they expect - search once, see all options, pick the right one.

Ready to implement this clean, user-friendly search system? 🎯
