# StreamDevice Camera IOC — Implementation Guide

This guide documents the conventional EPICS IOC developed for the [EPICS-Controlled Camera Characterization and Vision Platform](../README.md). It covers the simulated TCP service, the conventional IOC and its CA/PVA support, standalone Picamera2 acquisition, and the expanded Python TCP camera server tested in October 2026. The expanded acquisition commands and event-driven status/file-path monitoring are integrated into the IOC and have been tested through Channel Access and PVAccess. The separate Python PVAccess image publisher and Phoebus display are also described at an architectural level. Section 23 describes the 26 October TCP refactoring and actual-value monitoring. Section 24 documents the EPICS-controlled scanning implementation tested on 27 October. Older configurations are retained as explicitly historical examples; use the later sections for current PV names and operation. Shared-port communication limitations remain documented below.

For dependency installation, see [EPICS Environment Setup](epics_setup.md). For errors encountered during development, see [Troubleshooting](troubleshooting.md).

## 1. Objective and implementation status

The IOC communicates with a Python TCP service through **asyn** and **StreamDevice** on a Raspberry Pi Zero 2 W with a Sony IMX219 CSI camera. Development separates EPICS integration from direct Python/TCP testing.

### Milestone 1 — Simulated camera communication

- Created a conventional EPICS IOC using EPICS Base templates.
- Established StreamDevice/asyn TCP communication with `acquisition/camera_server_simulator.py`.
- Implemented `STATUS?` and verified local and remote Channel Access.

### Milestone 2 — Physical camera and PVAccess

- Discovered the IMX219 through Picamera2 and developed `acquisition/picamera2_server.py`, preserving the simulator.
- Initially opened the camera on `STATUS?`; **this behavior has since been changed** so a status query does not initialize the camera.
- Linked PVAccess and QSRV, enabling CA and PVA access to the existing `CAM:GetStatus` IOC record.

### Milestone 3 — Standalone and TCP-controlled acquisition

- Tested a standalone Picamera2 script at `acquisition/tests/test_camera_acquisition.py`.
- Captured JPEG and JSON metadata from the **same completed request**, with timestamp-matched filenames.
- Tested manual exposure and analogue gain against frame metadata.
- Implemented and tested TCP commands for camera lifecycle, settings, acquisition and latest file paths using Netcat.
- Verified single acquisition (returning to `IDLE`) and repeated acquisition while already `STREAMING`.
- Added centralized status changes, line-delimited TCP input, basic error handling and cleanup on detected disconnection.

**Historical checkpoint:** At Milestone 3, the expanded Python server was tested independently using Netcat. Milestone 4 subsequently integrated the controls and monitoring into EPICS (Section 20). Expanded PVAccess testing and automation are described in Section 21.

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
│   ├── picamera2_server.py
│   ├── pva_image_publisher.py
│   ├── tests/
│   │   └── test_camera_acquisition.py
│   └── images/   # generated files, ignored by Git
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── implementation_and_results.md
│   ├── troubleshooting.md
│   └── notes/
│       ├── epics_device_integration.md
│       ├── test_picamera2_acquisition.md
│       ├── automated_acquisition_and_characterization.md  # historical note
│       ├── tcp_connection_and_metadata_monitoring.md
│       └── pva_image_publisher.md
├── automation/
│   └── camera_scan.py
├── data/
│   └── scan/  # generated CSV files; ignored by Git
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
include /path/to/epics/support/modules/RELEASE.local
```

The shared release configuration contains paths of the following form:

```makefile
SUPPORT=/path/to/epics/support/modules
EPICS_BASE=/path/to/epics/base
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

## 7. EPICS database — `camera.db` (historical first version)

Source: `streamdevice_cameraApp/Db/camera.db`.

```text
record(stringin, "$(P)$(R)GetStatus") {
    field(DESC, "Camera acquisition status")
    field(DTYP, "stream")
    field(INP, "@stream_camera.proto getStatus $(PORT)")
    field(SCAN, "Passive")
}
```

- `stringin` stores a string returned by the service, such as `CLOSED` or `IDLE`.
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

## 8. StreamDevice protocol — `stream_camera.proto` (historical first version)

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
Python → IOC: CLOSED\n  (before the first camera operation, with the current server)
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

Both Python services bind to `127.0.0.1:5000`. Run only one at a time. Loopback binding limits direct TCP access to the Pi; remote CA/PVA clients connect to the IOC.

### 10.1 Simulator and standalone test

`acquisition/camera_server_simulator.py` implements the original fixed `STATUS?` response (`IDLE\n`) without camera hardware. `acquisition/tests/test_camera_acquisition.py` independently tests still configuration, 180-degree rotation, manual exposure/gain, JPEG capture, matching metadata and resource release. See [Standalone Picamera2 Acquisition Test](notes/test_picamera2_acquisition.md).

### 10.2 Camera state and centralized status updates

The real server starts with:

```python
camera = None
camera_status = "CLOSED"
auto_exposure = True
exposure_time = 20000   # microseconds
analogue_gain = 1.0
last_image_path = "NONE"
last_metadata_path = "NONE"
```

`update_camera_status(new_status)` changes the global `camera_status` only if the state differs. Status values are application-maintained, not independent hardware-health measurements.

| State | Meaning |
|---|---|
| `CLOSED` | Camera object is not initialized |
| `IDLE` | Initialized, not streaming |
| `STREAMING` | `camera.start()` is active; frames are produced without necessarily being displayed |
| `ACQUIRING` | Acquisition operation is in progress |
| `PREVIEWING` | Reserved for future live-preview integration |
| `ERROR` | A camera operation failed |

`STATUS?` reports the current state **without opening the camera**; `STATUS_DESC?` returns its explanation. The TCP server processes commands sequentially, so an `ACQUIRING` state is not necessarily observable through a second query until acquisition completes.

### 10.3 Camera discovery and lifecycle functions

`find_camera()` searches `Picamera2.global_camera_info()` for a model named `imx219`. `initialize_camera()` opens it only when `camera is None` and returns the existing object otherwise. The functions use the global name `camera` for the retained object and `cam` for local references or function parameters.

| Function | Responsibility |
|---|---|
| `initialize_camera()` | Find and open camera if needed; set `IDLE` |
| `configure_camera(cam)` | Create/apply still configuration with `Transform(hflip=1, vflip=1)` |
| `apply_camera_settings(cam)` | Apply automatic exposure, or manual exposure and gain |
| `start_camera()` | Initialize, configure, apply settings and start if not already streaming; set `STREAMING` |
| `stop_camera()` | Stop an active stream without closing the camera; set `IDLE` |
| `close_camera()` | Stop if needed, close, reset global object and set `CLOSED` |
| `acquire_image()` | Capture, save matched files, release request, restore streaming condition |

