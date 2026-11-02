
import os
import time

# Set before importing PyEpics
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = "1000000"

import numpy as np
import epics

from picamera2 import Picamera2
from libcamera import Transform


# ==========================================
# Configuration
# ==========================================

WIDTH = 320
HEIGHT = 240
CHANNELS = 3

EPICS_PREFIX = "AD:"

INPUT_PREFIX = f"{EPICS_PREFIX}Input:"
IMAGE_PREFIX = f"{EPICS_PREFIX}Image1:"

INPUT_PV = f"{INPUT_PREFIX}ArrayIn"
OUTPUT_COUNTER_PV = f"{IMAGE_PREFIX}ArrayCounter_RBV"
OUTPUT_ARRAY_PV = f"{IMAGE_PREFIX}ArrayData"

EXPECTED_ELEMENTS = WIDTH * HEIGHT * CHANNELS

# areaDetector enum values
ND_UINT8 = 1
COLOR_RGB1 = 2
CALLBACK_ON_UPDATE = 0
IMAGE_MODE_CONTINUOUS = 2


# ==========================================
# EPICS helper functions
# ==========================================

def put_pv(name, value):
    """Write an EPICS PV and check for success."""

    success = epics.caput(
        name,
        value,
        wait=True,
        timeout=10
    )

    if success != 1:
        raise RuntimeError(
            f"Failed to write EPICS PV: {name}"
        )


def verify_pv(name, expected):
    """Verify a scalar EPICS readback."""

    actual = epics.caget(name, as_string=False)

    if actual is None:
        raise RuntimeError(
            f"Cannot read EPICS PV: {name}"
        )

    if int(actual) != expected:
        raise RuntimeError(
            f"{name}: expected {expected}, got {actual}"
        )


# ==========================================
# Configure areaDetector
# ==========================================

def configure_areadetector():
    """Configure the IOC for 320x240 RGB1 image transfer."""

    print("\nConfiguring areaDetector...")

    # Stop acquisition while changing image settings
    put_pv(f"{INPUT_PREFIX}Acquire", 0)

    settings = {
        f"{INPUT_PREFIX}SizeX": WIDTH,
        f"{INPUT_PREFIX}SizeY": HEIGHT,
        f"{INPUT_PREFIX}NDimensions": 3,
        f"{INPUT_PREFIX}DataType": ND_UINT8,
        f"{INPUT_PREFIX}ColorMode": COLOR_RGB1,
        f"{INPUT_PREFIX}CallbackMode": CALLBACK_ON_UPDATE,
        f"{INPUT_PREFIX}AppendMode": 0,
        f"{INPUT_PREFIX}ImageMode": IMAGE_MODE_CONTINUOUS,
        f"{INPUT_PREFIX}ArrayCallbacks": 1,
        f"{IMAGE_PREFIX}EnableCallbacks": 1,
    }

    for pv, value in settings.items():
        put_pv(pv, value)

    # Configure RGB1 NDArray dimensions:
    # [channels, width, height]
    dimensions = np.array(
        [CHANNELS, WIDTH, HEIGHT],
        dtype=np.int32
    )

    put_pv(
        f"{INPUT_PREFIX}Dimensions",
        dimensions
    )

    # Verify important configuration readbacks
    verify_pv(f"{INPUT_PREFIX}SizeX_RBV", WIDTH)
    verify_pv(f"{INPUT_PREFIX}SizeY_RBV", HEIGHT)
    verify_pv(f"{INPUT_PREFIX}NDimensions_RBV", 3)
    verify_pv(f"{INPUT_PREFIX}DataType_RBV", ND_UINT8)
    verify_pv(f"{INPUT_PREFIX}ColorMode_RBV", COLOR_RGB1)
    verify_pv(
        f"{INPUT_PREFIX}ImageMode_RBV",
        IMAGE_MODE_CONTINUOUS
    )
    verify_pv(
        f"{IMAGE_PREFIX}EnableCallbacks_RBV",
        1
    )

    # Dimensions_RBV is not used for verification because
    # NDDriverStdArrays may not update this readback.
    # The driver's internal dimensions can be checked
    # using asynReport(1, "STDARRAYS").

    # Start continuous acquisition
    # Start continuous acquisition without waiting for
    # the acquisition operation to complete
    success = epics.caput(
        f"{INPUT_PREFIX}Acquire",
        1,
        wait=False,
        timeout=5
    )

    if success != 1:
        raise RuntimeError("Failed to issue acquisition command")

    # Allow the IOC to update its acquisition state
    time.sleep(0.2)

    # Verify that acquisition is active
    verify_pv(f"{INPUT_PREFIX}Acquire_RBV", 1)

    print("Continuous acquisition enabled")
    print("areaDetector configured successfully")


