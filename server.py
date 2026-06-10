# =============================================================================
# server.py
# Solar Panel Predictive Maintenance — Gemini AI Bridge Server
#
# How it works:
#   1. Polls Blynk cloud every 5 seconds for sensor data
#   2. Sends data to Gemini AI every 60 seconds for routine check
#   3. Sends data to Gemini immediately if values change significantly
#   4. Gemini decides if anything is wrong and what to do
#   5. Pushes Gemini diagnosis back to Blynk app
#   6. Saves everything to CSV
#
# Run with:
#   python server.py
# =============================================================================

import time
import csv
import os
import requests
import json
from datetime import datetime

# =============================================================================
# !! CHANGE THESE PLACEHOLDERS !!
# =============================================================================

BLYNK_AUTH_TOKEN = "bQZ1s1NAff6eb7FOWnWDUNTkNDzHq8gJ"    # <-- CHANGE THIS
GEMINI_API_KEY   = "AIzaSyAhOu_Eb5QMkUEOb-k9hB6-dop3oC0Cc3E"       # <-- CHANGE THIS

# =============================================================================
# Configuration
# =============================================================================

# Blynk cloud base URL
BLYNK_URL = "https://blynk.cloud/external/api"

# How often to read sensors from Blynk (seconds)
POLL_INTERVAL = 5

# How often to send routine check to Gemini (seconds)
GEMINI_ROUTINE_INTERVAL = 60

# How much a value must change to trigger immediate Gemini check
# Example: 2.0 means voltage must change by 2V to trigger
SIGNIFICANT_CHANGE = {
    "bus_voltage_V": 2.0,    # Volts
    "current_mA":    500.0,  # Milliamps
    "power_mW":      1000.0, # Milliwatts
    "temperature_C": 5.0,    # Celsius
    "lux":           5000.0, # Lux
}

# CSV file path
CSV_FILE = "solar_data.csv"

# Gemini API URL — using gemini-pro model
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-pro:generateContent?key={GEMINI_API_KEY}"
)

# =============================================================================
# CSV Setup
# =============================================================================

CSV_COLUMNS = [
    "timestamp",
    "bus_voltage_V",
    "current_mA",
    "power_mW",
    "temperature_C",
    "lux",
    "gemini_status",    # OK or ANOMALY
    "ai_diagnosis",     # Full Gemini response
]

def initialize_csv():
    """Create CSV with header row if file doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
        print(f"[CSV] Created: {CSV_FILE}")

def save_to_csv(row: dict):
    """Append one row to CSV."""
    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(row)

# =============================================================================
# Blynk Functions
# =============================================================================

def get_pin_value(pin: str) -> float:
    """Read one virtual pin value from Blynk cloud."""
    try:
        url = f"{BLYNK_URL}/get?token={BLYNK_AUTH_TOKEN}&{pin}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            value = response.json()
            return float(value[0]) if value else 0.0
    except Exception as e:
        print(f"[Blynk] Read error {pin}: {e}")
    return 0.0

def push_to_blynk(pin: str, value):
    """Push a value to Blynk virtual pin."""
    try:
        url = f"{BLYNK_URL}/update?token={BLYNK_AUTH_TOKEN}&{pin}={value}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"[Blynk] Pushed {pin} = {str(value)[:50]}")
        else:
            print(f"[Blynk] Push failed {pin}: {response.status_code}")
    except Exception as e:
        print(f"[Blynk] Push error {pin}: {e}")

def get_all_sensor_data() -> dict:
    """Read all sensor values from Blynk virtual pins."""
    print("[Blynk] Reading sensors...")
    data = {
        "bus_voltage_V": get_pin_value("v0"),
        "current_mA":    get_pin_value("v1"),
        "power_mW":      get_pin_value("v2"),
        "temperature_C": get_pin_value("v3"),
        "lux":           get_pin_value("v4"),
    }
    print(
        f"[Sensors] "
        f"V={data['bus_voltage_V']:.2f}V | "
        f"I={data['current_mA']:.1f}mA | "
        f"P={data['power_mW']:.1f}mW | "
        f"T={data['temperature_C']:.1f}C | "
        f"L={data['lux']:.0f}lux"
    )
    return data

# =============================================================================
# Change Detection
# Triggers immediate Gemini check if values shift significantly
# =============================================================================

def has_significant_change(current: dict, previous: dict) -> bool:
    """
    Returns True if any sensor value changed more than
    its defined threshold since the last Gemini check.
    """
    if not previous:
        return True  # First reading always triggers

    for key, threshold in SIGNIFICANT_CHANGE.items():
        current_val  = current.get(key, 0)
        previous_val = previous.get(key, 0)
        if abs(current_val - previous_val) >= threshold:
            print(
                f"[Change] {key} changed by "
                f"{abs(current_val - previous_val):.2f} "
                f"(threshold: {threshold})"
            )
            return True
    return False

# =============================================================================
# Gemini AI Analysis
# No thresholds — Gemini decides everything
# =============================================================================

def ask_gemini(data: dict) -> tuple:
    """
    Sends sensor data to Gemini.
    Gemini analyses based on its own solar panel knowledge.

    Returns:
        (status, diagnosis) where:
        status    = "OK" or "ANOMALY"
        diagnosis = full text response from Gemini
    """

    # This prompt tells Gemini to:
    # 1. Use its own knowledge of solar panel standards
    # 2. Analyse all values together as a system
    # 3. Respond in a strict short format for Blynk's 1024 limit
   prompt = f"""You are an expert solar panel diagnostics AI.