`Picamera2(...)` opens the camera, `configure()` prepares the pipeline, `start()` begins producing frames, `capture_request()` obtains a completed frame and metadata, `stop()` stops streaming, and `close()` releases the camera. `START` alone does **not** provide a visible preview.

### 10.4 Exposure and gain control

The server stores requested exposure time in microseconds, requested analogue gain as a floating-point value and automatic-exposure mode as a Boolean. Setting these values while the camera is closed does not open it. If streaming, the setter reapplies camera controls.

```python
if auto_exposure:
    cam.set_controls({"AeEnable": True})
else:
    cam.set_controls({
        "AeEnable": False,
        "ExposureTime": exposure_time,
        "AnalogueGain": analogue_gain,
    })
```

`set_exposure()` rejects nonpositive or noninteger input; `set_gain()` rejects nonpositive, nonfinite or nonnumeric input. `set_auto_exposure()` maps `1` to enabled and `0` to disabled; the EPICS enum record exposes the labels **Enable** and **Disable**. The Python readbacks report **requested** settings, not measured settings. Actual frame settings are saved in JSON metadata. Sensor-specific range validation is not yet complete.

### 10.5 Image acquisition and state restoration

`acquire_image()` records whether the camera was already streaming, initializes/starts it if needed, and sets `ACQUIRING`. It generates an output directory and timestamp-matched filenames, then uses a single completed Picamera2 request:

```python
request = camera.capture_request()
request.save("main", str(image_path))
metadata = request.get_metadata()
with open(metadata_path, "w") as file:
    json.dump(metadata, file, indent=4, default=str)
```

The actual implementation wraps startup, capture and saving in `try`/`except`/`finally`. `finally` releases the request if created and stops streaming if acquisition started it. On successful completion, the status becomes `IDLE` if acquisition started streaming, or returns to `STREAMING` if streaming was already active. On an acquisition failure, the function sets `ERROR` and propagates the exception to the command handler.

Only after a successful acquisition are `last_image_path` and `last_metadata_path` updated. The function returns **both** paths as a tuple. Output is stored in `acquisition/images/` as:

```text
image_YYYYMMDD_HHMMSS_microseconds.jpg
image_YYYYMMDD_HHMMSS_microseconds_metadata.json
```

The filename timestamp is a host-side identifier; sensor timestamps remain in the metadata. The JPEG is processed image data, not raw Bayer data.

### 10.6 Supported TCP command interface (tested directly)

| Command | Response or effect |
|---|---|
| `STATUS?` | Current state |
| `STATUS_DESC?` | Human-readable state description |
| `START` | Initialize/configure/start; `OK` |
| `STOP` | Stop streaming, retain camera; `OK` |
| `CLOSE` | Release camera; `OK` |
| `ACQUIRE` | Save JPEG + metadata; `OK` after completion |
| `EXPOSURE <microseconds>` / `EXPOSURE?` | Set/read requested exposure |
| `GAIN <value>` / `GAIN?` | Set/read requested analogue gain |
| `AUTO_EXPOSURE 0` / `AUTO_EXPOSURE 1` | Disable/enable AE |
| `AUTO_EXPOSURE?` | Return `0` or `1` |
| `LATEST_IMAGE_PATH?` | Last successful JPEG path, or `NONE` |
| `LATEST_METADATA_PATH?` | Last successful JSON path, or `NONE` |

`process_command(command)` dispatches these operations and returns newline-terminated responses. Basic exceptions are caught and returned as `ERROR: ...\n`; the command loop remains available for subsequent requests in normal recoverable cases. Unknown commands return an error. Full fault recovery is not yet implemented.

### 10.7 TCP socket, framing and cleanup

The server creates an IPv4 TCP listening socket, sets `SO_REUSEADDR`, binds to `127.0.0.1:5000`, and calls `listen(1)`. The outer loop waits at `accept()` for one active client; the inner loop processes commands on that connection.

The original `recv(1024)` assumed one read equaled one command. The updated server uses a text reader:

```python
reader = connection.makefile("r", encoding="utf-8")
while True:
    data = reader.readline()
    if not data:
        break
    command = data.strip()
    response = process_command(command)
    connection.sendall(response.encode("utf-8"))
```

`readline()` waits for a newline and handles TCP splitting/combining bytes into arbitrary chunks. The text reader already decodes UTF-8: **do not call `data.decode()`** on its returned string. Each Python response includes `\n`, matching the StreamDevice `Terminator = LF` convention.

On a detected TCP disconnection, the server calls `close_camera()`, closes the reader and client socket, and waits for a new client. On server shutdown, the outer `finally` closes the camera and listening socket. Unexpected socket failures and silent network disconnections are not yet comprehensively handled.

### 10.8 Direct TCP tests completed

The server was tested with Netcat on the Pi, independently of the IOC:

```bash
python3 -u acquisition/picamera2_server.py
# In another terminal:
nc 127.0.0.1 5000
```

Tests confirmed `CLOSED → STREAMING → IDLE → CLOSED`, requested-setting write/readback, automatic-exposure switching, a successful `ACQUIRE` returning to `IDLE`, valid matching JPEG/JSON metadata, latest-file-path readbacks, and repeated acquisitions that preserve `STREAMING` until `STOP`. These were standalone TCP tests; subsequent EPICS integration tests are documented in Section 20.

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

## 13. Run and test the system (original workflow and direct TCP tests)

### Terminal 1 — Python server

From the repository root, run **one** service:

```bash
python3 -u acquisition/picamera2_server.py
# OR, for the original simulator:
python3 -u acquisition/camera_server_simulator.py
```

Only one process can bind port 5000. The real server starts with camera state `CLOSED` and does not initialize the camera merely to answer `STATUS?`.

### Terminal 2 — IOC

```bash
cd epics/streamdevice_camera/streamdevice_camera_ioc/iocBoot/iocstreamdevice_camera
./st.cmd
```

The startup script invokes `../../bin/linux-arm/streamdevice_camera`. If needed, use `chmod +x st.cmd`. Confirm the `epics>` prompt.

### Terminal 3 — Existing EPICS status record

In the **original status-only IOC**, `SCAN = Passive` required explicit processing. The following is a historical test, not the current workflow:

```bash
caput CAM:GetStatus.PROC 1
caget CAM:GetStatus
pvget CAM:GetStatus
```

With the **current Python server**, a status query before camera initialization returns `CLOSED`, not `IDLE`. A subsequent successful camera operation can change that status, but the IOC record will only reflect a new value after processing. StreamDevice processing can be asynchronous, so immediate reads may not guarantee freshness.

