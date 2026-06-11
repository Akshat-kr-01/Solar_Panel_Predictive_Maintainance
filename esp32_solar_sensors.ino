// =============================================================================
// esp32_solar_sensors.ino
// Solar Panel Predictive Maintenance — ESP32 Firmware
// =============================================================================
//
// WHAT THIS CODE DOES:
//   Every 5 seconds it reads 3 sensors:
//     - INA219  → measures solar panel voltage, current, power
//     - DHT22   → measures air temperature near the panel
//     - BH1750  → measures light intensity (lux)
//   Then sends all 5 values to your Blynk dashboard over WiFi.
//   Your server.py reads them from Blynk and calls Gemini AI.
//
// VIRTUAL PIN MAP (must match your Blynk dashboard):
//   V0 = Bus Voltage  (V)
//   V1 = Current      (mA)
//   V2 = Power        (mW)
//   V3 = Temperature  (C)
//   V4 = Light        (lux)
//   V5 = System Status    <-- server.py writes this
//   V6 = AI Diagnosis     <-- server.py writes this
//
// HARDWARE PINS USED:
//   GPIO21 = SDA  (I2C data  — shared by INA219 and BH1750)
//   GPIO22 = SCL  (I2C clock — shared by INA219 and BH1750)
//   GPIO4  = DATA (DHT22 temperature sensor)
//   Micro-USB = power from laptop + code upload
//
// =============================================================================
// STEP 1 — FILL IN YOUR 3 CREDENTIALS BELOW BEFORE UPLOADING
// =============================================================================

// Your Blynk Template ID — already correct from your dashboard
#define BLYNK_TEMPLATE_ID    "TMPL30u4QrUA"

// Your Blynk Template Name — must match exactly what you named it
#define BLYNK_TEMPLATE_NAME  "Solar Panel Monitor"

// Your Blynk Device Auth Token
// Find it: Blynk dashboard → Devices → Solar Panel 1 → Auth Token (click copy)
#define BLYNK_AUTH_TOKEN     "bQZ1s1NAff6eb7FOWnWDUNTkNDzHq8gJ"

// Print Blynk connection logs to Serial Monitor (helpful for debugging)
#define BLYNK_PRINT Serial

// =============================================================================
// LIBRARIES — must all be installed in Arduino IDE
// Install via: Tools → Manage Libraries → search each name
//   - Blynk              (by Volodymyr Shymanskyy) v1.3.5
//   - Adafruit INA219    (by Adafruit)
//   - DHT sensor library (by Adafruit)
//   - Adafruit Unified Sensor (by Adafruit) — needed by DHT
//   - BH1750             (by Christopher Laws)
// =============================================================================

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <DHT.h>
#include <BH1750.h>

// =============================================================================
// STEP 2 — FILL IN YOUR WIFI CREDENTIALS
// IMPORTANT: ESP32 only works on 2.4 GHz WiFi — NOT 5 GHz
// You can use: home WiFi, mobile hotspot, or laptop hotspot
// =============================================================================

const char* WIFI_SSID     = "LAPTOP-K8GAL522 1368";  // <-- your WiFi name
const char* WIFI_PASSWORD = "144jY1(7";              // <-- your WiFi password

// =============================================================================
// PIN DEFINITIONS
// =============================================================================

#define DHT_PIN  4      // GPIO4  → connects to DHT22 DATA pin
#define DHT_TYPE DHT22  // we are using the DHT22 model (not DHT11)

// =============================================================================
// SENSOR OBJECTS
// These create the software handles to talk to each sensor chip
// =============================================================================

Adafruit_INA219 ina219;    // INA219 at I2C address 0x40 (default, no soldering needed)
BH1750          lightMeter; // BH1750 at I2C address 0x23 (ADDR pin connected to GND)
DHT             dht(DHT_PIN, DHT_TYPE); // DHT22 on GPIO4

// =============================================================================
// BLYNK TIMER
// Used to call readAndSendSensors() every 5 seconds without blocking the loop
// =============================================================================

BlynkTimer timer;

// =============================================================================
// readAndSendSensors()
// This function runs automatically every 5 seconds (set up in setup() below)
// It reads all 3 sensors and pushes the data to Blynk virtual pins V0–V4
// =============================================================================

