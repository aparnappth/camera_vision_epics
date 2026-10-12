# StreamDevice Camera IOC — Implementation Guide

This document describes the development, configuration and testing of a conventional EPICS IOC that communicates with a Python TCP server using StreamDevice and asyn.

The implementation is part of the [EPICS-Controlled Camera Characterization and Vision Platform](../README.md).

For installation of EPICS Base, asyn and StreamDevice, see [EPICS Environment Setup](epics_setup.md).

## 1. Objective and Current Status

The objective is to create an EPICS interface for controlling a Raspberry Pi IMX219 camera using Python and Picamera2.

The current implementation establishes communication between an EPICS IOC and a Python TCP service. It supports a status query that returns a fixed `IDLE` response.

**Implemented and tested:**

- Conventional EPICS IOC compiled for `linux-arm`.
- StreamDevice and asyn integrated into the IOC.
- Python TCP server running on the Raspberry Pi.
- On-demand status request using `CAM:GetStatus.PROC`.
- Local EPICS Channel Access communication.
- Remote EPICS access from Windows Subsystem for Linux (WSL).

**Not yet implemented:** Picamera2 camera control, image acquisition, exposure settings, image saving and real camera-status monitoring.

## 2. Communication Architecture

```text
Windows / WSL
    |
    | caget / caput
    v
EPICS Channel Access
    |
    v
EPICS IOC (Raspberry Pi)
    |
    | camera.db
    v
StreamDevice
    |
    | stream_camera.proto
    v
asyn TCP/IP (CAM_PORT)
    |
    | 127.0.0.1:5000
    v
Python TCP server
    |
    | STATUS?
    v
Response: IDLE
```

The eventual camera interface will extend the Python service:

```text
Python TCP server
       |
    Picamera2
       |
    libcamera
       |
 Linux camera drivers
       |
     IMX219
```

The EPICS IOC and Python service are separate processes.

EPICS communicates with the Python service through a TCP connection, rather than executing a Python file directly.

## 3. Directory Structure

The current implementation is located in:

```text
camera_vision_epics/
├── acquisition/
│   └── camera_server.py
│
└── epics/
    └── streamdevice_camera/
        └── streamdevice_camera_ioc/
            ├── configure/
            │   └── RELEASE
            ├── streamdevice_cameraApp/
            │   ├── Db/
            │   │   ├── Makefile
            │   │   ├── camera.db
            │   │   └── stream_camera.proto
            │   └── src/
            │       ├── Makefile
            │       └── streamdevice_cameraMain.cpp
            ├── iocBoot/
            │   └── iocstreamdevice_camera/
            │       ├── Makefile
            │       └── st.cmd
            └── Makefile
```

After compilation, EPICS also generates directories such as `bin/`, `db/`, `dbd/`, `lib/` and architecture-specific build directories.

These generated files are excluded from Git.

## 4. Generating the Conventional IOC

The IOC was generated using the EPICS Base application templates.

From the project root:

```bash
mkdir -p epics/streamdevice_camera/streamdevice_camera_ioc
cd epics/streamdevice_camera/streamdevice_camera_ioc
```

Generate the IOC application:

```bash
makeBaseApp.pl -t ioc streamdevice_camera
```

This creates the application source directory and the EPICS build configuration.

Generate the IOC boot directory:

```bash
makeBaseApp.pl -i -t ioc streamdevice_camera
```

When prompted for the application name, select `streamdevice_camera`.

This creates:

```text
iocBoot/iocstreamdevice_camera/
```

**For users cloning this repository:** The IOC skeleton is already included. These generation commands are provided to explain how the application was created. Do not run them again inside the existing IOC directory.

## 5. Configuring External Dependencies

The IOC must locate three external components:

- EPICS Base
- asyn
- StreamDevice

These dependencies are configured in:

```text
configure/RELEASE
```

The original Raspberry Pi installation uses:

```makefile
include /home/aparna/projects/epics/support/modules/RELEASE.local
```

The shared configuration contains:

```makefile
SUPPORT=/home/aparna/projects/epics/support/modules
EPICS_BASE=/home/aparna/projects/epics/base
ASYN=$(SUPPORT)/asyn
STREAM=$(SUPPORT)/StreamDevice
CALC=
PCRE=
```

The IOC's `configure/RELEASE` also defines the EPICS Base location.

**Reproducing on another system:** Update these paths to match the local EPICS installation. The absolute paths shown here are specific to the original Raspberry Pi environment.