**Current implementation:** The new camera commands have now been tested through EPICS; see Section 20 for current tests.

### Direct Python/TCP tests

Run `nc 127.0.0.1 5000` in a separate terminal while the Python server is running. Send one command per line; for example:

```text
STATUS?
AUTO_EXPOSURE 0
EXPOSURE 20000
GAIN 1.0
ACQUIRE
STATUS?
LATEST_IMAGE_PATH?
LATEST_METADATA_PATH?
```

This exercises the expanded server without involving the IOC. `ACQUIRE` returns `OK` only after saving completes. Inspect matching files under `acquisition/images/` and verify actual settings in the JSON metadata.

### Shutdown

Stop the IOC with `exit` at `epics>` and the Python server with Ctrl+C. Detected IOC TCP disconnection closes the camera; the server continues waiting for a new connection.

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

Both access the same IOC record. With `SCAN = Passive`, both normally return the **stored** value; neither automatically sends a fresh `STATUS?` to Python. `pvput` is the PVA write counterpart of `caput`. The expanded camera-control PVs have since been added and tested (Sections 20 and 21).

## 15. Passive readback, I/O Intr and on-demand status (historical design discussion)

A normal `caget CAM:GetStatus` or `pvget CAM:GetStatus` reads the **IOC's stored record value**; it does not automatically send `STATUS?` to Python. To trigger the current passive record explicitly:

```bash
caput CAM:GetStatus.PROC 1
```

That write processes the record; it does not set the status to `1`. With the expanded server, the Python `STATUS?` command reports the current software state without initializing the camera.

`PINI = YES` can process at IOC startup, periodic `SCAN` values cause polling, and `SCAN = "I/O Intr"` requires suitable device-support/event notification. **Changing `SCAN` to I/O Intr alone does not make Python status changes automatically appear in EPICS.** A notification mechanism compatible with StreamDevice/asyn and the chosen protocol must first be designed and tested; unsolicited messages must not corrupt request-response parsing.

