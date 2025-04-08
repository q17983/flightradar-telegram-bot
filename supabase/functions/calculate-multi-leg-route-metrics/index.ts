// Follow this setup guide to integrate the Deno language server with your editor:
// https://deno.land/manual/getting_started/setup_your_environment
// This enables autocomplete, go to definition, etc.

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts"

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { Pool } from 'https://deno.land/x/postgres@v0.17.0/mod.ts'
import { corsHeaders } from '../_shared/cors.ts'

const DATABASE_POOL_SIZE = 3
// Max time allowed between arrival and next departure to be considered part of the same journey (in seconds)
// e.g., 48 hours = 48 * 60 * 60 = 172800 seconds
const MAX_GROUND_TIME_SECONDS = 172800;

console.log(`Function "calculate-multi-leg-route-metrics" up and running!`)

interface MovementLeg {
    registration: string;
    origin_code: string;
    destination_code: string;
    scheduled_departure: Date | null; // Use Date objects for easier comparison
    scheduled_arrival: Date | null;
    flight_time: unknown; // Interval type from DB
    flight_time_seconds: number | null;
}

interface Journey {
    registration: string;
    operator: string | null; // Add operator info
    legs: { origin: string; destination: string; dep: string | null; arr: string | null; flight_time_seconds: number | null }[];
    num_legs: number;
    total_flight_time_seconds: number;
    total_ground_time_seconds: number;
}


