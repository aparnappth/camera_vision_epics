# StreamDevice Camera IOC — Implementation Guide

This guide documents the conventional EPICS IOC developed for the [EPICS-Controlled Camera Characterization and Vision Platform](../README.md). It covers the original simulated TCP camera service (Milestone 1) and the Picamera2/IMX219 integration with Channel Access (CA) and PVAccess (PVA) support (Milestone 2).

For dependency installation, see [EPICS Environment Setup](epics_setup.md). For errors encountered during development, see [Troubleshooting](troubleshooting.md).

## 1. Objective and implementation status

The IOC communicates with a Python TCP service through **asyn** and **StreamDevice**. The Python service runs on a Raspberry Pi Zero 2 W with a Sony IMX219 CSI camera.

### Milestone 1 — Simulated camera communication

- Created a conventional EPICS IOC using the EPICS Base application templates.
- Established a TCP command/response interface between StreamDevice and `acquisition/camera_server_simulator.py`.
- Implemented `STATUS?`, returning a simulated `IDLE` response.
- Verified local and remote Channel Access from the Raspberry Pi and Windows Subsystem for Linux (WSL).

### Milestone 2 — Picamera2 and PVAccess

- Detected the physical IMX219 through Picamera2 and inspected its properties and controls.
- Added `acquisition/picamera2_server.py` while retaining the original simulator.
- Implemented model-name-based discovery and **lazy initialization**: the camera is opened on the first supported `STATUS?` request, not when the TCP server starts.
- Reused the same camera object for later status requests, and released it on normal keyboard-interrupt shutdown.
- Enabled PVAccess by linking the PVA server and **QSRV**, which exposes ordinary IOC database records to PVA clients.
- Verified that both `caget` and `pvget` can access `CAM:GetStatus`.

**Scope of the current implementation:** `IDLE` is a software-maintained state meaning Picamera2 successfully opened the camera. It is not a measurement of ongoing hardware health, and no image capture has yet been implemented through EPICS.

## 2. Communication architecture

```text
              EPICS clients
         +---------+---------+
         |                   |
    Channel Access       PVAccess
    caget / caput        pvget / pvput
         |                   |
         |                  QSRV
         +---------+---------+
                   |
             EPICS IOC
             camera.db
                   |
              StreamDevice
           stream_camera.proto
                   |
             asyn TCP/IP
            127.0.0.1:5000
                   |
          Python TCP service
                   |
               Picamera2
                   |
               libcamera
                   |
                IMX219
```

The IOC and Python service are separate processes on the Raspberry Pi. `camera.db` defines EPICS records; `stream_camera.proto` defines the wire commands; asyn provides the TCP connection; and the Python service interprets those commands. **The `.proto` file does not invoke Picamera2 methods directly.** It sends text such as `STATUS?`, which Python translates into an operation.

The simulator uses the same TCP interface but does not access the physical camera. CA and PVA are alternative client protocols for the same IOC records; neither replaces StreamDevice.

## 3. Repository structure