The `RELEASE` configuration tells the EPICS build system where external modules are installed. It does not, by itself, determine which libraries are linked into the IOC.

## 6. IOC Source Makefile

The IOC executable is configured in:

```text
streamdevice_cameraApp/src/Makefile
```

The important sections are described below.

### 6.1 IOC executable

```makefile
PROD_IOC = streamdevice_camera
```

This specifies the name of the executable to build.

### 6.2 Database definitions

The application includes EPICS Base, asyn and StreamDevice definitions.

The relevant configuration used in the working build is:

```makefile
streamdevice_camera_DBD += base.dbd
streamdevice_camera_DBD += asyn.dbd
streamdevice_camera_DBD += drvAsynIPPort.dbd
streamdevice_camera_DBD += stream.dbd
```

The DBD files declare record types, device support and registration functions available to the IOC.

The asyn IP port registration allows the IOC to configure TCP/IP communication.

### 6.3 Libraries

The IOC links against StreamDevice and asyn:

```makefile
streamdevice_camera_LIBS += stream
streamdevice_camera_LIBS += asyn
```

It also links the standard EPICS Base IOC libraries:

```makefile
streamdevice_camera_LIBS += $(EPICS_BASE_IOC_LIBS)
```

The DBD definitions and libraries serve different purposes:

- **DBD files** declare the EPICS components to register.
- **Libraries** contain the compiled implementations of those components.

Both are required for the corresponding functionality to be available.

## 7. EPICS Database — `camera.db`

The source database is located at:

```text
streamdevice_cameraApp/Db/camera.db
```

The current record is:

```text
record(stringin, "$(P)$(R)GetStatus") {
    field(DESC, "Camera acquisition status")
    field(DTYP, "stream")
    field(INP, "@stream_camera.proto getStatus $(PORT)")
    field(SCAN, "Passive")
}
```

### 7.1 Record type

```text
record(stringin, "$(P)$(R)GetStatus")
```

This defines a string input record.

The record is used because the Python server returns text such as `IDLE`.

### 7.2 Database macros

The database uses:

| Macro | Purpose | Example |
|---|---|---|
| `P` | Device prefix | `CAM:` |
| `R` | Additional record-name component | Empty |
| `PORT` | asyn port name | `CAM_PORT` |

When loaded with these values:

```text
P=CAM:,R=,PORT=CAM_PORT
```

the record becomes:

```text
CAM:GetStatus
```

Macros allow the same database to be reused for different devices or port names.

### 7.3 Device support

```text
field(DTYP, "stream")
```

This tells EPICS to use StreamDevice when processing the record.

### 7.4 Input link

```text
field(INP, "@stream_camera.proto getStatus $(PORT)")
```

The input link identifies three things:

| Component | Meaning |
|---|---|
| `stream_camera.proto` | StreamDevice protocol file |
| `getStatus` | Protocol operation |
| `$(PORT)` | Configured asyn port |

After macro substitution, the input link becomes:

```text
@stream_camera.proto getStatus CAM_PORT
```

### 7.5 Passive processing

```text
field(SCAN, "Passive")
```

The record is not periodically scanned.

Instead, a fresh status request can be triggered explicitly through its `.PROC` field.

This avoids continuously sending `STATUS?` commands to the Python service.

## 8. StreamDevice Protocol — `stream_camera.proto`

The protocol source is located at:

```text
streamdevice_cameraApp/Db/stream_camera.proto
```

Its current contents are:

```text
Terminator = LF;

getStatus {
    out "STATUS?";
    in "%s";
}
```

### 8.1 Message terminator

```text
Terminator = LF;
```

This specifies a line-feed character (`\n`) as the message terminator.

The actual transmitted request is:

```text
STATUS?\n
```

The expected response is:

```text
IDLE\n
```

TCP transports a stream of bytes and does not inherently preserve command boundaries. A terminator provides a way to identify complete text messages.

### 8.2 Protocol operation

```text
getStatus {
    out "STATUS?";
    in "%s";
}
```

`getStatus` is the name of a StreamDevice protocol operation.

It is referenced by the EPICS database, but the name itself is not sent to Python.

The `out` statement sends the command, while the `in` statement parses the returned string.

### 8.3 Why the protocol is separate

The database defines which operation should be performed.

The protocol file defines the command and response format.

The Python server implements the command.

For example, changing the Python command from `STATUS?` to another text command would generally require updating the protocol and Python service, not necessarily the EPICS record name.

## 9. Installing Database and Protocol Files

The source files are installed using:

