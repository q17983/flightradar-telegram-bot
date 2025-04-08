// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3

// --- Region Definitions (Hardcoded for now) ---
// TODO: Consider moving this mapping to a database table for flexibility
const regionAirportCodes: { [key: string]: string[] } = {
  china: [
    'PVG', 'PEK', 'CAN', 'SZX', 'CTU', 'CKG', 'SHA', 'XIY', 'HGH', 'NKG',
    'WUH', 'CSX', 'KMG', 'XMN', 'TSN', 'DLC', 'CGO', 'SHE', 'HRB', 'TAO' // Add more China codes
  ],
  southeastasia: [
    'SIN', 'KUL', 'BKK', 'DMK', 'CGK', 'SGN', 'HAN', 'MNL', 'CEB', 'RGN',
    'PNH', 'REP', 'VTE', 'LPQ', 'BWN', 'DPS', 'SUB', 'PEN', 'DAD', 'CRK' // Add more SEA codes
  ],
  // Add other regions here if needed, e.g., 'europe', 'northamerica'
};
// --- End Region Definitions ---

console.log(`Function "get-operator-origins-by-region" up and running!`)

/**
 * Finds origin airports within a specified region (China or SouthEastAsia)
 * from which a specific operator departed during a given time frame.
 * Returns the frequency of departures from each origin airport in that region.
 */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection;

  try {
    if (!req.body) throw new Error("Request body is missing.")

    const { operator_identifier, region, start_time, end_time } = await req.json()

    // Basic validation
    if (!operator_identifier || !region || !start_time || !end_time) {
      throw new Error("Missing required parameters: operator_identifier, region, start_time, end_time")
    }

    // --- Get Airport Codes for Region ---
    const regionKey = region.toLowerCase().replace(/\s+/g, ''); // Normalize region name
    const airportCodes = regionAirportCodes[regionKey];

    if (!airportCodes || airportCodes.length === 0) {
        throw new Error(`Region '${region}' is not defined or has no airports listed.`);
    }
    // --- End Get Airport Codes ---

    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      console.error("Database connection string (DATABASE_URL) not found in environment variables.")
      throw new Error("Internal server configuration error.")
    }

    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    connection = await pool.connect()

    try {
      // Use '= ANY($array)' for efficient filtering against the list of airport codes
      const sql = `
        SELECT
            m.origin_code,
            m.origin_name,
            COUNT(m.id) as frequency
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE (
            a.operator ILIKE $1 OR
            a.operator_iata_code = $1 OR
            a.operator_icao_code = $1
          )
            AND m.scheduled_departure >= $2
            AND m.scheduled_departure <= $3
            AND m.origin_code = ANY($4::varchar[]) -- Filter origin by the list of codes for the region
            AND a.operator IS NOT NULL
        GROUP BY m.origin_code, m.origin_name
        ORDER BY frequency DESC, m.origin_code ASC;
      `
      const result = await connection.queryObject(sql, [
        operator_identifier, // $1
        start_time,          // $2
        end_time,            // $3
        airportCodes,        // $4 (Pass the array of airport codes directly)
      ])

      const rawOriginData = result.rows
      const originData = rawOriginData.map(row => ({
        ...row,
        frequency: Number(row.frequency),
      }));

      console.log(`Found ${originData.length} origin airports in region "${region}" for operator "${operator_identifier}" within the period.`);

      return new Response(
        JSON.stringify({ results: originData }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )

    } finally {
      if (connection) await connection.release();
    }
  } catch (error) {
    console.error("Error in get-operator-origins-by-region:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
    const isInputError = (error instanceof Error && (error.message.startsWith("Missing required parameters") || error.message.includes("is not defined")));
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500;

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

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/get-operator-origins-by-region' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
