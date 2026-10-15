# Import Picamera2 to access the Raspberry Pi camera
from picamera2 import Picamera2
# Import Path to manage file and directory locations
from pathlib import Path

# Import Transform to control image orientation
from libcamera import Transform

# Import JSON to save camera acquisition metadata
import json

# Import datetime to generate unique filenames for each acquisition
from datetime import datetime

# Get the directory containing this Python script
script_dir = Path(__file__).resolve().parent

# Generate a timestamp for this acquisition
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

# Define matching filenames for the image and metadata
image_path = script_dir / f"image_{timestamp}.jpg"
metadata_path = script_dir / f"image_{timestamp}_metadata.json"

# Open the IMX219 camera
camera = Picamera2(0)

# Create still-image configuration with 180-degree rotation
config = camera.create_still_configuration(
    transform=Transform(hflip=1, vflip=1)
)

# Apply the still-image configuration to the camera
camera.configure(config)

# Display the configuration
#print(config)

# Disable automatic exposure and set manual acquisition parameters
camera.set_controls({
    "AeEnable": False,
    "ExposureTime": 20000,
    "AnalogueGain": 1.0
})

# Initially, no capture request has been created
request = None

try:
    # Start camera streaming
    camera.start()
    print("Camera started successfully")

    # Capture an image and its metadata in the same request
    request = camera.capture_request()

    # Save the image from the captured request
    request.save("main", str(image_path))

    # Retrieve metadata from the same request
    metadata = request.get_metadata()

    # Save metadata as a JSON file
    with open(metadata_path, "w") as file:
        json.dump(metadata, file, indent=4, default=str)

    print(f"Image saved to: {image_path}")
    print(f"Metadata saved to: {metadata_path}")

finally:
    # Release the capture request if one was created
    if request is not None:
        request.release()
        print("Capture request released")

    # Stop the camera if it is running
    if camera.started:
        camera.stop()
        print("Camera stopped")

    # Release camera resources
    camera.close()
    print("Camera released")