```text
camera_vision_epics/
├── README.md
├── acquisition/
│   ├── camera_server_simulator.py
│   └── picamera2_server.py
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       └── epics_device_integration.md
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

The build generates `bin/`, `db/`, `dbd/`, `lib/` and architecture-specific output directories. These are build artifacts, not source files, and are excluded from Git.

## 4. Generating the IOC application

The IOC was originally generated with EPICS Base application templates:

```bash
mkdir -p epics/streamdevice_camera/streamdevice_camera_ioc
cd epics/streamdevice_camera/streamdevice_camera_ioc
makeBaseApp.pl -t ioc streamdevice_camera
makeBaseApp.pl -i -t ioc streamdevice_camera
```

Select `streamdevice_camera` when prompted for the application name. This creates the source tree and `iocBoot/iocstreamdevice_camera/`.

**If cloning this repository, do not rerun these commands inside the existing IOC directory.** The generated application skeleton is already version-controlled.

## 5. External dependencies and RELEASE configuration

The IOC uses EPICS Base, asyn and StreamDevice. The original Raspberry Pi environment was configured through `configure/RELEASE` with:

```makefile
include /home/aparna/projects/epics/support/modules/RELEASE.local
```

The shared release configuration contains paths of the following form:

```makefile
SUPPORT=/home/aparna/projects/epics/support/modules
EPICS_BASE=/home/aparna/projects/epics/base
ASYN=$(SUPPORT)/asyn
STREAM=$(SUPPORT)/StreamDevice
CALC=
PCRE=
```

These are machine-specific absolute paths. Adjust them to match your installation when reproducing the build. The RELEASE file tells the build system where dependencies are located; the IOC Makefile determines which components are registered and linked. In this project, the PVA and QSRV components were available in the existing EPICS Base installation.

The versions used in the development environment were EPICS Base R7.0.10, asyn R4-46 and StreamDevice 2.8.26. Check compatibility when using other versions.

## 6. IOC source Makefile

The IOC executable is configured in `streamdevice_cameraApp/src/Makefile`.

### 6.1 Executable and database definitions

```makefile
PROD_IOC = streamdevice_camera
DBD += streamdevice_camera.dbd

streamdevice_camera_DBD += base.dbd
streamdevice_camera_DBD += asyn.dbd
streamdevice_camera_DBD += drvAsynIPPort.dbd
streamdevice_camera_DBD += stream.dbd

# PVAccess server and IOC database provider
streamdevice_camera_DBD += PVAServerRegister.dbd
streamdevice_camera_DBD += qsrv.dbd
```

DBD files declare record types, device support, drivers and registration functions. `drvAsynIPPort.dbd` supports configuration of the asyn TCP/IP port. `PVAServerRegister.dbd` registers PVA server startup, and `qsrv.dbd` registers the QSRV provider.

### 6.2 Libraries

The relevant linked libraries are:

```makefile
streamdevice_camera_LIBS += stream
streamdevice_camera_LIBS += asyn

streamdevice_camera_LIBS += qsrv
streamdevice_camera_LIBS += pvAccessIOC
streamdevice_camera_LIBS += pvAccess
streamdevice_camera_LIBS += pvData

streamdevice_camera_LIBS += $(EPICS_BASE_IOC_LIBS)
```

Libraries contain the compiled implementations; DBD files provide the declarations needed by IOC registration. Both are needed. The complete Makefile also retains the generated record/device-driver registration source and IOC entry point.

## 7. EPICS database — `camera.db`

Source: `streamdevice_cameraApp/Db/camera.db`.

```text
record(stringin, "$(P)$(R)GetStatus") {
    field(DESC, "Camera acquisition status")
    field(DTYP, "stream")
    field(INP, "@stream_camera.proto getStatus $(PORT)")
    field(SCAN, "Passive")
}
```

- `stringin` stores a string returned by the service, such as `IDLE`.
- `DTYP = stream` selects StreamDevice record support.
- `INP` identifies the protocol file, operation name and asyn port.
- `SCAN = Passive` means the IOC does not poll this record periodically; processing must be triggered explicitly or by another supported processing mechanism.

### 7.1 Macros

| Macro | Meaning | Example |
|---|---|---|
| `P` | PV prefix | `CAM:` |
| `R` | Additional record-name suffix/prefix component | empty |
| `PORT` | asyn port name | `CAM_PORT` |

Loading with `P=CAM:,R=,PORT=CAM_PORT` creates the record `CAM:GetStatus`. After macro substitution, the input link is:

```text
@stream_camera.proto getStatus CAM_PORT
```

**Configuration check:** During development, the IOC startup output also showed an unused-looking `SCAN=1 second` macro argument. The displayed database record has a literal `field(SCAN, "Passive")`, so that extra macro does not change its SCAN field unless the source database actually references `$(SCAN)`. Confirm the runtime value with `caget CAM:GetStatus.SCAN` and document any future change consistently.

## 8. StreamDevice protocol — `stream_camera.proto`

Source: `streamdevice_cameraApp/Db/stream_camera.proto`.

```text
Terminator = LF;

