# Import Picamera2 class to access and control the Raspberry Pi camera
from picamera2 import Picamera2

# Import Python's built-in socket module for TCP/IP communication
import socket

# Import JSON to save acquisition metadata
import json

# Import Path to manage file and directory locations
from pathlib import Path

# Import datetime to generate unique acquisition filenames
from datetime import datetime

# Import Transform to control camera image orientation
from libcamera import Transform

# Import math to validate numerical camera settings
import math

import threading
import time

# Define the IP address and port for the TCP server
HOST = "127.0.0.1"
PORT = 5000

# Initially, the camera is not opened
camera = None

# Initial camera state
camera_status = "CLOSED"


# Define the meaning of each camera operating state
status_messages = {
    "CLOSED": "Camera is not initialized (camera = None)",
    "IDLE": "Camera is initialized but not streaming",
    "STREAMING": "Camera is running (camera.start()), producing frames without necessarily displaying them",
    "ACQUIRING": "Camera is processing an image acquisition request",
    "PREVIEWING": "Camera is streaming and a live preview is active",
    "ERROR": "A camera operation has failed"
}

# Default acquisition parameters
auto_exposure = True
exposure_time = 20000   # Microseconds
analogue_gain = 1.0     # Unity gain
# Actual settings reported by completed camera frames
actual_exposure = None
actual_gain = None

METADATA_CHECK_INTERVAL = 0.2  # seconds
GAIN_CHANGE_THRESHOLD = 0.01
EXPOSURE_CHANGE_THRESHOLD = 10  # microseconds

# Paths of the latest successfully acquired image and metadata
last_image_path = "NONE"
last_metadata_path = "NONE"


# Manage the single TCP connection shared by commands and notifications.
class TCPConnection:
    def __init__(self):
        self.connection = None
        self.lock = threading.Lock()

    def set_connection(self, connection):
        with self.lock:
            self.connection = connection

    def send(self, message):
        # Return False when no IOC is connected; propagate real socket errors.
        with self.lock:
            if self.connection is None:
                return False
            self.connection.sendall(message.encode("utf-8"))
            return True

    def clear_connection(self):
        # Detach first so the worker cannot send to a closed socket.
        with self.lock:
            self.connection = None


tcp = TCPConnection()


# Find the IMX219 camera and return its camera index
def find_camera():
    cameras = Picamera2.global_camera_info()

    for cam in cameras:
        if cam["Model"] == "imx219":
            return cam["Num"]

    raise RuntimeError("IMX219 camera not found")



# Update the camera status (only when its state changes)
def update_camera_status(new_status):
    global camera_status

    if camera_status != new_status:
        camera_status = new_status
        print(f"Camera status changed to: {new_status}")

        # Send status notification through the existing TCP connection
        message = f"STATUS:{new_status}\n"
        tcp.send(message)

# Read actual exposure and gain from completed frames
def frame_callback(request):
    global actual_exposure, actual_gain

    metadata = request.get_metadata()

    new_exposure = metadata.get("ExposureTime")
    new_gain = metadata.get("AnalogueGain")

    if new_exposure is not None:
        actual_exposure = new_exposure

    if new_gain is not None:
        actual_gain = new_gain


def monitor_actual_settings():
    """Publish changed camera settings without blocking the frame callback."""
    previous_exposure = None
    previous_gain = None
    previous_camera = None

    while True:
        time.sleep(METADATA_CHECK_INTERVAL)

        cam = camera
        if cam is None or not cam.started:
            previous_exposure = None
            previous_gain = None
            previous_camera = None
            continue

        # A newly initialized camera needs fresh values, not old metadata.
        if cam is not previous_camera:
            previous_camera = cam
            previous_exposure = None
            previous_gain = None

        exposure = actual_exposure
        gain = actual_gain

        if exposure is not None and (
            previous_exposure is None
            or abs(exposure - previous_exposure) >= EXPOSURE_CHANGE_THRESHOLD
        ):
            try:
                if tcp.send(f"ACTUAL_EXPOSURE:{exposure}\n"):
                    previous_exposure = exposure
                    print(f"Actual exposure: {exposure} us")
            except OSError as error:
                print(f"Exposure notification failed: {error}")

        if gain is not None and (
            previous_gain is None
            or abs(gain - previous_gain) >= GAIN_CHANGE_THRESHOLD
        ):
            try:
                if tcp.send(f"ACTUAL_GAIN:{gain}\n"):
                    previous_gain = gain
                    print(f"Actual gain: {gain}")
            except OSError as error:
                print(f"Gain notification failed: {error}")


