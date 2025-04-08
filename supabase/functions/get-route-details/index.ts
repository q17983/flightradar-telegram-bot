// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool, QueryObjectResult } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3

console.log(`Function "get-route-details" up and running!`)

// Helper function to safely convert query result to number or return null
function safeToNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const num = Number(value);
  return isNaN(num) ? null : num;
}

/**
 * This function provides details about a specific direct route, including
 * total movements, flight time statistics (in seconds), and aircraft types used.
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
    const { origin_code, destination_code, start_time, end_time } = await req.json()

    // Basic validation
    if (!origin_code || !destination_code || !start_time || !end_time) {
      throw new Error("Missing required parameters: origin_code, destination_code, start_time, end_time")
    }
    // TODO: Add more robust validation

    // 3. Retrieve Database connection string
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    // 4. Create connection pool
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)

    // 5. Connect to the database
    connection = await pool.connect() // Assign to outer scope variable

    // --- Query 1: Aggregate Flight Stats & Total Movements ---
    const aggSql = `
      SELECT
          COUNT(m.id) as total_movements,
          -- Extract epoch for calculation, handle NULLs with AVG/MIN/MAX
          AVG(EXTRACT(EPOCH FROM m.flight_time)) as avg_flight_time_epoch,
          MIN(EXTRACT(EPOCH FROM m.flight_time)) as min_flight_time_epoch,
          MAX(EXTRACT(EPOCH FROM m.flight_time)) as max_flight_time_epoch
      FROM movements m
      WHERE m.origin_code = $1
        AND m.destination_code = $2
        AND m.scheduled_departure >= $3
        AND m.scheduled_departure <= $4
        AND m.flight_time IS NOT NULL; -- Only include movements with flight_time for stats
    `
    const aggResult = await connection.queryObject<{
       total_movements: bigint; // COUNT returns bigint
       avg_flight_time_epoch: number | null; // Aggregates might return number or null
       min_flight_time_epoch: number | null;
       max_flight_time_epoch: number | null;
    }>(aggSql, [
      origin_code,
      destination_code,
      start_time,
      end_time,
    ])

    const aggData = aggResult.rows[0] // Aggregation returns one row
    const totalMovements = aggData ? Number(aggData.total_movements) : 0; // Convert bigint count

    // --- Query 2: Aircraft Type Frequency ---
    const typeSql = `
      SELECT
          a.type,
          COUNT(m.id) as frequency
      FROM movements m
      JOIN aircraft a ON m.registration = a.registration
      WHERE m.origin_code = $1
        AND m.destination_code = $2
        AND m.scheduled_departure >= $3
        AND m.scheduled_departure <= $4
      GROUP BY a.type
      ORDER BY frequency DESC, a.type ASC;
    `
    const typeResult = await connection.queryObject<{ type: string; frequency: bigint }>(typeSql, [
      origin_code,
      destination_code,
      start_time,
      end_time,
    ])

    // Format type results (convert BigInt frequency)
    const aircraftTypes = typeResult.rows.map(row => ({
       type: row.type,
       frequency: Number(row.frequency),
    }));

    console.log(`Route details query for ${origin_code}->${destination_code}: Found ${totalMovements} total movements and ${aircraftTypes.length} aircraft types.`);

    // --- Combine results ---
    const responsePayload = {
      origin_code: origin_code,
      destination_code: destination_code,
      period_start: start_time,
      period_end: end_time,
      total_movements: totalMovements,
      // Use helper function for safe conversion
      average_flight_time_seconds: safeToNumber(aggData?.avg_flight_time_epoch),
      min_flight_time_seconds: safeToNumber(aggData?.min_flight_time_epoch),
      max_flight_time_seconds: safeToNumber(aggData?.max_flight_time_epoch),
      aircraft_types: aircraftTypes,
    }

    // Return the combined results
    return new Response(
      JSON.stringify(responsePayload),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
    )

  } catch (error) {
    // Handle errors
    console.error("Error in get-route-details:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
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
  } finally {
      // Release connection if it was established
      if (connection) {
         try {
           await connection.release();
           console.log("Database connection released.");
         } catch (releaseError) {
           console.error("Error releasing database connection:", releaseError);
         }
      }
  }
})

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/get-route-details' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
