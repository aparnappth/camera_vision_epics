# StreamDevice Camera IOC — Implementation Guide

This guide documents the conventional EPICS IOC developed for the [EPICS-Controlled Camera Characterization and Vision Platform](../README.md). It covers the simulated TCP service, the conventional IOC and its CA/PVA support, standalone Picamera2 acquisition, and the expanded Python TCP camera server tested in October 2026. The new acquisition commands have **not yet been integrated into the IOC database or StreamDevice protocol**.

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

**Verified boundary:** The expanded Python server is working over direct TCP. The IOC's `camera.db` and `stream_camera.proto` still describe the earlier status-only interface; the new commands have **not yet been tested through EPICS**.

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
│   ├── tests/
│   │   └── test_camera_acquisition.py
│   └── images/   # generated files, ignored by Git
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       ├── epics_device_integration.md
│       └── test_picamera2_acquisition.md
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

`set_exposure()` rejects nonpositive or noninteger input; `set_gain()` rejects nonpositive, nonfinite or nonnumeric input. `set_auto_exposure()` maps `1` to enabled and `0` to disabled; the future EPICS enum record is intended to expose the labels **Enable** and **Disable**. The Python readbacks report **requested** settings, not measured settings. Actual frame settings are saved in JSON metadata. Sensor-specific range validation is not yet complete.

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

Tests confirmed `CLOSED → STREAMING → IDLE → CLOSED`, requested-setting write/readback, automatic-exposure switching, a successful `ACQUIRE` returning to `IDLE`, valid matching JPEG/JSON metadata, latest-file-path readbacks, and repeated acquisitions that preserve `STREAMING` until `STOP`. These tests do **not** establish that the new commands work through EPICS yet.

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

The database still uses `SCAN = Passive`; to request processing, run:

```bash
caput CAM:GetStatus.PROC 1
caget CAM:GetStatus
pvget CAM:GetStatus
```

With the **current Python server**, a status query before camera initialization returns `CLOSED`, not `IDLE`. A subsequent successful camera operation can change that status, but the IOC record will only reflect a new value after processing. StreamDevice processing can be asynchronous, so immediate reads may not guarantee freshness.

**Do not attempt the new camera commands through EPICS yet:** the corresponding `camera.db` records and `.proto` operations are pending.

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

Both access the same IOC record. With `SCAN = Passive`, both normally return the **stored** value; neither automatically sends a fresh `STATUS?` to Python. `pvput` is the PVA write counterpart of `caput`. Camera-setting commands exist in the Python TCP server but the corresponding IOC PVs have not yet been added.

## 15. Passive readback, I/O Intr and on-demand status

A normal `caget CAM:GetStatus` or `pvget CAM:GetStatus` reads the **IOC's stored record value**; it does not automatically send `STATUS?` to Python. To trigger the current passive record explicitly:

```bash
caput CAM:GetStatus.PROC 1
```

That write processes the record; it does not set the status to `1`. With the expanded server, the Python `STATUS?` command reports the current software state without initializing the camera.

`PINI = YES` can process at IOC startup, periodic `SCAN` values cause polling, and `SCAN = "I/O Intr"` requires suitable device-support/event notification. **Changing `SCAN` to I/O Intr alone does not make Python status changes automatically appear in EPICS.** A notification mechanism compatible with StreamDevice/asyn and the chosen protocol must first be designed and tested; unsolicited messages must not corrupt request-response parsing.

**Open requirement:** Provide event-driven status/readback updates without periodic polling, and investigate fresh-on-read semantics separately. A single ordinary CA/PVA PV read does not inherently force a hardware transaction. The expanded Python server centralizes state changes in `update_camera_status()` to simplify future notification integration.

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

- Simulated `STATUS?` through StreamDevice/asyn and local/remote Channel Access.
- Existing IOC status record exposed through CA and PVA using QSRV.
- Physical IMX219 discovery and standalone JPEG + matching JSON acquisition.
- Expanded Python TCP interface: camera lifecycle, settings, status, capture and latest-path readbacks.
- Newline-delimited input parsing, basic command errors and cleanup on detected disconnect.
- Direct Netcat tests of single and repeated acquisition with metadata verification.

### Pending EPICS integration

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
- JPEG files on the Pi rather than EPICS image arrays or raw sensor data.
- Preview integration and areaDetector remain future work.

The next implementation task is to update **`stream_camera.proto` and `camera.db`** and test the expanded EPICS interface. Keep the tested Python server and earlier IOC build configuration as reproducible checkpoints.

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

**Implementation status (16 October 2026):** The original IOC status interface works over CA and PVA; standalone and TCP-controlled IMX219 image acquisition with matched metadata have been tested. Expanded EPICS acquisition PVs, event-driven updates and fresh-on-read behavior remain pending.