**Historical requirement, subsequently implemented in part:** Event-driven status and file-path updates are now operational via I/O Intr; fresh-on-read semantics remain a separate issue. A single ordinary CA/PVA PV read does not inherently force a hardware transaction. The expanded Python server centralizes state changes in `update_camera_status()` to simplify future notification integration.

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
export EPICS_CA_ADDR_LIST=<PI_IP_ADDRESS>
```

Test:

```bash
caget CAM:GetStatus
caput CAM:GetStatus.PROC 1
caget CAM:GetStatus
```

This remote CA configuration was successfully tested. Remote PVA discovery from WSL was not separately verified during that milestone; remote PVA clients may need their own network configuration.

## 17. Multiple clients and access considerations

Multiple operator interfaces, scripts and remote terminals can access the IOC over CA or PVA. They do not each need a separate TCP connection to the Python camera service. The current Python implementation handles one accepted TCP client at a time, which is adequate for the intended IOC-to-service connection.

The Python service binds to `127.0.0.1`, limiting direct remote access to that socket. **This does not restrict access to the EPICS IOC itself.** For deployment beyond a trusted laboratory network, consider IOC access-security rules, firewall restrictions and appropriately secured networking. These protections have not been implemented as part of this milestone.

## 18. Current limitations and next development steps

### Implemented and tested

- Simulated `STATUS?` through StreamDevice/asyn and local/remote Channel Access.
- Existing IOC status record exposed through CA and PVA using QSRV.
- Physical IMX219 discovery and standalone JPEG + matching JSON acquisition.
- Expanded Python TCP interface: camera lifecycle, settings, status, capture and latest-path readbacks.
- Newline-delimited input parsing, basic command errors and cleanup on detected disconnect.
- Direct Netcat tests of single and repeated acquisition with metadata verification.

### Milestone 4 EPICS integration — completed since this historical checkpoint

- Add the new commands to `stream_camera.proto`, including suitable request/response formats.
- Add readback and control records to `camera.db` (`GetStatus`, `GetStatusDescription`, `GetExposure`, `SetExposure`, `GetGain`, `SetGain`, `GetAutoExposure`, `SetAutoExposure`, `Start`, `Stop`, `Acquire`, `Close`, `GetLatestImagePath`, `GetLatestMetadataPath`).
- Select appropriate EPICS record types and sufficiently long storage for full file paths; standard `stringin` may be too short.
- Test the full workflow through `caput`/`caget` and `pvput`/`pvget`.
- Design and test I/O Intr/event-driven readback updates without confusing them with on-demand PV reads.

### Longer-term limitations

- One active TCP client and sequential blocking acquisition; no live status query during blocking capture.
- Software-maintained state rather than independent sensor-health monitoring.
- Incomplete recovery for exceptional socket/camera failures and silent disconnects.
- Requested-setting readbacks, with actual settings recorded in metadata.
- Original JPEG files remain on the Pi. A separate publisher provides a reduced-resolution RGB array through PVAccess, not raw sensor data.
- Preview integration and areaDetector remain future work.

The EPICS integration described in this historical section has been performed. Sections 20 and 21 describe the tested configuration, expanded PVA verification and remaining limitations.



## 20. Milestone 4 — EPICS-controlled acquisition and monitoring (18 October 2026; historical configuration)

This section documents the **18 October tested configuration**, subsequently extended in Section 23, and supersedes the earlier status-only database/protocol examples in Sections 7, 8, 13, 15 and 18. The older sections are retained to show how the implementation evolved.

### 20.1 Design goals and boundaries

The objective was to operate the IMX219 from EPICS, acquire JPEG/JSON pairs, and have ordinary `caget` and Phoebus clients read up-to-date IOC values **without a separate `.PROC` command or periodic application-level polling**. The design distinguishes (a) state changes arising during camera operations, (b) requested parameter settings written through EPICS, and (c) new file paths produced by successful acquisition. These do not require identical record-processing mechanisms.

The IOC uses one asyn TCP connection to the Python server on `127.0.0.1:5000`. Channel Access was used for the expanded interface tests. QSRV also exposes the IOC records through PVAccess. The expanded PV set was subsequently tested through PVA; see Section 21.

### 20.2 PVs and processing choices at Milestone 4

| PV (with `P=CAM:,R=`) | Record | Protocol | Processing |
|---|---|---|---|
| `CAM:CameraCommand` | `mbbo` | `cameraCommand` | Passive output |
| `CAM:GetStatus` | `stringin` | `monitorStatus` | I/O Intr, initial `VAL=CLOSED` |
| `CAM:GetStatusDescription` | `waveform` CHAR[256] | `getStatusDescription` | Passive; manual processing only |
| `CAM:SetExposure` / `CAM:GetExposure` | `longout` / `longin` | `setExposure` / `getExposure` | Setter FLNK to passive readback |
| `CAM:SetGain` / `CAM:GetGain` | `ao` / `ai` | `setGain` / `getGain` | Setter FLNK to passive readback |
| `CAM:SetAutoExposure` / `CAM:GetAutoExposure` | `mbbo` / `mbbi` | `setAutoExposure` / `getAutoExposure` | Setter FLNK to passive readback |
| `CAM:GetLatestImagePath` | `waveform` CHAR[512] | `monitorLatestImagePath` | I/O Intr |
| `CAM:GetLatestMetadataPath` | `waveform` CHAR[512] | `monitorLatestMetadataPath` | I/O Intr |

### 20.3 Why one `mbbo` command record rather than four buttons or `stringout`?

Possible command-record designs include separate `bo` commands, a free-text `stringout`, and one `mbbo`. A `stringout` would map directly to Python's `START`, `STOP`, `ACQUIRE` and `CLOSE` text but would also permit arbitrary input. `mbbo` constrains the operator to four named states and works naturally with Phoebus selection widgets. It maps `Start=0`, `Stop=1`, `Acquire=2`, `Close=3`; StreamDevice converts the selected enum to uppercase text:

```text
cameraCommand {
    ReplyTimeout = 10000;
    out "%{START|STOP|ACQUIRE|CLOSE}";
    #in "OK";
}
```

For example, `caput CAM:CameraCommand Acquire` sends `ACQUIRE` to Python. Repeating `Acquire` was tested and produced distinct JPEG/JSON pairs even though the `mbbo` retains the same selected state. **The command PV is the last requested operation, not a camera-state readback.**

The final command protocol is **output-only**. `ReplyTimeout` does not currently control an acknowledgement wait because `in "OK"` is commented out. Importantly, the actual Python `process_command()` still returns `OK\n` for camera commands; the TCP loop still sends that response. Thus unconsumed `OK` lines remain a **known shared-port robustness issue**, not a confirmed acknowledgement-free implementation. A successful `caput` alone does not prove acquisition finished.

### 20.4 Passive, periodic, PINI and I/O Intr: why status uses I/O Intr

- **Passive** records process when triggered by a write, forward link, `.PROC`, etc.; a normal `caget` reads the IOC's stored value and does not query Python.
- **Periodic SCAN**, such as `1 second`, would repeatedly issue requests regardless of camera changes. Periodic polling is not used.
- **PINI** requests processing at IOC initialization; it cannot make an input-only monitor protocol issue `STATUS?` and does not by itself handle reconnection.
- **I/O Intr** allows StreamDevice device support to process a record when matching incoming data arrives. It does **not** directly observe a Python variable; Python must transmit the update.

The Python function `update_camera_status(new_status)` changes the stored state and sends `STATUS:<state>\n` over the active TCP connection. The current protocol and record are:

```text
monitorStatus {
    in "STATUS:%s";
}
```

```text
record(stringin, "$(P)$(R)GetStatus") {
    field(DESC, "Camera operating status")
    field(DTYP, "stream")
    field(INP, "@stream_camera.proto monitorStatus $(PORT)")
    field(SCAN, "I/O Intr")
    field(VAL, "CLOSED")
}
```

Sequence: Python updates its status → sends `STATUS:ACQUIRING\n` → StreamDevice's input-only protocol matches the line → I/O Intr updates the record → `camonitor` receives a value event and `caget` reads the last stored value. No separate TCP port was used. The protocol was initially tested on a temporary `CAM:MonitorStatusTest` PV before being used by `CAM:GetStatus`.

The initial `VAL=CLOSED` is **an assumed value**, matching the normal Python server startup (`camera=None`, `camera_status="CLOSED"`) and its intended camera-close-on-disconnect behavior. It is not a fresh hardware query. Reconnection and silent-disconnect synchronization are not yet robustly verified.

### 20.5 Why FLNK was used for requested exposure, gain and automatic exposure

These three readbacks represent **requested settings maintained in Python**, usually changed through EPICS setters. A forward link from each setter causes its passive readback record to process after the setter operation completes, avoiding both periodic queries and additional unsolicited messages.

```text
record(longout, "$(P)$(R)SetExposure") {
    field(DTYP, "stream")
    field(OUT, "@stream_camera.proto setExposure $(PORT)")
    field(SCAN, "Passive")
    field(FLNK, "$(P)$(R)GetExposure")
}
```

The equivalent links are `SetGain → GetGain` and `SetAutoExposure → GetAutoExposure`. The getter protocols send `EXPOSURE?`, `GAIN?`, and `AUTO_EXPOSURE?`. Tests showed the setter command followed by the matching getter in Python's terminal, and the readback PVs updated without manual `.PROC`. The exposure setter and readback now also specify `EGU = "us"`. The passive `GetExposure`, `GetGain`, and `GetAutoExposure` records use `PINI = "YES"` to request their values at IOC initialization. The output setter records do not use PINI, avoiding unintended writes of their initial values. Startup reads depend on the Python TCP service being reachable; PINI does not handle later reconnection or synchronize the setter values.

For automatic exposure, the EPICS enum labels are `Disable=0`, `Enable=1`, matching Python's Boolean conversion. These readbacks do **not** establish the actual exposure/gain used by a captured frame; the JPEG's associated JSON metadata is the source for applied frame settings. FLNK does not detect changes originating outside these EPICS setters.

### 20.6 Why acquisition paths use I/O Intr and CHAR waveform records

A successful `acquire_image()` saves both files, updates `last_image_path` and `last_metadata_path`, and sends two messages on the same TCP connection:

```text
IMAGE_PATH:/path/to/acquisition/images/image_<timestamp>.jpg
METADATA_PATH:/path/to/acquisition/images/image_<timestamp>_metadata.json
```

The input-only StreamDevice protocols are:

```text
monitorLatestImagePath {
    in "IMAGE_PATH:%s";
}
monitorLatestMetadataPath {
    in "METADATA_PATH:%s";
}
```

Both database records use `SCAN="I/O Intr"`, `FTVL="CHAR"` and `NELM="512"`. The ordinary EPICS string record has a short fixed capacity; a CHAR waveform stores a longer path as character bytes (ASCII codes for these paths), terminated by zero. `caget -S` and `camonitor -S` display these arrays as readable text. A path is **not** the image contents. A separate Python PVAccess publisher now provides a resized RGB image to Phoebus; this does not change the file-path waveform records.

The path notifications are emitted only after successful acquisition; repeated acquisition and simultaneous `camonitor -S CAM:GetStatus CAM:GetLatestImagePath CAM:GetLatestMetadataPath` were tested. The monitor receives independently updated PVs, not one combined message.

### 20.7 Why automatic status-description FLNK was postponed

An initial implementation linked `GetStatus → GetStatusDescription` to request `STATUS_DESC?` whenever status changed. Three problems appeared:

1. `in "%s"` parsed only `Camera` before whitespace, producing surplus-input and INVALID alarms. Changing to a scanset `in "%[^\n]"` accepted spaces.
2. With the unprefixed description response, a `STATUS:STREAMING` notification was sometimes incorrectly consumed as description text. Adding Python's `DESCRIPTION:` response prefix and matching `in "DESCRIPTION:%[^\n]"` made that mismatch detectable.
3. During blocking `ACQUIRE`, Python's sequential command loop could not promptly service the `STATUS_DESC?` query triggered by FLNK. StreamDevice logged `No reply within 1000 ms to "STATUS_DESC?<0a>"`, and the description record entered `TIMEOUT INVALID`. A later query returned the correct description.

The resulting database therefore keeps `GetStatusDescription` **Passive without a FLNK from GetStatus**. The query protocol remains available for explicit processing; automatic description updates are postponed. Increasing the timeout alone would not resolve shared-port message routing.

### 20.8 Shared-port notifications: what worked and what did not

The single connection carries ordinary query responses, command acknowledgements, and unsolicited `STATUS:`, `IMAGE_PATH:` and `METADATA_PATH:` lines. Tests showed that an active `cameraCommand` expecting `in "OK"` sometimes received `STATUS:IDLE` or `STATUS:STREAMING` first, logging `got ... where "OK" was expected`. Switching `cameraCommand` to output-only avoided that particular expected-`OK` match, but **did not establish reliable message demultiplexing**; Python still sends `OK` for those commands.

Rapid `IDLE → STREAMING → ACQUIRING` transitions were sometimes absent from `camonitor`, while the final state was correct. When acquiring from an already streaming camera, `ACQUIRING → STREAMING` appeared consistently in the tests. These observations suggest timing/dispatch effects but do not prove the exact root cause. A later intermittent `CAM:SetAutoExposure` mismatch likewise showed `STATUS:IDLE` where `OK` was expected, although the controls worked and the error did not recur in subsequent tests. Do not introduce arbitrary sleeps as a substitute for investigating message routing.

**Known limitation:** These tests demonstrate working status and file-path updates in the exercised scenarios, not guaranteed lossless delivery of all intermediate events or error-free mixed-message operation. Future work should examine message framing, transaction serialization, outstanding `OK` responses, error/status alarms and reconnection behavior; a dedicated event connection remains a possible fallback if required by reliability testing. The StreamDevice option `ExtraInput = Ignore;` is an untested possibility for investigation, not a verified fix for a status notification arriving before the expected `OK`.

### 20.9 Reproducible tests and observed outcomes

Run the Python server and IOC in separate terminals, then use a normal Linux shell (not `epics>`) for CA client commands:

```bash
caput CAM:CameraCommand Start
caget CAM:GetStatus
caput CAM:CameraCommand Stop
caput CAM:CameraCommand Acquire
caput CAM:CameraCommand Acquire
caput CAM:CameraCommand Close
```

The repeated `Acquire` commands saved distinct JPEG/JSON pairs. For monitoring:

```bash
camonitor -S CAM:GetStatus CAM:GetLatestImagePath CAM:GetLatestMetadataPath
```

To test FLNK readbacks:

```bash
caput CAM:SetExposure 40000
caget CAM:GetExposure
caput CAM:SetGain 2.0
caget CAM:GetGain
caput CAM:SetAutoExposure 0
caget CAM:GetAutoExposure
```

Expected requested-setting readbacks were `40000`, `2.0` and `Disable` respectively; the Python log showed corresponding setter and getter commands. `camonitor` also displayed `ACQUIRING` and final `IDLE`/`STREAMING` in acquisition tests. The full JPEG/JSON files were verified on disk.

### 20.10 Limitations identified at this historical checkpoint

- Resolve the output-only `cameraCommand` versus Python `OK` response inconsistency and assess shared-port notification routing under repeated operations.
- Improve cleanup: `update_camera_status()` currently calls `connection.sendall()` directly, including when camera cleanup may occur after a socket disconnect. Guarding notification delivery and handling errors are needed.
- Revisit initial synchronization after IOC restart or connection loss; `VAL=CLOSED` is a startup assumption.
- Decide whether status descriptions should be derived from the status PV or published as their own events.
- The basic Phoebus controls and separate PVAccess image display are implemented; larger-image performance and reliability have not been characterized.

## 21. Expanded PVAccess testing and PyEpics automation

### 21.1 PVAccess verification

QSRV exposes the existing IOC database records through PVAccess. No separate PVA versions of the camera records are required. The expanded interface was tested using `pvget`, `pvput`, and `pvmonitor`, including camera commands, exposure, analogue gain, automatic-exposure control, camera status, and the latest image and metadata paths.

```bash
pvget CAM:GetStatus
pvput CAM:SetExposure 20000
pvget CAM:GetExposure
pvmonitor CAM:GetStatus
```

The tested control and readback operations worked. The brief `ACQUIRING` state was sometimes absent from `pvmonitor`, as it was from `camonitor`. This remains an observed limitation, not a confirmed restriction of either CA or PVA. The exact stage where intermediate updates are missed has not been established.

### 21.2 Automated acquisition through the existing IOC (original script)

The original `automation/exposure_sweep.py` uses **PyEpics**, a Python client for Channel Access. It communicates with the IOC through PVs; it does not call Picamera2 or connect directly to the camera TCP server. This keeps experiment sequencing separate from hardware control.

The original automation disables automatic exposure, sets a fixed requested gain, and repeats the following sequence for each exposure time:

1. Write the exposure setpoint through `CAM:SetExposure`.
2. Read `CAM:GetExposure` (the requested-value readback **at the time**) until it matches the requested value, or stop after a timeout. **As of 26 October this PV now reports actual frame exposure; the script must be updated to use `CAM:ExposureRB` for the requested-value check.**
3. Read the existing `CAM:GetLatestImagePath`, then send `Acquire` through `CAM:CameraCommand`.
4. Wait until `CAM:GetLatestImagePath` contains a new path. This indicates that a new image path has been published after saving.
5. Wait until `CAM:GetLatestMetadataPath` matches the new image's filename stem.
6. Write the requested exposure, exposure readback, requested gain, and both file paths to one CSV row. Each completed row is flushed to the output file.

The acquisition command protocol is output-only. A successful EPICS write is therefore **not** proof that image capture finished. Checking the new path is a practical completion indicator for the tested workflow, but missed notifications, reconnections, and failed acquisitions still require additional handling.

The sweep writes its CSV log to `data/exposure_sweeps/` on the computer running the automation script. JPEG and JSON files continue to be saved by the camera server on the Raspberry Pi. These generated files are excluded from Git.

### 21.3 Local and remote operation

| Component or operation | Location |
|---|---|
| IMX219, libcamera and Picamera2 | Raspberry Pi |
| Python camera TCP server and conventional IOC | Raspberry Pi in the current setup |
| `caget`/`caput` and `pvget`/`pvput` clients | Raspberry Pi or a remote computer with network access to the IOC |
| PyEpics exposure automation | Raspberry Pi or a remote computer with Channel Access connectivity |
| Acquired JPEG and JSON metadata | Saved on the Raspberry Pi |
| Exposure-sweep CSV | Saved on the computer running the automation |
| Characterization scripts | Any computer that can access the CSV, images and metadata |

The TCP service is bound to `127.0.0.1:5000`, which is a **local loopback address**, not the Pi's Wi-Fi address. Remote automation communicates with the IOC through Channel Access. It does not need direct access to port 5000.

Reading an image path through EPICS does not transfer the image itself. The current CSV records absolute paths on the Raspberry Pi. Remote analysis requires file transfer or shared storage and suitable path handling. The initial analysis scripts assume the recorded paths are accessible from the computer where they run.

### 21.4 Scope of the characterization scripts

`characterization/check_exposure.py` compares the requested exposure in the sweep CSV with the camera-reported `ExposureTime` in the corresponding JSON metadata. `characterization/analyze_exposure_response.py` uses Pillow, NumPy and Matplotlib to calculate basic grayscale JPEG statistics and save an exposure-response plot.

These scripts analyze saved files and do not require the IOC or camera to be running once the data is available. The results describe **processed JPEG output**; they do not establish intrinsic sensor linearity or noise performance. The detailed measurement procedure, code explanations and results are in [Automated Acquisition and Initial Camera Characterization](notes/automated_acquisition_and_characterization.md).

## 22. Phoebus control and separate PVAccess image display

### 22.1 Division of responsibilities

The existing StreamDevice IOC continues to handle camera commands, exposure and gain settings, camera status, and the latest JPEG/JSON file paths. Phoebus uses these IOC PVs for camera control and monitoring. No image-data waveform or additional asyn TCP port has been added to the IOC.

Image display is provided by a **separate Python program**, `acquisition/pva_image_publisher.py`, using PyEpics, Pillow, NumPy and the `p4p` PVAccess library. It is not part of `picamera2_server.py` and can be started only when image visualization is needed.

```text
Phoebus on Windows
    |-- CA/PVA --> conventional IOC --> StreamDevice/asyn --> TCP 5000 --> camera server --> IMX219
    |-- PVA ----> CAM:Image (separate Python p4p publisher)
                               ^
                               | reads saved JPEG on Raspberry Pi
                        CAM:GetLatestImagePath (via PyEpics)
