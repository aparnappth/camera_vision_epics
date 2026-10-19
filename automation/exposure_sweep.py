
# Automated exposure sweep using PyEpics

import epics
import time
import csv
from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# EPICS Process Variables
# --------------------------------------------------

PV_STATUS = "CAM:GetStatus"

PV_SET_EXPOSURE = "CAM:SetExposure"
PV_GET_EXPOSURE = "CAM:GetExposure"

PV_SET_GAIN = "CAM:SetGain"
PV_GET_GAIN = "CAM:GetGain"

PV_SET_AUTO_EXPOSURE = "CAM:SetAutoExposure"
PV_GET_AUTO_EXPOSURE = "CAM:GetAutoExposure"

PV_CAMERA_COMMAND = "CAM:CameraCommand"

PV_IMAGE_PATH = "CAM:GetLatestImagePath"
PV_METADATA_PATH = "CAM:GetLatestMetadataPath"


# --------------------------------------------------
# Measurement settings
# --------------------------------------------------

exposure_values = [5000, 10000, 20000, 40000, 80000]

fixed_gain = 1.0

timeout = 10
poll_interval = 0.05


# --------------------------------------------------
# Wait for a PV to reach an expected value
# --------------------------------------------------

def wait_for_readback(pv_name, expected_value):

    start_time = time.monotonic()

    while True:

        current_value = epics.caget(pv_name)

        if current_value is not None and current_value == expected_value:
            return current_value

        if time.monotonic() - start_time > timeout:
            raise TimeoutError(
                f"{pv_name} did not reach {expected_value}"
            )

        time.sleep(poll_interval)


# --------------------------------------------------
# Acquire one image at a requested exposure
# --------------------------------------------------

def acquire_at_exposure(requested_exposure):

    print(f"\nSetting exposure to {requested_exposure} us")

    # Set exposure through EPICS
    if epics.caput(
        PV_SET_EXPOSURE,
        requested_exposure,
        wait=True
    ) != 1:
        raise RuntimeError("Failed to write exposure setpoint")

    # Wait for the FLNK-triggered exposure readback
    actual_readback = wait_for_readback(
        PV_GET_EXPOSURE,
        requested_exposure
    )

    print(f"Exposure readback: {actual_readback} us")

    # Read the previous image path
    previous_image_path = epics.caget(
        PV_IMAGE_PATH,
        as_string=True
    )

    # Trigger acquisition
    print("Acquiring image...")

    if epics.caput(
        PV_CAMERA_COMMAND,
        "Acquire",
        wait=True
    ) != 1:
        raise RuntimeError("Failed to send acquisition command")

    # Wait until the image path changes
    start_time = time.monotonic()

    while True:

        current_image_path = epics.caget(
            PV_IMAGE_PATH,
            as_string=True
        )

        if (
            current_image_path
            and current_image_path != previous_image_path
        ):
            break

        if time.monotonic() - start_time > timeout:
            raise TimeoutError(
                "No new image path received after acquisition"
            )

        time.sleep(poll_interval)

    # Determine the matching metadata filename
    expected_metadata_path = (
        current_image_path.removesuffix(".jpg")
        + "_metadata.json"
    )

    # Wait for the matching metadata path
    start_time = time.monotonic()

    while True:

        metadata_path = epics.caget(
            PV_METADATA_PATH,
            as_string=True
        )

        if metadata_path == expected_metadata_path:
            break

        if time.monotonic() - start_time > timeout:
            raise TimeoutError(
                "Matching metadata path was not received"
            )

        time.sleep(poll_interval)

    print(f"Image: {current_image_path}")
    print(f"Metadata: {metadata_path}")

    # Return the acquisition information
    return {
        "requested_exposure_us": requested_exposure,
        "exposure_readback_us": actual_readback,
        "requested_gain": fixed_gain,
        "image_path": current_image_path,
        "metadata_path": metadata_path
    }


# --------------------------------------------------
# Main automated measurement
# --------------------------------------------------

def main():

    print("Starting EPICS-controlled exposure sweep")

    # Check IOC communication
    camera_status = epics.caget(PV_STATUS)

    if camera_status is None:
        raise ConnectionError("Cannot communicate with EPICS IOC")

    print(f"Initial camera status: {camera_status}")

    # Disable automatic exposure
    if epics.caput(
        PV_SET_AUTO_EXPOSURE,
        0,
        wait=True
    ) != 1:
        raise RuntimeError("Failed to disable automatic exposure")

    wait_for_readback(PV_GET_AUTO_EXPOSURE, 0)

    # Set fixed analogue gain
    if epics.caput(
        PV_SET_GAIN,
        fixed_gain,
        wait=True
    ) != 1:
        raise RuntimeError("Failed to set analogue gain")

    wait_for_readback(PV_GET_GAIN, fixed_gain)

    # Create a measurement-log directory
    output_dir = Path("data/exposure_sweeps")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create a unique CSV filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = output_dir / f"exposure_sweep_{timestamp}.csv"

    fieldnames = [
        "requested_exposure_us",
        "exposure_readback_us",
        "requested_gain",
        "image_path",
        "metadata_path"
    ]

    # Perform the exposure sweep and save each completed result
    with open(csv_path, "w", newline="") as file:

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        file.flush()

        for exposure in exposure_values:

            result = acquire_at_exposure(exposure)

            writer.writerow(result)
            file.flush()

    print("\nExposure sweep completed successfully")
    print(f"Measurement log saved to: {csv_path}")


# --------------------------------------------------
# Run the automation
# --------------------------------------------------

if __name__ == "__main__":
    main()
