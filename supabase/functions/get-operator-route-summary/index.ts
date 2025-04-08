// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts' // Use shared CORS

const DATABASE_POOL_SIZE = 3

console.log(`Function "get-operator-route-summary" up and running!`)

/**
 * This function finds all direct routes flown by a specific operator
 * within a given time frame and returns the frequency for each route.
 * It filters by scheduled departure times.
 * The operator can be identified by name, IATA code, or ICAO code.
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
    const { operator_identifier, start_time, end_time } = await req.json()

    // Basic validation
    if (!operator_identifier || !start_time || !end_time) {
      throw new Error("Missing required parameters: operator_identifier, start_time, end_time")
    }
    // TODO: Add date validation

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL') // Use DATABASE_URL from .env.local
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    const connection = await pool.connect()

    try {
      // 6. Define the SQL query
      // Joins movements with aircraft.
      // Filters by operator name OR IATA code OR ICAO code.
      // Filters by scheduled departure time window.
      // Groups by origin/destination codes to count frequency per route.
      const sql = `
        SELECT
            m.origin_code,
            m.destination_code,
            COUNT(m.id) as frequency
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE (
            a.operator ILIKE $1 OR      -- Case-insensitive match for name
            a.operator_iata_code = $1 OR -- Exact match for IATA (usually uppercase)
            a.operator_icao_code = $1    -- Exact match for ICAO (usually uppercase)
          )
            AND m.scheduled_departure >= $2 -- Filter by scheduled time
            AND m.scheduled_departure <= $3
          GROUP BY m.origin_code, m.destination_code
          ORDER BY frequency DESC, m.origin_code ASC, m.destination_code ASC;
      `
      // 7. Execute the query
      // Note: We pass the identifier 3 times for the 3 possible matches in the WHERE clause
      const result = await connection.queryObject(sql, [
        operator_identifier, // $1 (used for operator, iata, icao checks)
        start_time,          // $2
        end_time,            // $3
      ])

      // 8. Format results (Convert BigInt frequency to Number)
      const rawRouteData = result.rows
      const routeData = rawRouteData.map(row => ({
        ...row,
        frequency: Number(row.frequency),
      }));

      console.log(`Found ${routeData.length} routes for operator "${operator_identifier}" within the period.`);

      // Return the results
      return new Response(
        JSON.stringify({ results: routeData }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )

    } finally {
      // 9. Release connection
      connection.release()
    }
  } catch (error) {
    // Handle errors
    console.error("Error in get-operator-route-summary:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
    const isInputError = error instanceof Error && error.message.startsWith("Missing required parameters");
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500;

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

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/get-operator-route-summary' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
