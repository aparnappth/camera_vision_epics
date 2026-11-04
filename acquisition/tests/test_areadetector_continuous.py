
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
    """Configure the IOC for continuous RGB1 image transfer."""

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

    # RGB1 NDArray dimensions: [channels, width, height]
    dimensions = np.array(
        [CHANNELS, WIDTH, HEIGHT],
        dtype=np.int32
    )

    put_pv(f"{INPUT_PREFIX}Dimensions", dimensions)

    # Verify configuration readbacks
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

    # Start acquisition without waiting for completion
    success = epics.caput(
        f"{INPUT_PREFIX}Acquire",
        1,
        wait=False,
        timeout=5
    )

    if success != 1:
        raise RuntimeError(
            "Failed to issue acquisition command"
        )

    # Wait until acquisition is active
    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:

        actual = epics.caget(
            f"{INPUT_PREFIX}Acquire_RBV",
            as_string=False
        )

        if actual is not None and int(actual) == 1:
            break

        time.sleep(0.1)

    else:
        raise RuntimeError(
            "areaDetector did not enter acquisition mode"
        )

    print("Continuous acquisition enabled")
    print("areaDetector configured successfully")


# ==========================================
# Continuous camera acquisition
# ==========================================

def main():

    camera = None
    request = None
    frame_count = 0

    try:
        # Configure IOC before accessing the camera
        configure_areadetector()

        # Open IMX219 camera
        camera = Picamera2(0)

        # Configure RGB video acquisition
        config = camera.create_video_configuration(
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

        print("\nContinuous acquisition started")
        print("Press Ctrl+C to stop\n")

        # ==========================================
        # Continuous acquisition loop
        # ==========================================

        while True:

            # Capture image and metadata
            request = camera.capture_request()

            try:
                frame = request.make_array("main")
                metadata = request.get_metadata()

            finally:
                request.release()
                request = None

            # Verify image format
            if frame.shape != (HEIGHT, WIDTH, CHANNELS):
                raise ValueError(
                    f"Unexpected frame shape: {frame.shape}"
                )

            if frame.dtype != np.uint8:
                raise ValueError(
                    f"Unexpected frame dtype: {frame.dtype}"
                )

            # ==========================================
            # Prepare RGB image
            # ==========================================

            # Convert Picamera2 channel order for RGB1
            frame_rgb = np.ascontiguousarray(
                frame[:, :, ::-1]
            )

            # Flatten image
            pixels = frame_rgb.reshape(-1)

            # Preserve byte patterns for asynInt8ArrayOut
            pixels_int8 = pixels.view(np.int8)

            if pixels_int8.size != EXPECTED_ELEMENTS:
                raise RuntimeError(
                    "Unexpected number of image elements"
                )

            # ==========================================
            # Transfer image through EPICS
            # ==========================================

            put_pv(INPUT_PV, pixels_int8)

            frame_count += 1

            print(
                f"Frame {frame_count}: "
                f"exposure={metadata.get('ExposureTime')} us, "
                f"gain={metadata.get('AnalogueGain')}"
            )

    except KeyboardInterrupt:
        print("\nContinuous acquisition stopped by user")

    finally:

        # Release any outstanding capture request
        if request is not None:
            request.release()
            print("Capture request released")

        # Stop and close camera
        if camera is not None:

            if camera.started:
                camera.stop()
                print("Camera stopped")

            camera.close()
            print("Camera released")

        print(f"Total frames transferred: {frame_count}")


if __name__ == "__main__":
    main()