```

### 22.2 Image update workflow

After an acquisition, the camera server saves the full-resolution JPEG and matching metadata on the Raspberry Pi. The IOC publishes the latest JPEG path through `CAM:GetLatestImagePath`. The image publisher checks this PV, detects a new path, opens the corresponding saved JPEG, converts it to RGB, and resizes it to 100 × 100 pixels. The resulting flattened unsigned 8-bit array is published as `CAM:Image` through PVAccess.

The current publisher checks the path periodically rather than subscribing to a monitor callback. It can therefore miss intermediate images if several acquisitions finish between checks. The image publisher must run on a computer that can access the JPEG paths returned by the IOC; in the current setup it runs on the Raspberry Pi. The original JPEG and metadata are not transferred to Windows by this PV.

The Phoebus Image widget was tested with `pva://CAM:Image`, width and height set to 100, color mode `TYPE_RGB1`, and **Unsigned Data** enabled. The RGB image updated after a new acquisition. This is image visualization, not live video streaming or an areaDetector/NTNDArray implementation.

The Python code, `NTScalar("aB")`, `SharedPV`, `StaticProvider`, array layout, and run instructions are covered in [PVAccess Image Publisher](notes/pva_image_publisher.md).

### 22.3 IOC database refinements

The exposure setter and readback records include `EGU = "us"` to label exposure times in microseconds. The passive exposure, gain and automatic-exposure readback records use `PINI = "YES"` to request initial values when the IOC starts. Setter records remain passive without PINI to avoid sending unintended default commands. The readback initialization depends on successful communication with the Python camera server and does not automatically refresh after reconnection.

