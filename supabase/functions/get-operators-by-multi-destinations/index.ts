// Follow this setup for each endpoint.
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'

const DATABASE_POOL_SIZE = 3
console.log(`Function "get-operators-by-multi-destinations" up and running!`)

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    console.log("Function 9 received request body:", await req.clone().text())

    // 1. Parse request body
    if (!req.body) {
      throw new Error("Request body is missing.")
    }
    
    const { 
      destination_codes, 
      minimum_destinations = null,
      start_time = "2024-01-01", 
      end_time = "2024-12-31" 
    } = await req.json()

    console.log("Function 9: Parsed parameters:", { destination_codes, minimum_destinations, start_time, end_time })

    // 2. Validate inputs
    if (!destination_codes || !Array.isArray(destination_codes) || destination_codes.length === 0) {
      throw new Error("Missing or invalid parameter: destination_codes must be a non-empty array")
    }

    // Validate each destination code
    for (const code of destination_codes) {
      if (!code || typeof code !== 'string' || code.length !== 3) {
        throw new Error(`Invalid destination code: ${code}. Must be 3-letter airport codes.`)
      }
    }

    const min_dest = minimum_destinations || destination_codes.length
    if (min_dest > destination_codes.length) {
      throw new Error("minimum_destinations cannot be greater than the number of destination_codes provided")
    }

    console.log("Function 9: Validation passed, proceeding with query")

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    let connection

    try {
      // 5. Connect to the database
      connection = await pool.connect()
      console.log("Function 9: Database connection established")

      // 6. Much simpler SQL query - no subqueries or complex logic
      const simplifiedSql = `
        SELECT DISTINCT
          a.operator,
          a.operator_iata_code,
          a.operator_icao_code,
          m.destination_code,
          COUNT(*) as flights_to_destination,
          COUNT(CASE WHEN 
            UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
            OR UPPER(a.aircraft_details) LIKE '%-F%'
            OR UPPER(a.aircraft_details) LIKE '%CARGO%'
            OR UPPER(a.aircraft_details) LIKE '%BCF%'
            OR UPPER(a.aircraft_details) LIKE '%SF%'
          THEN 1 END) as freighter_flights,
          COUNT(CASE WHEN NOT (
            UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
            OR UPPER(a.aircraft_details) LIKE '%-F%'
            OR UPPER(a.aircraft_details) LIKE '%CARGO%'
            OR UPPER(a.aircraft_details) LIKE '%BCF%'
            OR UPPER(a.aircraft_details) LIKE '%SF%'
          ) THEN 1 END) as passenger_flights
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code = ANY($3)
          AND m.scheduled_departure >= $1
          AND m.scheduled_departure <= $2
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, m.destination_code
        ORDER BY a.operator, m.destination_code
        LIMIT 200
      `

      console.log("Function 9: Executing simplified SQL query")
      console.log("SQL parameters:", [start_time, end_time, destination_codes])

      const result = await connection.queryObject(simplifiedSql, [start_time, end_time, destination_codes])
      
      console.log("Function 9: Query executed successfully, rows returned:", result.rows.length)

      if (result.rows.length === 0) {
        return new Response(
          JSON.stringify({
            message: `No operators found serving ${min_dest >= destination_codes.length ? 'all' : 'at least ' + min_dest} of the specified destinations: ${destination_codes.join(', ')}`,
            destinations_requested: destination_codes,
            minimum_destinations_required: min_dest,
            period: { start_time, end_time },
            total_operators: 0
          }),
          { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        )
      }

      // 7. Process and filter results for multi-destination operators
      const operatorMap = new Map()

      for (const row of result.rows) {
        const operatorKey = `${row.operator}|${row.operator_iata_code}|${row.operator_icao_code}`
        
        if (!operatorMap.has(operatorKey)) {
          operatorMap.set(operatorKey, {
            operator: row.operator,
            operator_iata_code: row.operator_iata_code,
            operator_icao_code: row.operator_icao_code,
            destinations: new Map(),
            total_flights: 0,
            total_freighter_flights: 0,
            total_passenger_flights: 0
          })
        }

        const operator = operatorMap.get(operatorKey)
        
        operator.destinations.set(row.destination_code, {
          destination_code: row.destination_code,
          total_flights: row.flights_to_destination,
          freighter_flights: row.freighter_flights,
          passenger_flights: row.passenger_flights,
          freighter_percentage: row.flights_to_destination > 0 ? 
            Math.round((row.freighter_flights / row.flights_to_destination) * 100) : 0
        })
        
        operator.total_flights += row.flights_to_destination
        operator.total_freighter_flights += row.freighter_flights
        operator.total_passenger_flights += row.passenger_flights
      }

      // Filter to only operators serving the minimum required destinations
      const filteredOperators = Array.from(operatorMap.values()).filter(op => 
        op.destinations.size >= min_dest
      )

      // 8. Convert filtered operators to final response format
      const operators = filteredOperators.map(op => ({
        operator: op.operator,
        operator_iata_code: op.operator_iata_code,
        operator_icao_code: op.operator_icao_code,
        destinations_served: op.destinations.size,
        destinations_list: Array.from(op.destinations.keys()).sort(),
        total_flights: op.total_flights,
        freighter_flights: op.total_freighter_flights,
        passenger_flights: op.total_passenger_flights,
        freighter_percentage: op.total_flights > 0 ? 
          Math.round((op.total_freighter_flights / op.total_flights) * 100) : 0,
        destinations: Array.from(op.destinations.values())
      }))

      // 9. Calculate summary statistics
      const summary = {
        total_operators: operators.length,
        destinations_requested: destination_codes,
        minimum_destinations_required: min_dest,
        period: { start_time, end_time },
        total_flights_all_operators: operators.reduce((sum, op) => sum + op.total_flights, 0),
        avg_destinations_per_operator: operators.length > 0 ? 
          Math.round((operators.reduce((sum, op) => sum + op.destinations_served, 0) / operators.length) * 10) / 10 : 0
      }

      console.log("Function 9: Response prepared successfully")

      return new Response(
        JSON.stringify({
          summary,
          operators: operators.slice(0, 50) // Limit to top 50 operators
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )

    } finally {
      if (connection) {
        connection.release()
      }
      await pool.end()
    }

  } catch (error) {
    console.error("Error in get-operators-by-multi-destinations:", error.message)
    const isInputError = error instanceof Error && (
      error.message.startsWith("Missing") ||
      error.message.startsWith("Invalid") ||
      error.message.includes("must be")
    )
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred."
    const statusCode = isInputError ? 400 : 500

    return new Response(
      JSON.stringify({ error: clientErrorMessage }),
      { 
        status: statusCode,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
})
