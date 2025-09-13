// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { corsHeaders } from '../_shared/cors.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

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

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_ANON_KEY')!
    const supabase = createClient(supabaseUrl, supabaseKey)

    console.log("🔍 Searching for operators serving multiple destinations...")

    // Query to find operators that serve the specified destinations
    const { data: operators, error } = await supabase
      .from('flight_data')
      .select(`
        operator_iata,
        operator_name,
        destination_iata,
        destination_name,
        aircraft_type,
        aircraft_registration
      `)
      .in('destination_iata', destination_codes)
      .gte('departure_time', start_time)
      .lte('departure_time', end_time)
      .not('operator_iata', 'is', null)
      .not('operator_name', 'is', null)

    if (error) {
      console.log("❌ Database error:", error)
      return new Response(
        JSON.stringify({ error: 'Database query failed', details: error.message }),
        { 
          status: 500, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      )
    }

    console.log("📊 Raw query results:", operators?.length || 0, "records")

    if (!operators || operators.length === 0) {
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

    // Group by operator and count unique destinations served
    const operatorDestinations = new Map()
    
    operators.forEach(flight => {
      const key = `${flight.operator_iata}|${flight.operator_name}`
      if (!operatorDestinations.has(key)) {
        operatorDestinations.set(key, {
          operator_iata: flight.operator_iata,
          operator_name: flight.operator_name,
          destinations: new Set(),
          aircraft_types: new Set(),
          total_flights: 0
        })
      }
      
      const operator = operatorDestinations.get(key)
      operator.destinations.add(flight.destination_iata)
      operator.aircraft_types.add(flight.aircraft_type)
      operator.total_flights++
    })

    // Filter operators that serve ALL specified destinations
    const multiDestinationOperators = Array.from(operatorDestinations.values())
      .filter(operator => operator.destinations.size >= destination_codes.length)
      .map(operator => ({
        operator_iata: operator.operator_iata,
        operator_name: operator.operator_name,
        destinations_served: Array.from(operator.destinations),
        aircraft_types: Array.from(operator.aircraft_types),
        total_flights: operator.total_flights
      }))
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