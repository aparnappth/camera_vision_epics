
import socket

HOST = "127.0.0.1"
PORT = 5000

# Create a TCP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Allow quick reuse of the port after restarting
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Assign IP address and port
server.bind((HOST, PORT))

# Start listening for connections
server.listen(1)

print(f"Camera server listening on {HOST}:{PORT}")

try:
    while True:
        # Wait for a client connection
        connection, address = server.accept()
        print(f"Connected by {address}")

        with connection:
            while True:
                # Receive data from the client
                data = connection.recv(1024)

                if not data:
                    break

                command = data.decode("utf-8").strip()
                print(f"Received command: {command}")

                # Process the command
                if command == "STATUS?":
                    response = "IDLE\n"
                else:
                    response = "ERROR\n"

                # Send response to the client
                connection.sendall(response.encode("utf-8"))

except KeyboardInterrupt:
    print("\nStopping camera server")

finally:
    server.close()

