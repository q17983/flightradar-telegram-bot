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
 * ENHANCED Function 1: Get operators flying TO a destination with freighter/passenger breakdown
 * Returns detailed breakdown by aircraft type and operator with freight vs passenger classification
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
      // 6. Enhanced SQL query with aircraft type and freighter classification
      const sql = `
        SELECT
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            a.type as aircraft_type,
            a.aircraft_details,
            COUNT(m.id) as frequency,
            CASE 
                WHEN (
                  -- Explicit freighter terms
                  UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
                  OR UPPER(a.aircraft_details) LIKE '%CARGO%'
                  OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
                  OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
                  OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
                  OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F patterns
                  
                  -- Broad F pattern for comprehensive coverage
                  OR UPPER(a.aircraft_details) LIKE '%F%'
                )
                -- Exclude military and passenger patterns
                AND NOT (
                  UPPER(a.aircraft_details) LIKE '%FK%'          -- Military variants (e.g., 767-2FK)
                  OR UPPER(a.aircraft_details) LIKE '%TANKER%'   -- Military tanker
                  OR UPPER(a.aircraft_details) LIKE '%VIP%'      -- VIP configuration
                  OR UPPER(a.aircraft_details) LIKE '%FIRST%'    -- First class
                  OR UPPER(a.aircraft_details) LIKE '%FLEX%'     -- Flexible config
                )
                THEN 'Freighter'
                ELSE 'Passenger'
            END as aircraft_category
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code = $1
          AND m.actual_arrival >= $2
          AND m.actual_arrival <= $3
          AND m.actual_arrival IS NOT NULL
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, a.type, a.aircraft_details, aircraft_category
        ORDER BY frequency DESC, a.operator ASC;
      `
      
      // 7. Execute the query
      const result = await connection.queryObject(sql, [
        destination_code, // $1
        start_time,       // $2
        end_time,         // $3
      ])

      // 8. Process results into freighter/passenger breakdown
      const rawData = result.rows.map(row => ({
        ...row,
        frequency: Number(row.frequency),
      }));

      // Group by aircraft category
      const freighterData = rawData.filter(row => row.aircraft_category === 'Freighter');
      const passengerData = rawData.filter(row => row.aircraft_category === 'Passenger');

      // Aggregate by operator for each category
      const aggregateByOperator = (data: any[]) => {
        const operatorMap = new Map();
        
        data.forEach(row => {
          const key = `${row.operator}|${row.operator_iata_code}|${row.operator_icao_code}`;
          if (!operatorMap.has(key)) {
            operatorMap.set(key, {
              operator: row.operator,
              operator_iata_code: row.operator_iata_code,
              operator_icao_code: row.operator_icao_code,
              total_frequency: 0,
              aircraft_types: []
            });
          }
          
          const operator = operatorMap.get(key);
          operator.total_frequency += row.frequency;
          operator.aircraft_types.push({
            aircraft_type: row.aircraft_type,
            aircraft_details: row.aircraft_details,
            frequency: row.frequency
          });
        });
        
        return Array.from(operatorMap.values())
          .sort((a, b) => b.total_frequency - a.total_frequency)
          .map(op => ({
            ...op,
            aircraft_types: op.aircraft_types.sort((a, b) => b.frequency - a.frequency)
          }));
      };

      const freighterOperators = aggregateByOperator(freighterData);
      const passengerOperators = aggregateByOperator(passengerData);

      // Calculate summary statistics
      const totalFreighterFlights = freighterOperators.reduce((sum, op) => sum + op.total_frequency, 0);
      const totalPassengerFlights = passengerOperators.reduce((sum, op) => sum + op.total_frequency, 0);
      const totalFlights = totalFreighterFlights + totalPassengerFlights;

      const freighterPercentage = totalFlights > 0 ? Math.round((totalFreighterFlights / totalFlights) * 100) : 0;
      const passengerPercentage = 100 - freighterPercentage;

      console.log(`Enhanced Function 1: Found ${freighterOperators.length} freighter operators and ${passengerOperators.length} passenger operators flying to "${destination_code}"`);

      // Return enhanced structured results
      return new Response(
        JSON.stringify({
          destination_code,
          period_start: start_time,
          period_end: end_time,
          summary: {
            total_flights: totalFlights,
            freighter_flights: totalFreighterFlights,
            passenger_flights: totalPassengerFlights,
            freighter_percentage: freighterPercentage,
            passenger_percentage: passengerPercentage
          },
          freighter_operators: freighterOperators,
          passenger_operators: passengerOperators
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )

    } finally {
      // 9. Release connection
      if (connection) await connection.release();
    }
  } catch (error) {
    // Handle errors
    console.error("Error in enhanced get-operators-by-destination:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
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

/* Enhanced Function 1 Testing:
  curl -i --location --request POST 'https://prcnxrkyjnpljoqiazkp.supabase.co/functions/v1/get-operators-by-destination' \
    --header 'Authorization: Bearer [TOKEN]' \
    --header 'apikey: [APIKEY]' \
    --header 'Content-Type: application/json' \
    --data '{"destination_code":"TLV","start_time":"2024-04-01","end_time":"2025-05-31"}'
*/