# Initialize the IMX219 camera only if it is not already open
def initialize_camera():
    global camera, actual_exposure, actual_gain

    if camera is None:
        camera_id = find_camera()
        actual_exposure = None
        actual_gain = None
        camera = Picamera2(camera_id)
        camera.post_callback = frame_callback
        update_camera_status("IDLE")
        print("IMX219 camera initialized successfully")

    return camera


# Configure the camera for still-image acquisition
def configure_camera(cam):

    config = cam.create_still_configuration(
        transform=Transform(hflip=1, vflip=1)
    )

    cam.configure(config)

# Apply the requested exposure and gain settings
def apply_camera_settings(cam):

    if auto_exposure:
        cam.set_controls({
            "AeEnable": True
        })

    else:
        cam.set_controls({
            "AeEnable": False,
            "ExposureTime": exposure_time,
            "AnalogueGain": analogue_gain
        })

# Update the requested exposure time
def set_exposure(value):
    global exposure_time

    # Convert the received value into an integer
    new_exposure = int(value)

    # Check that the exposure time is positive
    if new_exposure <= 0:
        raise ValueError("Exposure time must be positive")

    # Store the validated exposure time
    exposure_time = new_exposure

    # Apply settings if the camera is already streaming
    if camera is not None and camera.started:
        apply_camera_settings(camera)

# Update the requested analogue gain
def set_gain(value):
    global analogue_gain

    # Convert the received value into a floating-point number
    new_gain = float(value)

    # Check that the gain is a finite, positive number
    if not math.isfinite(new_gain) or new_gain <= 0:
        raise ValueError("Analogue gain must be a finite, positive number")

    # Store the validated analogue gain
    analogue_gain = new_gain

    # Apply settings if the camera is already streaming
    if camera is not None and camera.started:
        apply_camera_settings(camera)

# Enable or disable automatic exposure
def set_auto_exposure(value):
    global auto_exposure

    # Convert the received numerical value to a Boolean
    auto_exposure = bool(int(value))

    # Apply settings if the camera is already streaming
    if camera is not None and camera.started:
        apply_camera_settings(camera)

# Start the camera streaming pipeline
def start_camera():

    # Initialize the camera if it is not already open
    cam = initialize_camera()

    # Start streaming only if the camera is not already running
    if not cam.started:

        # Configure the camera for still-image acquisition
        configure_camera(cam)

        # Apply automatic or manual exposure and gain settings
        apply_camera_settings(cam)

        # Start the camera streaming pipeline
        cam.start()

        # Update the camera operating state
        update_camera_status("STREAMING")

# Stop camera streaming without closing the camera
def stop_camera():

    # Use the existing global camera object
    if camera is not None and camera.started:

        # Stop the camera streaming pipeline
        camera.stop()

        # Update the camera operating state
        update_camera_status("IDLE")

# Close the camera and release its resources
def close_camera():
    global camera, actual_exposure, actual_gain

    # Check whether the camera has been initialized
    if camera is not None:

        # Stop streaming if the camera is running
        if camera.started:
            camera.stop()

        # Release camera resources
        camera.close()

        # Reset the global camera variable
        camera = None
        actual_exposure = None
        actual_gain = None

    # Update the camera operating state
    update_camera_status("CLOSED")


