
# Import Picamera2 class to access and control the Raspberry Pi camera
from picamera2 import Picamera2

# Import Python's built-in socket module for TCP/IP communication
import socket

# Define the IP address and port for the TCP server
HOST = "127.0.0.1"
PORT = 5000

# Initially, the camera is not opened
camera = None

# Initial camera state
camera_status = "CLOSED"


# Find the IMX219 camera and return its camera index
def find_camera():
    cameras = Picamera2.global_camera_info()

    for cam in cameras:
        if cam["Model"] == "imx219":
            return cam["Num"]

    raise RuntimeError("IMX219 camera not found")

# Initialize the IMX219 camera only if it is not already open
def initialize_camera():
    global camera, camera_status

    if camera is None:
        camera_id = find_camera()
        camera = Picamera2(camera_id)
        camera_status = "IDLE"
        print("IMX219 camera initialized successfully")

    return camera

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
