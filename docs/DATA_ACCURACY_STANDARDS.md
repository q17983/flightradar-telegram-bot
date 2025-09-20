# 🎯 FlightRadar Scraper - Data Accuracy Standards

**Last Updated:** September 20, 2025  
**Status:** MANDATORY for All Functions  
**Priority:** HIGHEST - Data accuracy over performance

---

## 🚨 **CORE PRINCIPLE: ACCURACY OVER SPEED**

**"We would rather increase waiting time than sacrifice data accuracy"**

All functions must prioritize complete and accurate data over performance optimizations. Users prefer to wait longer for complete results rather than receive fast but incomplete data.

---

## 📋 **MANDATORY DATA ACCURACY RULES**

### **Rule 1: No Data Loss Through Filtering**
- ❌ **NEVER** use `HAVING COUNT(*) > 1` or similar filters that eliminate legitimate data
- ❌ **NEVER** reduce LIMIT below what's needed for complete coverage
- ❌ **NEVER** exclude operators, aircraft, or routes without explicit business logic
- ✅ **ALWAYS** include single-flight operations (they may be important charter/cargo flights)
- ✅ **ALWAYS** use `HAVING COUNT(*) >= 1` (or remove HAVING clause entirely)

### **Rule 2: Complete Operator Coverage**
- ✅ **ALWAYS** include ALL operators serving a route/destination
- ✅ **ALWAYS** use sufficient LIMIT (minimum 50,000 records for search/analysis queries)
- ✅ **Display functions** may use reasonable limits (15-50) for optimal user experience
- ✅ **ALWAYS** alert user if data exceeds processing limits
- ❌ **NEVER** silently truncate operator lists in search results

### **Rule 3: Accurate Aircraft Classification**
- ✅ **ALWAYS** use complete freighter detection logic:
  ```sql
  CASE 
    WHEN (
      -- Explicit freighter terms
      UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
      OR UPPER(a.aircraft_details) LIKE '%CARGO%'
      OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
      OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
      OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
      OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F patterns
      OR UPPER(a.aircraft_details) LIKE '%F%'        -- Broad F pattern
    )
    -- Exclude military and passenger patterns
    AND NOT (
      UPPER(a.aircraft_details) LIKE '%FK%'          -- Military variants
      OR UPPER(a.aircraft_details) LIKE '%TANKER%'   -- Military tanker
      OR UPPER(a.aircraft_details) LIKE '%VIP%'      -- VIP configuration
      OR UPPER(a.aircraft_details) LIKE '%FIRST%'    -- First class
      OR UPPER(a.aircraft_details) LIKE '%FLEX%'     -- Flexible config
    )
    THEN 'Freighter'
    ELSE 'Passenger'
  END as aircraft_category
  ```
- ❌ **NEVER** use simplified freighter detection that misses aircraft types

### **Rule 4: Time Range Integrity**
- ✅ **ALWAYS** respect user-specified time ranges exactly
- ✅ **ALWAYS** include boundary dates (>= start_date AND <= end_date)
- ❌ **NEVER** silently adjust time ranges for performance

### **Rule 5: Geographic Accuracy**
- ✅ **ALWAYS** use complete airport/country/continent matching
- ✅ **ALWAYS** include all airports matching geographic criteria
- ❌ **NEVER** exclude airports to reduce result size

---

## ⚠️ **TIMEOUT MANAGEMENT STRATEGY**

When queries risk timeout due to large datasets:

### **Preferred Approach:**
1. **Alert User** with specific message about data volume
2. **Suggest Time Frame Reduction** with specific recommendations
3. **Maintain Full Accuracy** within the suggested time frame
4. **Never Silently Truncate** results

### **Timeout Alert Template:**
```json
{
  "error": "Too many results to process accurately",
  "message": "The query returned too many results (10,000+ records) which may cause incomplete data or timeouts.",
  "suggestion": "Please narrow your search by using a shorter time frame:",
  "recommended_time_frames": [
    "Past 3 months: Reduce time range to last 3 months for more focused analysis",
    "Past 6 months: Use 6-month window for seasonal analysis",
    "Specific year: Choose a specific year (e.g., 2024-01-01 to 2024-12-31)",
    "Peak season: Focus on specific busy periods"
  ],
  "data_accuracy_note": "We prioritize complete data accuracy over speed. A shorter time frame will ensure you get all operators without missing any important data."
}
```

---

## 🔍 **MANDATORY ACCURACY CHECKS**

### **Before Deployment:**
- [ ] **Query Review:** Does the query include ALL relevant data?
- [ ] **Filter Audit:** Do any filters eliminate important data?
- [ ] **Limit Check:** Is the LIMIT at least 50,000 for complete coverage?
- [ ] **Classification Review:** Is aircraft/operator classification complete?
- [ ] **Time Range Test:** Are boundary conditions handled correctly?
- [ ] **Callback System Test:** Do callback handlers produce identical results to direct function calls?
- [ ] **Large Dataset Test:** Can the system handle 100+ operator results in callback context?

