// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3
console.log(`Function "get-operators-by-geographic-locations" up and running!`)

/**
 * Function 10: Enhanced Geographic Multi-Destination Analysis
 * Find operators serving multiple geographic locations (airports, countries, continents)
 * Uses airports_geography table for intelligent geographic matching
 */
serve(async (req: Request) => {
  // 1. Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection; // Define connection outside try block to access in finally

  try {
    console.log("=== Function 10: get-operators-by-geographic-locations ===")
    console.log("Request method:", req.method)
    
    // Parse request body
    const requestData = await req.json()
    console.log("Request body:", requestData)
    
    const { 
      first_location_type, 
      first_location_value, 
      second_location_type, 
      second_location_value, 
      start_time, 
      end_time 
    } = requestData

    // Validate required parameters
    if (!first_location_type || !first_location_value || !second_location_type || !second_location_value) {
      console.log("❌ Missing location parameters")
      return new Response(
        JSON.stringify({ 
          error: 'All location parameters are required: first_location_type, first_location_value, second_location_type, second_location_value' 
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

    // Validate location types
    const validTypes = ['airport', 'country', 'continent']
    if (!validTypes.includes(first_location_type) || !validTypes.includes(second_location_type)) {
      console.log("❌ Invalid location types:", { first_location_type, second_location_type })
      return new Response(
        JSON.stringify({ 
          error: 'location_type must be one of: airport, country, continent' 
        }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      )
    }

    console.log("✅ Valid parameters received:", { 
      first_location_type, first_location_value, 
      second_location_type, second_location_value, 
      start_time, end_time 
    })

    // 4. Connect to the database
    const databaseUrl = Deno.env.get('DATABASE_URL')!
    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    
    // 5. Connect to the database
    connection = await pool.connect()

    try {
      // 6. Build dynamic SQL query based on location types
      const buildLocationCondition = (locationType: string, locationValue: string, tableAlias: string) => {
        switch (locationType) {
          case 'airport':
            return `${tableAlias}.iata_code = '${locationValue.toUpperCase()}'`
          case 'country':
            return `${tableAlias}.country_name ILIKE '${locationValue}'`
          case 'continent':
            return `${tableAlias}.continent = '${locationValue.toUpperCase()}'`
          default:
            throw new Error(`Invalid location type: ${locationType}`)
        }
      }

      // Build the main query with geographic intelligence
      const sql = `
        WITH first_location_airports AS (
          SELECT DISTINCT ag.iata_code, ag.airport_name, ag.country_name, ag.continent
          FROM airports_geography ag
          WHERE ${buildLocationCondition(first_location_type, first_location_value, 'ag')}
        ),
        second_location_airports AS (
          SELECT DISTINCT ag.iata_code, ag.airport_name, ag.country_name, ag.continent  
          FROM airports_geography ag
          WHERE ${buildLocationCondition(second_location_type, second_location_value, 'ag')}
        ),
        operator_flights AS (
          SELECT
            a.operator,
            a.operator_iata_code,
            a.operator_icao_code,
            a.type as aircraft_type,
            a.aircraft_details,
            a.registration,
            m.destination_code,
            ag.airport_name as destination_name,
            ag.country_name as dest_country,
            ag.continent as dest_continent,
            COUNT(*) as frequency,
            CASE 
              WHEN UPPER(a.aircraft_details) LIKE '%FREIGHTER%' 
                OR UPPER(a.aircraft_details) LIKE '%-F%'
                OR UPPER(a.aircraft_details) LIKE '%CARGO%'
                OR UPPER(a.aircraft_details) LIKE '%BCF%'
                OR UPPER(a.aircraft_details) LIKE '%SF%'
              THEN 'Freighter'
              ELSE 'Passenger'
            END as aircraft_category,
            CASE 
              WHEN fla.iata_code IS NOT NULL THEN 'first_location'
              WHEN sla.iata_code IS NOT NULL THEN 'second_location'
            END as location_match
          FROM movements m
          JOIN aircraft a ON m.registration = a.registration
          JOIN airports_geography ag ON m.destination_code = ag.iata_code
          LEFT JOIN first_location_airports fla ON m.destination_code = fla.iata_code
          LEFT JOIN second_location_airports sla ON m.destination_code = sla.iata_code
          WHERE (fla.iata_code IS NOT NULL OR sla.iata_code IS NOT NULL)
            AND m.scheduled_departure >= $1
            AND m.scheduled_departure <= $2
            AND a.operator IS NOT NULL
          GROUP BY a.operator, a.operator_iata_code, a.operator_icao_code, 
                   a.type, a.aircraft_details, a.registration,
                   m.destination_code, ag.airport_name, ag.country_name, ag.continent,
                   aircraft_category, location_match
        )
        SELECT 
          operator,
          operator_iata_code,
          operator_icao_code,
          aircraft_type,
          aircraft_details,
          registration,
          destination_code,
          destination_name,
          dest_country,
          dest_continent,
          frequency,
          aircraft_category,
          location_match
        FROM operator_flights
        ORDER BY operator, aircraft_category, aircraft_type, frequency DESC;
      `
      
      // 7. Execute the query
      const queryResult = await connection.queryObject(sql, [start_time, end_time])

      console.log("📊 Raw query results:", queryResult.rows?.length || 0, "records")

      if (!queryResult.rows || queryResult.rows.length === 0) {
        console.log("❌ No data found")
        return new Response(
          JSON.stringify({ 
            message: 'No operators found serving the specified geographic locations',
            search_criteria: {
              first_location: { type: first_location_type, value: first_location_value },
              second_location: { type: second_location_type, value: second_location_value }
            },
            time_range: { start_time, end_time }
          }),
          { 
            status: 200, 
            headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
          }
        )
      }

      // 8. Process results - Group by operator and analyze geographic coverage
      const operatorMap = new Map()
      
      queryResult.rows.forEach(flight => {
        const operatorKey = `${flight.operator_iata_code}|${flight.operator}`
        
        if (!operatorMap.has(operatorKey)) {
          operatorMap.set(operatorKey, {
            operator: flight.operator,
            operator_iata_code: flight.operator_iata_code,
            operator_icao_code: flight.operator_icao_code,
            first_location_flights: 0,
            second_location_flights: 0,
            total_flights: 0,
            freighter_flights: 0,
            passenger_flights: 0,
            aircraft_types: new Map(),
            destinations: {
              first_location: new Set(),
              second_location: new Set()
            },
            countries_served: new Set(),
            continents_served: new Set()
          })
        }
        
        const operator = operatorMap.get(operatorKey)
        const flightCount = Number(flight.frequency)
        
        // Track location-specific flights
        if (flight.location_match === 'first_location') {
          operator.first_location_flights += flightCount
          operator.destinations.first_location.add(flight.destination_code)
        } else if (flight.location_match === 'second_location') {
          operator.second_location_flights += flightCount
          operator.destinations.second_location.add(flight.destination_code)
        }
        
        operator.total_flights += flightCount
        operator.countries_served.add(flight.dest_country)
        operator.continents_served.add(flight.dest_continent)
        
        // Track aircraft category
        if (flight.aircraft_category === 'Freighter') {
          operator.freighter_flights += flightCount
        } else {
          operator.passenger_flights += flightCount
        }
        
        // Track aircraft types with detailed breakdown
        const aircraftKey = `${flight.aircraft_type}|${flight.aircraft_category}`
        if (!operator.aircraft_types.has(aircraftKey)) {
          operator.aircraft_types.set(aircraftKey, {
            aircraft_type: flight.aircraft_type,
            aircraft_details: flight.aircraft_details,
            aircraft_category: flight.aircraft_category,
            registrations: new Set(),
            flights: 0,
            destinations: new Map()
          })
        }
        
        const aircraft = operator.aircraft_types.get(aircraftKey)
        aircraft.registrations.add(flight.registration)
        aircraft.flights += flightCount
        
        // Track destinations per aircraft type
        if (!aircraft.destinations.has(flight.destination_code)) {
          aircraft.destinations.set(flight.destination_code, {
            name: flight.destination_name,
            country: flight.dest_country,
            continent: flight.dest_continent,
            flights: 0
          })
        }
        aircraft.destinations.get(flight.destination_code).flights += flightCount
      })

      // 9. Filter operators serving BOTH locations and format results
      const qualifiedOperators = Array.from(operatorMap.values())
        .filter(op => op.first_location_flights > 0 && op.second_location_flights > 0)
        .map(operator => {
          const freighter_percentage = operator.total_flights > 0 
            ? Math.round((operator.freighter_flights / operator.total_flights) * 100) 
            : 0
          const passenger_percentage = 100 - freighter_percentage
          
          // Process aircraft types
          const passenger_aircraft = []
          const freighter_aircraft = []
          
          operator.aircraft_types.forEach(aircraft => {
            const aircraftData = {
              aircraft_type: aircraft.aircraft_type,
              aircraft_details: aircraft.aircraft_details,
              flights: aircraft.flights,
              registrations: Array.from(aircraft.registrations).slice(0, 10), // Limit to first 10
              destinations: Array.from(aircraft.destinations.entries())
                .map(([code, dest]) => ({
                  code,
                  name: dest.name,
                  country: dest.country,
                  continent: dest.continent,
                  flights: dest.flights
                }))
                .sort((a, b) => b.flights - a.flights)
                .slice(0, 5) // Top 5 destinations per aircraft type
            }
            
            if (aircraft.aircraft_category === 'Freighter') {
              freighter_aircraft.push(aircraftData)
            } else {
              passenger_aircraft.push(aircraftData)
            }
          })
          
          return {
            operator: operator.operator,
            operator_iata_code: operator.operator_iata_code,
            operator_icao_code: operator.operator_icao_code,
            total_flights: operator.total_flights,
            first_location_flights: operator.first_location_flights,
            second_location_flights: operator.second_location_flights,
            freighter_flights: operator.freighter_flights,
            passenger_flights: operator.passenger_flights,
            freighter_percentage,
            passenger_percentage,
            geographic_coverage: {
              first_location_destinations: Array.from(operator.destinations.first_location),
              second_location_destinations: Array.from(operator.destinations.second_location),
              countries_served: Array.from(operator.countries_served),
              continents_served: Array.from(operator.continents_served)
            },
            fleet_breakdown: {
              passenger_aircraft: passenger_aircraft.sort((a, b) => b.flights - a.flights),
              freighter_aircraft: freighter_aircraft.sort((a, b) => b.flights - a.flights)
            }
          }
        })
        .sort((a, b) => b.total_flights - a.total_flights)

      console.log("✅ Found", qualifiedOperators.length, "operators serving both geographic locations")

      const result = {
        message: `Found ${qualifiedOperators.length} operators serving both geographic locations`,
        search_criteria: {
          first_location: { 
            type: first_location_type, 
            value: first_location_value 
          },
          second_location: { 
            type: second_location_type, 
            value: second_location_value 
          }
        },
        time_range: { start_time, end_time },
        operators: qualifiedOperators,
        summary: {
          total_operators: qualifiedOperators.length,
          total_flights: qualifiedOperators.reduce((sum, op) => sum + op.total_flights, 0),
          freighter_flights: qualifiedOperators.reduce((sum, op) => sum + op.freighter_flights, 0),
          passenger_flights: qualifiedOperators.reduce((sum, op) => sum + op.passenger_flights, 0)
        }
      }

      console.log("🎯 Final result summary:", {
        operators: result.operators.length,
        total_flights: result.summary.total_flights
      })

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
