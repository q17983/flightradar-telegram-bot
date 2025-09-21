// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.7.1'
import { corsHeaders } from '../_shared/cors.ts' // Use shared CORS

const DATABASE_POOL_SIZE = 3
console.log(`Function "get-operator-details" up and running!`)

/**
 * Function 8: Get operator details with smart search and fleet/route analysis
 * Supports cross-field search (IATA, ICAO, operator name) with disambiguation
 */
serve(async (req: Request) => {
  // 1. Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection; // Define connection outside try block to access in finally

  try {
    // 2. Parse incoming request body
    if (!req.body) {
      throw new Error("Request body is missing.")
    }
    
    const { 
      search_query, 
      operator_selection, 
      start_time = "2024-01-01", 
      end_time = "2024-12-31",
      geographic_filter,  // ENHANCED: Geographic filtering
      filter_type         // ENHANCED: "country" or "continent"
    } = await req.json()

    // Basic validation
    if (!search_query && !operator_selection) {
      throw new Error("Missing required parameter: search_query or operator_selection")
    }

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL') // Use DATABASE_URL from .env.local
    console.log("Function 8: DATABASE_URL available:", !!databaseUrl)
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      console.log("Available env vars:", Object.keys(Deno.env.toObject()))
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    connection = await pool.connect()
    console.log("Function 8: Database connection established successfully")

    // Test basic database connectivity
    const testResult = await connection.queryObject("SELECT 1 as test")
    console.log("Function 8: Database test query successful:", testResult.rows)

    // 6. ENHANCED: Handle three modes: search, get details, or geographic filtering
    console.log("Function 8 mode check - operator_selection:", operator_selection, "search_query:", search_query, "geographic_filter:", geographic_filter)
    
    if (operator_selection && geographic_filter) {
      // Mode 3: ENHANCED - Geographic filtering for operator destinations
      console.log("Function 8: Getting geographic destinations for:", operator_selection, "in", geographic_filter)
      return await getOperatorGeographicDestinations(connection, operator_selection, geographic_filter, filter_type, start_time, end_time)
    } else if (operator_selection) {
      // Mode 2: Get full operator details (after selection)
      return await getOperatorDetails(connection, operator_selection, start_time, end_time)
    } else {
      // Mode 1: Search for operators (return selection list)
      return await searchOperators(connection, search_query)
    }

  } catch (error) {
    // Handle errors
    console.error("Error in get-operator-details:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
    const isInputError = error instanceof Error && (
      error.message.startsWith("Missing required parameter") ||
      error.message.startsWith("Invalid") ||
      error.message.startsWith("No operators found")
    );
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500;

    // Ensure connection is released even if error happened before finally
    if (connection) {
        try { await connection.release(); } catch (releaseError) { console.error("Error releasing connection during error handling:", releaseError); }
    }

    return new Response(
      JSON.stringify({ error: clientErrorMessage }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: statusCode,
      }
    )
  } finally {
    // 7. Release connection
    if (connection) await connection.release();
  }
})

/**
 * Search for operators across IATA, ICAO, and name fields
 */
async function searchOperators(connection: any, searchQuery: string) {
  const searchSql = `
    SELECT DISTINCT
        a.operator,
        a.operator_iata_code,
        a.operator_icao_code,
        COUNT(*) as aircraft_count,
        -- Calculate freighter percentage
        ROUND(
            (COUNT(CASE WHEN (
                -- Explicit freighter terms
                UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
                OR UPPER(a.aircraft_details) LIKE '%CARGO%'
                OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
                OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
                OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
                OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F patterns
                
                -- Broad F pattern for comprehensive coverage
                OR UPPER(a.aircraft_details) LIKE '%F%'
            )
            -- Exclude military and passenger patterns
            AND NOT (
                UPPER(a.aircraft_details) LIKE '%FK%'          -- Military variants (e.g., 767-2FK)
                OR UPPER(a.aircraft_details) LIKE '%TANKER%'   -- Military tanker
                OR UPPER(a.aircraft_details) LIKE '%VIP%'      -- VIP configuration
                OR UPPER(a.aircraft_details) LIKE '%FIRST%'    -- First class
                OR UPPER(a.aircraft_details) LIKE '%FLEX%'     -- Flexible config
            )
            THEN 1 END) * 100.0 / COUNT(*)), 0
        ) as freighter_percentage,
        -- Determine match type for ranking
        CASE 
            WHEN UPPER(COALESCE(a.operator_iata_code, '')) = UPPER($1) THEN 1
            WHEN UPPER(COALESCE(a.operator_icao_code, '')) = UPPER($1) THEN 2  
            WHEN UPPER(a.operator) = UPPER($1) THEN 3
            WHEN UPPER(a.operator) LIKE UPPER($1) || '%' THEN 4
            WHEN UPPER(a.operator) LIKE '%' || UPPER($1) || '%' THEN 5
            WHEN UPPER(COALESCE(a.operator_iata_code, '')) LIKE '%' || UPPER($1) || '%' THEN 6
            WHEN UPPER(COALESCE(a.operator_icao_code, '')) LIKE '%' || UPPER($1) || '%' THEN 7
            ELSE 8
        END as match_rank
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
    ORDER BY match_rank ASC, aircraft_count DESC
    LIMIT 15;
  `
  
  const result = await connection.queryObject(searchSql, [searchQuery])
  
  if (result.rows.length === 0) {
    throw new Error(`No operators found matching "${searchQuery}"`)
  }

  // Process results for selection response
  const operators = result.rows.map((row, index) => ({
    selection_id: (index + 1).toString(),
    operator: row.operator,
    operator_iata_code: row.operator_iata_code,
    operator_icao_code: row.operator_icao_code,
    aircraft_count: Number(row.aircraft_count),
    freighter_percentage: Number(row.freighter_percentage),
    passenger_percentage: 100 - Number(row.freighter_percentage),
    match_rank: Number(row.match_rank)
  }));

  console.log(`Found ${operators.length} operators matching "${searchQuery}"`);

  return new Response(
    JSON.stringify({
      search_query: searchQuery,
      result_type: "search_results",
      operators_found: operators,
      total_matches: operators.length,
      message: `Select operator by number (1-${operators.length}) or search again`
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  )
}

/**
 * Get full operator details (fleet breakdown + route analysis)
 */
async function getOperatorDetails(connection: any, operatorSelection: string, startTime: string, endTime: string) {
  // First, we need to map selection back to operator
  // For now, we'll use a simple approach - reconstruct search or use operator name directly
  
  // Fleet Analysis Query
  const fleetSql = `
    SELECT 
        a.operator,
        a.operator_iata_code,
        a.operator_icao_code,
        a.type as aircraft_type,
        a.aircraft_details,
        a.registration,
        CASE 
          -- Rule 1: VIP/Corporate (Highest Priority)
          WHEN UPPER(a.aircraft_details) LIKE '%(BBJ%)'
          THEN 'Passenger (VIP/Corporate)'
          
          -- Rule 2: Dedicated Freighters (Second Priority)
          WHEN (
            -- Production Freighters (F as standalone suffix)
            UPPER(a.aircraft_details) LIKE '%F' 
            OR UPPER(a.aircraft_details) LIKE '%-F'
            -- Note: Multi-letter F patterns (FH, FN, FB, FE, FZ, F2) may be customer codes
            
            -- Converted Freighters
            OR UPPER(a.aircraft_details) LIKE '%(BCF)'
            OR UPPER(a.aircraft_details) LIKE '%(BDSF)'
            OR UPPER(a.aircraft_details) LIKE '%(SF)'
            OR UPPER(a.aircraft_details) LIKE '%(PCF)'
            OR UPPER(a.aircraft_details) LIKE '%(P2F)'
            OR UPPER(a.aircraft_details) LIKE '%PF'
            
            -- Explicit Terms
            OR UPPER(a.aircraft_details) LIKE '%FREIGHTER%'
            OR UPPER(a.aircraft_details) LIKE '%CARGO%'
          )
          AND NOT UPPER(a.aircraft_details) LIKE '%(BBJ%)'
          AND NOT UPPER(a.aircraft_details) LIKE '%FK%'
          AND NOT UPPER(a.aircraft_details) LIKE '%TANKER%'
          AND NOT UPPER(a.aircraft_details) LIKE '%VIP%'
          AND NOT UPPER(a.aircraft_details) LIKE '%FIRST%'
          THEN 'Freighter'
          
          -- Rule 3: Multi-Role (Third Priority)
          WHEN (
            UPPER(a.aircraft_details) LIKE '%(FC)'
            OR UPPER(a.aircraft_details) LIKE '%(CF)'
            OR UPPER(a.aircraft_details) LIKE '%(C)'
            OR UPPER(a.aircraft_details) LIKE '%(M)'
          )
          AND NOT UPPER(a.aircraft_details) LIKE '%(BBJ%)'
          AND NOT (
            UPPER(a.aircraft_details) LIKE '%(BCF)'
            OR UPPER(a.aircraft_details) LIKE '%(BDSF)'
            OR UPPER(a.aircraft_details) LIKE '%(SF)'
            OR UPPER(a.aircraft_details) LIKE '%(PCF)'
            OR UPPER(a.aircraft_details) LIKE '%(P2F)'
          )
          THEN 'Multi-Role (Passenger/Cargo)'
          
          -- Rule 4: Default Passenger
          ELSE 'Passenger'
        END as aircraft_category
    FROM aircraft a
    WHERE a.operator = $1
      AND a.operator IS NOT NULL
    ORDER BY a.aircraft_details, a.registration;
  `

  // Route Analysis Query - Enhanced to show TOP 30 destinations
  const routeSql = `
    SELECT 
        m.destination_code,
        COUNT(*) as total_flights,
        array_agg(DISTINCT a.type ORDER BY a.type) as aircraft_types_used,
        ROUND(COUNT(*) / 12.0, 1) as avg_flights_per_month
    FROM movements m
    JOIN aircraft a ON m.registration = a.registration
    WHERE a.operator = $1
      AND m.actual_arrival >= $2
      AND m.actual_arrival <= $3
      AND m.actual_arrival IS NOT NULL
    GROUP BY m.destination_code
    ORDER BY total_flights DESC
    LIMIT 50;
  `

  // Execute both queries
  const [fleetResult, routeResult] = await Promise.all([
    connection.queryObject(fleetSql, [operatorSelection]),
    connection.queryObject(routeSql, [operatorSelection, startTime, endTime])
  ]);

  if (fleetResult.rows.length === 0) {
    throw new Error(`No fleet data found for operator "${operatorSelection}"`)
  }

  // Process fleet data
  const fleetData = fleetResult.rows.map(row => ({
    ...row,
    aircraft_category: row.aircraft_category
  }));

  // Get operator basic info
  const operatorInfo = fleetData[0];

  // Group fleet by aircraft type
  const fleetByType = new Map();
  fleetData.forEach(aircraft => {
    const key = `${aircraft.aircraft_type}|${aircraft.aircraft_details}|${aircraft.aircraft_category}`;
    if (!fleetByType.has(key)) {
      fleetByType.set(key, {
        aircraft_type: aircraft.aircraft_type,
        aircraft_details: aircraft.aircraft_details,
        aircraft_category: aircraft.aircraft_category,
        count: 0,
        registrations: []
      });
    }
    const group = fleetByType.get(key);
    group.count++;
    group.registrations.push(aircraft.registration);
  });

  const fleetBreakdown = Array.from(fleetByType.values())
    .sort((a, b) => b.count - a.count);

  // Calculate fleet summary
  const totalAircraft = fleetData.length;
  const freighterAircraft = fleetData.filter(a => a.aircraft_category === 'Freighter').length;
  const passengerAircraft = totalAircraft - freighterAircraft;
  const freighterPercentage = totalAircraft > 0 ? Math.round((freighterAircraft / totalAircraft) * 100) : 0;
  const passengerPercentage = 100 - freighterPercentage;

  // Process route data
  const topDestinations = routeResult.rows.map(row => ({
    destination_code: row.destination_code,
    total_flights: Number(row.total_flights),
    aircraft_types_used: row.aircraft_types_used || [],
    avg_flights_per_month: Number(row.avg_flights_per_month)
  }));

  console.log(`Generated full profile for operator "${operatorSelection}" with ${totalAircraft} aircraft and ${topDestinations.length} destinations`);

  return new Response(
    JSON.stringify({
      search_query: operatorSelection,
      result_type: "operator_details",
      operator_details: {
        operator_name: operatorInfo.operator,
        operator_iata_code: operatorInfo.operator_iata_code,
        operator_icao_code: operatorInfo.operator_icao_code,
        total_aircraft_count: totalAircraft,
        period_start: startTime,
        period_end: endTime
      },
      fleet_breakdown: fleetBreakdown,
      fleet_summary: {
        total_aircraft: totalAircraft,
        freighter_aircraft: freighterAircraft,
        passenger_aircraft: passengerAircraft,
        freighter_percentage: freighterPercentage,
        passenger_percentage: passengerPercentage,
        unique_aircraft_types: fleetBreakdown.length
      },
      top_destinations: topDestinations
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  )
}

/**
 * ENHANCED: Get operator destinations filtered by geography (country/continent)
 */
async function getOperatorGeographicDestinations(
  connection: any, 
  operatorSelection: string, 
  geographicFilter: string, 
  filterType: string,
  startTime: string, 
  endTime: string
) {
  console.log(`Getting geographic destinations for ${operatorSelection} in ${geographicFilter} (${filterType})`)

  // Geographic filtering query with airports_geography integration
  const geographicSql = `
    SELECT 
        m.destination_code,
        ag.airport_name,
        ag.country_name,
        ag.continent,
        COUNT(*) as total_flights,
        array_agg(DISTINCT a.type ORDER BY a.type) as aircraft_types_used,
        ROUND(COUNT(*) / 12.0, 1) as avg_flights_per_month
    FROM movements m
    JOIN aircraft a ON m.registration = a.registration
    JOIN airports_geography ag ON m.destination_code = ag.iata_code
    WHERE a.operator = $1
      AND m.actual_arrival >= $2
      AND m.actual_arrival <= $3
      AND m.actual_arrival IS NOT NULL
      AND (
        CASE 
          WHEN $4 = 'country' THEN ag.country_name ILIKE $5
          WHEN $4 = 'continent' THEN ag.continent ILIKE $5
          ELSE false
        END
      )
    GROUP BY m.destination_code, ag.airport_name, ag.country_name, ag.continent
    ORDER BY total_flights DESC
    LIMIT 50;
  `

  // Execute the geographic query
  console.log(`DEBUG: Geographic query parameters:`, {
    operator: operatorSelection,
    startTime,
    endTime,
    filterType,
    geographicFilter: geographicFilter
  });

  const geographicResult = await connection.queryObject(geographicSql, [
    operatorSelection,  // $1
    startTime,          // $2
    endTime,            // $3
    filterType,         // $4
    `%${geographicFilter}%`  // $5 - Use LIKE pattern for flexible matching
  ]);

  console.log(`Geographic query returned ${geographicResult.rows?.length || 0} destinations`)
  
  // DEBUG: Check if operator exists at all
  const operatorCheckSql = `
    SELECT DISTINCT a.operator, COUNT(*) as total_flights
    FROM movements m
    JOIN aircraft a ON m.registration = a.registration
    WHERE (a.operator ILIKE '%${operatorSelection}%' 
           OR a.operator ILIKE '%Icel%' 
           OR a.operator ILIKE '%Iceland%')
      AND m.actual_arrival >= $1
      AND m.actual_arrival <= $2
      AND m.actual_arrival IS NOT NULL
    GROUP BY a.operator
    ORDER BY total_flights DESC
    LIMIT 10;
  `;
  
  const operatorCheck = await connection.queryObject(operatorCheckSql, [startTime, endTime]);
  console.log(`DEBUG: Similar operators found:`, operatorCheck.rows);

  if (!geographicResult.rows || geographicResult.rows.length === 0) {
    return new Response(
      JSON.stringify({
        error: `No destinations found for ${operatorSelection} in ${geographicFilter}. Try alternative spelling or check if operator serves this region.`,
        operator: operatorSelection,
        geographic_filter: geographicFilter,
        filter_type: filterType
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 404 }
    )
  }

  // Process the geographic results
  const geographicDestinations = geographicResult.rows.map(row => ({
    destination_code: row.destination_code,
    airport_name: row.airport_name,
    country_name: row.country_name,
    continent: row.continent,
    total_flights: Number(row.total_flights),
    aircraft_types_used: row.aircraft_types_used || [],
    avg_flights_per_month: Number(row.avg_flights_per_month)
  }));

  console.log(`Successfully processed ${geographicDestinations.length} geographic destinations`)

  return new Response(
    JSON.stringify({
      result_type: "geographic_destinations",
      operator: operatorSelection,
      geographic_filter: geographicFilter,
      filter_type: filterType,
      period_start: startTime,
      period_end: endTime,
      total_destinations: geographicDestinations.length,
      total_flights: geographicDestinations.reduce((sum, dest) => sum + dest.total_flights, 0),
      geographic_destinations: geographicDestinations
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  )
}

/* Function 8 Testing:
  
  // Search mode
  curl -i --location --request POST 'http://localhost:54321/functions/v1/get-operator-details' \
    --header 'Authorization: Bearer [TOKEN]' \
    --header 'Content-Type: application/json' \
    --data '{"search_query":"FX"}'

  // Details mode  
  curl -i --location --request POST 'http://localhost:54321/functions/v1/get-operator-details' \
    --header 'Authorization: Bearer [TOKEN]' \
    --header 'Content-Type: application/json' \
    --data '{"operator_selection":"FedEx","start_time":"2024-01-01","end_time":"2024-12-31"}'

  // ENHANCED: Geographic filtering mode
  curl -i --location --request POST 'http://localhost:54321/functions/v1/get-operator-details' \
    --header 'Authorization: Bearer [TOKEN]' \
    --header 'Content-Type: application/json' \
    --data '{"operator_selection":"Qatar Airways","geographic_filter":"China","filter_type":"country","start_time":"2024-01-01","end_time":"2024-12-31"}'
*/
