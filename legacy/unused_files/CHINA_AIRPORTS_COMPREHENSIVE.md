# 🇨🇳 Comprehensive China Airports List

## Discovery Strategy

### **Method 1: ICAO Code Pattern (Most Reliable)**
- All China airports use ICAO prefix 'Z***'
- Database query: `WHERE destination_code LIKE 'Z%'`
- This captures ALL China airports systematically

### **Method 2: Known Major Airports (Verification)**

## **Tier 1: International Hubs (4 airports)**
- **PEK** - Beijing Capital International Airport
- **PVG** - Shanghai Pudong International Airport  
- **CAN** - Guangzhou Baiyun International Airport
- **SZX** - Shenzhen Bao'an International Airport

## **Tier 2: Major Regional Hubs (15 airports)**
- **CTU** - Chengdu Shuangliu International Airport
- **KMG** - Kunming Changshui International Airport
- **XIY** - Xi'an Xianyang International Airport
- **WUH** - Wuhan Tianhe International Airport
- **NKG** - Nanjing Lukou International Airport
- **HGH** - Hangzhou Xiaoshan International Airport
- **CSX** - Changsha Huanghua International Airport
- **TSN** - Tianjin Binhai International Airport
- **DLC** - Dalian Zhoushuizi International Airport
- **HRB** - Harbin Taiping International Airport
- **URC** - Urumqi Diwopu International Airport
- **CKG** - Chongqing Jiangbei International Airport
- **XMN** - Xiamen Gaoqi International Airport
- **FOC** - Fuzhou Changle International Airport
- **SHE** - Shenyang Taoxian International Airport

## **Tier 3: Secondary Cities (25+ airports)**
- **CGO** - Zhengzhou Xinzheng International Airport
- **TNA** - Jinan Yaoqiang International Airport
- **HET** - Hohhot Baita International Airport
- **JJN** - Quanzhou Jinjiang Airport
- **NNG** - Nanning Wuxu International Airport
- **TAO** - Qingdao Jiaodong International Airport
- **YNT** - Yantai Penglai International Airport
- **WEH** - Weihai Dashuibo Airport
- **WNZ** - Wenzhou Longwan International Airport
- **JUZ** - Quzhou Airport
- **HLD** - Hailar Dongshan Airport
- **JMU** - Jiamusi Dongjiao Airport
- **TCG** - Tacheng Airport
- **LYI** - Linyi Shubuling Airport
- **ENY** - Yanbian Chaoyangchuan Airport
- **CIH** - Changzhi Wangcun Airport

## **Complete Discovery Methods**

### **Database Query Approach:**
```sql
-- Find ALL China airports in our database
SELECT DISTINCT
    destination_code,
    destination_name,
    COUNT(*) as flight_count,
    COUNT(DISTINCT a.operator) as operator_count
FROM movements m
JOIN aircraft a ON m.registration = a.registration  
WHERE destination_code LIKE 'Z%'
  AND destination_code IS NOT NULL
  AND destination_name IS NOT NULL
GROUP BY destination_code, destination_name
ORDER BY flight_count DESC;
```

### **Verification Strategy:**
1. **Test with Bot:** Use Telegram bot to test known airports
2. **Cross-Reference:** Compare with aviation databases
3. **Pattern Analysis:** Look for any non-Z* China airports
4. **Regional Coverage:** Ensure all provinces covered

## **Expected Benefits:**

### **For Function Development:**
- **Complete Coverage:** No missing China airports
- **Reliable Data:** Based on actual flight data
- **Scalable:** Same approach works for other regions

### **For Business Value:**
- **Market Analysis:** Complete China aviation landscape
- **Route Planning:** All possible China destinations
- **Competition Research:** Every operator's China presence
- **Opportunity Identification:** Underserved airports

## **Next Steps:**
1. Query database with 'Z%' pattern
2. Verify major known airports are included
3. Create final comprehensive China airports list
4. Use this list for Function development

**This systematic approach ensures we capture ALL China airports, not just the major ones!**