### **During Development:**
- [ ] **Test with Large Datasets:** Verify behavior with high-volume routes
- [ ] **Test Edge Cases:** Single-flight operators, rare aircraft types
- [ ] **Test Time Boundaries:** Start/end date edge cases
- [ ] **Compare Results:** Cross-check with known data for accuracy
- [ ] **Test Callback Consistency:** Verify callback results match direct function calls
- [ ] **Test Function Switching:** Ensure mismatch dialogs work and produce correct results

---

## 📊 **FUNCTION-SPECIFIC ACCURACY REQUIREMENTS**

### **Function 1: get-operators-by-destination**
- ✅ Include ALL operators (freighter AND passenger)
- ✅ Complete aircraft type breakdown
- ✅ All registrations per aircraft type
- ✅ Accurate flight frequency counts

### **Function 8: get-operator-details**
- ✅ Complete fleet analysis (all aircraft types)
- ✅ Top destinations (reasonable limit: 50 for display)
- ✅ Accurate freighter/passenger percentages
- ✅ Complete registration lists (reasonable limit for display)

### **Function 10: get-operators-by-geographic-locations**
- ✅ ALL operators serving BOTH locations
- ✅ Complete airport coverage per continent/country
- ✅ All aircraft types and registrations
- ✅ Accurate geographic matching

### **Function 12: aircraft-to-destination-search**
- ✅ ALL operators using specified aircraft type
- ✅ ALL destinations served by that aircraft
- ✅ Complete route frequency data
- ✅ Accurate aircraft variant matching

### **Callback System Accuracy Requirements**
- ✅ **Identical Results:** Callback execution must produce same results as direct function calls
- ✅ **Data Consistency:** MockMessage approach maintains all data integrity
- ✅ **Error Handling:** Same error handling patterns as normal message processing
- ⚠️ **Large Dataset Limitation:** 100+ operator results may require alternative UX in callback context
- ✅ **Function Switching:** Mismatch detection and switching preserves data accuracy

---

## 🚫 **FORBIDDEN OPTIMIZATIONS**

### **Never Use These for Performance:**
- ❌ `HAVING COUNT(*) > 1` (eliminates single-flight operations)
- ❌ `LIMIT < 50000` for search/analysis queries (may miss operators)
- ❌ `LIMIT < 15-50` for display functions (poor user experience)
- ❌ Simplified freighter detection (misses aircraft types)
- ❌ Geographic filtering that excludes valid airports
- ❌ Time range adjustments without user consent
- ❌ Operator exclusions based on flight frequency

### **Acceptable Optimizations:**
- ✅ Query structure improvements (CTEs, JOINs)
- ✅ Index utilization
- ✅ Connection pooling
- ✅ Result caching (if data integrity maintained)
- ✅ Timeout alerts with user guidance

---

## 🎯 **ACCURACY VALIDATION PROCESS**

### **For Each Function:**
1. **Manual Verification:** Test with known routes/operators
2. **Cross-Reference:** Compare results with external sources
3. **Edge Case Testing:** Single flights, rare aircraft, small operators
4. **Volume Testing:** High-traffic routes, long time periods
5. **Boundary Testing:** Date ranges, geographic edges

### **Accuracy Metrics:**
- **Completeness:** Are all expected operators/aircraft included?
- **Correctness:** Are classifications and counts accurate?
- **Consistency:** Do results match across similar queries?
- **Coverage:** Are edge cases and rare scenarios handled?

---

## 📈 **CONTINUOUS ACCURACY MONITORING**

### **Regular Checks:**
- **Monthly:** Spot-check function results against known data
- **After Updates:** Full accuracy validation after any changes
- **User Reports:** Investigate any accuracy concerns immediately

### **Accuracy Regression Prevention:**
- **Code Reviews:** All changes reviewed for accuracy impact
- **Test Cases:** Maintain accuracy test suite
- **Documentation:** Keep accuracy requirements updated

---

## 🏆 **ACCURACY SUCCESS METRICS**

### **Target Standards:**
- **100% Operator Coverage:** No operators missed due to filtering
- **100% Aircraft Classification:** All aircraft correctly categorized
- **100% Time Range Accuracy:** Exact adherence to user time frames
- **Zero Silent Truncation:** All data limits communicated to user

### **Quality Indicators:**
- ✅ User satisfaction with result completeness
- ✅ No reports of missing operators/aircraft
- ✅ Consistent results across similar queries
- ✅ Clear communication when limits reached

---

**Remember: Our users depend on complete, accurate flight data for critical business decisions. Data accuracy is not negotiable.**

**Last Updated:** September 20, 2025  
**Next Review:** After any function modification  
**Maintainer:** FlightRadar Development Team
