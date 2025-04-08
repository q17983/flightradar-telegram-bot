// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts' // Use shared CORS

const DATABASE_POOL_SIZE = 3

console.log(`Function "get-operators-by-destination" up and running!`)

/**
 * This function finds all operators flying TO a specific destination airport
 * within a given time frame and returns the frequency for each operator.
 * It filters by scheduled departure times.
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
    // Expect destination_code, start_time, end_time
    const { destination_code, start_time, end_time } = await req.json()

    // Basic validation
    if (!destination_code || !start_time || !end_time) {
      throw new Error("Missing required parameters: destination_code, start_time, end_time")
    }
    // TODO: Add more robust validation

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL') // Use DATABASE_URL from .env.local
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    connection = await pool.connect()

    try {
      // 6. Define the SQL query
      // Joins movements with aircraft.
      // Filters ONLY by destination_code.
      // Filters by scheduled departure time window.
      // Excludes entries where the operator name is missing.
      // Groups by operator details to count frequency per operator.
      const sql = `
        SELECT
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            COUNT(m.id) as frequency
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code = $1 -- Filter ONLY by destination
          AND m.scheduled_departure >= $2 -- Filter by scheduled time
          AND m.scheduled_departure <= $3
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code
        ORDER BY frequency DESC, a.operator ASC;
      `
      // 7. Execute the query
      const result = await connection.queryObject(sql, [
        destination_code, // $1
        start_time,       // $2
        end_time,         // $3
      ])

      // 8. Format results (Convert BigInt frequency to Number)
      const rawOperatorData = result.rows
      const operatorData = rawOperatorData.map(row => ({
        ...row,
        frequency: Number(row.frequency),
      }));

      console.log(`Found ${operatorData.length} operators flying to "${destination_code}" within the period.`);

      // Return the results
      return new Response(
        JSON.stringify({ results: operatorData }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )

    } finally {
      // 9. Release connection
      if (connection) await connection.release(); // Ensure release if connection was made
    }
  } catch (error) {
    // Handle errors
    console.error("Error in get-operators-by-destination:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
    const isInputError = error instanceof Error && error.message.startsWith("Missing required parameters");
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
  }
})

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/get-operators-by-destination' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