## 23. TCP communication refactoring and actual camera-setting monitoring (26 October 2026)

This section describes the **current tested implementation** and supersedes the earlier direct `connection.sendall(...)` examples and the exposure/gain PV names in Sections 10, 20 and 21. The conventional IOC, StreamDevice/asyn port, and camera server remain separate processes; there is still one TCP connection on `127.0.0.1:5000`. The separate PVAccess image publisher is unchanged.

### 23.1 Why the Python communication was refactored

The earlier server used a global accepted socket directly from status, acquisition-path and command-response functions. Actual exposure and gain monitoring introduced another execution context that needed to publish messages. A small `TCPConnection` class now centralizes the accepted socket reference and outgoing writes without creating a second connection or a second server.

The class provides `set_connection(connection)` to register the socket returned by `server.accept()`, `send(message)` to encode and transmit newline-terminated messages, and `clear_connection()` to detach the socket before closing it. A `threading.Lock` serializes cooperating calls to these methods so concurrent Python threads do not write overlapping byte sequences. `send()` returns `False` if no connection is registered; actual socket errors are allowed to propagate for handling by the caller. Clearing the reference does not itself close the socket.

This lock **does not guarantee protocol-level response ordering**. A complete `ACTUAL_EXPOSURE:` notification may still arrive when StreamDevice is waiting for an `OK` acknowledgement. The shared-port robustness limitation remains open.

### 23.2 Actual settings from Picamera2 frame metadata

The Python server retains `exposure_time` and `analogue_gain` as **requested settings**. New variables `actual_exposure` and `actual_gain` start as `None` and are updated from `ExposureTime` and `AnalogueGain` in the metadata of completed frames. `initialize_camera()` registers `camera.post_callback = frame_callback`. The callback only reads metadata and stores the latest values; it does not perform network I/O or save a JPEG.

