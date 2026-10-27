"""Simple EPICS-controlled exposure/gain scan using saved JPEG images."""

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import epics
import numpy as np
from PIL import Image

# Camera PVs
PV_STATUS = epics.PV("CAM:GetStatus")
PV_CAMERA_COMMAND = epics.PV("CAM:CameraCommand")
PV_SET_AUTO_EXPOSURE = epics.PV("CAM:SetAutoExposure")
PV_GET_AUTO_EXPOSURE = epics.PV("CAM:GetAutoExposure")
PV_SCAN_SET_EXPOSURE = epics.PV("CAM:ScanSetExposure")
PV_SCAN_SET_GAIN = epics.PV("CAM:ScanSetGain")
PV_EXPOSURE_RB = epics.PV("CAM:ExposureRB")
PV_GAIN_RB = epics.PV("CAM:GainRB")
PV_IMAGE_PATH = epics.PV("CAM:GetLatestImagePath")
PV_METADATA_PATH = epics.PV("CAM:GetLatestMetadataPath")

# Scan configuration and commands
PV_SCAN_ENABLE = epics.PV("CAM:ScanEnable")
PV_SCAN_TYPE = epics.PV("CAM:ScanType")
PV_SCAN_START_EXPOSURE = epics.PV("CAM:ScanStartExposure")
PV_SCAN_END_EXPOSURE = epics.PV("CAM:ScanEndExposure")
PV_SCAN_START_GAIN = epics.PV("CAM:ScanStartGain")
PV_SCAN_END_GAIN = epics.PV("CAM:ScanEndGain")
PV_SCAN_POINTS = epics.PV("CAM:ScanPoints")
PV_START_SCAN = epics.PV("CAM:StartScan")
PV_STOP_SCAN = epics.PV("CAM:StopScan")

# Scan results
PV_SCAN_STATUS = epics.PV("CAM:ScanStatus")
PV_SCAN_PROGRESS = epics.PV("CAM:ScanProgress")
PV_SCAN_MEAN_INTENSITY = epics.PV("CAM:ScanMeanIntensity")
PV_SCAN_EXPOSURE = epics.PV("CAM:ScanExposure")
PV_SCAN_GAIN = epics.PV("CAM:ScanGain")
PV_SCAN_INTENSITY = epics.PV("CAM:ScanIntensity")

TIMEOUT = 10.0
POLL_INTERVAL = 0.05
MAX_SCAN_POINTS = 100
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "scan"


def put(pv, value):
    """Write a PV, reporting a failed Channel Access put."""
    if pv.put(value, wait=True, timeout=TIMEOUT) != 1:
        raise RuntimeError(f"Cannot write {pv.pvname}")


def wait_for_readback(pv, expected, tolerance=0):
    start = time.monotonic()
    while time.monotonic() - start < TIMEOUT:
        if PV_STOP_SCAN.get() == 1 or PV_SCAN_ENABLE.get() != 1:
            raise InterruptedError("Scan stopped or disabled")
        value = pv.get()
        if value is not None and abs(float(value) - expected) <= tolerance:
            return value
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"{pv.pvname} did not reach {expected}")


def wait_for_new_image(previous_path):
    """Wait for a new image path and its matching metadata path."""
    start = time.monotonic()
    while time.monotonic() - start < TIMEOUT:
        if PV_STOP_SCAN.get() == 1 or PV_SCAN_ENABLE.get() != 1:
            raise InterruptedError("Scan stopped or disabled")
        image_path = PV_IMAGE_PATH.get(as_string=True)
        if image_path and image_path not in ("NONE", previous_path):
            expected_metadata = image_path.removesuffix(".jpg") + "_metadata.json"
            while time.monotonic() - start < TIMEOUT:
                if PV_STOP_SCAN.get() == 1 or PV_SCAN_ENABLE.get() != 1:
                    raise InterruptedError("Scan stopped or disabled")
                metadata_path = PV_METADATA_PATH.get(as_string=True)
                if metadata_path == expected_metadata:
                    return image_path, metadata_path
                time.sleep(POLL_INTERVAL)
            raise TimeoutError("Matching metadata path not received")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("No new image path received")


def acquire_image():
    previous_path = PV_IMAGE_PATH.get(as_string=True)
    put(PV_CAMERA_COMMAND, "Acquire")
    return wait_for_new_image(previous_path)


def measure_image(image_path, metadata_path, scan_type):
    """Return actual frame setting and mean grayscale JPEG intensity."""
    with open(metadata_path, encoding="utf-8") as file:
        metadata = json.load(file)
    key = "ExposureTime" if scan_type == "Exposure" else "AnalogueGain"
    actual_value = metadata.get(key)
    if actual_value is None:
        raise ValueError(f"{key} missing from frame metadata")
    with Image.open(image_path) as image:
        intensity = float(np.asarray(image.convert("L"), dtype=np.float64).mean())
    return float(actual_value), intensity


