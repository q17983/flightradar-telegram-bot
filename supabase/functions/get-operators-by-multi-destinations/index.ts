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
 * Function 9: Get operators flying to multiple destinations
 * Based on Function 1 structure but for multiple destinations
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
    // Expect destination_codes (array), start_time, end_time
    const { destination_codes, start_time, end_time } = await req.json()

    // Basic validation
    if (!destination_codes || !Array.isArray(destination_codes) || destination_codes.length === 0) {
      throw new Error("Missing required parameter: destination_codes must be a non-empty array")
    }
    if (!start_time || !end_time) {
      throw new Error("Missing required parameters: start_time, end_time")
    }

    console.log("Function 9: Processing destinations:", destination_codes)

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

    try {
      // 6. Simple SQL query - just get operators for any of the destinations
      const sql = `
        SELECT DISTINCT
          a.operator,
          a.operator_iata_code,
          a.operator_icao_code,
          m.destination_code,
          COUNT(*) as total_flights
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code = ANY($1)
          AND m.scheduled_departure >= $2
          AND m.scheduled_departure <= $3
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, m.destination_code
        ORDER BY a.operator, m.destination_code
        LIMIT 100
      `

      console.log("Function 9: Executing SQL query")
      const result = await connection.queryObject(sql, [destination_codes, start_time, end_time])
      console.log("Function 9: Query successful, rows:", result.rows.length)

      if (result.rows.length === 0) {
        return new Response(
          JSON.stringify({
            message: `No operators found for destinations: ${destination_codes.join(', ')}`,
            destinations_requested: destination_codes,
            period: { start_time, end_time },
            total_operators: 0
          }),
          { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        )
      }

      // 7. Process results - group by operator and filter for multi-destination
      const operatorMap = new Map()

      for (const row of result.rows) {
        const operatorKey = row.operator
        
        if (!operatorMap.has(operatorKey)) {
          operatorMap.set(operatorKey, {
            operator: row.operator,
            operator_iata_code: row.operator_iata_code,
            operator_icao_code: row.operator_icao_code,
            destinations: [],
            total_flights: 0
          })
        }

        const operator = operatorMap.get(operatorKey)
        operator.destinations.push({
          destination_code: row.destination_code,
          flights: row.total_flights
        })
        operator.total_flights += row.total_flights
      }

      // 8. Filter to operators serving multiple destinations
      const multiDestOperators = Array.from(operatorMap.values()).filter(op => 
        op.destinations.length >= Math.min(2, destination_codes.length)
      )

      // 9. Sort by total flights
      multiDestOperators.sort((a, b) => b.total_flights - a.total_flights)

      console.log("Function 9: Found", multiDestOperators.length, "multi-destination operators")

      return new Response(
        JSON.stringify({
          summary: {
            total_operators: multiDestOperators.length,
            destinations_requested: destination_codes,
            period: { start_time, end_time }
          },
          operators: multiDestOperators.slice(0, 20) // Limit to top 20
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )

    } finally {
      // Always release the connection
      if (connection) {
        connection.release()
      }
      await pool.end()
    }

  } catch (error) {
    // Handle errors
    console.error("Error in get-operators-by-multi-destinations:", error.message)
    const isInputError = error instanceof Error && (
      error.message.startsWith("Missing required parameter") ||
      error.message.startsWith("Invalid") ||
      error.message.includes("must be")
    );
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500;

    // Ensure connection is released even if error happened before finally
    if (connection) {
      try {
        connection.release()
      } catch (releaseError) {
        console.error("Error releasing connection:", releaseError)
      }
    }

    return new Response(
      JSON.stringify({ error: clientErrorMessage }),
      { 
        status: statusCode,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
})