A lightweight daemon monitoring thread checks the latest values at `METADATA_CHECK_INTERVAL = 0.2` seconds. It sends changes using the shared `tcp.send()` method. The initial configured thresholds are `EXPOSURE_CHANGE_THRESHOLD = 10` microseconds and `GAIN_CHANGE_THRESHOLD = 0.01`. Comparisons are made against the last **reported** value, so small changes can accumulate before an update is published. The first available values after monitoring begins are reported. These thresholds reduce notification traffic; they are not measurement accuracy specifications or permitted setting errors.

The actual-value messages are:

```text
ACTUAL_EXPOSURE:19999
ACTUAL_GAIN:1.0
```

These are examples, not fixed sensor readings. The callback can update while streaming without saving images. The actual-value PVs represent the latest reported completed-frame metadata, not independent hardware-register measurements. After streaming stops they can retain the last values; freshness/invalidity signaling has not yet been implemented. The saved JSON metadata remains the frame-specific source for characterization.

### 23.3 Current StreamDevice protocols and configuration

The requested-setting queries have changed from `EXPOSURE?` and `GAIN?` to `EXPOSURE_RB?` and `GAIN_RB?`. The setters continue using `EXPOSURE <value>` and `GAIN <value>`.

```text
getExposureRB {
    out "EXPOSURE_RB?";
    in "%d";
}

getGainRB {
    out "GAIN_RB?";
    in "%f";
}

monitorActualExposure {
    in "ACTUAL_EXPOSURE:%d";
}

monitorActualGain {
    in "ACTUAL_GAIN:%f";
}
```

The global protocol configuration tested for this iteration is:

```text
Terminator = LF;
# ReplyTimeout = 2000;
# ReadTimeout = 2000;
ExtraInput = Ignore;
```

The two timeout settings were left commented out. `ExtraInput = Ignore;` is now part of the tested configuration, **but has not been shown to fix** intermittent status/acknowledgement mismatches. In particular, it does not guarantee correct routing of unsolicited messages that arrive before the expected response. Earlier sections describing this option as *untested* refer to the previous implementation checkpoint.

### 23.4 Current exposure and gain PVs

| PV | EPICS record | Source | Processing |
|---|---|---|---|
| `CAM:SetExposure` | `longout` | Requested exposure setpoint | StreamDevice passive output; FLNK to `ExposureRB` |
| `CAM:ExposureRB` | `longin` | Requested exposure stored by Python | Passive StreamDevice query `getExposureRB`; `PINI=YES` |
| `CAM:GetExposure` | `longin` | Camera-reported exposure from frames | `monitorActualExposure`; `I/O Intr` |
| `CAM:SetGain` | `ao` | Requested analogue gain setpoint | StreamDevice passive output; FLNK to `GainRB` |
| `CAM:GainRB` | `ai` | Requested gain stored by Python | Passive StreamDevice query `getGainRB`; `PINI=YES` |
| `CAM:GetGain` | `ai` | Camera-reported gain from frames | `monitorActualGain`; `I/O Intr` |

Exposure records use engineering units `us`; gain records display three decimal places. The existing automatic-exposure setter/readback arrangement remains unchanged. The actual-value records are input-only monitors and do not require startup processing: they update after valid notifications arrive. An initial zero in an uninitialized record must not be interpreted as a valid camera measurement.

### 23.5 Testing and remaining limitations

The refactored Python server passed a syntax check and was exercised directly through Netcat. The updated IOC records and actual exposure/gain values were then tested successfully through Phoebus. This confirms operation for the scenarios exercised, **not** exhaustive reliability under concurrent messages, disconnects or rapid state changes.

The former `automation/exposure_sweep.py` and two standalone characterization scripts were retired from the active repository after their historical experiments. The current automation is `automation/camera_scan.py`, described in Section 24. The saved-image approach still requires local access to JPEG/JSON files; it does not transfer full-resolution images through an IOC PV.

## 24. EPICS-controlled camera scanning (27 October 2026)

This section describes the **current scan implementation** and supersedes the earlier automation paths and planned-scan statements elsewhere in this guide. It extends the same IOC database; no second IOC, TCP connection or scan-specific StreamDevice protocol was introduced. The scan program is `automation/camera_scan.py`, a separate PyEpics client that communicates with IOC PVs through Channel Access.

### 24.1 Division of responsibilities

```text
Phoebus / caput / caget
         |
         v
EPICS IOC (camera.db)
  |-- Scan configuration, commands, results: soft records
  |-- Normal and scan-only exposure/gain setters: StreamDevice
  |-- Requested-value readbacks: FLNK-triggered StreamDevice queries
  |-- Actual exposure/gain and acquisition paths: I/O Intr
         |
         v
StreamDevice + asyn --> TCP 127.0.0.1:5000 --> Picamera2 server --> IMX219
         ^
         |
PyEpics camera_scan.py (reads scan PVs; sets camera controls;
  acquires saved JPEG/JSON; computes intensity; publishes arrays/CSV)
```

The scan controller does not use Picamera2 directly. Its current intensity calculation reads a saved JPEG on the Raspberry Pi, so this version runs where those image paths are accessible. The separate `pva_image_publisher.py` remains responsible for Phoebus image display, not for scan execution.

### 24.2 Scan configuration and control soft records

| PV | Record | Purpose |
|---|---|---|
| `CAM:ScanEnable` | `bo` | Enable/disable scan mode |
| `CAM:ScanType` | `mbbo` | Exposure (0) or Gain (1) |
| `CAM:ScanStartExposure`, `CAM:ScanEndExposure` | `longout` | Exposure range, integer microseconds |
| `CAM:ScanStartGain`, `CAM:ScanEndGain` | `ao` | Dimensionless analogue gain range |
| `CAM:ScanPoints` | `longout` | Number of measurement points |
| `CAM:StartScan`, `CAM:StopScan` | `bo` | Scan requests read by the PyEpics program |

These are **soft records**: they hold scan parameters or command flags in the IOC and have no StreamDevice `DTYP`/`OUT` command. The scan program reads the configuration when executing a scan. Exposure and gain have separate start/end PVs because their units, numerical precision and valid ranges differ. The scan program validates parameters, including the waveform capacity limit of 100 points.

The initial sequential controller polls the command PVs rather than registering PyEpics callbacks or creating additional Python threads. It acknowledges `StartScan` by resetting it to zero, checks `ScanEnable`, clears a stale `StopScan` request and runs the selected scan. It checks for Stop Scan at safe points; an in-progress blocking camera acquisition cannot be forcibly interrupted by this mechanism. Scan Enable triggers the controller to disable automatic exposure through the existing `CAM:SetAutoExposure` PV; it is verified before a scan. The auto-exposure setter is not currently protected by a database-level scan interlock.

