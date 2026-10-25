
from pathlib import Path
import time

import epics
import numpy as np
from PIL import Image

from p4p.nt import NTScalar
from p4p.server import Server, StaticProvider
from p4p.server.thread import SharedPV


# Image display configuration
IMAGE_WIDTH = 100
IMAGE_HEIGHT = 100

# EPICS PVs
PV_IMAGE_PATH = "CAM:GetLatestImagePath"
PV_IMAGE_DATA = "CAM:Image"

# Polling interval for the EPICS PV
CHECK_INTERVAL = 0.5


# Create the PVAccess image PV
image_type = NTScalar("aB")

initial_pixels = np.zeros(
    IMAGE_WIDTH * IMAGE_HEIGHT * 3,
    dtype=np.uint8
)

image_pv = SharedPV(
    initial=image_type.wrap(initial_pixels)
)

provider = StaticProvider("camera_image")
provider.add(PV_IMAGE_DATA, image_pv)


def publish_image(image_path):
    """Read a saved JPEG and publish its RGB pixel data."""

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        resized = rgb.resize((IMAGE_WIDTH, IMAGE_HEIGHT))
        pixels = np.asarray(resized, dtype=np.uint8)

    pixel_array = pixels.flatten()

    image_pv.post(image_type.wrap(pixel_array))

    print(f"Published image: {image_path}")


def main():
    """Watch for new acquisitions and update the image PV."""

    previous_image_path = None

    print(f"Watching {PV_IMAGE_PATH}")
    print(f"Publishing {PV_IMAGE_DATA}")

    with Server(providers=[provider]):

        try:
            while True:

                # Read the latest image path from the IOC
                image_path = epics.caget(
                    PV_IMAGE_PATH,
                    as_string=True
                )

                # Check whether a new image is available
                if (
                    image_path
                    and image_path != "NONE"
                    and image_path != previous_image_path
                ):

                    path = Path(image_path)

                    if path.is_file():
                        try:
                            publish_image(path)
                            previous_image_path = image_path

                        except Exception as error:
                            print(f"Image publication failed: {error}")

                    else:
                        print(f"Image file not found: {path}")

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping image publisher")


if __name__ == "__main__":
    main()
