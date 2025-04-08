// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3

console.log(`Function "get-operator-frequency" up and running!`)

/**
 * This function calculates the frequency of operators flying DIRECTLY
 * between a specified origin and destination airport within a given time frame.
 *
 * It relies on filtering by scheduled departure times, as actual times
 * might be null in the data.
 *
 * IMPORTANT: This function does NOT analyze multi-leg journeys, positioning flights,
 * technical stops, or total flight time across complex routes (like TAS-HKG-TAS-TLV-TAS).
 * Calculating operational costs or efficiency for such routes would require a
 * different, more complex analysis function.
 */
serve(async (req: Request) => {
  // 1. Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // 2. Parse incoming request body
    if (!req.body) {
       throw new Error("Request body is missing.")
    }
    const { origin_code, destination_code, start_time, end_time } = await req.json()

    // Basic validation
    // TODO: Add more robust validation (e.g., check if codes are valid IATA/ICAO format, check date string validity)
    if (!origin_code || !destination_code || !start_time || !end_time) {
      throw new Error("Missing required parameters: origin_code, destination_code, start_time, end_time")
    }

    // 3. Retrieve Database connection string from environment variables
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not set as a Supabase secret.")
      throw new Error("Internal server configuration error.") // Don't expose missing env var to client
    }

    // 4. Create PostgreSQL connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    const connection = await pool.connect()

    try {
      // 6. Define the SQL query
      // Filters by origin/destination codes (as requested for common language).
      // Filters by SCHEDULED departure time window (more reliable than actual which can be null).
      // Joins with aircraft table to get operator details.
      // Excludes entries where the operator name is missing.
      // TODO: Consider adding an optional 'aircraft_role' parameter (e.g., 'freighter', 'passenger')
      //       to filter based on aircraft_details (e.g., containing 'F'), likely requiring modification here
      //       or a separate dedicated function.
      const sql = `
        SELECT
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            COUNT(m.id) as frequency
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.origin_code = $1      -- Use origin_code as primary filter
          AND m.destination_code = $2 -- Use destination_code as primary filter
          AND m.scheduled_departure >= $3 -- Filter by scheduled time for reliability
          AND m.scheduled_departure <= $4
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code
        ORDER BY frequency DESC, a.operator ASC; -- Order by frequency, then alphabetically
      `
      // 7. Execute the query safely with parameters
      const result = await connection.queryObject(sql, [
        origin_code,
        destination_code,
        start_time, // Ensure frontend sends valid ISO 8601 timestamp strings (e.g., 'YYYY-MM-DDTHH:MM:SSZ')
        end_time,
      ])

  // 8. Format results
          // 8. Format results
          const rawFrequencyData = result.rows // rows contains objects like { ..., frequency: 123n } (n denotes BigInt)

          // ---> ADD THIS STEP TO CONVERT BigInt TO Number <---
          const frequencyData = rawFrequencyData.map(row => ({
            ...row, // Copy other properties (operator, iata, icao)
            frequency: Number(row.frequency), // Convert BigInt frequency to Number
          }));
          // ---> END OF ADDED STEP <---

          console.log(`Found ${frequencyData.length} operators for route ${origin_code}->${destination_code} within the specified period.`);

          // Return the MODIFIED results as JSON (around line 87)
          return new Response(
            JSON.stringify({ results: frequencyData }), // Use the converted data
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
          )

        } finally {
          // 9. Release the connection back to the pool
          connection.release()
        }
      } catch (error) {
    // Log the detailed error on the server
    console.error("Error in get-operator-frequency:", error.message, error.stack ? `\nStack: ${error.stack}` : '')

    // Return a generic or specific error message to the client
    const isInputError = error instanceof Error && error.message.startsWith("Missing required parameters");
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500; // 400 Bad Request for missing params, 500 otherwise

    return new Response(
      JSON.stringify({ error: clientErrorMessage }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: statusCode,
      }
    )
  }
})

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/get-operator-frequency' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