### 24.3 Database-level interlocks and dedicated scan setters

The normal exposure and gain setters must not process while scan mode is enabled, but the automation must still be able to change the camera settings. The database therefore has two sets of output records sharing the **same existing StreamDevice protocols** (`setExposure` and `setGain`).

```text
# Added to the normal SetExposure and SetGain records
field(SDIS, "$(P)$(R)ScanEnable")
field(DISV, "1")

# Added to the ScanSetExposure and ScanSetGain records
field(SDIS, "$(P)$(R)ScanEnable")
field(DISV, "0")
```

| `ScanEnable` | Normal `SetExposure` / `SetGain` | `ScanSetExposure` / `ScanSetGain` |
|---|---|---|
| 0 | Processes normally | Processing disabled |
| 1 | Processing disabled | Processes normally |

The scan-specific records are `longout` (`CAM:ScanSetExposure`) and `ao` (`CAM:ScanSetGain`), with passive StreamDevice output and forward links to `CAM:ExposureRB` and `CAM:GainRB` respectively. Both sets of setters use the same TCP camera server commands. No new `.proto` command was needed.

**Important:** `SDIS` disables record *processing*, not necessarily writes to its `VAL` field, and does not enforce client identity or exclusive ownership of the scan-only PVs. The scan program also needs to validate its settings and check the requested readback. These interlocks were tested through Phoebus for the intended normal/scan modes.

During initial testing, `SDIS` links included the `CP` modifier. This caused the normal exposure/gain setters to process their default zero values during IOC initialization, producing Python validation errors (`Exposure time must be positive`, `Analogue gain must be a finite, positive number`). Both setters had `PINI=NO` and `SCAN=Passive`; removing `CP` from the `SDIS` links resolved the observed startup errors. **Do not reintroduce `CP`** for these disable links: the disable condition is evaluated when a setter processes, without requesting processing whenever Scan Enable changes.

### 24.4 Scan status and measurement results

| PV | Record | Data |
|---|---|---|
| `CAM:ScanStatus` | `mbbo` | IDLE, RUNNING, COMPLETED, STOPPED, ERROR |
| `CAM:ScanProgress` | `longout` | Number of completed points |
| `CAM:ScanMeanIntensity` | `ao` | Latest mean grayscale JPEG intensity |
| `CAM:ScanExposure` | `waveform` | Exposure X values from captured-frame metadata |
| `CAM:ScanGain` | `waveform` | Gain X values from captured-frame metadata |
| `CAM:ScanIntensity` | `waveform` | Corresponding mean intensity Y values |

The waveform records use `FTVL="DOUBLE"` and `NELM="100"`. `NELM` is the allocated maximum; `NORD` reports the valid number of elements. The scan program publishes growing arrays after each completed measurement. The X values come from the saved JSON metadata associated with the same JPEG used for the Y intensity calculation, rather than from a potentially independently updated live readback.

A simple array test used `caput -a` to write three values and verified `NORD=3`. Ordinary `caget` displayed the full 100-element capacity, including trailing zeros, while `pvget` returned only the valid values in the tested setup. For example:

```bash
caput -a CAM:ScanExposure 3 5000 10000 20000
caget CAM:ScanExposure.NORD
pvget CAM:ScanExposure
```

### 24.5 Sequential scan workflow and outputs

The current `camera_scan.py` uses persistent `epics.PV()` objects and their `.get()`/`.put()` methods. It waits for Start Scan, reads and validates the selected range, disables/verifies automatic exposure, and iterates over scan points. For each point it writes through `CAM:ScanSetExposure` or `CAM:ScanSetGain`, waits for `CAM:ExposureRB` or `CAM:GainRB`, requests `Acquire`, waits for a new JPEG path and matching JSON path, reads the saved files, computes mean 8-bit grayscale intensity, and updates the status, progress and waveform PVs. It also saves a timestamped CSV under `data/scan/`. JPEG and JSON files are stored under `acquisition/images/`.

The scan uses a changed `CAM:GetLatestImagePath` and matching `CAM:GetLatestMetadataPath` as practical acquisition-completion indicators. The camera-command StreamDevice protocol remains output-only, so a successful PV write is not itself a completion acknowledgement. The arrays are held in IOC memory and are not a replacement for saved CSV data. The scan program currently uses a single NaN placeholder when resetting plot waveforms; this is a one-element array, not a true empty array.

### 24.6 Phoebus XY Plot and CA/PVA array-length behavior

A Phoebus XY Plot initially showed an unwanted `(0, 0)` point. In the tested configuration, Channel Access exposed the full 100-element waveform capacity with trailing zeros, even though both waveform `NORD` fields reflected the number of valid points. PVAccess (`pvget`) returned the valid elements only. Changing the Phoebus trace PVs to explicit PVA addresses resolved the observed extra point:

```text
Exposure scan: X = pva://CAM:ScanExposure
               Y = pva://CAM:ScanIntensity

Gain scan:     X = pva://CAM:ScanGain
               Y = pva://CAM:ScanIntensity
```

The trace type was changed from Step to Line for the exposure-response plot. Phoebus responsiveness was also reported as unusually slow during display testing; the cause was not established. This is an observation, not evidence of a specific PVA or waveform defect.

### 24.7 Verification and remaining work

**Tested:** scan PV definitions, numerical waveform writes, normal-versus-scan setter interlocks, a saved-JPEG exposure scan, metadata-based X values, mean-intensity publication, CSV logging and a Phoebus PVA XY Plot without the spurious origin point.

**Not yet fully verified:** gain-scan execution, Stop Scan behavior, repeated-scan robustness, long scans, reconnection and mixed TCP notification reliability, performance of the Phoebus display, and a future in-memory intensity measurement mode that avoids saving each image. The old `exposure_sweep.py` and two standalone characterization scripts were removed from the active repository; their earlier experiments are documented in `implementation_and_results.md` and historical notes.

## 25. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [StreamDevice Documentation](https://paulscherrerinstitute.github.io/StreamDevice/)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)

---

**Implementation status (27 October 2026):** The refactored TCP server and actual-value readbacks remain operational. The IOC now includes scan configuration, scan-only setters, `SDIS`/`DISV` interlocks and result waveform PVs. A sequential PyEpics exposure scan with saved JPEG/JSON data, mean-intensity calculation, CSV logging and live Phoebus PVAccess plotting was tested. Gain scanning, stop behavior, repeated-run robustness, shared-port message ordering and display performance remain to be verified.
