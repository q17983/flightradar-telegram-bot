// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
// CORS headers for cross-origin requests
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

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
    // Expect search_query, operator_selection, start_time, end_time
    const requestBody = await req.json()
    console.log("Function 8 received request body:", JSON.stringify(requestBody))
    
    const { 
      search_query, 
      operator_selection, 
      start_time = "2024-04-01", 
      end_time = "2025-05-31" 
    } = requestBody

    // Basic validation
    if (!search_query && !operator_selection) {
      throw new Error("Missing required parameter: search_query or operator_selection")
    }

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    connection = await pool.connect()

    // 6. Handle two modes: search or get details
    console.log("Function 8 mode check - operator_selection:", operator_selection, "search_query:", search_query)
    
    if (operator_selection) {
      // Mode 2: Get full operator details (after selection)
      console.log("Function 8: Getting operator details for:", operator_selection)
      return await getOperatorDetails(connection, operator_selection, start_time, end_time)
    } else {
      // Mode 1: Search for operators (return selection list)
      console.log("Function 8: Searching for operators with query:", search_query)
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
  console.log("searchOperators called with query:", searchQuery)
  
  const searchSql = `
    SELECT DISTINCT
        a.operator,
        a.operator_iata_code,
        a.operator_icao_code,
        COUNT(*) as aircraft_count,
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
        a.operator_iata_code = $1
        OR a.operator_icao_code = $1
        OR UPPER(a.operator) LIKE UPPER($1)
      )
    GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code
    ORDER BY aircraft_count DESC
    LIMIT 15;
  `
  
  console.log("Executing search SQL with query:", searchQuery)
  console.log("SQL:", searchSql)
  
  const result = await connection.queryObject(searchSql, [searchQuery])
  
  console.log("Search SQL result:", result.rows.length, "rows found")
  
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
            WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
              OR UPPER(a.aircraft_details) LIKE '%-F%'
              OR UPPER(a.aircraft_details) LIKE '%CARGO%'
              OR UPPER(a.aircraft_details) LIKE '%BCF%'
              OR UPPER(a.aircraft_details) LIKE '%SF%'
            THEN 'Freighter'
            ELSE 'Passenger'
        END as aircraft_category
    FROM aircraft a
    WHERE a.operator = $1
      AND a.operator IS NOT NULL
    ORDER BY a.aircraft_details, a.registration;
  `

  // Route Analysis Query
  const routeSql = `
    SELECT 
        m.destination_code,
        COUNT(*) as total_flights,
        array_agg(DISTINCT a.type ORDER BY a.type) as aircraft_types_used,
        ROUND(COUNT(*) / 12.0, 1) as avg_flights_per_month
    FROM movements m
    JOIN aircraft a ON m.registration = a.registration
    WHERE a.operator = $1
      AND m.scheduled_departure >= $2
      AND m.scheduled_departure <= $3
    GROUP BY m.destination_code
    ORDER BY total_flights DESC
    LIMIT 20;
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
*/
