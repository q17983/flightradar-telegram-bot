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

      // 6. Enhanced SQL query to find operators serving multiple destinations
      const placeholders = destination_codes.map((_, index) => `$${index + 3}`).join(', ')
      
      const enhancedSql = `
        WITH operator_destinations AS (
          SELECT 
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            m.destination_code,
            a.type,
            a.aircraft_details,
            CASE 
              WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
                OR UPPER(a.aircraft_details) LIKE '%-F%'
                OR UPPER(a.aircraft_details) LIKE '%CARGO%'
                OR UPPER(a.aircraft_details) LIKE '%BCF%'
                OR UPPER(a.aircraft_details) LIKE '%SF%'
              THEN 'Freighter'
              ELSE 'Passenger'
            END as aircraft_category,
            COUNT(*) as flights_count
          FROM movements m
          JOIN aircraft a ON m.registration = a.registration
          WHERE m.destination_code IN (${placeholders})
            AND m.scheduled_departure >= $1
            AND m.scheduled_departure <= $2
            AND a.operator IS NOT NULL
          GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, 
                   m.destination_code, a.type, a.aircraft_details, aircraft_category
        ),
        operator_destination_counts AS (
          SELECT 
            operator,
            operator_iata_code,
            operator_icao_code,
            COUNT(DISTINCT destination_code) as destinations_served,
            ARRAY_AGG(DISTINCT destination_code ORDER BY destination_code) as destinations_list
          FROM operator_destinations
          GROUP BY operator, operator_iata_code, operator_icao_code
          HAVING COUNT(DISTINCT destination_code) >= $${destination_codes.length + 3}
        ),
        enhanced_results AS (
          SELECT 
            odc.operator,
            odc.operator_iata_code,
            odc.operator_icao_code,
            odc.destinations_served,
            odc.destinations_list,
            od.destination_code,
            od.aircraft_category,
            od.type,
            od.aircraft_details,
            SUM(od.flights_count) as total_flights,
            COUNT(DISTINCT od.type) as aircraft_types_count
          FROM operator_destination_counts odc
          JOIN operator_destinations od ON odc.operator = od.operator 
            AND odc.operator_iata_code = od.operator_iata_code 
            AND odc.operator_icao_code = od.operator_icao_code
          GROUP BY odc.operator, odc.operator_iata_code, odc.operator_icao_code,
                   odc.destinations_served, odc.destinations_list,
                   od.destination_code, od.aircraft_category, od.type, od.aircraft_details
        )
        SELECT 
          operator,
          operator_iata_code,
          operator_icao_code,
          destinations_served,
          destinations_list,
          destination_code,
          aircraft_category,
          type,
          aircraft_details,
          total_flights,
          aircraft_types_count,
          -- Summary calculations
          SUM(total_flights) OVER (PARTITION BY operator, operator_iata_code, operator_icao_code) as operator_total_flights,
          SUM(CASE WHEN aircraft_category = 'Freighter' THEN total_flights ELSE 0 END) 
            OVER (PARTITION BY operator, operator_iata_code, operator_icao_code) as operator_freighter_flights,
          SUM(CASE WHEN aircraft_category = 'Passenger' THEN total_flights ELSE 0 END) 
            OVER (PARTITION BY operator, operator_iata_code, operator_icao_code) as operator_passenger_flights
        FROM enhanced_results
        ORDER BY operator_total_flights DESC, operator, destination_code, aircraft_category DESC, total_flights DESC
      `

      console.log("Function 9: Executing enhanced SQL query")
      console.log("SQL parameters:", [start_time, end_time, ...destination_codes, min_dest])

      const result = await connection.queryObject(enhancedSql, [start_time, end_time, ...destination_codes, min_dest])
      
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

      // 7. Process and structure the results
      const operatorMap = new Map()

      for (const row of result.rows) {
        const operatorKey = `${row.operator}|${row.operator_iata_code}|${row.operator_icao_code}`
        
        if (!operatorMap.has(operatorKey)) {
          operatorMap.set(operatorKey, {
            operator: row.operator,
            operator_iata_code: row.operator_iata_code,
            operator_icao_code: row.operator_icao_code,
            destinations_served: row.destinations_served,
            destinations_list: row.destinations_list,
            total_flights: row.operator_total_flights,
            freighter_flights: row.operator_freighter_flights,
            passenger_flights: row.operator_passenger_flights,
            freighter_percentage: Math.round((row.operator_freighter_flights / row.operator_total_flights) * 100),
            destinations: new Map()
          })
        }

        const operator = operatorMap.get(operatorKey)
        const dest = row.destination_code

        if (!operator.destinations.has(dest)) {
          operator.destinations.set(dest, {
            destination_code: dest,
            total_flights: 0,
            freighter_flights: 0,
            passenger_flights: 0,
            aircraft_details: []
          })
        }

        const destData = operator.destinations.get(dest)
        destData.total_flights += row.total_flights
        
        if (row.aircraft_category === 'Freighter') {
          destData.freighter_flights += row.total_flights
        } else {
          destData.passenger_flights += row.total_flights
        }

        destData.aircraft_details.push({
          type: row.type,
          aircraft_details: row.aircraft_details,
          category: row.aircraft_category,
          flights: row.total_flights
        })
      }

      // 8. Convert to final response format
      const operators = Array.from(operatorMap.values()).map(op => ({
        ...op,
        destinations: Array.from(op.destinations.values()).map(dest => ({
          ...dest,
          freighter_percentage: dest.total_flights > 0 ? Math.round((dest.freighter_flights / dest.total_flights) * 100) : 0
        }))
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