This is a MINI epoxy solar panel with these specs:
- Max voltage: 5.5V
- Max current: 120mA
- Max power: 0.65W

Analyse these real-time sensor readings:
Voltage : {data['bus_voltage_V']:.2f} V
Current : {data['current_mA']:.1f} mA
Power   : {data['power_mW']:.1f} mW
Temp    : {data['temperature_C']:.1f} C
Light   : {data['lux']:.0f} lux

Using your expert knowledge:
- Decide if readings are normal or anomalous
- Consider this is a small mini panel
- Apply solar panel physics and failure patterns

Reply ONLY in this exact format under 800 characters:
STATUS: [OK or ANOMALY]
CAUSE: [one line explanation]
FIX1: [first action]
FIX2: [second action]
FIX3: [third action]
URGENCY: [None/Low/Medium/High/Critical]"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        print("[Gemini] Sending data for analysis...")
        response = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=20
        )

        if response.status_code == 200:
            result     = response.json()
            diagnosis  = (result["candidates"][0]
                                ["content"]["parts"][0]["text"])

            # Trim to 900 chars to stay safely under Blynk 1024 limit
            diagnosis  = diagnosis.strip()[:900]

            # Extract status from first line
            first_line = diagnosis.split("\n")[0].upper()
            status     = "ANOMALY" if "ANOMALY" in first_line else "OK"

            print(f"[Gemini] Status: {status}")
            return status, diagnosis

        else:
            print(f"[Gemini] API error: {response.status_code}")
            return "ERROR", f"Gemini API error: {response.status_code}"

    except Exception as e:
        print(f"[Gemini] Request failed: {e}")
        return "ERROR", "AI diagnosis unavailable."

# =============================================================================
# Main Loop
# =============================================================================

def main():
    print("=" * 55)
    print("  Solar Panel Predictive Maintenance — AI Server")
    print("=" * 55)
    print(f"  Polling sensors : every {POLL_INTERVAL}s")
    print(f"  Gemini routine  : every {GEMINI_ROUTINE_INTERVAL}s")
    print(f"  CSV logging     : {CSV_FILE}")
    print("  Press Ctrl+C to stop.")
    print("=" * 55 + "\n")

    initialize_csv()

    # Track previous data for change detection
    previous_data       = {}

    # Track time of last Gemini call
    last_gemini_time    = 0

    while True:
        try:
            # --- Read all sensors from Blynk ---
            data = get_all_sensor_data()

            # Skip if ESP32 not connected yet (all zeros)
            if all(v == 0.0 for v in data.values()):
                print("[WARN] All zeros — waiting for ESP32...\n")
                time.sleep(POLL_INTERVAL)
                continue

            # --- Decide whether to call Gemini ---
            time_since_last = time.time() - last_gemini_time
            routine_due     = time_since_last >= GEMINI_ROUTINE_INTERVAL
            changed         = has_significant_change(data, previous_data)

            gemini_status  = "SKIPPED"
            ai_diagnosis   = "Waiting for next Gemini check..."

            if routine_due or changed:
                reason = "routine check" if routine_due else "significant change detected"
                print(f"[Gemini] Triggering analysis ({reason})...")

                gemini_status, ai_diagnosis = ask_gemini(data)
                last_gemini_time            = time.time()
                previous_data               = data.copy()

                # --- Push results to Blynk ---
                # V5 = alert status (short string)
                status_msg = (
                    "✓ System Normal"
                    if gemini_status == "OK"
                    else "⚠ Anomaly Detected"
                )
                push_to_blynk("v5", status_msg)

                # V6 = full AI diagnosis (Terminal widget)
                push_to_blynk("v6", ai_diagnosis)

            # --- Save to CSV ---
            row = {
                "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bus_voltage_V": data["bus_voltage_V"],
                "current_mA":    data["current_mA"],
                "power_mW":      data["power_mW"],
                "temperature_C": data["temperature_C"],
                "lux":           data["lux"],
                "gemini_status": gemini_status,
                "ai_diagnosis":  ai_diagnosis,
            }
            save_to_csv(row)
            print(f"[CSV] Row saved. Gemini: {gemini_status}\n")

        except KeyboardInterrupt:
            print("\n[Server] Stopped.")
            break
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")

        time.sleep(POLL_INTERVAL)

# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()