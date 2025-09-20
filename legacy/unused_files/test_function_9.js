// Test Function 9 directly using Node.js
const https = require('https');

// Use the same credentials and URL as the Telegram bot
const SUPABASE_URL = process.env.SUPABASE_URL || "https://prcnxrkyjnpljoqiazkp.supabase.co";
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY;

console.log("🧪 Testing Function 9 directly...");
console.log("SUPABASE_URL:", SUPABASE_URL);
console.log("ANON_KEY available:", !!SUPABASE_ANON_KEY);

const testData = {
  destination_codes: ["HKG", "JFK"],
  start_time: "2024-04-01", 
  end_time: "2025-05-31"
};

const url = `${SUPABASE_URL}/functions/v1/get-operators-by-multi-destinations`;
const data = JSON.stringify(testData);

console.log("🚀 Calling Function 9 with data:", testData);

const options = {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
    'Content-Length': data.length
  }
};

const req = https.request(url, options, (res) => {
  console.log(`📊 Response Status: ${res.statusCode}`);
  console.log(`📊 Response Headers:`, res.headers);
  
  let responseData = '';
  
  res.on('data', (chunk) => {
    responseData += chunk;
  });
  
  res.on('end', () => {
    console.log(`📋 Response Body:`, responseData);
    
    try {
      const jsonResponse = JSON.parse(responseData);
      console.log(`✅ Parsed JSON Response:`, jsonResponse);
    } catch (e) {
      console.log(`❌ Could not parse as JSON:`, e.message);
    }
  });
});

req.on('error', (error) => {
  console.error(`❌ Request Error:`, error);
});

req.write(data);
req.end();
