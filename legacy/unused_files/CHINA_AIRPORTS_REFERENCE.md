# 🇨🇳 Complete China Airport Reference List

## **Purpose**
This comprehensive list ensures we capture ALL China airports when developing regional functions, not just major hubs.

## **China Airport ICAO/IATA Codes**

### **Major International Hubs (Tier 1)**
| ICAO | IATA | Airport Name | City |
|------|------|--------------|------|
| ZBAA | PEK | Beijing Capital International | Beijing |
| ZPPP | PVG | Shanghai Pudong International | Shanghai |
| ZGGG | CAN | Guangzhou Baiyun International | Guangzhou |
| ZGSZ | SZX | Shenzhen Bao'an International | Shenzhen |

### **Major Regional Hubs (Tier 2)**
| ICAO | IATA | Airport Name | City |
|------|------|--------------|------|
| ZUUU | CTU | Chengdu Shuangliu International | Chengdu |
| ZPKM | KMG | Kunming Changshui International | Kunming |
| ZLXY | XIY | Xi'an Xianyang International | Xi'an |
| ZHWH | WUH | Wuhan Tianhe International | Wuhan |
| ZSNJ | NKG | Nanjing Lukou International | Nanjing |
| ZSHC | HGH | Hangzhou Xiaoshan International | Hangzhou |
| ZGHA | CSX | Changsha Huanghua International | Changsha |
| ZBTJ | TSN | Tianjin Binhai International | Tianjin |
| ZYTX | DLC | Dalian Zhoushuizi International | Dalian |
| ZYHB | HRB | Harbin Taiping International | Harbin |
| ZWWW | URC | Urumqi Diwopu International | Urumqi |
| ZUCK | CKG | Chongqing Jiangbei International | Chongqing |

### **Important Secondary Cities (Tier 3)**
| ICAO | IATA | Airport Name | City |
|------|------|--------------|------|
| ZHCC | CGO | Zhengzhou Xinzheng International | Zhengzhou |
| ZSJN | TNA | Jinan Yaoqiang International | Jinan |
| ZBHH | HET | Hohhot Baita International | Hohhot |
| ZSQD | TAO | Qingdao Jiaodong International | Qingdao |
| ZYNN | NNG | Nanning Wuxu International | Nanning |
| ZSAM | XMN | Xiamen Gaoqi International | Xiamen |
| ZSFZ | FOC | Fuzhou Changle International | Fuzhou |
| ZYTX | SHE | Shenyang Taoxian International | Shenyang |
| ZYYN | YNT | Yantai Penglai International | Yantai |
| ZSWH | WEH | Weihai Dashuibo | Weihai |
| ZSWZ | WNZ | Wenzhou Longwan International | Wenzhou |
| ZJHK | HAK | Haikou Meilan International | Haikou |
| ZJSY | SYX | Sanya Phoenix International | Sanya |

### **Additional Regional Airports (Tier 4)**
| ICAO | IATA | Airport Name | City |
|------|------|--------------|------|
| ZJQZ | JUZ | Quzhou | Quzhou |
| ZYHL | HLD | Hailar Dongshan | Hailar |
| ZYJS | JMU | Jiamusi Dongjiao | Jiamusi |
| ZWTC | TCG | Tacheng | Tacheng |
| ZSLY | LYI | Linyi Shubuling | Linyi |
| ZYYJ | YNJ | Yanji Chaoyangchuan | Yanji |
| ZBCZ | CIH | Changzhi Wangcun | Changzhi |

## **Database Query Strategy**

### **Method 1: ICAO Pattern (Recommended)**
```sql
-- Find ALL China airports using ICAO prefix
SELECT DISTINCT
    destination_code,
    destination_name,
    COUNT(*) as flight_count
FROM movements 
WHERE destination_code LIKE 'Z%'
  AND destination_code IS NOT NULL
GROUP BY destination_code, destination_name
ORDER BY flight_count DESC;
```

### **Method 2: Known Airport Verification**
```sql
-- Verify major known China airports
SELECT destination_code, destination_name, COUNT(*) as flights
FROM movements
WHERE destination_code IN (
    'PEK', 'PVG', 'CAN', 'SZX', 'CTU', 'KMG', 'XIY', 'WUH',
    'NKG', 'HGH', 'CSX', 'TSN', 'DLC', 'HRB', 'URC', 'CKG',
    'CGO', 'TNA', 'HET', 'TAO', 'NNG', 'XMN', 'FOC', 'SHE'
)
GROUP BY destination_code, destination_name
ORDER BY flights DESC;
```

## **Expected Coverage**
- **238 total civil airports** in China (as of 2019)
- **Major hubs:** ~15 airports handling most international traffic
- **Regional airports:** ~50 airports with significant domestic traffic  
- **Secondary airports:** ~170+ smaller regional facilities

## **Benefits for Function Development**
1. **Complete Coverage:** Ensures no China airport is missed
2. **Data Validation:** Cross-reference with our database results  
3. **Tier Classification:** Understand airport importance levels
4. **Scalable:** Same approach works for other regions

## **Next Steps**
1. Run database query with 'Z%' pattern
2. Compare results with this reference list
3. Identify any gaps or unexpected airports
4. Create final comprehensive China airport array for functions

**This reference ensures our regional functions capture the complete China aviation landscape!**
