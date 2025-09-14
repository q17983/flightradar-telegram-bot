// China Airport Discovery Script
// Run this to analyze our database for ALL China airports

const fetch = require('node-fetch');

async function discoverChinaAirports() {
    console.log("🇨🇳 Discovering ALL China Airports in Database...\n");
    
    // Test query to find all Z* airports
    const query = {
        destination_codes: ["PEK"], // Test with Beijing first
        start_time: "2024-04-01",
        end_time: "2025-05-31"
    };
    
    try {
        const response = await fetch('https://prcnxrkyjnpljoqiazkp.supabase.co/functions/v1/get-operators-by-destination', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${process.env.SUPABASE_ANON_KEY}`
            },
            body: JSON.stringify(query)
        });
        
        const result = await response.json();
        console.log("Sample result:", result);
        
    } catch (error) {
        console.error("Error:", error);
    }
}

// Example China airports to verify
const KNOWN_CHINA_AIRPORTS = [
    // Major International Hubs
    'PEK', 'PVG', 'CAN', 'SZX',
    
    // Regional Capitals  
    'CTU', 'KMG', 'XIY', 'WUH', 'NKG', 'HGH', 'CSX', 'TSN',
    
    // Northeast China
    'DLC', 'HRB', 'SHE', 'CGQ', 'DDG',
    
    // Northwest China  
    'URC', 'LHW', 'XNN', 'YIN',
    
    // Southwest China
    'CKG', 'GYS', 'ZUH', 'LJG',
    
    // Southeast China
    'XMN', 'FOC', 'NNC', 'HAK', 'SYX',
    
    // Central China
    'CGO', 'TNA', 'HET', 'JJN',
    
    // Eastern China
    'NNG', 'TAO', 'YNT', 'WEH', 'WNZ'
];

console.log("Known China Airports Count:", KNOWN_CHINA_AIRPORTS.length);
console.log("Sample airports:", KNOWN_CHINA_AIRPORTS.slice(0, 10));

module.exports = { KNOWN_CHINA_AIRPORTS, discoverChinaAirports };
