import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { Pool } from "https://deno.land/x/postgres@v0.17.0/mod.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

const DATABASE_POOL_SIZE = 3
console.log(`Function "aircraft-to-destination-search" up and running!`)

/**
 * Function 12: Aircraft-to-Destination Operator Search
 * Allows users to find operators that can fly specific aircraft types to specific destinations
 * 
 * Modes:
 * 1. Get available aircraft types from database
 * 2. Search operators by aircraft types + destinations
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
    
    const requestBody = await req.json()
    console.log("Function 12 received request body:", JSON.stringify(requestBody))
    
    const { 
      mode = "search", // "get_aircraft_types" or "search"
      aircraft_types = [], 
      destinations = [],
      start_time = "2024-04-01", 
      end_time = "2025-05-31" 
    } = requestBody

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

    // 6. Handle different modes
    console.log("Function 12 mode:", mode)
    
    if (mode === "get_aircraft_types") {
      return await getAvailableAircraftTypes(connection)
    } else if (mode === "search") {
      if (!aircraft_types.length || !destinations.length) {
        throw new Error("Missing required parameters: aircraft_types and destinations")
      }
      return await searchOperatorsByAircraftAndDestinations(connection, aircraft_types, destinations, start_time, end_time)
    } else {
      throw new Error(`Invalid mode: ${mode}`)
    }

  } catch (error) {
    console.error("Function 12 error:", error)
    return new Response(
      JSON.stringify({ 
        error: error.message || "An unexpected error occurred.",
        function_name: "aircraft_to_destination_search"
      }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  } finally {
    // 7. Always close database connection
    if (connection) {
      try {
        connection.release()
      } catch (releaseError) {
        console.error("Error releasing database connection:", releaseError)
      }
    }
  }
})

/**
 * Get all available aircraft types from the database with statistics
 */
