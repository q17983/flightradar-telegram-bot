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
            COUNT(m.id) as frequency,
            CASE 
              -- Rule 1: VIP/Corporate (Highest Priority)
              WHEN UPPER(a.aircraft_details) LIKE '%(BBJ%)'
              THEN 'Passenger (VIP/Corporate)'
              
              -- Rule 2: Dedicated Freighters (Second Priority)
              WHEN (
                -- A) Explicit Conversion Codes
                UPPER(a.aircraft_details) LIKE '%(BCF)'     -- Boeing Converted Freighter
                OR UPPER(a.aircraft_details) LIKE '%(BDSF)' -- Boeing Dedicated Special Freighter
                OR UPPER(a.aircraft_details) LIKE '%(SF)'   -- Special Freighter
                OR UPPER(a.aircraft_details) LIKE '%(PCF)'  -- Passenger to Cargo Freighter
                OR UPPER(a.aircraft_details) LIKE '%(P2F)'  -- Passenger to Freighter
                OR UPPER(a.aircraft_details) LIKE '%PF'     -- Package Freighter
                
                -- B) Production Freighter Models with Customer Codes
                -- Boeing 777-F variants (777-F + customer code)
                OR UPPER(a.aircraft_details) LIKE '%777-F%'  -- Covers 777-FS2, 777-FHT, 777-FFX, 777-F28, etc.
                
                -- Boeing 747-F variants (Enhanced for all patterns)
                OR UPPER(a.aircraft_details) LIKE '%747-%F'     -- Standard 747-8F pattern
                OR UPPER(a.aircraft_details) LIKE '%747-4%F'    -- 747-400F variants (direct F)
                OR UPPER(a.aircraft_details) LIKE '%747-2%F'    -- 747-200F variants (direct F)
                OR UPPER(a.aircraft_details) LIKE '%747-4%F(%'  -- 747-4xxF(ER) patterns (F followed by parentheses)
                OR UPPER(a.aircraft_details) LIKE '%747-2%F(%'  -- 747-2xxF(ER) patterns (F followed by parentheses)
                OR UPPER(a.aircraft_details) LIKE '%747-4%(F)'  -- 747-4xx(F) patterns (F in parentheses)
                OR UPPER(a.aircraft_details) LIKE '%747-2%(F)'  -- 747-2xx(F) patterns (F in parentheses)
                
                -- Boeing 767-F variants
                OR UPPER(a.aircraft_details) LIKE '%767-%F'  -- 767-300F pattern
                
                -- Airbus A330-F variants
                OR UPPER(a.aircraft_details) LIKE '%A330-%F' -- A330-200F, A330-300F patterns
                
                -- Generic F suffix for other models
                OR UPPER(a.aircraft_details) LIKE '%-F'      -- Dash-F pattern (e.g., ATR-72F)
                OR (UPPER(a.aircraft_details) LIKE '%F' AND NOT UPPER(a.aircraft_details) LIKE '%F%F%') -- Single F suffix
                
                -- Explicit Terms
                OR UPPER(a.aircraft_details) LIKE '%FREIGHTER%'
                OR UPPER(a.aircraft_details) LIKE '%CARGO%'
              )
              AND NOT UPPER(a.aircraft_details) LIKE '%(BBJ%)'
              AND NOT UPPER(a.aircraft_details) LIKE '%FK%'
              AND NOT UPPER(a.aircraft_details) LIKE '%TANKER%'
              AND NOT UPPER(a.aircraft_details) LIKE '%VIP%'
              AND NOT UPPER(a.aircraft_details) LIKE '%FIRST%'
              THEN 'Freighter'
              
              -- Rule 3: Multi-Role (Third Priority)
              WHEN (
                UPPER(a.aircraft_details) LIKE '%(FC)'
                OR UPPER(a.aircraft_details) LIKE '%(CF)'
                OR UPPER(a.aircraft_details) LIKE '%(C)'
                OR UPPER(a.aircraft_details) LIKE '%(M)'
              )
              AND NOT UPPER(a.aircraft_details) LIKE '%(BBJ%)'
              AND NOT (
                UPPER(a.aircraft_details) LIKE '%(BCF)'
                OR UPPER(a.aircraft_details) LIKE '%(BDSF)'
                OR UPPER(a.aircraft_details) LIKE '%(SF)'
                OR UPPER(a.aircraft_details) LIKE '%(PCF)'
                OR UPPER(a.aircraft_details) LIKE '%(P2F)'
              )
              THEN 'Multi-Role (Passenger/Cargo)'
              
              -- Rule 4: Default Passenger
              ELSE 'Passenger'
            END as aircraft_category
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE m.destination_code IN (${destinationPlaceholders})
          AND m.actual_arrival >= $1
          AND m.actual_arrival <= $${destination_codes.length + 2}
          AND m.actual_arrival IS NOT NULL
          AND a.operator IS NOT NULL
        GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, a.type, a.aircraft_details, m.destination_code, m.destination_name, aircraft_category
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

      // 8. Group by operator and separate freighter/passenger operations
      const operatorDestinations = new Map()
      
      queryResult.rows.forEach(flight => {
        const key = `${flight.operator_iata_code}|${flight.operator}`
        if (!operatorDestinations.has(key)) {
          operatorDestinations.set(key, {
            operator_iata: flight.operator_iata_code,
            operator_name: flight.operator,
            destinations: new Set(),
            freighter_flights: 0,
            passenger_flights: 0,
            freighter_aircraft: new Set(),
            passenger_aircraft: new Set(),
            total_flights: 0
          })
        }
        
        const operator = operatorDestinations.get(key)
        operator.destinations.add(flight.destination_code)
        operator.total_flights += Number(flight.frequency)
        
        // Separate freighter and passenger operations
        if (flight.aircraft_category === 'Freighter') {
          operator.freighter_flights += Number(flight.frequency)
          operator.freighter_aircraft.add(flight.aircraft_type)
        } else {
          operator.passenger_flights += Number(flight.frequency)
          operator.passenger_aircraft.add(flight.aircraft_type)
        }
      })

      // 9. Filter operators that serve ALL specified destinations and format results
      const multiDestinationOperators = Array.from(operatorDestinations.values())
        .filter(operator => operator.destinations.size >= destination_codes.length)
        .map(operator => {
          const freighter_percentage = operator.total_flights > 0 
            ? Math.round((operator.freighter_flights / operator.total_flights) * 100) 
            : 0
          const passenger_percentage = 100 - freighter_percentage
          
          return {
            operator_iata: operator.operator_iata,
            operator_name: operator.operator_name,
            destinations_served: Array.from(operator.destinations),
            total_flights: operator.total_flights,
            freighter_flights: operator.freighter_flights,
            passenger_flights: operator.passenger_flights,
            freighter_percentage,
            passenger_percentage,
            freighter_aircraft: Array.from(operator.freighter_aircraft),
            passenger_aircraft: Array.from(operator.passenger_aircraft),
            aircraft_breakdown: {
              freighter: Array.from(operator.freighter_aircraft),
              passenger: Array.from(operator.passenger_aircraft)
            }
          }
        })
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