getStatus {
    out "STATUS?";
    in "%s";
}
```

`Terminator = LF` specifies a newline (`\n`) for the request and response. The `out` statement sends `STATUS?`; the `in` statement parses the returned string. `getStatus` is the operation name referenced by the database; **that name is not sent to Python**.

The exchange is:

```text
IOC → Python: STATUS?\n
Python → IOC: IDLE\n
```

The record chooses the operation, the `.proto` file defines the wire format, and Python implements the command. TCP is a byte stream; a newline is the protocol's intended command delimiter.

## 9. Installing database and protocol files

In `streamdevice_cameraApp/Db/Makefile`, the working installation includes:

```makefile
DB += camera.db
DB += stream_camera.proto
```

After `make`, both should appear in the IOC root's installed `db/` directory:

```bash
ls db
```

Expected filenames:

```text
camera.db
stream_camera.proto
```

**Edit the sources in `streamdevice_cameraApp/Db/`, not the generated copies in `db/`.** Installed files can be overwritten by the next build.

## 10. Python TCP camera services

Both services listen on the same local address:

```python
HOST = "127.0.0.1"
PORT = 5000
```

Only one can run on that address and port at a time. Binding to `127.0.0.1` prevents direct TCP connections to this Python service from other computers; remote EPICS clients connect to the IOC instead.

### 10.1 Simulator

`acquisition/camera_server_simulator.py` is the Milestone 1 implementation. It receives `STATUS?` and responds with a fixed value:

```python
response = "IDLE\n"
```

It does not use Picamera2. Keep it as a way to test the IOC and StreamDevice communication independently of the camera.

### 10.2 Real Picamera2 service: initial state

`acquisition/picamera2_server.py` imports:

```python
from picamera2 import Picamera2
import socket
```

The server starts with:

```python
camera = None
camera_status = "CLOSED"
```

`None` means no camera object has been created. Starting the TCP server alone does not open the IMX219.

### 10.3 Finding the camera by model name

```python
def find_camera():
    cameras = Picamera2.global_camera_info()

    for cam in cameras:
        if cam["Model"] == "imx219":
            return cam["Num"]

    raise RuntimeError("IMX219 camera not found")
```

This searches Picamera2's discovered cameras and returns the index of the first IMX219. It raises an error if none is found. If several IMX219 cameras are present, this approach does not distinguish them by unique hardware ID.

### 10.4 Lazy initialization and global state

```python
def initialize_camera():
    global camera, camera_status

    if camera is None:
        camera_id = find_camera()
        camera = Picamera2(camera_id)
        camera_status = "IDLE"
        print("IMX219 camera initialized successfully")

    return camera
```

The `global` declaration allows the function to reassign the variables defined at module level. The new values persist after the function returns, for as long as the Python process runs. The `if camera is None` check opens the camera only once; later calls reuse the object.

Here, `IDLE` means the camera was opened successfully and no acquisition was started. It is **not** a live hardware-health check. `Picamera2(...)` opens/acquires the camera; image streaming requires further configuration and startup.

### 10.5 Socket creation and listening

```python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)
```

- `AF_INET` selects IPv4; `SOCK_STREAM` selects TCP.
- `SO_REUSEADDR` assists with address reuse during some restart scenarios. It does not permit two servers to bind the same active address/port combination.
- `bind()` assigns the local address and port.
- `listen(1)` requests a pending-connection backlog of one; it does **not** limit the total number of clients over the server's lifetime.

### 10.6 Outer and inner loops

The relevant current implementation is:

```python
try:
    while True:
        # Wait for a TCP connection from the IOC
        connection, address = server.accept()
        print(f"Connected by {address}")

        while True:
            # Wait for bytes on the accepted connection
            data = connection.recv(1024)

            if not data:
                break

            command = data.decode("utf-8").strip()
            print(f"Received command: {command}")

            if command == "STATUS?":
                initialize_camera()
                response = camera_status + "\n"
            else:
                response = "ERROR\n"

            connection.sendall(response.encode("utf-8"))

        connection.close()

