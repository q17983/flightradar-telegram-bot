-- Test queries to understand the aircraft table structure

-- 1. Check total records
SELECT COUNT(*) as total_aircraft FROM aircraft;

-- 2. Check distinct aircraft types
SELECT DISTINCT type, COUNT(*) as count 
FROM aircraft 
WHERE type IS NOT NULL 
GROUP BY type 
ORDER BY count DESC;

-- 3. Check sample data
SELECT registration, type, operator, aircraft_details 
FROM aircraft 
WHERE type IS NOT NULL 
LIMIT 10;

-- 4. Check if there are NULL operators
SELECT 
  COUNT(*) as total_records,
  COUNT(CASE WHEN operator IS NULL THEN 1 END) as null_operators,
  COUNT(CASE WHEN operator IS NOT NULL THEN 1 END) as non_null_operators
FROM aircraft;

-- 5. Check specific types from scraper list
SELECT type, COUNT(*) as count
FROM aircraft 
WHERE type IN ('A330', 'B747', 'B757', 'B767', 'B777', 'IL76', 'B737')
GROUP BY type
ORDER BY count DESC;