async function getAvailableAircraftTypes(connection: any) {
  console.log("Getting aircraft types - using exact same pattern as working Function 8")
  
  try {
    // Use the EXACT same query pattern as Function 8 (which works perfectly)
    const aircraftTypesSql = `
      SELECT 
          a.type as aircraft_type,
          COUNT(*) as aircraft_count,
          COUNT(DISTINCT a.operator) as operator_count
      FROM aircraft a
      WHERE a.operator IS NOT NULL
      GROUP BY a.type
      ORDER BY aircraft_count DESC;
    `
    
    console.log("Executing aircraft types query...")
    const result = await connection.queryObject(aircraftTypesSql)
    console.log(`Query returned ${result.rows.length} rows`)
    
    if (result.rows.length > 0) {
      console.log("First 5 aircraft types:", result.rows.slice(0, 5))
    }
    
    const aircraftTypes = result.rows.map(row => ({
      aircraft_type: row.aircraft_type,
      aircraft_count: Number(row.aircraft_count),
      operator_count: Number(row.operator_count)
    }))
    
    console.log(`Successfully processed ${aircraftTypes.length} aircraft types`)
    
    return new Response(
      JSON.stringify({
        aircraft_types: aircraftTypes,
        total_types: aircraftTypes.length,
        function_name: "aircraft_to_destination_search"
      }),
      { 
        status: 200, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
    
  } catch (error) {
    console.error("Error in getAvailableAircraftTypes:", error)
    return new Response(
      JSON.stringify({
        error: `Failed to get aircraft types: ${error.message}`,
        aircraft_types: [],
        total_types: 0,
        function_name: "aircraft_to_destination_search"
      }),
      { 
        status: 200, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
}

/**
 * Search operators by aircraft types and destinations
 */
async function searchOperatorsByAircraftAndDestinations(
  connection: any, 
  aircraftTypes: string[], 
  destinations: string[],
  startTime: string, 
  endTime: string
) {
  console.log(`Searching operators with aircraft types: ${aircraftTypes.join(', ')} to destinations: ${destinations.join(', ')}`)
  
  // Parse destinations into different categories
  const { airportCodes, countryPatterns, continentCodes } = parseDestinations(destinations)
  
  console.log("Parsed destinations:", { airportCodes, countryPatterns, continentCodes })
  
  const searchSql = `
    SELECT 
        a.operator,
        a.operator_iata_code,
        a.operator_icao_code,
        array_agg(DISTINCT a.type ORDER BY a.type) as available_aircraft_types,
        COUNT(DISTINCT a.registration) as total_fleet_size,
        COUNT(DISTINCT CASE WHEN a.type = ANY($1) THEN a.registration END) as matching_fleet_size,
        COUNT(DISTINCT m.destination_code) as destination_count,
        COUNT(*) as total_flights,
        array_agg(DISTINCT m.destination_code ORDER BY m.destination_code) as served_destinations,
        ROUND(COUNT(*) / 12.0, 1) as avg_monthly_flights,
        -- Get sample routes for top destinations
        array_agg(DISTINCT 
          CASE WHEN m.destination_code IN (
            SELECT sub_m.destination_code 
            FROM movements sub_m 
            JOIN aircraft sub_a ON sub_m.registration = sub_a.registration 
            WHERE sub_a.operator = a.operator 
            GROUP BY sub_m.destination_code 
            ORDER BY COUNT(*) DESC 
            LIMIT 3
          ) 
          THEN m.destination_code || ' (' || a.type || ')'
          END
        ) FILTER (WHERE m.destination_code IS NOT NULL) as top_routes_with_aircraft
    FROM aircraft a
    JOIN movements m ON a.registration = m.registration
    LEFT JOIN airports_geography ag ON m.destination_code = ag.iata_code
    WHERE a.type = ANY($1)  -- Aircraft types filter
      AND (
        ($2::text[] IS NULL OR array_length($2::text[], 1) IS NULL OR m.destination_code = ANY($2))  -- Airport codes
        OR ($3::text[] IS NULL OR array_length($3::text[], 1) IS NULL OR ag.country_name ILIKE ANY($3))  -- Country patterns
        OR ($4::text[] IS NULL OR array_length($4::text[], 1) IS NULL OR ag.continent = ANY($4))  -- Continent codes
      )
      AND m.scheduled_departure >= $5::date
      AND m.scheduled_departure <= $6::date
    GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code
    HAVING COUNT(DISTINCT CASE WHEN a.type = ANY($1) THEN a.registration END) > 0  -- Must have matching aircraft
    ORDER BY total_flights DESC;  -- NO LIMIT - show ALL results
  `
  
  console.log("Executing search with parameters:", {
    aircraftTypes,
    airportCodes: airportCodes.length > 0 ? airportCodes : null,
    countryPatterns: countryPatterns.length > 0 ? countryPatterns : null,
    continentCodes: continentCodes.length > 0 ? continentCodes : null,
    startTime,
    endTime
  })

  const searchResult = await connection.queryObject(searchSql, [
    aircraftTypes,  // $1
    airportCodes.length > 0 ? airportCodes : null,  // $2  
    countryPatterns.length > 0 ? countryPatterns : null,  // $3
    continentCodes.length > 0 ? continentCodes : null,  // $4
    startTime,  // $5
    endTime     // $6
  ])
  
  console.log(`Search query returned ${searchResult.rows.length} operators`)
  
  if (searchResult.rows.length === 0) {
    console.log("No operators found for search criteria")
    return new Response(
      JSON.stringify({
        search_summary: {
          aircraft_types: aircraftTypes,
          destinations: destinations,
          total_operators: 0,
          total_flights: 0,
          total_destinations: 0,
          period_start: startTime,
          period_end: endTime
        },
        operators: [],
        message: `❌ No operators found with aircraft types [${aircraftTypes.join(', ')}] serving destinations [${destinations.join(', ')}].\n\nTry different aircraft types or destinations.`,
        function_name: "aircraft_to_destination_search"
      }),
      { 
        status: 200, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
  
  // Process results
  const operators = searchResult.rows.map(row => ({
    operator: row.operator,
    operator_iata_code: row.operator_iata_code,
    operator_icao_code: row.operator_icao_code,
    available_aircraft_types: row.available_aircraft_types || [],
    total_fleet_size: Number(row.total_fleet_size),
    matching_fleet_size: Number(row.matching_fleet_size),
    destination_count: Number(row.destination_count),
    total_flights: Number(row.total_flights),
    served_destinations: row.served_destinations || [],
    avg_monthly_flights: Number(row.avg_monthly_flights),
    top_routes_with_aircraft: (row.top_routes_with_aircraft || []).filter(route => route != null)
  }))
  
  // Calculate summary statistics
  const totalOperators = operators.length
  const totalFlights = operators.reduce((sum, op) => sum + op.total_flights, 0)
  const totalDestinations = new Set(operators.flatMap(op => op.served_destinations)).size
  
  console.log(`Found ${totalOperators} operators matching search criteria`)
  
  return new Response(
    JSON.stringify({
      search_summary: {
        aircraft_types: aircraftTypes,
        destinations: destinations,
        total_operators: totalOperators,
        total_flights: totalFlights,
        total_destinations: totalDestinations,
        period_start: startTime,
        period_end: endTime
      },
      operators: operators,
      function_name: "aircraft_to_destination_search"
    }),
    { 
      status: 200, 
      headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
    }
  )
}

/**
 * Parse destinations into airport codes, country patterns, and continent codes
 */
function parseDestinations(destinations: string[]): {
  airportCodes: string[],
  countryPatterns: string[],
  continentCodes: string[]
} {
  const airportCodes: string[] = []
  const countryPatterns: string[] = []
  const continentCodes: string[] = []
  
  // Continent mapping
  const continentMap: { [key: string]: string } = {
    'asia': 'AS',
    'europe': 'EU', 
    'north america': 'NA',
    'south america': 'SA',
    'africa': 'AF',
    'oceania': 'OC',
    'antarctica': 'AN',
    'as': 'AS',
    'eu': 'EU',
    'na': 'NA', 
    'sa': 'SA',
    'af': 'AF',
    'oc': 'OC',
    'an': 'AN'
  }
  
  for (const dest of destinations) {
    const destLower = dest.toLowerCase().trim()
    
    // Check if it's a 3-letter airport code
    if (/^[a-z]{3}$/i.test(dest.trim())) {
      airportCodes.push(dest.trim().toUpperCase())
    }
    // Check if it's a continent
    else if (continentMap[destLower]) {
      continentCodes.push(continentMap[destLower])
    }
    // Otherwise treat as country name (with ILIKE pattern)
    else {
      // Capitalize first letter for better matching
      const destName = dest.trim()
      const capitalizedDest = destName.charAt(0).toUpperCase() + destName.slice(1).toLowerCase()
      countryPatterns.push(`%${capitalizedDest}%`)
    }
  }
  
  return { airportCodes, countryPatterns, continentCodes }
}
