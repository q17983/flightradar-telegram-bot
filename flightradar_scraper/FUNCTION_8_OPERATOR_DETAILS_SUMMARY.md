# Function 8: Get Operator Details - Complete Summary

## 🎯 **Function Overview**

**Function Name:** `get-operator-details`  
**Purpose:** Get comprehensive operator profile when provided with IATA code  
**Input:** Operator IATA code (e.g., "LY", "EK", "DL")  
**Priority:** High - Core operator analysis functionality  

---

## 📋 **Detailed Requirements**

### **Input Parameters:**
- `operator_iata_code` (required) - The IATA code of the operator (e.g., "LY" for El Al)
- `start_time` (optional) - Period start for route analysis (default: last 12 months)
- `end_time` (optional) - Period end for route analysis (default: current date)

### **Output Data Structure:**

```json
{
  "operator_iata_code": "LY",
  "operator_details": {
    "operator_name": "El Al",
    "operator_icao_code": "ELY",
    "total_aircraft_count": 45,
    "period_start": "2024-01-01",
    "period_end": "2024-12-31"
  },
  "fleet_breakdown": [
    {
      "aircraft_type": "A333",
      "aircraft_details": "Airbus A330-343",
      "count": 5,
      "aircraft_category": "Passenger",
      "registrations": ["4X-EKA", "4X-EKB", "4X-EKC", "4X-EKD", "4X-EKE"]
    },
    {
      "aircraft_type": "B738",
      "aircraft_details": "Boeing 737-8GP",
      "count": 7,
      "aircraft_category": "Passenger", 
      "registrations": ["4X-EHA", "4X-EHB", "4X-EHC", "4X-EHD", "4X-EHE", "4X-EHF", "4X-EHG"]
    }
  ],
  "fleet_summary": {
    "total_aircraft": 45,
    "freighter_aircraft": 3,
    "passenger_aircraft": 42,
    "freighter_percentage": 7,
    "passenger_percentage": 93,
    "unique_aircraft_types": 8
  },
  "top_destinations": [
    {
      "destination_code": "JFK",
      "destination_name": "John F Kennedy International Airport",
      "total_flights": 245,
      "aircraft_types_used": ["B772", "B78X"],
      "avg_flights_per_month": 20.4
    },
    {
      "destination_code": "LHR", 
      "destination_name": "London Heathrow",
      "total_flights": 189,
      "aircraft_types_used": ["A333", "B772"],
      "avg_flights_per_month": 15.8
    }
  ]
}
```

---

## 🔍 **Data Analysis Requirements**

### **1. Fleet Analysis:**
- ✅ Count total aircraft per operator
- ✅ Group by aircraft type and details
- ✅ List all registrations for each aircraft type
- ✅ Classify as freighter/passenger using same logic as Function 1
- ✅ Calculate fleet composition percentages

### **2. Route Analysis:**
- ✅ Find top 20 destinations by flight frequency
- ✅ Include destination names (if available)
- ✅ Show aircraft types used on each route
- ✅ Calculate average flights per month
- ✅ Focus on period specified (default: last 12 months)

### **3. Operator Profile:**
- ✅ Get operator name and ICAO code
- ✅ Provide fleet summary statistics
- ✅ Show period analyzed

---

## 🛠️ **Technical Implementation Plan**

### **Database Queries Needed:**

#### **Query 1: Fleet Analysis**
```sql
SELECT 
    a.operator,
    a.operator_iata_code,
    a.operator_icao_code,
    a.type as aircraft_type,
    a.aircraft_details,
    a.registration,
    CASE 
        WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
          OR UPPER(a.aircraft_details) LIKE '%-F%'
          OR UPPER(a.aircraft_details) LIKE '%CARGO%'
          OR UPPER(a.aircraft_details) LIKE '%BCF%'
          OR UPPER(a.aircraft_details) LIKE '%SF%'
        THEN 'Freighter'
        ELSE 'Passenger'
    END as aircraft_category
FROM aircraft a
WHERE a.operator_iata_code = $1
  AND a.operator IS NOT NULL
ORDER BY a.aircraft_details, a.registration;
```

#### **Query 2: Route Analysis**
```sql
SELECT 
    m.destination_code,
    COUNT(*) as total_flights,
    array_agg(DISTINCT a.type) as aircraft_types_used
FROM movements m
JOIN aircraft a ON m.registration = a.registration
WHERE a.operator_iata_code = $1
  AND m.scheduled_departure >= $2
  AND m.scheduled_departure <= $3
GROUP BY m.destination_code
ORDER BY total_flights DESC
LIMIT 20;
```

### **Data Processing Steps:**
1. ✅ Validate IATA code input
2. ✅ Execute fleet analysis query
3. ✅ Group aircraft by type and collect registrations
4. ✅ Calculate fleet statistics and percentages
5. ✅ Execute route analysis query
6. ✅ Enhance with destination names (if available)
7. ✅ Calculate monthly averages
8. ✅ Format structured response

