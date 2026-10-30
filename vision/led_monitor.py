
"""EPICS-controlled camera-based RGB LED status monitoring."""

import json
import time
from pathlib import Path

import epics
import numpy as np
from PIL import Image


# Monitoring configuration
ACQUISITION_INTERVAL = 3.0
ACQUISITION_TIMEOUT = 10.0
POLL_INTERVAL = 0.1
SCAN_WAIT_INTERVAL = 0.5
AUTO_EXPOSURE_TIMEOUT = 5.0


# EPICS process variables
PV_VISION_ENABLE = epics.PV("CAM:VisionEnable")
PV_VISION_STATUS = epics.PV("CAM:VisionStatus")
PV_LED_STATUS = epics.PV("CAM:LEDStatus")

PV_SCAN_ENABLE = epics.PV("CAM:ScanEnable")
PV_SCAN_STATUS = epics.PV("CAM:ScanStatus")
PV_START_SCAN = epics.PV("CAM:StartScan")

PV_CAMERA_COMMAND = epics.PV("CAM:CameraCommand")
PV_IMAGE_PATH = epics.PV("CAM:GetLatestImagePath")
PV_METADATA_PATH = epics.PV("CAM:GetLatestMetadataPath")

PV_SET_AUTO_EXPOSURE = epics.PV("CAM:SetAutoExposure")
PV_GET_AUTO_EXPOSURE = epics.PV("CAM:GetAutoExposure")

PV_RED_GREEN_RATIO = epics.PV("CAM:LEDRedGreenRatio")
PV_YELLOW_FRACTION = epics.PV("CAM:LEDYellowFraction")


# LED status values
UNKNOWN = 0
NORMAL = 1
WARNING = 2
FAULT = 3

# Vision program status values
IDLE = 0
RUNNING = 1
ERROR = 2
WAITING = 3

# Scan status values
SCAN_RUNNING = 1


def put(pv, value):
    """Write an EPICS PV and check the write result."""

    result = pv.put(value, wait=True, timeout=5)

    if result != 1:
        raise RuntimeError(f"Failed to write {pv.pvname}")


def get(pv, as_string=False):
    """Read an EPICS PV and check that a value was returned."""

    value = pv.get(as_string=as_string, timeout=5)

    if value is None:
        raise RuntimeError(f"Failed to read {pv.pvname}")

    return value


def set_vision_state(state):
    """Update the vision monitoring program state."""

    put(PV_VISION_STATUS, state)


def set_led_unknown():
    """Invalidate the previous LED classification."""

    put(PV_LED_STATUS, UNKNOWN)


def vision_requested():
    """Return True when vision monitoring is enabled."""

    return get(PV_VISION_ENABLE) == 1


def wait_for_scan():
    """Wait for an active scan, then disable scan mode."""

    if get(PV_SCAN_ENABLE) != 1:
        return

    set_vision_state(WAITING)
    set_led_unknown()

    print("Scan mode enabled. Checking scan status...")

    while True:

        if not vision_requested():
            raise InterruptedError("Vision monitoring cancelled")

        scan_status = get(PV_SCAN_STATUS)

        if scan_status == SCAN_RUNNING:
            time.sleep(SCAN_WAIT_INTERVAL)
            continue

        if get(PV_START_SCAN) == 1:
            print("Waiting for pending scan request...")
            time.sleep(SCAN_WAIT_INTERVAL)
            continue

        # Recheck before disabling scan mode
        if get(PV_SCAN_STATUS) == SCAN_RUNNING:
            continue

        print("No active scan. Disabling scan mode...")

        put(PV_SCAN_ENABLE, 0)

        if get(PV_SCAN_ENABLE) != 0:
            raise RuntimeError("Failed to disable scan mode")

        if get(PV_SCAN_STATUS) == SCAN_RUNNING:
            raise RuntimeError("Scan started during vision handover")

        print("Scan mode disabled.")
        return


def enable_auto_exposure():
    """Enable automatic exposure before LED monitoring begins."""

    if not vision_requested():
        raise InterruptedError("Vision monitoring cancelled")

    if get(PV_GET_AUTO_EXPOSURE) == 1:
        print("Automatic exposure already enabled")
        return

    print("Enabling automatic exposure...")

    put(PV_SET_AUTO_EXPOSURE, 1)

    start = time.monotonic()

    while time.monotonic() - start < AUTO_EXPOSURE_TIMEOUT:

        if not vision_requested():
            raise InterruptedError("Vision monitoring cancelled")

        if get(PV_GET_AUTO_EXPOSURE) == 1:
            print("Automatic exposure enabled")
            return

        time.sleep(POLL_INTERVAL)

    raise TimeoutError("Automatic exposure readback did not update")


def classify_led(red_count, yellow_count, green_count):
    """Classify LED colour using experimental HSV measurements."""

    total = red_count + yellow_count + green_count

    if total < 1000:
        return UNKNOWN, 0.0, 0.0

    red_green_ratio = red_count / max(green_count, 1)
    yellow_fraction = yellow_count / total

    if red_green_ratio > 20 and yellow_fraction < 0.05:
        status = FAULT

    elif yellow_fraction > 0.10:
        status = WARNING

    elif red_green_ratio < 0.2 and yellow_fraction < 0.02:
        status = NORMAL

    else:
        status = UNKNOWN

    return status, red_green_ratio, yellow_fraction


