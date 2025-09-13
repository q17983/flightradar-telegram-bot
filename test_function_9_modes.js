// Test Function 9 in different modes
const https = require('https');

const url = "https://prcnxrkyjnpljoqiazkp.supabase.co/functions/v1/get-operators-by-multi-destinations";

function testFunction9(testName, data, useAuth = true) {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify(data);
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': postData.length
      }
    };
    
    if (useAuth) {
      options.headers['Authorization'] = 'Bearer test';
    }
    
    console.log(`\n🧪 Test: ${testName}`);
    console.log(`📤 Data:`, data);
    
    const req = https.request(url, options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        console.log(`📊 Status: ${res.statusCode}`);
        console.log(`📋 Response:`, responseData);
        
        try {
          const jsonResponse = JSON.parse(responseData);
          console.log(`✅ Parsed:`, jsonResponse);
          resolve({ status: res.statusCode, data: jsonResponse });
        } catch (e) {
          console.log(`❌ Parse Error:`, e.message);
          resolve({ status: res.statusCode, data: responseData });
        }
      });
    });
    
    req.on('error', (error) => {
      console.error(`❌ Request Error:`, error);
      reject(error);
    });
    
    req.write(postData);
    req.end();
  });
}

async function runTests() {
  console.log("🚀 Testing Function 9 in different modes...\n");
  
  // Test 1: Test mode
  await testFunction9("Test Mode", { test_mode: true });
  
  // Test 2: Real parameters
  await testFunction9("Real Parameters", {
    destination_codes: ["HKG", "JFK"],
    start_time: "2024-04-01",
    end_time: "2025-05-31"
  });
  
  // Test 3: No auth (should still work with our test modes)
  await testFunction9("No Auth Test Mode", { test_mode: true }, false);
  
  console.log("\n✅ All tests completed!");
}

runTests().catch(console.error);
