#  GNU nano 8.4                          acquisition/tests/test_camera_acquisition.py                              M
# Import Picamera2 to access the Raspberry Pi camera
from picamera2 import Picamera2
# Import Path to manage file and directory locations
from pathlib import Path

# Import Transform to control image orientation
from libcamera import Transform


# Get the directory containing this Python script
script_dir = Path(__file__).resolve().parent

# Define the image filename in the same directory
image_path = script_dir / "test_image.jpg"

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

# Start camera streaming
camera.start()
print("Camera started successfully")

# Capture and save the image in the script's directory
camera.capture_file(str(image_path))

print(f"Image saved to: {image_path}")

# Stop camera streaming
camera.stop()
print("Camera stopped")

# Release camera resources
#camera.close()