def analyze_image(image_path):
    """Analyze the full JPEG using HSV colour segmentation."""

    with Image.open(image_path) as image:
        hsv = np.asarray(image.convert("RGB").convert("HSV"))

    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_coloured = (saturation > 100) & (value > 100)

    red_mask = (
        ((hue < 15) | (hue > 240))
        & bright_coloured
    )

    yellow_mask = (
        (hue >= 25) & (hue <= 50)
        & bright_coloured
    )

    green_mask = (
        (hue >= 55) & (hue <= 115)
        & bright_coloured
    )

    red_count = int(np.count_nonzero(red_mask))
    yellow_count = int(np.count_nonzero(yellow_mask))
    green_count = int(np.count_nonzero(green_mask))

    status, ratio, fraction = classify_led(
        red_count, yellow_count, green_count
    )

    print(
        f"Red={red_count}, Yellow={yellow_count}, "
        f"Green={green_count}, R/G={ratio:.4f}, "
        f"Yellow fraction={fraction:.4f}"
    )

    return status, ratio, fraction


def acquisition_allowed():
    """Check whether a vision acquisition is permitted."""

    if not vision_requested():
        return False

    if get(PV_SCAN_ENABLE) == 1:
        return False

    if get(PV_SCAN_STATUS) == SCAN_RUNNING:
        return False

    if get(PV_START_SCAN) == 1:
        return False

    return True


def acquire_image():
    """Acquire a JPEG and matching metadata through EPICS."""

    if not acquisition_allowed():
        raise InterruptedError("Vision acquisition not permitted")

    previous_path = get(PV_IMAGE_PATH, as_string=True)

    # CameraCommand: Start=0, Stop=1, Acquire=2, Close=3
    put(PV_CAMERA_COMMAND, 2)

    start = time.monotonic()

    while time.monotonic() - start < ACQUISITION_TIMEOUT:

        if not acquisition_allowed():
            raise InterruptedError("Vision monitoring interrupted")

        image_path = get(PV_IMAGE_PATH, as_string=True)
        metadata_path = get(PV_METADATA_PATH, as_string=True)

        if (
            image_path
            and image_path != "NONE"
            and image_path != previous_path
            and metadata_path
            and metadata_path != "NONE"
        ):
            image_file = Path(image_path)
            metadata_file = Path(metadata_path)

            expected_metadata = image_file.stem + "_metadata.json"

            if (
                metadata_file.name == expected_metadata
                and image_file.is_file()
                and metadata_file.is_file()
            ):
                return image_file, metadata_file

        time.sleep(POLL_INTERVAL)

    raise TimeoutError("Camera acquisition timed out")


def monitor_led():
    """Perform one image acquisition and LED classification."""

    image_path, metadata_path = acquire_image()

    with open(metadata_path, "r") as file:
        metadata = json.load(file)

    status, ratio, fraction = analyze_image(image_path)

    if not acquisition_allowed():
        raise InterruptedError("Vision monitoring interrupted")

    put(PV_RED_GREEN_RATIO, ratio)
    put(PV_YELLOW_FRACTION, fraction)
    put(PV_LED_STATUS, status)

    status_names = ["UNKNOWN", "NORMAL", "WARNING", "FAULT"]

    print(
        f"Image: {image_path.name}, "
        f"Exposure: {metadata.get('ExposureTime')}, "
        f"Gain: {metadata.get('AnalogueGain')}, "
        f"LED status: {status_names[status]}"
    )


def main():
    """Run the EPICS-controlled LED monitoring loop."""

    set_vision_state(IDLE)
    set_led_unknown()

    print("LED vision monitor ready")

    last_acquisition = None
    auto_exposure_ready = False

    while True:

        if not vision_requested():

            if get(PV_VISION_STATUS) != IDLE:
                set_vision_state(IDLE)
                set_led_unknown()

            last_acquisition = None
            auto_exposure_ready = False

            time.sleep(POLL_INTERVAL)
            continue

        try:
            # Wait for scan completion and disable scan mode
            wait_for_scan()

            if not acquisition_allowed():
                set_vision_state(WAITING)
                set_led_unknown()
                auto_exposure_ready = False
                time.sleep(POLL_INTERVAL)
                continue

            # Enable automatic exposure once when entering vision mode
            if not auto_exposure_ready:
                enable_auto_exposure()
                auto_exposure_ready = True

            if not acquisition_allowed():
                raise InterruptedError("Vision acquisition not permitted")

            if get(PV_VISION_STATUS) != RUNNING:
                set_vision_state(RUNNING)
                print("LED vision monitoring started")

            now = time.monotonic()

            if (
                last_acquisition is None
                or now - last_acquisition >= ACQUISITION_INTERVAL
            ):
                last_acquisition = now
                monitor_led()

        except InterruptedError as error:
            print(error)
            set_led_unknown()
            set_vision_state(IDLE)

            last_acquisition = None
            auto_exposure_ready = False

        except Exception as error:
            print(f"Vision monitoring error: {error}")

            set_led_unknown()
            set_vision_state(ERROR)

            last_acquisition = time.monotonic()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print("\nLED vision monitor stopped")

    finally:
        try:
            set_led_unknown()
            set_vision_state(IDLE)
        except Exception as error:
            print(f"Could not reset vision PVs: {error}")