def scan_settings():
    """Read and validate the scan parameters from EPICS."""
    scan_type = PV_SCAN_TYPE.get(as_string=True)
    if scan_type not in ("Exposure", "Gain"):
        raise ValueError(f"Invalid scan type: {scan_type}")
    points = PV_SCAN_POINTS.get()
    if points is None or not 1 <= int(points) <= MAX_SCAN_POINTS:
        raise ValueError("ScanPoints must be between 1 and 100")
    points = int(points)
    if scan_type == "Exposure":
        start = PV_SCAN_START_EXPOSURE.get()
        end = PV_SCAN_END_EXPOSURE.get()
    else:
        start = PV_SCAN_START_GAIN.get()
        end = PV_SCAN_END_GAIN.get()
    if start is None or end is None or not np.isfinite([start, end]).all():
        raise ValueError("Scan range is unavailable or invalid")
    if min(start, end) <= 0:
        raise ValueError("Scan values must be positive")
    values = np.linspace(start, end, points)
    if scan_type == "Exposure":
        values = np.rint(values).astype(int).tolist()
        if len(set(values)) != len(values):
            raise ValueError("Exposure scan contains repeated integer values")
    else:
        values = values.tolist()
    return scan_type, values


def publish_arrays(scan_type, x_values, intensities):
    """Publish only completed measurement points."""
    x_pv = PV_SCAN_EXPOSURE if scan_type == "Exposure" else PV_SCAN_GAIN
    put(x_pv, np.asarray(x_values, dtype=np.float64))
    put(PV_SCAN_INTENSITY, np.asarray(intensities, dtype=np.float64))


def run_scan():
    if PV_SCAN_ENABLE.get() != 1:
        print("Enable scan mode first")
        return
    try:
        if PV_GET_AUTO_EXPOSURE.get() != 0:
            put(PV_SET_AUTO_EXPOSURE, 0)
            wait_for_readback(PV_GET_AUTO_EXPOSURE, 0)
        scan_type, values = scan_settings()
        x_pv = PV_SCAN_SET_EXPOSURE if scan_type == "Exposure" else PV_SCAN_SET_GAIN
        rb_pv = PV_EXPOSURE_RB if scan_type == "Exposure" else PV_GAIN_RB
        tolerance = 0 if scan_type == "Exposure" else 0.001

        # Replace the previous scan's plot with a single non-plottable point.
        # New measurements replace this placeholder with real arrays.
        put(PV_SCAN_EXPOSURE, np.array([np.nan]))
        put(PV_SCAN_GAIN, np.array([np.nan]))
        put(PV_SCAN_INTENSITY, np.array([np.nan]))
        put(PV_SCAN_PROGRESS, 0)
        put(PV_SCAN_MEAN_INTENSITY, 0)
        put(PV_SCAN_STATUS, "RUNNING")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = OUTPUT_DIR / f"{scan_type.lower()}_scan_{stamp}.csv"
        x_values, intensities = [], []
        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=[
                "scan_type", "requested_value", "requested_readback",
                "actual_value", "mean_intensity", "image_path", "metadata_path"
            ])
            writer.writeheader()
            for requested in values:
                if PV_STOP_SCAN.get() == 1 or PV_SCAN_ENABLE.get() != 1:
                    raise InterruptedError("Scan stopped or disabled")
                put(x_pv, requested)
                readback = wait_for_readback(rb_pv, requested, tolerance)
                image_path, metadata_path = acquire_image()
                actual, intensity = measure_image(image_path, metadata_path, scan_type)
                x_values.append(actual)
                intensities.append(intensity)
                writer.writerow({
                    "scan_type": scan_type, "requested_value": requested,
                    "requested_readback": readback, "actual_value": actual,
                    "mean_intensity": intensity, "image_path": image_path,
                    "metadata_path": metadata_path
                })
                file.flush()
                publish_arrays(scan_type, x_values, intensities)
                put(PV_SCAN_MEAN_INTENSITY, intensity)
                put(PV_SCAN_PROGRESS, len(x_values))
                print(f"{len(x_values)}/{len(values)}: {actual:g} -> {intensity:.3f}")
        put(PV_SCAN_STATUS, "COMPLETED")
        print(f"Scan completed. CSV: {csv_path}")
    except InterruptedError as error:
        print(error)
        put(PV_SCAN_STATUS, "STOPPED")
    except Exception as error:
        print(f"Scan failed: {error}")
        put(PV_SCAN_STATUS, "ERROR")


def main():
    if not PV_STATUS.wait_for_connection(timeout=TIMEOUT):
        raise ConnectionError("Cannot connect to EPICS IOC")
    print("Camera scan ready. Enable scan mode, then press Start Scan.")
    last_enable = None
    # Clear stale command requests when this program starts.
    put(PV_START_SCAN, 0)
    put(PV_STOP_SCAN, 0)
    put(PV_SCAN_STATUS, "IDLE")
    while True:
        enabled = PV_SCAN_ENABLE.get()
        if enabled == 1 and last_enable != 1:
            try:
                put(PV_SET_AUTO_EXPOSURE, 0)
                print("Automatic exposure disabled for scan mode")
            except Exception as error:
                print(f"Could not disable automatic exposure: {error}")
        last_enable = enabled
        if PV_START_SCAN.get() == 1:
            put(PV_START_SCAN, 0)  # Acknowledge immediately
            if enabled == 1:
                put(PV_STOP_SCAN, 0)
                run_scan()
            else:
                print("Scan is not enabled")
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Camera scan program stopped")