except KeyboardInterrupt:
    print("\nKeyboard interrupt: Stopping camera server")

finally:
    server.close()
    if camera is not None:
        camera.close()
        print("Camera released")
```

**Execution sequence:**

1. `accept()` blocks until a TCP client connects. Establishing a TCP connection is separate from sending `STATUS?`.
2. Once accepted, Python enters the inner loop and blocks at `recv()` until data arrives or the connection closes.
3. On `STATUS?`, Python initializes the camera if needed, prepares `IDLE\n`, and sends it back using `sendall()`.
4. The inner loop repeats and waits for more data on the **same** connection.
5. If the client closes its sending direction normally, `recv()` returns the empty **bytes** object `b""`. `if not data: break` exits the inner loop, then `connection.close()` runs.
6. The outer loop waits for a new connection. It does not exit merely because the IOC disconnected.
7. Pressing Ctrl+C normally raises `KeyboardInterrupt`, causing the outer `finally` to close the listening socket and camera.

The server handles one accepted client at a time. Multiple EPICS CA/PVA clients can still communicate with the **IOC** without each opening a separate Python TCP connection.

### 10.7 Current implementation limitations

The current code treats each `recv(1024)` result as one complete command. TCP does not guarantee this: commands may be split across reads or combined into a single read. Before expanding the protocol, implement newline-delimited command framing and test repeated commands.

The code also does not yet send a structured error response if camera initialization fails; unexpected exceptions may terminate the server. Cleanup of the accepted client socket is not guaranteed on every exceptional path. These are future robustness improvements, not features already implemented.

## 11. IOC startup — `st.cmd`

Source: `iocBoot/iocstreamdevice_camera/st.cmd`.

The essential startup commands are:

```text
dbLoadDatabase "../../dbd/streamdevice_camera.dbd"
streamdevice_camera_registerRecordDeviceDriver(pdbbase)

drvAsynIPPortConfigure("CAM_PORT", "127.0.0.1:5000", 0, 0, 0)
epicsEnvSet("STREAM_PROTOCOL_PATH", "../../db")
dbLoadRecords("../../db/camera.db", "P=CAM:,R=,PORT=CAM_PORT,SCAN=1 second")

