// =============================================================================
// esp32_solar_sensors.ino
// Solar Panel Predictive Maintenance — ESP32 Firmware
//
// How it works:
//   1. Connects to WiFi
//   2. Connects to Blynk cloud
//   3. Reads INA219, DHT22, BH1750 every 5 seconds
//   4. Pushes all values to Blynk virtual pins
//   5. server.py on PC reads from Blynk + calls Gemini
//
// Virtual Pin Map:
//   V0 = Voltage (V)
//   V1 = Current (mA)
//   V2 = Power (mW)
//   V3 = Temperature (C)
//   V4 = Lux
//   V5 = Alert Status (pushed by server.py)
//   V6 = AI Diagnosis (pushed by server.py)
// =============================================================================

// --- Blynk Config (must be BEFORE Blynk include) ---
#define BLYNK_TEMPLATE_ID   "TMPL30u4QrUA"    // <-- CHANGE THIS
#define BLYNK_TEMPLATE_NAME "Solar Panel Monitor"  // <-- CHANGE THIS
#define BLYNK_AUTH_TOKEN    "bQZ1s1NAff6eb7FOWnWDUNTkNDzHq8gJ"      // <-- CHANGE THIS
#define BLYNK_PRINT Serial  // Print Blynk logs to Serial Monitor

// --- Core Libraries ---
#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>

// --- Sensor Libraries ---
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <DHT.h>
#include <BH1750.h>

// =============================================================================s
// !! CHANGE THESE PLACEHOLDERS !!
// =============================================================================

// Your WiFi credentials
const char* WIFI_SSID     = "LAPTOP-K8GAL522 1368";      // <-- CHANGE THIS
const char* WIFI_PASSWORD = "144jY1(7";  // <-- CHANGE THIS

// =============================================================================
// Pin Definitions
// =============================================================================

#define DHT_PIN  4       // GPIO4 → DHT22 DATA pin
#define DHT_TYPE DHT22   // Sensor type

// =============================================================================
// Sensor Objects
// =============================================================================

Adafruit_INA219 ina219;   // I2C address 0x40
BH1750 lightMeter;         // I2C address 0x23
DHT dht(DHT_PIN, DHT_TYPE);

// =============================================================================
// Blynk Timer
// Used to send data every 5 seconds without blocking
// =============================================================================

BlynkTimer timer;

// =============================================================================
// readAndSendSensors()
// Called by Blynk timer every 5 seconds
// Reads all 3 sensors and pushes to Blynk virtual pins
// =============================================================================

void readAndSendSensors() {
  Serial.println("\n---- Reading Sensors ----");

  // --- INA219: Voltage, Current, Power ---
  float voltage = ina219.getBusVoltage_V();
  float current = ina219.getCurrent_mA();
  float power   = ina219.getPower_mW();

  // Warn if all zeros (likely wiring issue)
  if (voltage == 0.0 && current == 0.0) {
    Serial.println("[WARN] INA219 reading all zeros.");
    Serial.println("       Check VIN+/VIN- wiring.");
  }

  // --- BH1750: Light intensity ---
  float lux = lightMeter.readLightLevel();
  if (lux < 0) {
    Serial.println("[WARN] BH1750 read error.");
    lux = 0.0;
  }

  // --- DHT22: Temperature ---
  float temperature = dht.readTemperature();
  if (isnan(temperature)) {
    Serial.println("[WARN] DHT22 read failed.");
    temperature = 0.0;
  }

  // --- Print to Serial Monitor ---
  Serial.printf("  Voltage    : %.3f V\n",   voltage);
  Serial.printf("  Current    : %.2f mA\n",  current);
  Serial.printf("  Power      : %.2f mW\n",  power);
  Serial.printf("  Temperature: %.1f C\n",   temperature);
  Serial.printf("  Light      : %.1f lux\n", lux);
  Serial.println("-------------------------");

  // --- Push all values to Blynk virtual pins ---
  Blynk.virtualWrite(V0, voltage);
  Blynk.virtualWrite(V1, current);
  Blynk.virtualWrite(V2, power);
  Blynk.virtualWrite(V3, temperature);
  Blynk.virtualWrite(V4, lux);

  Serial.println("[Blynk] Data pushed to V0-V4.");
}

// =============================================================================
// setup()
// Runs once on power on
// =============================================================================

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Solar Panel Monitor Starting ===");

  // --- Initialize I2C ---
  Wire.begin(); // SDA=21, SCL=22 by default on ESP32

  // --- Initialize INA219 ---
  if (!ina219.begin()) {
    Serial.println("[ERROR] INA219 not found!");
    Serial.println("        Check SDA/SCL wiring.");
    while (true) { delay(1000); }
  }
  Serial.println("[OK] INA219 ready.");

  // --- Initialize BH1750 ---
  if (!lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("[ERROR] BH1750 not found!");
    Serial.println("        Check SDA/SCL wiring.");
    while (true) { delay(1000); }
  }
  Serial.println("[OK] BH1750 ready.");

  // --- Initialize DHT22 ---
  dht.begin();
  Serial.println("[OK] DHT22 ready.");

  // --- Connect to Blynk (handles WiFi internally) ---
  Serial.println("[WiFi] Connecting to Blynk...");
  Blynk.begin(
    BLYNK_AUTH_TOKEN,
    WIFI_SSID,
    WIFI_PASSWORD,
    "blynk.cloud",
    80
  );
  Serial.println("[OK] Blynk connected!");

  // --- Set timer to read sensors every 5 seconds ---
  // 5000 ms = 5 seconds
  timer.setInterval(5000L, readAndSendSensors);
  Serial.println("[OK] Timer set. Sending data every 5 seconds.");
  Serial.println("=== Setup Complete ===\n");
}

// =============================================================================
// loop()
// Keeps Blynk connection alive and runs the timer
// =============================================================================

void loop() {
  Blynk.run();  // Maintains Blynk connection
  timer.run();  // Fires readAndSendSensors() every 5 seconds
}