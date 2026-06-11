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

BLYNK_AUTH_TOKEN = "bQZ1s1NAff6eb7FOWnWDUNTkNDzHq8gJ"   # <-- PASTE YOUR BLYNK TOKEN
GEMINI_API_KEY   = "AQ.Ab8RN6L5WnNpX8ibNLcD4I49Zw3uQY6M8pVgN0lGt2zgB73uWw"      # <-- PASTE YOUR GEMINI KEY

# =============================================================================
# Configuration
# =============================================================================

BLYNK_URL                = "https://blynk.cloud/external/api"
POLL_INTERVAL            = 5    # seconds between sensor reads
GEMINI_ROUTINE_INTERVAL  = 60   # seconds between routine AI checks

SIGNIFICANT_CHANGE = {
    "bus_voltage_V": 2.0,
    "current_mA":    500.0,
    "power_mW":      1000.0,
    "temperature_C": 5.0,
    "lux":           5000.0,
}

CSV_FILE = "solar_data.csv"

# FIX: Use gemini-1.5-flash (gemini-pro is deprecated)
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
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
    "gemini_status",
    "ai_diagnosis",
]

def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
        print(f"[CSV] Created: {CSV_FILE}")

def save_to_csv(row: dict):
    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(row)

# =============================================================================
# Blynk Functions
# =============================================================================

def get_pin_value(pin: str) -> float:
    try:
        url      = f"{BLYNK_URL}/get?token={BLYNK_AUTH_TOKEN}&{pin}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            value = response.json()
            return float(value[0]) if value else 0.0
    except Exception as e:
        print(f"[Blynk] Read error {pin}: {e}")
    return 0.0

def push_to_blynk(pin: str, value):
    try:
        url      = f"{BLYNK_URL}/update?token={BLYNK_AUTH_TOKEN}&{pin}={value}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"[Blynk] Pushed {pin} = {str(value)[:60]}")
        else:
            print(f"[Blynk] Push failed {pin}: {response.status_code}")
    except Exception as e:
        print(f"[Blynk] Push error {pin}: {e}")

def get_all_sensor_data() -> dict:
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
# =============================================================================

def has_significant_change(current: dict, previous: dict) -> bool:
    if not previous:
        return True
    for key, threshold in SIGNIFICANT_CHANGE.items():
        curr_val = current.get(key, 0)
        prev_val = previous.get(key, 0)
        if abs(curr_val - prev_val) >= threshold:
            print(
                f"[Change] {key} changed by "
                f"{abs(curr_val - prev_val):.2f} "
                f"(threshold: {threshold})"
            )
            return True
    return False

# =============================================================================
# Gemini AI Analysis
# =============================================================================

def ask_gemini(data: dict) -> tuple:
    # FIX: Correct indentation — prompt must be flush with function body
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
            result    = response.json()
            diagnosis = (result["candidates"][0]
                               ["content"]["parts"][0]["text"])
            diagnosis = diagnosis.strip()[:900]

            first_line = diagnosis.split("\n")[0].upper()
            status     = "ANOMALY" if "ANOMALY" in first_line else "OK"

            print(f"[Gemini] Status: {status}")
            return status, diagnosis

        else:
            print(f"[Gemini] API error: {response.status_code} — {response.text[:200]}")
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

    previous_data    = {}
    last_gemini_time = 0

    while True:
        try:
            data = get_all_sensor_data()

            if all(v == 0.0 for v in data.values()):
                print("[WARN] All zeros — waiting for ESP32...\n")
                time.sleep(POLL_INTERVAL)
                continue

            time_since_last = time.time() - last_gemini_time
            routine_due     = time_since_last >= GEMINI_ROUTINE_INTERVAL
            changed         = has_significant_change(data, previous_data)

            gemini_status = "SKIPPED"
            ai_diagnosis  = "Waiting for next Gemini check..."

            if routine_due or changed:
                reason = "routine check" if routine_due else "significant change"
                print(f"[Gemini] Triggering analysis ({reason})...")

                gemini_status, ai_diagnosis = ask_gemini(data)
                last_gemini_time            = time.time()
                previous_data               = data.copy()

                status_msg = (
                    "✓ System Normal"
                    if gemini_status == "OK"
                    else "⚠ Anomaly Detected"
                )
                push_to_blynk("v5", status_msg)
                push_to_blynk("v6", ai_diagnosis)

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