import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { Pool } from "https://deno.land/x/postgres@v0.17.0/mod.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

console.log(`Test function for checking aircraft data`)

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection;

  try {
    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) {
      throw new Error("DATABASE_URL not found")
    }

    const pool = new Pool(databaseUrl, 3, true)
    connection = await pool.connect()

    // Test 1: Total aircraft count
    const totalSql = `SELECT COUNT(*) as total_aircraft FROM aircraft;`
    const totalResult = await connection.queryObject(totalSql)
    console.log("Total aircraft:", totalResult.rows[0])

    // Test 2: Sample aircraft data
    const sampleSql = `SELECT registration, type, operator FROM aircraft LIMIT 10;`
    const sampleResult = await connection.queryObject(sampleSql)
    console.log("Sample aircraft data:", sampleResult.rows)

    // Test 3: Aircraft types with counts
    const typesSql = `
      SELECT 
        type,
        COUNT(*) as aircraft_count,
        COUNT(DISTINCT operator) as operator_count
      FROM aircraft 
      WHERE type IS NOT NULL 
        AND operator IS NOT NULL
      GROUP BY type 
      ORDER BY aircraft_count DESC 
      LIMIT 20;
    `
    const typesResult = await connection.queryObject(typesSql)
    console.log("Aircraft types with counts:", typesResult.rows)

    // Test 4: Check for specific types
    const specificTypesSql = `
      SELECT type, COUNT(*) as count
      FROM aircraft 
      WHERE type IN ('A330', 'B747', 'B757', 'B767', 'B777', 'IL76', 'B737', 'A320', 'A350', 'B787')
      GROUP BY type
      ORDER BY count DESC;
    `
    const specificResult = await connection.queryObject(specificTypesSql)
    console.log("Specific aircraft types:", specificResult.rows)

    return new Response(
      JSON.stringify({
        total_aircraft: totalResult.rows[0],
        sample_data: sampleResult.rows,
        aircraft_types: typesResult.rows,
        specific_types: specificResult.rows,
        success: true
      }),
      { 
        status: 200, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )

  } catch (error) {
    console.error("Test function error:", error)
    return new Response(
      JSON.stringify({ 
        error: error.message,
        success: false
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
      } catch (e) {
        console.error("Error releasing connection:", e)
      }
    }
  }
})
