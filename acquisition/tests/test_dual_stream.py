"""Test simultaneous main and low-resolution camera streams."""

from picamera2 import Picamera2
from libcamera import Transform
import time

camera = Picamera2()

try:
    config = camera.create_still_configuration(
        lores={"size": (160, 120), "format": "YUV420"},
        transform=Transform(hflip=1, vflip=1)
    )

    camera.configure(config)

    print("Camera configuration:")
    print(camera.camera_configuration())

    camera.start()
    time.sleep(2)

    # Obtain a low-resolution frame directly from memory
    frame = camera.capture_array("lores")

    print("\nLow-resolution frame:")
    print("Shape:", frame.shape)
    print("Data type:", frame.dtype)
    print("Size:", frame.nbytes, "bytes")

    # Verify that the main stream still works
    request = camera.capture_request()

    try:
        print("\nMain stream metadata:")
        print(request.get_metadata())

        request.save("main", "/tmp/dual_stream_test.jpg")
        print("Main image saved successfully")

    finally:
        request.release()

finally:
    camera.stop()
    camera.close()