# ==========================================
# Camera acquisition and image transfer
# ==========================================

def main():

    camera = None
    request = None

    try:
        # Configure the IOC before accessing the camera
        configure_areadetector()

        # Open the IMX219 camera
        camera = Picamera2(0)

        # Configure RGB acquisition with 180-degree rotation
        config = camera.create_still_configuration(
            main={
                "size": (WIDTH, HEIGHT),
                "format": "RGB888"
            },
            transform=Transform(hflip=1, vflip=1)
        )

        camera.configure(config)

        # Enable automatic exposure and gain
        camera.set_controls({
            "AeEnable": True
        })

        camera.start()
        print("\nCamera started successfully")

        # Allow automatic exposure to settle
        time.sleep(2)

        # Capture image and metadata from the same request
        request = camera.capture_request()

        frame = request.make_array("main")
        metadata = request.get_metadata()

        print(f"Captured frame shape: {frame.shape}")
        print(f"Frame data type: {frame.dtype}")

        print(
            f"Actual exposure: "
            f"{metadata.get('ExposureTime')} us"
        )
        print(
            f"Actual analogue gain: "
            f"{metadata.get('AnalogueGain')}"
        )

        # Verify frame format
        if frame.shape != (HEIGHT, WIDTH, CHANNELS):
            raise ValueError(
                f"Unexpected frame shape: {frame.shape}"
            )

        if frame.dtype != np.uint8:
            raise ValueError(
                f"Unexpected frame dtype: {frame.dtype}"
            )

        # ==========================================
        # Prepare RGB image for areaDetector
        # ==========================================

        # Convert Picamera2 channel order for RGB1 display
        frame_rgb = np.ascontiguousarray(
            frame[:, :, ::-1]
        )

        # Flatten RGB data
        pixels = frame_rgb.reshape(-1)

        # asynInt8ArrayOut uses signed 8-bit values.
        # Preserve the original byte patterns.
        pixels_int8 = pixels.view(np.int8)

        print(
            f"Transferring {pixels_int8.size} "
            f"image elements to areaDetector"
        )

        # ==========================================
        # Transfer through EPICS
        # ==========================================

        before = epics.caget(OUTPUT_COUNTER_PV)

        if before is None:
            raise RuntimeError(
                "Cannot read output plugin array counter"
            )

        print(f"Plugin array counter before: {before}")

        put_pv(INPUT_PV, pixels_int8)

        print("Image waveform sent successfully")

        # Allow the output plugin to process the callback
        deadline = time.monotonic() + 5
        after = before

        while time.monotonic() < deadline:
            after = epics.caget(OUTPUT_COUNTER_PV)

            if after is not None and after > before:
                break

            time.sleep(0.1)

        print(f"Plugin array counter after: {after}")

        if after is None or after <= before:
            raise RuntimeError(
                "NDPluginStdArrays did not receive a new image"
            )

        print("NDPluginStdArrays received the image")

        # ==========================================
        # Verify output waveform
        # ==========================================

        output_nord = epics.caget(
            OUTPUT_ARRAY_PV + ".NORD"
        )

        if output_nord is None:
            raise RuntimeError(
                "Cannot read output waveform element count"
            )

        output_nord = int(output_nord)

        print(
            f"Output waveform elements: {output_nord}"
        )

        if output_nord != EXPECTED_ELEMENTS:
            raise RuntimeError(
                f"Expected {EXPECTED_ELEMENTS} elements, "
                f"received {output_nord}"
            )

        print("Output image size verified")
        print("\nSingle-frame areaDetector test successful")

    finally:

        if request is not None:
            request.release()
            print("Capture request released")

        if camera is not None:
            if camera.started:
                camera.stop()
                print("Camera stopped")

            camera.close()
            print("Camera released")


if __name__ == "__main__":
    main()
