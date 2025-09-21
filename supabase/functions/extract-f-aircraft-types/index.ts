import { serve } from "https://deno.land/std@0.177.0/http/server.ts"
import { Pool } from "https://deno.land/x/postgres@v0.17.0/mod.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
}

serve(async (req: Request) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection: any = null
  
  try {
    // Get database connection string from environment
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      throw new Error('DATABASE_URL environment variable is not set')
    }

    // Create connection pool
    const pool = new Pool(databaseUrl, 3, true)
    connection = await pool.connect()

    // Query to extract all aircraft types and details containing 'F'
    const sql = `
      SELECT DISTINCT
        a.type as aircraft_type,
        a.aircraft_details,
        COUNT(*) as aircraft_count,
        COUNT(DISTINCT a.operator) as operator_count,
        COUNT(DISTINCT a.registration) as registration_count,
        -- Current freighter classification
        CASE 
          WHEN (
            -- Explicit freighter terms
            UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
            OR UPPER(a.aircraft_details) LIKE '%CARGO%'
            OR UPPER(a.aircraft_details) LIKE '%BCF%'      -- Boeing Converted Freighter
            OR UPPER(a.aircraft_details) LIKE '%BDSF%'     -- Boeing Dedicated Special Freighter
            OR UPPER(a.aircraft_details) LIKE '%SF%'       -- Special Freighter
            OR UPPER(a.aircraft_details) LIKE '%-F%'       -- Dash-F patterns
            OR UPPER(a.aircraft_details) LIKE '%F%'        -- Broad F pattern
          )
          -- Exclude military and passenger patterns
          AND NOT (
            UPPER(a.aircraft_details) LIKE '%FK%'          -- Military variants
            OR UPPER(a.aircraft_details) LIKE '%TANKER%'   -- Military tanker
            OR UPPER(a.aircraft_details) LIKE '%VIP%'      -- VIP configuration
            OR UPPER(a.aircraft_details) LIKE '%FIRST%'    -- First class
            OR UPPER(a.aircraft_details) LIKE '%FLEX%'     -- Flexible config
          )
          THEN 'Freighter'
          ELSE 'Passenger'
        END as current_classification
      FROM aircraft a
      WHERE a.aircraft_details IS NOT NULL
        AND (
          UPPER(a.aircraft_details) LIKE '%F%'  -- Contains 'F' anywhere
          OR UPPER(a.type) LIKE '%F%'           -- Also check aircraft type
        )
        AND a.operator IS NOT NULL
        AND a.operator != ''
      GROUP BY a.type, a.aircraft_details
      ORDER BY 
        current_classification DESC,  -- Freighters first
        aircraft_count DESC,          -- Most common first
        a.type,                       -- Then alphabetically
        a.aircraft_details
    `

    console.log("🔍 Extracting all aircraft types containing 'F'...")
    const result = await connection.queryObject(sql)
    
    console.log(`Found ${result.rows.length} distinct aircraft types/details containing 'F'`)

    // Group results by current classification for easier review
    const freighters = result.rows.filter(row => row.current_classification === 'Freighter')
    const passengers = result.rows.filter(row => row.current_classification === 'Passenger')

    const response = {
      message: `Found ${result.rows.length} aircraft types/details containing 'F'`,
      summary: {
        total_types: result.rows.length,
        currently_classified_as_freighter: freighters.length,
        currently_classified_as_passenger: passengers.length
      },
      freighter_classified: freighters.map(row => ({
        aircraft_type: row.aircraft_type,
        aircraft_details: row.aircraft_details,
        aircraft_count: Number(row.aircraft_count),
        operator_count: Number(row.operator_count),
        registration_count: Number(row.registration_count),
        current_classification: row.current_classification
      })),
      passenger_classified: passengers.map(row => ({
        aircraft_type: row.aircraft_type,
        aircraft_details: row.aircraft_details,
        aircraft_count: Number(row.aircraft_count),
        operator_count: Number(row.operator_count),
        registration_count: Number(row.registration_count),
        current_classification: row.current_classification
      }))
    }

    return new Response(
      JSON.stringify(response, null, 2),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )

  } catch (error) {
    console.error("❌ Error extracting F aircraft types:", error)
    return new Response(
      JSON.stringify({ 
        error: "Failed to extract aircraft types",
        details: error.message 
      }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  } finally {
    if (connection) {
      try {
        connection.release()
      } catch (releaseError) {
        console.error("Error releasing database connection:", releaseError)
      }
    }
  }
})