```text
streamdevice_cameraApp/Db/Makefile
```

The relevant entries are:

```makefile
DB += camera.db
DB += stream_camera.proto
```

After building, the files are installed into:

```text
streamdevice_camera_ioc/db/
```

The installed directory should contain:

```text
camera.db
stream_camera.proto
```

Always edit the source files in `streamdevice_cameraApp/Db/`.

Changes made directly to installed copies can be overwritten during the next build.

## 10. Python TCP Server

The Python server is implemented in:

```text
acquisition/camera_server.py
```

It uses Python's built-in `socket` module.

### 10.1 Server address

```python
HOST = "127.0.0.1"
PORT = 5000
```

`127.0.0.1` is the loopback address.

Because both the IOC and Python service run on the Raspberry Pi, the server does not need to listen on the Pi's external network interface.

Port `5000` is a chosen application port, not an EPICS-specific port.

### 10.2 Socket setup

The server creates a TCP socket:

```python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

It binds to the configured address and starts listening:

```python
server.bind((HOST, PORT))
server.listen(1)
```

### 10.3 Receiving commands

The server accepts a client connection and receives bytes using:

```python
connection, address = server.accept()
data = connection.recv(1024)
```

The received bytes are decoded into text:

```python
command = data.decode("utf-8").strip()
```

The current implementation recognizes:

```python
if command == "STATUS?":
    response = "IDLE\n"
else:
    response = "ERROR\n"
```

The response is transmitted using:

```python
connection.sendall(response.encode("utf-8"))
```

### 10.4 Current limitations

The Python server is intended as an initial communication test.

It handles one active client connection at a time and assumes that a complete command is received in one `recv()` operation.

For more robust operation, the server should eventually buffer incoming data and process complete newline-terminated messages.

The server currently returns a fixed `IDLE` response. It does not query Picamera2 or the physical camera.

## 11. IOC Startup — `st.cmd`

The IOC startup script is located at:

```text
iocBoot/iocstreamdevice_camera/st.cmd
```

Its essential configuration is:

```text
dbLoadDatabase "../../dbd/streamdevice_camera.dbd"
streamdevice_camera_registerRecordDeviceDriver(pdbbase)

drvAsynIPPortConfigure("CAM_PORT", "127.0.0.1:5000", 0, 0, 0)

epicsEnvSet("STREAM_PROTOCOL_PATH", "../../db")

dbLoadRecords("../../db/camera.db", "P=CAM:,R=,PORT=CAM_PORT")

iocInit()
```

### 11.1 Loading and registering support

```text
dbLoadDatabase "../../dbd/streamdevice_camera.dbd"
streamdevice_camera_registerRecordDeviceDriver(pdbbase)
```

These commands load and register the record and device-support definitions compiled into the IOC.

### 11.2 Configuring asyn TCP/IP

```text
drvAsynIPPortConfigure("CAM_PORT", "127.0.0.1:5000", 0, 0, 0)
```

This creates the named asyn communication port `CAM_PORT`.

The port connects to the Python TCP service listening at `127.0.0.1:5000`.

The `.proto` file does not contain the server address. It uses the port configured here.

### 11.3 Protocol search path

```text
epicsEnvSet("STREAM_PROTOCOL_PATH", "../../db")
```

This tells StreamDevice where to find the installed protocol file.

### 11.4 Loading records

```text
dbLoadRecords("../../db/camera.db", "P=CAM:,R=,PORT=CAM_PORT")
```

This loads the database and supplies its macro values.

### 11.5 IOC initialization

```text
iocInit()
```

This initializes the IOC after the support components, communication ports and database records have been configured.

## 12. Building the IOC

From the repository root:

```bash
cd epics/streamdevice_camera/streamdevice_camera_ioc
```

Build:

```bash
make -j2
```

Verify the executable:

```bash
ls bin/linux-arm/streamdevice_camera
```

Verify the installed database and protocol:

```bash
ls db
```

Expected:

```text
camera.db
stream_camera.proto
```

The IOC was successfully compiled and linked against EPICS Base, asyn and StreamDevice on the Raspberry Pi.

## 13. Running the System

The Python server and IOC run as separate processes.

### Terminal 1 — Start Python

From the repository root:

```bash
python3 acquisition/camera_server.py
```

Expected:

```text
Camera server listening on 127.0.0.1:5000
```

Leave the server running.

### Terminal 2 — Start the IOC

Navigate to:

```bash
cd epics/streamdevice_camera/streamdevice_camera_ioc/iocBoot/iocstreamdevice_camera
```

Run:

```bash
./st.cmd
```

The startup script uses the executable specified in its first line:

```text
#!../../bin/linux-arm/streamdevice_camera
```

If necessary, enable executable permission:

```bash
chmod +x st.cmd
```

The IOC should initialize and display the `epics>` prompt.

### Terminal 3 — Test the PV

On the Raspberry Pi, request a fresh status:

```bash
caput CAM:GetStatus.PROC 1
```

Then read it:

```bash
caget CAM:GetStatus
```

Expected:

```text
CAM:GetStatus    IDLE
```

The Python terminal should show:

```text
Received command: STATUS?
```

This confirms communication through EPICS, StreamDevice, asyn and the Python service.

## 14. Understanding On-Demand Status Requests

The `CAM:GetStatus` record uses passive processing.

Therefore, running:

```bash
caget CAM:GetStatus
```

normally reads the value already stored in the EPICS record.

It does not necessarily send a new command to Python.

To explicitly request a fresh status:

```bash
caput CAM:GetStatus.PROC 1
```

The complete sequence is:

```text
caput CAM:GetStatus.PROC 1
              |
              v
      EPICS record processing
              |
              v
       StreamDevice getStatus
              |
              v
       Send STATUS? over TCP
              |
              v
         Python server
              |
              v
         Return IDLE
              |
              v
       Update CAM:GetStatus
