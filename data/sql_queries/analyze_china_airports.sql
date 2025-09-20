-- Comprehensive China Airport Analysis

-- Method 1: Find all airports with China ICAO prefix 'Z'
SELECT DISTINCT
    destination_code,
    destination_name,
    COUNT(*) as total_flights,
    COUNT(DISTINCT operator) as operator_count
FROM movements m
JOIN aircraft a ON m.registration = a.registration
WHERE destination_code LIKE 'Z%'
  AND destination_code IS NOT NULL
  AND destination_name IS NOT NULL
GROUP BY destination_code, destination_name
ORDER BY total_flights DESC;

-- Method 2: Find airports by country name (if available)
SELECT DISTINCT
    destination_code,
    destination_name,
    COUNT(*) as total_flights
FROM movements m
WHERE (destination_name LIKE '%China%' 
    OR destination_name LIKE '%Beijing%'
    OR destination_name LIKE '%Shanghai%'
    OR destination_name LIKE '%Guangzhou%'
    OR destination_name LIKE '%Shenzhen%'
    OR destination_code LIKE 'Z%')
  AND destination_code IS NOT NULL
GROUP BY destination_code, destination_name
ORDER BY total_flights DESC;

-- Method 3: Major known China airports verification
SELECT 
    destination_code,
    destination_name,
    COUNT(*) as flights
FROM movements
WHERE destination_code IN (
    'PEK', 'PVG', 'CAN', 'SZX', 'CTU', 'KMG', 'XIY', 'DLC', 'WUH', 'CSX',
    'NKG', 'HGH', 'TSN', 'HRB', 'SJW', 'CGO', 'TNA', 'HET', 'URC', 'LHW',
    'NNG', 'TAO', 'XMN', 'FOC', 'HAK', 'SYX', 'NZH', 'JJN', 'MDG', 'DDG',
    'YNT', 'WEH', 'WNZ', 'JUZ', 'HLD', 'JMU', 'TCG', 'LYI', 'ENY', 'CIH'
)
GROUP BY destination_code, destination_name
ORDER BY flights DESC;
