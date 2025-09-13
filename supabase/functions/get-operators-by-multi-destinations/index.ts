// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { corsHeaders } from '../_shared/cors.ts'

console.log(`Function "get-operators-by-multi-destinations" up and running!`)

/**
 * Function 9: ULTRA SIMPLE TEST VERSION
 * Just test parameter extraction without any database calls
 */
serve(async (req: Request) => {
  // 1. Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    console.log("Function 9: Starting request processing...")
    
    // SPECIAL TEST MODE: If no body provided, return test data
    if (!req.body) {
      console.log("Function 9: No request body - returning test mode response")
      return new Response(
        JSON.stringify({
          test_mode: true,
          message: "Function 9 is running and can return responses!",
          function_status: "WORKING",
          next_step: "Test with actual parameters"
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }
    
    console.log("Function 9: About to parse JSON...")
    const requestData = await req.json()
    console.log("Function 9: Parsed JSON successfully:", requestData)
    
    // SPECIAL TEST: If request contains "test_mode", return hard-coded success
    if (requestData.test_mode === true) {
      console.log("Function 9: Test mode activated - returning hard-coded success")
      return new Response(
        JSON.stringify({
          test_mode: true,
          message: "Function 9 can successfully process JSON requests!",
          received_data: requestData,
          function_status: "JSON_PARSING_WORKS",
          next_step: "Test with real destination codes"
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }
    
    const { destination_codes, start_time, end_time } = requestData

    console.log("Function 9: Extracted parameters:")
    console.log("- destination_codes:", destination_codes, "Type:", typeof destination_codes)
    console.log("- start_time:", start_time, "Type:", typeof start_time)
    console.log("- end_time:", end_time, "Type:", typeof end_time)

    // Basic validation
    if (!destination_codes) {
      console.error("Function 9: destination_codes is missing")
      throw new Error("Missing required parameter: destination_codes")
    }
    
    if (!Array.isArray(destination_codes)) {
      console.error("Function 9: destination_codes is not an array:", typeof destination_codes)
      throw new Error("destination_codes must be an array")
    }
    
    if (destination_codes.length === 0) {
      console.error("Function 9: destination_codes array is empty")
      throw new Error("destination_codes array cannot be empty")
    }
    
    if (!start_time || !end_time) {
      console.error("Function 9: Missing time parameters")
      throw new Error("Missing required parameters: start_time, end_time")
    }

    console.log("Function 9: All validation passed!")
    
    // Just return the extracted parameters as a test
    const response = {
      success: true,
      message: "Function 9 parameter extraction successful!",
      extracted_data: {
        destination_codes: destination_codes,
        destination_count: destination_codes.length,
        first_destination: destination_codes[0],
        start_time: start_time,
        end_time: end_time
      },
      next_step: "Will add database logic once parameter extraction works"
    }

    console.log("Function 9: Returning success response")
    
    return new Response(
      JSON.stringify(response),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    console.error("Function 9: ERROR:", error)
    console.error("Function 9: Error message:", error.message)
    console.error("Function 9: Error stack:", error.stack)
    
    return new Response(
      JSON.stringify({ 
        error: `Function 9 test failed: ${error.message}`,
        details: error.stack
      }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    )
  }
})