```

A subsequent `caget` reads the updated value.

StreamDevice processing may be asynchronous, so clients requiring a guaranteed fresh result should account for completion rather than assume that every command and readback is instantaneous.

## 15. Remote Access from Windows / WSL

The IOC runs on the Raspberry Pi, but remote EPICS clients can access its PVs through Channel Access.

The development environment uses WSL Linux on Windows.

### 15.1 Configure EPICS tools in WSL

A separate EPICS Base installation is available at:

```text
~/EPICS/epics-base
```

The WSL environment can be configured with:

```bash
export EPICS_BASE="$HOME/EPICS/epics-base"
export PATH="$EPICS_BASE/bin/linux-x86_64:$PATH"
```

### 15.2 Configure IOC discovery

WSL networking may prevent automatic EPICS UDP broadcast discovery.

To specify the Raspberry Pi address explicitly:

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=192.168.0.176
```

Replace `192.168.0.176` with the Pi's current IP address.

On the Pi, check:

```bash
hostname -I
```

### 15.3 Read and process the PV remotely

From WSL:

```bash
caget CAM:GetStatus
```

To request a fresh status:

```bash
caput CAM:GetStatus.PROC 1
caget CAM:GetStatus
```

Remote communication was successfully verified.

The WSL client communicates with the EPICS IOC, not directly with the Python TCP server.

## 16. Multiple Clients and EPICS

One important motivation for using EPICS is that multiple applications can access the same instrument through a common IOC.

For example:

```text
Operator GUI ──────┐
                   |
Python analysis ───┼──> EPICS IOC
                   |         |
Remote terminal ───┘         v
                         StreamDevice
                              |
                           asyn TCP
                              |
                         Python server
```

The EPICS IOC exposes PVs to multiple Channel Access clients.

Those clients do not each require a separate connection to the Python service.

The current Python server handles one active TCP client at a time, which is sufficient for this initial IOC-to-service architecture.

As the project develops, simultaneous control requests and camera-busy conditions will require explicit handling.

## 17. Current Limitations

The working system demonstrates communication infrastructure only.

Current limitations include:

- The Python service returns a fixed status.
- Picamera2 is not yet integrated.
- No physical camera acquisition is performed through EPICS.
- No image data is exposed through EPICS.
- No exposure or gain PVs are implemented.
- TCP command framing and error recovery need improvement.
- Acquisition state management has not yet been implemented.

## 18. Next Development Steps

The next milestone is to connect the existing Python service to Picamera2 while preserving the EPICS communication interface.

Planned additions include:

- Reading actual camera information.
- Implementing an acquisition command.
- Setting exposure and gain.
- Reporting acquisition status.
- Saving acquired images.
- Tracking image counters and errors.

The areaDetector implementation will be developed separately rather than incorporated into this conventional StreamDevice IOC.

## 19. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [StreamDevice Documentation](https://paulscherrerinstitute.github.io/StreamDevice/)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)

---

**Implementation status:** EPICS-to-Python TCP communication and remote Channel Access have been successfully demonstrated. Picamera2 integration is the next milestone.
