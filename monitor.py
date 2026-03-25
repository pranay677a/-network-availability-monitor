import subprocess
import platform
import csv
import re
from datetime import datetime
from pathlib import Path

DEVICES_FILE = "devices.txt"
RESULTS_FILE = "results.csv"
LATENCY_THRESHOLD_MS = 100

def load_devices(filename: str) -> list[str]:
    path = Path(filename)
    if not path.exists():
        print(f"Device list file not found: {filename}")
        return []
    with path.open("r", encoding="utf-8") as f:
        devices = [line.strip() for line in f if line.strip()]
    return devices

def ping_device(device: str) -> dict:
    system = platform.system().lower()

    if system == "windows":
        command = ["ping", "-n", "4", "-w", "1000", device]
    else:
        command = ["ping", "-c", "4", "-W", "1", device]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout + result.stderr
        return parse_ping_output(device, output, result.returncode)
    except subprocess.TimeoutExpired:
        return {
            "device": device,
            "status": "DOWN",
            "latency_ms": None,
            "packet_loss_percent": 100,
            "alert": "Ping timed out"
        }
    except Exception as e:
        return {
            "device": device,
            "status": "DOWN",
            "latency_ms": None,
            "packet_loss_percent": 100,
            "alert": f"Error: {e}"
        }

def parse_ping_output(device: str, output: str, returncode: int) -> dict:
    latency = None
    packet_loss = None
    status = "UP" if returncode == 0 else "DOWN"
    alert_messages = []

    # Windows latency parsing
    win_latency_match = re.search(r"Average = (\d+)ms", output)
    # Linux/macOS latency parsing
    unix_latency_match = re.search(r"=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms", output)

    if win_latency_match:
        latency = float(win_latency_match.group(1))
    elif unix_latency_match:
        latency = float(unix_latency_match.group(1))

    # Windows packet loss parsing
    win_loss_match = re.search(r"(\d+)% loss", output)
    # Linux/macOS packet loss parsing
    unix_loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)

    if win_loss_match:
        packet_loss = float(win_loss_match.group(1))
    elif unix_loss_match:
        packet_loss = float(unix_loss_match.group(1))

    if packet_loss is None:
        packet_loss = 100.0 if status == "DOWN" else 0.0

    if latency is not None and latency > LATENCY_THRESHOLD_MS:
        alert_messages.append(f"High latency: {latency} ms")

    if packet_loss > 0:
        alert_messages.append(f"Packet loss: {packet_loss}%")

    if status == "DOWN":
        alert_messages.append("Device unreachable")

    return {
        "device": device,
        "status": status,
        "latency_ms": latency,
        "packet_loss_percent": packet_loss,
        "alert": "; ".join(alert_messages) if alert_messages else "OK"
    }

def write_results(filename: str, rows: list[dict]) -> None:
    file_exists = Path(filename).exists()
    with open(filename, "a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp",
            "device",
            "status",
            "latency_ms",
            "packet_loss_percent",
            "alert"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for row in rows:
            writer.writerow(row)

def main() -> None:
    devices = load_devices(DEVICES_FILE)
    if not devices:
        print("No devices found in devices.txt")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    print(f"\nNetwork Monitoring Run - {timestamp}")
    print("-" * 60)

    for device in devices:
        result = ping_device(device)
        row = {
            "timestamp": timestamp,
            **result
        }
        results.append(row)

        print(
            f"Device: {result['device']:<20} "
            f"Status: {result['status']:<5} "
            f"Latency: {str(result['latency_ms']):<8} "
            f"Loss: {result['packet_loss_percent']}% "
            f"Alert: {result['alert']}"
        )

    write_results(RESULTS_FILE, results)
    print("\nResults saved to results.csv")

if __name__ == "__main__":
    main()