---

## 📊 **Expected Use Cases**

### **Business Intelligence:**
- "Show me El Al's fleet composition"
- "What aircraft types does Emirates operate?"
- "Where does Lufthansa fly most frequently?"
- "How many freighters does FedEx have?"

### **Telegram Bot Commands:**
- "Operator details LY" → El Al complete profile
- "Fleet breakdown EK" → Emirates fleet analysis
- "Show operator DL" → Delta Air Lines details

---

## 🎨 **Telegram Bot Display Format**

```
✈️ **OPERATOR PROFILE: EL AL (LY/ELY)**
📅 *Analysis Period: Jan 2024 - Dec 2024*

🚁 **FLEET SUMMARY**:
📊 *Total Aircraft: 45 (93% passenger, 7% freighter)*
🔢 *Aircraft Types: 8 different models*

🛩️ **FLEET BREAKDOWN**:
1. **Airbus A330-343** (5 aircraft) - Passenger
   • 4X-EKA, 4X-EKB, 4X-EKC, 4X-EKD, 4X-EKE

2. **Boeing 737-8GP** (7 aircraft) - Passenger  
   • 4X-EHA, 4X-EHB, 4X-EHC, 4X-EHD, 4X-EHE, 4X-EHF, 4X-EHG

🌍 **TOP DESTINATIONS** (20.4 avg/month):
1. **JFK** (New York): 245 flights [B772, B78X]
2. **LHR** (London): 189 flights [A333, B772] 
3. **CDG** (Paris): 156 flights [B738, A333]
```

---

## 🔧 **Technical Considerations**

### **Performance Optimizations:**
- ✅ Use indexes on `operator_iata_code` 
- ✅ Limit destination results to top 20
- ✅ Cache operator details for repeated queries
- ✅ Use connection pooling

### **Error Handling:**
- ✅ Invalid IATA code → "Operator not found"
- ✅ No aircraft data → "No fleet information available" 
- ✅ No movement data → "No route information available"
- ✅ Database connection issues → Proper error messages

### **Data Validation:**
- ✅ IATA code format (2-3 characters, uppercase)
- ✅ Date range validation
- ✅ Handle null/empty operator fields

---

## 🚀 **Implementation Priority**

### **Phase 1: Core Function (High Priority)**
- ✅ Fleet analysis with aircraft breakdown
- ✅ Basic operator information
- ✅ Registration listing per aircraft type
- ✅ Freighter/passenger classification

### **Phase 2: Route Analysis (Medium Priority)**  
- ✅ Top 20 destinations analysis
- ✅ Aircraft types per route
- ✅ Flight frequency calculations

### **Phase 3: Enhanced Features (Future)**
- ⏳ Destination name resolution
- ⏳ Seasonal route analysis
- ⏳ Fleet utilization metrics
- ⏳ Historical fleet changes

---

## 🎯 **Success Criteria**

### **Functional Requirements:**
- ✅ Accurate fleet count and breakdown
- ✅ Complete registration listing
- ✅ Proper freighter/passenger classification
- ✅ Top destination identification
- ✅ Clear, structured output format

### **Performance Requirements:**
- ✅ Response time < 3 seconds
- ✅ Handle concurrent requests
- ✅ Proper error handling
- ✅ Memory efficient processing

### **User Experience:**
- ✅ Intuitive Telegram bot integration
- ✅ Clear, formatted output
- ✅ Helpful error messages
- ✅ Consistent with Function 1 style

---

## 📋 **Development Checklist**

- [ ] **Phase 1: Preparation**
  - [ ] Create CHECKPOINT_004 before starting
  - [ ] Design database schema requirements
  - [ ] Plan SQL queries and data processing
  - [ ] Define response structure

- [ ] **Phase 2: Core Development**
  - [ ] Create `get-operator-details` Supabase function
  - [ ] Implement fleet analysis query
  - [ ] Add aircraft grouping and registration collection
  - [ ] Implement freighter/passenger classification
  - [ ] Test locally with sample IATA codes

- [ ] **Phase 3: Route Analysis**
  - [ ] Add route analysis query
  - [ ] Implement top destinations logic
  - [ ] Add aircraft type aggregation per route
  - [ ] Calculate flight frequency metrics

- [ ] **Phase 4: Integration & Deployment**
  - [ ] Update Telegram bot with new formatting function
  - [ ] Add command recognition for operator queries
  - [ ] Test locally with complete flow
  - [ ] Deploy to Supabase cloud
  - [ ] Deploy updated bot to Railway
  - [ ] Create final checkpoint

---

**Estimated Development Time:** 4-6 hours  
**Complexity:** Medium-High  
**Dependencies:** Existing database schema, Function 1 patterns  
**Next Step:** Create CHECKPOINT_004 and begin Phase 1 development

Ready to proceed with Function 8 development? 🚀