void readAndSendSensors() {

  Serial.println("\n-------- Reading Sensors --------");

  // ------------------------------------------------------------------
  // INA219 — reads voltage, current, power from the solar panel
  // The solar panel wires go into the INA219 screw terminal
  // ------------------------------------------------------------------
  float voltage = ina219.getBusVoltage_V();   // volts
  float current = ina219.getCurrent_mA();     // milliamps
  float power   = ina219.getPower_mW();       // milliwatts

  // INA219 sometimes reads tiny negative values at zero current — clamp to 0
  if (current < 0.0) current = 0.0;
  if (power   < 0.0) power   = 0.0;

  // Warn in Serial Monitor if INA219 reads all zeros (likely a wiring issue)
  if (voltage == 0.0 && current == 0.0) {
    Serial.println("[WARN] INA219 reads zero — check VIN+ and VIN- screw terminal wiring.");
  }

  // ------------------------------------------------------------------
  // BH1750 — reads light intensity in lux
  // Higher lux = brighter light = more solar energy available
  // ------------------------------------------------------------------
  float lux = lightMeter.readLightLevel();

  // If BH1750 returns a negative number, something went wrong — set to 0
  if (lux < 0.0) {
    Serial.println("[WARN] BH1750 read error — check SDA/SCL wiring.");
    lux = 0.0;
  }

  // ------------------------------------------------------------------
  // DHT22 — reads temperature in Celsius
  // Place this sensor near (but not touching) the solar panel
  // ------------------------------------------------------------------
  float temperature = dht.readTemperature(); // Celsius

  // DHT22 returns NaN (not a number) if read fails
  if (isnan(temperature)) {
    Serial.println("[WARN] DHT22 read failed — check DATA pin on GPIO4.");
    temperature = 0.0;
  }

  // ------------------------------------------------------------------
  // Print all readings to Serial Monitor (visible in Arduino IDE)
  // Open: Tools → Serial Monitor, set baud to 115200
  // ------------------------------------------------------------------
  Serial.printf("  Voltage     : %.3f V\n",   voltage);
  Serial.printf("  Current     : %.2f mA\n",  current);
  Serial.printf("  Power       : %.2f mW\n",  power);
  Serial.printf("  Temperature : %.1f C\n",   temperature);
  Serial.printf("  Light       : %.1f lux\n", lux);
  Serial.println("---------------------------------");

  // ------------------------------------------------------------------
  // Push all 5 values to Blynk virtual pins
  // These appear instantly on your Blynk dashboard gauges
  // ------------------------------------------------------------------
  Blynk.virtualWrite(V0, voltage);
  Blynk.virtualWrite(V1, current);
  Blynk.virtualWrite(V2, power);
  Blynk.virtualWrite(V3, temperature);
  Blynk.virtualWrite(V4, lux);

  Serial.println("[Blynk] Sent V0=voltage V1=current V2=power V3=temp V4=lux");
}

// =============================================================================
// setup()
// Runs ONCE when ESP32 powers on or after pressing the RST button
// Initialises all sensors, connects WiFi + Blynk, starts the 5-second timer
// =============================================================================

void setup() {

  // Start Serial so we can see log messages in Arduino IDE Serial Monitor
  Serial.begin(115200);
  delay(500); // short pause so Serial port is ready before first message

  Serial.println("\n========================================");
  Serial.println("   Solar Panel Monitor — Starting...");
  Serial.println("========================================");

  // ------------------------------------------------------------------
  // Start I2C bus
  // SDA = GPIO21 (data wire)
  // SCL = GPIO22 (clock wire)
  // Both INA219 and BH1750 share these same two wires
  // ------------------------------------------------------------------
  Wire.begin(21, 22);
  Serial.println("[I2C] Bus started on SDA=21, SCL=22");

  // ------------------------------------------------------------------
  // Initialise INA219
  // If wiring is correct this passes instantly
  // If it fails, the program stops here and prints an error
  // ------------------------------------------------------------------
  if (!ina219.begin()) {
    Serial.println("[ERROR] INA219 not found!");
    Serial.println("        Check: VCC→3V3, GND→GND, SDA→G21, SCL→G22");
    while (true) { delay(1000); } // stop here — fix wiring then reset ESP32
  }
  Serial.println("[OK] INA219 ready.");

  // ------------------------------------------------------------------
  // Initialise BH1750 in high-resolution continuous mode
  // This gives 1-lux resolution and updates automatically
  // ------------------------------------------------------------------
  if (!lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("[ERROR] BH1750 not found!");
    Serial.println("        Check: VCC→3V3, GND→GND, SDA→G21, SCL→G22, ADDR→GND");
    while (true) { delay(1000); } // stop here — fix wiring then reset ESP32
  }
  Serial.println("[OK] BH1750 ready.");

  // ------------------------------------------------------------------
  // Initialise DHT22
  // No begin() return value to check — it always returns true
  // We find out if it's wired correctly on the first read
  // ------------------------------------------------------------------
  dht.begin();
  delay(2000); // DHT22 needs 2 full seconds after power-on to stabilise
  Serial.println("[OK] DHT22 ready.");

  // ------------------------------------------------------------------
  // Connect to WiFi and Blynk cloud
  // Blynk.begin() handles both WiFi connection and Blynk handshake
  // It will keep retrying until it connects — be patient (~10 seconds)
  // ------------------------------------------------------------------
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(WIFI_SSID);
  Serial.println("       (this may take up to 15 seconds...)");

  Blynk.begin(
    BLYNK_AUTH_TOKEN,  // your device token
    WIFI_SSID,         // WiFi name
    WIFI_PASSWORD,     // WiFi password
    "blynk.cloud",     // Blynk server
    80                 // port
  );

  Serial.println("[OK] Blynk connected! Dashboard should show Online.");

  // ------------------------------------------------------------------
  // Set up the repeating timer
  // Every 5000 milliseconds (= 5 seconds), call readAndSendSensors()
  // ------------------------------------------------------------------
  timer.setInterval(5000L, readAndSendSensors);
  Serial.println("[OK] Timer set — reading sensors every 5 seconds.");

  Serial.println("========================================");
  Serial.println("   Setup complete. System running.");
  Serial.println("========================================\n");
}

// =============================================================================
// loop()
// Runs FOREVER after setup() finishes
// Just two lines — do not add delays or blocking code here
// =============================================================================

void loop() {
  Blynk.run(); // keeps WiFi + Blynk connection alive, handles reconnects
  timer.run(); // checks if 5 seconds have passed and fires readAndSendSensors()
}