# Acquire an image and its corresponding metadata
def acquire_image():
    global last_image_path, last_metadata_path

    # Initially, no capture request exists
    request = None

    # camera's streaming state before acquisition
    was_streaming = False
    

    try:
        
        # Update camera's streaming state before acquisition and Start streaming if necessary
        if camera is not None:
            was_streaming = camera.started
        
        if camera is None:
            initialize_camera()

        if not was_streaming:
            start_camera()


        # Update camera status
        update_camera_status("ACQUIRING")

        # Define the directory for acquired images
        image_dir = Path(__file__).resolve().parent / "images"

        # Create the directory if it does not exist
        image_dir.mkdir(parents=True, exist_ok=True)

        # Generate a unique acquisition timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Define matching image and metadata filenames
        image_path = image_dir / f"image_{timestamp}.jpg"
        metadata_path = image_dir / f"image_{timestamp}_metadata.json"

        # Capture a completed camera request
        request = camera.capture_request()

        # Save the image from the request
        request.save("main", str(image_path))

        # Retrieve metadata from the same request
        metadata = request.get_metadata()

        # Save metadata as JSON
        with open(metadata_path, "w") as file:
            json.dump(metadata, file, indent=4, default=str)

        print(f"Image saved to: {image_path}")
        print(f"Metadata saved to: {metadata_path}")

    except Exception as error:
        # Report an acquisition failure
        update_camera_status("ERROR")
        print(f"Image acquisition failed: {error}")

        # Propagate the error to the command handler
        raise

    finally:
        # Release the captured request if one exists
        if request is not None:
            request.release()

        # Stop streaming if acquisition started it
        if not was_streaming and camera is not None and camera.started:
            camera.stop()

    # Restore status after successful acquisition
    if was_streaming:
        update_camera_status("STREAMING")
    else:
        update_camera_status("IDLE")

    # Store the paths of the latest successful acquisition
    last_image_path = str(image_path)
    last_metadata_path = str(metadata_path)
    # Notify EPICS after successful acquisition
    tcp.send(f"IMAGE_PATH:{last_image_path}\n")

    tcp.send(f"METADATA_PATH:{last_metadata_path}\n")

    return str(image_path), str(metadata_path)



# Process commands received from the EPICS IOC
def process_command(command):

    try:
        if command == "STATUS?":
            return camera_status + "\n"

        elif command == "STATUS_DESC?":
            return "DESCRIPTION:" + status_messages[camera_status] + "\n"

        elif command == "START":
            start_camera()
            return "OK\n"

        elif command == "STOP":
            stop_camera()
            return "OK\n"

        elif command == "ACQUIRE":
            image_path, metadata_path = acquire_image()
            return "OK\n"

        elif command == "CLOSE":
            close_camera()
            return "OK\n"

        elif command.startswith("EXPOSURE "):
            value = command.split()[1]
            set_exposure(value)
            return "OK\n"

        elif command == "EXPOSURE_RB?":
            return f"{exposure_time}\n"

        elif command.startswith("GAIN "):
            value = command.split()[1]
            set_gain(value)
            return "OK\n"

        elif command == "GAIN_RB?":
            return f"{analogue_gain}\n"

        elif command.startswith("AUTO_EXPOSURE "):
            value = command.split()[1]
            set_auto_exposure(value)
            return "OK\n"

        elif command == "AUTO_EXPOSURE?":
            return f"{int(auto_exposure)}\n"
        
        elif command == "LATEST_IMAGE_PATH?":
            return last_image_path + "\n"

        elif command == "LATEST_METADATA_PATH?":
            return last_metadata_path + "\n"

        else:
            return "ERROR: Unknown command\n"

    except Exception as error:
        print(f"Command failed: {error}")
        return f"ERROR: {error}\n"


# Create the listening socket for the existing StreamDevice connection.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)

# Monitor metadata independently of the TCP command loop.
metadata_thread = threading.Thread(
    target=monitor_actual_settings,
    daemon=True,
)
metadata_thread.start()

try:
    while True:
        connection, address = server.accept()
        print(f"Connected by {address}")
        tcp.set_connection(connection)
        reader = None

        try:
            reader = connection.makefile("r", encoding="utf-8")
            while True:
                data = reader.readline()
                if not data:
                    break

                command = data.strip()
                print(f"Received command: {command}")
                response = process_command(command)
                tcp.send(response)
        except OSError as error:
            print(f"IOC communication failed: {error}")
        finally:
            # Do not let the metadata worker use this connection during cleanup.
            tcp.clear_connection()
            try:
                close_camera()
            except Exception as error:
                print(f"Camera cleanup failed: {error}")
            if reader is not None:
                reader.close()
            connection.close()
            print("IOC disconnected")

except KeyboardInterrupt:
    print("\nKeyboard interrupt: Stopping camera server")
finally:
    tcp.clear_connection()
    try:
        close_camera()
    except Exception as error:
        print(f"Camera cleanup failed: {error}")
    server.close()
    print("Camera server stopped")