iocInit()
```

The `dbLoadDatabase` and registration commands load the compiled record/device support. `drvAsynIPPortConfigure` defines `CAM_PORT` and points it to the Python TCP listener. `STREAM_PROTOCOL_PATH` locates the installed `.proto` file. `dbLoadRecords` loads the database with macros; `iocInit()` starts IOC operation.

**Note on `SCAN`:** The startup macro string shown during testing included `SCAN=1 second`, while the database source shown in this guide sets `SCAN` literally to `Passive`. The macro has no effect unless the database uses `$(SCAN)`. Verify the actual runtime setting before claiming that the IOC is periodically scanning.

If the Python service is not running at IOC startup, asyn may report a connection warning. This is separate from CA/PVA availability; start the Python server and check reconnection before diagnosing camera communication.

## 12. Build and verify the IOC

From the repository root:

```bash
cd epics/streamdevice_camera/streamdevice_camera_ioc
make -j2
```

Check the generated executable and installed files:

```bash
ls bin/linux-arm/streamdevice_camera
ls db
```

Check that PVA server and QSRV registrations are included:

```bash
grep -i -E 'qsrv|registerStartPVAServer' dbd/streamdevice_camera.dbd
```

The working build included:

```text
registrar(QSRVRegistrar)
registrar(registerStartPVAServer)
```

These registrations show the components are included in the generated IOC DBD. Successful runtime access must still be tested separately.

## 13. Run and test the system

### Terminal 1 — Python server

From the repository root, run **one** of:

```bash
# Real camera server
python3 -u acquisition/picamera2_server.py
```

or:

```bash
# Original simulated service
python3 -u acquisition/camera_server_simulator.py
```

`-u` makes terminal output unbuffered. The real camera server waits for a command before opening Picamera2. Stop one server before starting the other.

### Terminal 2 — IOC

```bash
cd epics/streamdevice_camera/streamdevice_camera_ioc/iocBoot/iocstreamdevice_camera
./st.cmd
```

The startup script's first line points to the built executable:

```text
#!../../bin/linux-arm/streamdevice_camera
```

If needed, restore executable permission with `chmod +x st.cmd`. Wait for the `epics>` prompt and check for startup errors.

### Terminal 3 — Read a fresh status

With the passive record, explicitly request processing:

```bash
caput CAM:GetStatus.PROC 1
```

Then read the stored result using either interface:

```bash
caget CAM:GetStatus
pvget CAM:GetStatus
```

After successful processing, the expected status is `IDLE`. Because StreamDevice can process asynchronously, a read issued immediately after the trigger may need to wait for completion to guarantee freshness.

The Python terminal should print `Received command: STATUS?` and, on the first such request, `IMX219 camera initialized successfully`. Later requests reuse the same camera object.

### Shutdown

Stop the IOC from its `epics>` prompt with `exit`. Stop the Python server with Ctrl+C; its shutdown handler closes the listening socket and releases the camera if it was opened.

## 14. Channel Access and PVAccess with QSRV

### 14.1 Why PVAccess initially timed out

`pvget` was installed, and the PVA libraries (`pvAccessIOC`, `pvAccess`, `pvData`) were available, but the IOC initially registered only the PVA server. At runtime it reported:

```text
ServerContext configured with no Providers will do nothing!
```

TCP port 5075 and UDP port 5076 were open, but `pvget CAM:GetStatus` timed out. The missing piece was the **QSRV IOC database provider**. Adding `qsrv.dbd` and linking `qsrv` exposed the IOC's ordinary records through PVA. The warning disappeared and `pvget` worked.

### 14.2 Build configuration

The required entries in `streamdevice_cameraApp/src/Makefile` are:

```makefile
streamdevice_camera_DBD += PVAServerRegister.dbd
streamdevice_camera_DBD += qsrv.dbd

streamdevice_camera_LIBS += qsrv
streamdevice_camera_LIBS += pvAccessIOC
streamdevice_camera_LIBS += pvAccess
streamdevice_camera_LIBS += pvData
```

They are used alongside `base.dbd`, `asyn.dbd`, `drvAsynIPPort.dbd`, `stream.dbd`, `stream`, `asyn`, and `$(EPICS_BASE_IOC_LIBS)`.

### 14.3 Diagnostics

The PVA server's actual IOC-shell commands in this installation were identified from `PVAServerRegister.cpp`:

```text
pvasr 1
pval 1
```

`pvasr` reports server information; `pval` lists PVs from registered providers. Other command names attempted during troubleshooting (`pvaSrv`, `pvaServerReport`, `pvaProviderList`) were not registered in this build.

Default PVA ports in this installation were TCP 5075 and UDP 5076. To inspect sockets on the Raspberry Pi:

```bash
ss -ltnp | grep ':5075'
ss -lunp | grep ':5076'
```

Open ports alone do not prove that an IOC database provider is registered. A successful `pvget` is the functional test.

### 14.4 Client behavior

```bash
caget CAM:GetStatus    # Channel Access
pvget CAM:GetStatus    # PVAccess
```

Both access the same IOC record. With `SCAN = Passive`, both normally return the **stored** value; neither automatically sends a fresh `STATUS?` to the Python service. `pvput` is the PVA write counterpart of `caput`, but no new camera-setting PVs have yet been implemented.

## 15. On-demand status: current behavior and open requirement

The distinction between **reading a PV** and **processing a record** is important:

```text
caput CAM:GetStatus.PROC 1
         |
         v
   IOC processes record
         |
         v
 StreamDevice sends STATUS?
         |
         v
 Python initializes/uses IMX219
         |
         v
 Returns IDLE; IOC stores result
         |
         v
 caget / pvget read stored value
