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



# Initialize the IMX219 camera only if it is not already open
def initialize_camera():
    global camera, camera_status

    if camera is None:
        camera_id = find_camera()
        camera = Picamera2(camera_id)
        camera_status = update_camera_status("IDLE")
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
    global camera

    # Check whether the camera has been initialized
    if camera is not None:

        # Stop streaming if the camera is running
        if camera.started:
            camera.stop()

        # Release camera resources
        camera.close()

        # Reset the global camera variable
        camera = None

    # Update the camera operating state
    update_camera_status("CLOSED")


# Acquire an image and its corresponding metadata
def acquire_image():

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

    return str(image_path)


# Create an IPv4 TCP socket for communication with the EPICS IOC
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Allow the socket address to be reused after restarting the server
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


# Associate the server socket with the IP address and port
server.bind((HOST, PORT))

# Start listening for incoming TCP connections
server.listen(1)

try:
    while True:
        # Wait for IOC connection
        connection, address = server.accept()
        print(f"Connected by {address}")

        while True:
            # Wait for command
            data = connection.recv(1024)

            if not data:
                break

            # Process command
            command = data.decode("utf-8").strip()
            # Display the command received from the IOC
            print(f"Received command: {command}")

            if command == "STATUS?":
                initialize_camera()
                response = camera_status + "\n"
            else:
                response = "ERROR\n"

            connection.sendall(response.encode("utf-8"))

        # Close connection when IOC disconnects
        connection.close()

except KeyboardInterrupt:
    # Handle Ctrl+C from the keyboard
    print("\nKeyboard interrupt: Stopping camera server")

finally:
    server.close()

    if camera is not None:
        camera.close()
        print("Camera released")