/**
 * Attempts to identify multi-leg journeys between a start origin and final destination
 * for a specific operator (optional) within a time frame. Calculates metrics like
 * total flight time and ground time.
 * WARNING: This logic is complex and relies on assumptions about connecting flights.
 */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  let connection;

  try {
    if (!req.body) throw new Error("Request body is missing.")

    const { start_origin_code, final_destination_code, start_time, end_time, operator_identifier } = await req.json()

    if (!start_origin_code || !final_destination_code || !start_time || !end_time) {
      throw new Error("Missing required parameters: start_origin_code, final_destination_code, start_time, end_time")
    }
    // TODO: Add validation for codes and dates

    const databaseUrl = Deno.env.get('DATABASE_URL')
    if (!databaseUrl) throw new Error("Internal server configuration error.")

    const pool = new Pool(databaseUrl, DATABASE_POOL_SIZE, true)
    connection = await pool.connect()

    try {
      // --- Step 1: Fetch Candidate Movement Data ---
      // Find aircraft potentially involved, then fetch all their movements in the window.
      const relevantAircraftSql = `
        SELECT DISTINCT a.registration, a.operator -- Fetch operator here too
        FROM movements m
        JOIN aircraft a ON m.registration = a.registration
        WHERE
          ( ($1::varchar IS NULL) OR (a.operator ILIKE $1 OR a.operator_iata_code = $1 OR a.operator_icao_code = $1) )
          AND m.scheduled_departure >= $2 AND m.scheduled_departure <= $3 -- Broad time window
          AND (m.origin_code = $4 OR m.destination_code = $5) -- Touched start OR end points
      `;

      const candidateMovementsSql = `
        WITH RelevantAircraft AS (${relevantAircraftSql})
        SELECT
            m.registration,
            ra.operator, -- Get operator from CTE
            m.origin_code,
            m.destination_code,
            m.scheduled_departure,
            m.scheduled_arrival,
            m.flight_time,
            EXTRACT(EPOCH FROM m.flight_time)::integer as flight_time_seconds
        FROM movements m
        JOIN RelevantAircraft ra ON m.registration = ra.registration
        WHERE m.scheduled_departure >= $2 AND m.scheduled_departure <= $3 -- Ensure within window
        ORDER BY m.registration, m.scheduled_departure;
      `;

      const candidateResult = await connection.queryObject<MovementLeg>(candidateMovementsSql, [
        operator_identifier ?? null, // $1: Use null if operator not provided
        start_time,                  // $2
        end_time,                    // $3
        start_origin_code,           // $4
        final_destination_code,      // $5
      ]);

      const allMovements = candidateResult.rows.map(m => ({
          ...m,
          // Convert DB timestamp strings to JS Date objects for easier comparison
          scheduled_departure: m.scheduled_departure ? new Date(m.scheduled_departure) : null,
          scheduled_arrival: m.scheduled_arrival ? new Date(m.scheduled_arrival) : null,
      }));

      console.log(`Fetched ${allMovements.length} potential movement legs for analysis.`);

      // --- Step 2: Process Data in TypeScript to Find Journeys ---
      const journeys: Journey[] = [];
      const movementsByReg: { [key: string]: MovementLeg[] } = {};

      // Group movements by registration
      for (const movement of allMovements) {
        if (!movementsByReg[movement.registration]) {
          movementsByReg[movement.registration] = [];
        }
        movementsByReg[movement.registration].push(movement);
      }

      // Iterate through each aircraft's sorted movements
      for (const registration in movementsByReg) {
        const legs = movementsByReg[registration]; // Already sorted by departure time
        if (legs.length < 1) continue; // Need at least one leg

        // Try to find sequences starting at the desired origin
        for (let i = 0; i < legs.length; i++) {
            if (legs[i].origin_code === start_origin_code) {
                // Found a potential starting leg, now try to build the journey
                const currentJourneyLegs: MovementLeg[] = [legs[i]];
                let currentLeg = legs[i];
                let possible = true;

                while (currentLeg.destination_code !== final_destination_code && possible) {
                    let foundNextLeg = false;
                    // Look for the next connecting leg for THIS aircraft
                    for (let j = i + 1; j < legs.length; j++) { // Look only forward in time
                        const nextPotentialLeg = legs[j];
                        // Check connection criteria
                        if (nextPotentialLeg.origin_code === currentLeg.destination_code &&
                            currentLeg.scheduled_arrival && nextPotentialLeg.scheduled_departure)
                        {
                            const groundTimeSeconds = (nextPotentialLeg.scheduled_departure.getTime() - currentLeg.scheduled_arrival.getTime()) / 1000;
                            // Check if within reasonable ground time and departure is after arrival
                            if (groundTimeSeconds >= 0 && groundTimeSeconds <= MAX_GROUND_TIME_SECONDS) {
                                currentJourneyLegs.push(nextPotentialLeg);
                                currentLeg = nextPotentialLeg; // Move to the next leg
                                foundNextLeg = true;
                                i = j; // Optimization: avoid re-checking legs we just added
                                break; // Found the immediate next leg
                            }
                        }
                    }
                    if (!foundNextLeg) {
                        possible = false; // Couldn't find a connecting leg
                    }
                } // end while searching for destination

                // If we ended at the final destination, record the journey
                if (currentLeg.destination_code === final_destination_code) {
                    let totalFlightTime = 0;
                    let totalGroundTime = 0;
                    const formattedLegs = [];

                    for(let k=0; k < currentJourneyLegs.length; k++) {
                        const leg = currentJourneyLegs[k];
                        totalFlightTime += leg.flight_time_seconds ?? 0;
                        formattedLegs.push({
                            origin: leg.origin_code,
                            destination: leg.destination_code,
                            dep: leg.scheduled_departure?.toISOString() ?? null,
                            arr: leg.scheduled_arrival?.toISOString() ?? null,
                            flight_time_seconds: leg.flight_time_seconds
                        });
                        // Calculate ground time (if not the last leg)
                        if (k < currentJourneyLegs.length - 1) {
                            const nextLeg = currentJourneyLegs[k+1];
                            if (leg.scheduled_arrival && nextLeg.scheduled_departure) {
                                const ground = (nextLeg.scheduled_departure.getTime() - leg.scheduled_arrival.getTime()) / 1000;
                                totalGroundTime += Math.max(0, ground); // Ensure non-negative
                            }
                        }
                    }

                    journeys.push({
                        registration: registration,
                        operator: currentJourneyLegs[0]?.operator ?? null, // Get operator from first leg
                        legs: formattedLegs,
                        num_legs: currentJourneyLegs.length,
                        total_flight_time_seconds: totalFlightTime,
                        total_ground_time_seconds: Math.round(totalGroundTime), // Round ground time
                    });
                }
            } // end if potential starting leg
        } // end for loop through legs of one aircraft
      } // end for loop through registrations

      console.log(`Identified ${journeys.length} potential multi-leg journeys from ${start_origin_code} to ${final_destination_code}.`);

      return new Response(
        JSON.stringify({ results: journeys }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
      )

    } finally {
      if (connection) await connection.release();
    }
  } catch (error) {
    console.error("Error in calculate-multi-leg-route-metrics:", error.message, error.stack ? `\nStack: ${error.stack}` : '')
    const isInputError = error instanceof Error && (error.message.startsWith("Missing required parameters"));
    const clientErrorMessage = isInputError ? error.message : "An internal server error occurred.";
    const statusCode = isInputError ? 400 : 500;

    if (connection) { try { await connection.release(); } catch (e) { console.error("Err releasing conn:", e)} }

    return new Response(
      JSON.stringify({ error: clientErrorMessage }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: statusCode }
    )
  }
})

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/calculate-multi-leg-route-metrics' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