```

`caput ...PROC 1` does not set the camera status to `1`; it asks EPICS to process the record. `caget CAM:GetStatus.PROC` would only read the processing field and would not perform that write.

Setting `PINI = YES` requests processing at IOC initialization; `SCAN = I/O Intr` is for device-support-driven update notifications where implemented; `SCAN = 1 second` causes periodic processing. None of these makes a standard `caget` or `pvget` automatically perform a fresh StreamDevice transaction on each read.

**Desired behavior (not yet implemented):** One user PV read should trigger a fresh camera-status request and return its result, without manual `.PROC` writes and without continuous polling. We have deliberately not adopted a wrapper command as the final design. A suitable IOC/device-support approach remains to be investigated.

## 16. Remote access from Windows / WSL

The IOC runs on the Raspberry Pi; WSL clients communicate with the IOC, not directly with the loopback-only Python TCP server.

The WSL EPICS Base installation was located at:

```text
~/EPICS/epics-base
```

Example shell setup:

```bash
export EPICS_BASE="$HOME/EPICS/epics-base"
export PATH="$EPICS_BASE/bin/linux-x86_64:$PATH"
```

If CA discovery does not find the Raspberry Pi automatically, determine the Pi's current IP using `hostname -I` on the Pi, then in WSL use (example address):

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=192.168.0.176
```

Test:

```bash
caget CAM:GetStatus
caput CAM:GetStatus.PROC 1
caget CAM:GetStatus
```

This remote CA configuration was successfully tested. Remote PVA discovery from WSL was not separately verified during this milestone; it may need its own network configuration.

## 17. Multiple clients and access considerations

Multiple operator interfaces, scripts and remote terminals can access the IOC over CA or PVA. They do not each need a separate TCP connection to the Python camera service. The current Python implementation handles one accepted TCP client at a time, which is adequate for the intended IOC-to-service connection.

The Python service binds to `127.0.0.1`, limiting direct remote access to that socket. **This does not restrict access to the EPICS IOC itself.** For deployment beyond a trusted laboratory network, consider IOC access-security rules, firewall restrictions and appropriately secured networking. These protections have not been implemented as part of this milestone.

## 18. Current limitations and next development steps

### Implemented and tested

- Simulated `STATUS?` response through StreamDevice/asyn.
- Real IMX219 discovery and opening through Picamera2.
- Lazy initialization and reuse of a software-held camera object.
- Repeated TCP command handling on a single accepted connection.
- Channel Access and PVAccess access to `CAM:GetStatus` using QSRV.
- Normal Ctrl+C shutdown and camera release.

### Not yet implemented

- Image capture or saving initiated through EPICS.
- Exposure-time and analogue-gain readback/control PVs.
- Accurate acquisition-state transitions and hardware-health monitoring.
- Robust newline-delimited TCP parsing, recovery and per-client exception cleanup.
- A fresh status query automatically triggered by a single PV read.
- Camera image transfer through EPICS or areaDetector.

The next development milestone is to implement actual camera acquisition and then introduce exposure/gain controls. The areaDetector approach remains a separate planned implementation, not part of this StreamDevice IOC.

## 19. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [StreamDevice Documentation](https://paulscherrerinstitute.github.io/StreamDevice/)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)

---

**Implementation status:** Milestone 1 (simulated TCP communication) and the initial Milestone 2 (Picamera2 camera initialization and CA/PVA access through QSRV) have been demonstrated. Image acquisition and on-demand fresh-value semantics remain future work.
