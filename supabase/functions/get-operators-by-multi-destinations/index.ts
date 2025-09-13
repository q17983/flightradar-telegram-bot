// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3
console.log(`Function "get-operators-by-multi-destinations" up and running!`)

/**
 * Function 9: Find operators serving multiple destinations
 * Based on the insight that origin/destination data is symmetric
 */
serve(async (req: Request) => {
  // 1. Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection; // Define connection outside try block to access in finally

  try {
    console.log("=== Function 9: get-operators-by-multi-destinations ===")
    console.log("Request method:", req.method)
    
    // Parse request body
    const requestData = await req.json()
    console.log("Request body:", requestData)
    
    const { destination_codes, start_time, end_time } = requestData

    // Validate required parameters
    if (!destination_codes || !Array.isArray(destination_codes) || destination_codes.length < 2) {
      console.log("❌ Invalid destination_codes:", destination_codes)
      return new Response(
        JSON.stringify({ 
          error: 'destination_codes must be an array with at least 2 destination codes' 
        }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      )
    }

    if (!start_time || !end_time) {
      console.log("❌ Missing time parameters:", { start_time, end_time })
      return new Response(
        JSON.stringify({ 
          error: 'start_time and end_time are required' 
        }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      )
    }

    console.log("✅ Valid parameters received:", { destination_codes, start_time, end_time })

    // 4. Connect to the database
    const databaseUrl = Deno.env.get('DATABASE_URL')!
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    
    // 5. Connect to the database
    connection = await pool.connect()

    try {
      // 6. Build SQL query to find operators serving multiple destinations
      const destinationPlaceholders = destination_codes.map((_, i) => `$${i + 2}`).join(',')
      const sql = `
        SELECT
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            a.type as aircraft_type,
            a.aircraft_details,
            m.destination_code,
            m.destination_name,
            COUNT(m.id) as frequency
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code IN (${destinationPlaceholders})
          AND m.scheduled_departure >= $1
          AND m.scheduled_departure <= $${destination_codes.length + 2}
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, a.type, a.aircraft_details, m.destination_code, m.destination_name
        ORDER BY a.operator, frequency DESC;
      `
      
      // 7. Execute the query
      const queryResult = await connection.queryObject(sql, [
        start_time,       // $1
        ...destination_codes, // $2, $3, etc.
        end_time          // $last
      ])

      console.log("📊 Raw query results:", queryResult.rows?.length || 0, "records")

      if (!queryResult.rows || queryResult.rows.length === 0) {
        console.log("❌ No data found")
        return new Response(
          JSON.stringify({ 
            message: 'No operators found serving the specified destinations',
            destination_codes,
            time_range: { start_time, end_time }
          }),
          { 
            status: 200, 
            headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
          }
        )
      }

      // 8. Group by operator and count unique destinations served
      const operatorDestinations = new Map()
      
      queryResult.rows.forEach(flight => {
        const key = `${flight.operator_iata_code}|${flight.operator}`
        if (!operatorDestinations.has(key)) {
          operatorDestinations.set(key, {
            operator_iata: flight.operator_iata_code,
            operator_name: flight.operator,
            destinations: new Set(),
            aircraft_types: new Set(),
            total_flights: 0
          })
        }
        
        const operator = operatorDestinations.get(key)
        operator.destinations.add(flight.destination_code)
        operator.aircraft_types.add(flight.aircraft_type)
        operator.total_flights += Number(flight.frequency)
      })

      // 9. Filter operators that serve ALL specified destinations
      const multiDestinationOperators = Array.from(operatorDestinations.values())
        .filter(operator => operator.destinations.size >= destination_codes.length)
        .map(operator => ({
          operator_iata: operator.operator_iata,
          operator_name: operator.operator_name,
          destinations_served: Array.from(operator.destinations),
          aircraft_types: Array.from(operator.aircraft_types),
          total_flights: operator.total_flights
        }))
        .sort((a, b) => b.total_flights - a.total_flights)

      console.log("✅ Found", multiDestinationOperators.length, "operators serving multiple destinations")

      const result = {
        message: `Found ${multiDestinationOperators.length} operators serving multiple destinations`,
        destination_codes,
        time_range: { start_time, end_time },
        operators: multiDestinationOperators,
        summary: {
          total_operators: multiDestinationOperators.length,
          destination_codes_requested: destination_codes.length,
          operators_serving_all: multiDestinationOperators.length
        }
      }

      console.log("🎯 Final result:", result)

      return new Response(
        JSON.stringify(result),
        { 
          status: 200, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      )

    } finally {
      if (connection) {
        connection.release()
      }
      pool.end()
    }

  } catch (error) {
    console.error("❌ Function error:", error)
    return new Response(
      JSON.stringify({ 
        error: 'Internal server error', 
        details: error.message 
      }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
})