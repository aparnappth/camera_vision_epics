# Troubleshooting — EPICS Camera Project

This document records problems encountered during development of the EPICS-controlled camera platform, how they were investigated, and which issues remain open.

For installation instructions, see [EPICS Environment Setup](epics_setup.md). For the IOC implementation, see [StreamDevice Camera IOC](streamdevice_ioc.md).

## 1. StreamDevice Example IOC Linker Error

**Error**

During the StreamDevice 2.8.26 build:

```text
undefined reference to `pvar_func_vxi11RegisterCommands'
collect2: error: ld returned 1 exit status
```

**Cause investigated**

The StreamDevice example IOC referenced a VXI-11 registration function that was not exported by the installed asyn shared library. VXI-11 is used by some laboratory instruments but is not required for this project's TCP/IP camera service.

**Outcome**

The StreamDevice library itself compiled and installed successfully (`libstream.so` and `libstream.a`). The example IOC was left unchanged; the project's own IOC subsequently compiled and linked successfully. The underlying VXI-11 registration mismatch was not resolved.

## 2. StreamDevice Protocol File Not Installed

**Symptom**

After `make`, the installed `db/` directory contained `camera.db` but not `stream_camera.proto`.

**Cause**

The original protocol file was in a separate `protocol/` directory, and the installation rule did not install it as intended.

**Solution**

Place the protocol source at:

```text
streamdevice_cameraApp/Db/stream_camera.proto
```

In `streamdevice_cameraApp/Db/Makefile`, include:

```makefile
DB += camera.db
DB += stream_camera.proto
```

Rebuild from the IOC root:

```bash
make -j2
ls db
```

Both `camera.db` and `stream_camera.proto` should appear. Edit the source files, not the generated installed copies.

## 3. EPICS Database Syntax Error

**Error**

During IOC startup:

```text
ERROR: syntax error
at or before 'field' in file "../../db/camera.db"
```

The database contained a malformed field:

```text
field(field(INP, "@stream_camera.proto getStatus CAM_PORT")
```

**Solution**

Correct the source database:

```text
field(INP, "@stream_camera.proto getStatus $(PORT)")
```

Rebuild and restart the IOC. Always edit `streamdevice_cameraApp/Db/camera.db`, rather than the installed `db/camera.db`.

## 4. Python TCP Port Already in Use

**Error**

```text
OSError: [Errno 98] Address already in use
```

**Cause encountered**

The Python server had been suspended with `Ctrl+Z` rather than terminated. The suspended process still held TCP port 5000.

**Solution**

Check shell jobs:

```bash
jobs
```

Resume the relevant suspended job, for example:

```bash
fg %1
```

Then stop it using `Ctrl+C`. To inspect listeners:

```bash
ss -ltnp | grep ':5000'
```

The simulator and Picamera2 server both use `127.0.0.1:5000`; run only one at a time. `SO_REUSEADDR` helps with certain restart cases but does not allow two servers to bind the same address and port simultaneously.

## 5. Empty EPICS Status Value

**Symptom**

```bash
caget CAM:GetStatus
```

returned the PV name without a visible status value.

**Cause**

The record used passive processing and had not yet successfully retrieved a status.

**Solution**

Request processing:

```bash
caput CAM:GetStatus.PROC 1
```

Then read:

```bash
caget CAM:GetStatus
```

Expected after successful processing:

```text
CAM:GetStatus    IDLE
```

A normal `caget` reads the stored PV value; it does not automatically send `STATUS?` to Python. StreamDevice processing may be asynchronous, so an immediate read is not a guarantee of a freshly completed request.

## 6. Remote Channel Access Timeout from WSL

**Error**

```text
Channel connect timed out: 'CAM:GetStatus.PROC' not found.
```

**Cause**

The WSL EPICS client could not discover the Raspberry Pi IOC using its automatic network discovery configuration.

**Solution**

First verify the PV locally on the Pi. Find the Pi's IP address:

```bash
hostname -I
```

In WSL, set the discovery address (replace the documentation-only example address with the current Pi IP):

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=192.0.2.10
```

Test:

```bash
caget CAM:GetStatus
```

Remote Channel Access was successfully established using explicit address configuration. The WSL client talks to the IOC, not directly to the Python camera server.

## 7. Bash Environment Variable Syntax Error

**Error**

```text
-bash: export: `192.0.2.10': not a valid identifier
```

**Cause**

A space was inserted after `=`:

```bash
export EPICS_CA_ADDR_LIST= 192.0.2.10
```

**Solution**

Use an assignment with no spaces around `=`:

```bash
export EPICS_CA_ADDR_LIST=192.0.2.10
```

## 8. EPICS Commands Not Found in WSL

**Symptom**

```bash
which caget
```

returned no path.

**Cause**

EPICS Base was installed but its executable directory was not on `PATH`.

**Solution**

The standalone WSL EPICS Base installation was at `~/EPICS/epics-base`. Add to `~/.bashrc`:

```bash
export EPICS_BASE="$HOME/EPICS/epics-base"
export PATH="$EPICS_BASE/bin/linux-x86_64:$PATH"
```

Reload and verify:

```bash
source ~/.bashrc
which caget
```

This avoids requiring Conda activation for ordinary EPICS client tools.

## 9. Linux Terminal and Process Management

| Command | Purpose |
|---|---|
| `pwd` | Show current directory |
| `cd ..` | Move to parent directory |
| `Ctrl+C` | Interrupt foreground program |
| `Ctrl+Z` | Suspend foreground program |
| `jobs` | List shell jobs |
| `fg %1` | Resume job 1 in foreground |
| `which caget` | Locate executable on `PATH` |
| `git status` | Inspect repository changes |

Suspending a server is not the same as terminating it. Suspended processes can retain sockets and other operating-system resources.

## 10. Picamera2 Import Not Found

**Error**

```text
ModuleNotFoundError: No module named 'picamera2'
```

**Investigation**

The initial Python interpreter could not import Picamera2. Camera detection through `rpicam-hello` or the libcamera C++ API does not imply that the Picamera2 Python package is available to the interpreter.

**Verification**

```bash
python3 -c "from picamera2 import Picamera2; print('Picamera2 available')"
```

This subsequently succeeded on the Raspberry Pi. On Raspberry Pi OS, `python3-picamera2` can be installed through the system package manager if absent. If import still fails after installation, check which Python interpreter or virtual environment is active.

## 11. Python Camera Server File Was Empty

**Symptom**

Running:

```bash
python3 acquisition/picamera2_server.py
```

returned immediately without printing anything.

**Cause**

The file was empty: `cat acquisition/picamera2_server.py` displayed no content. The intended code had not been saved to that file.

**Solution**

Edit and save the correct file, then verify:

```bash
cat acquisition/picamera2_server.py
```

In Nano, save using `Ctrl+O`, Enter, then exit with `Ctrl+X`.

## 12. Python Terminal Did Not Display the Received Command

**Symptom**

The IOC status request worked, and the IMX219 initialized, but the Python terminal did not show `Received command: STATUS?`.

**Cause and solution**

The running code initially lacked the diagnostic print statement. In the original `recv()` implementation, it was added after decoding the command:

```python
command = data.decode("utf-8").strip()
print(f"Received command: {command}")
```

Save and restart the Python process; editing a file does not update an already-running interpreter. For immediate console output, start with:

```bash
python3 -u acquisition/picamera2_server.py
```

The verified output included:

```text
Connected by ('127.0.0.1', 50190)
Received command: STATUS?
IMX219 camera initialized successfully
```

In the original implementation, the camera initialization message appeared on the first `STATUS?` request. The current server instead initializes the camera only when a camera operation requires it; `STATUS?` simply reports the maintained state.

## 13. PVAccess Client Timed Out While Channel Access Worked

**Symptom**

```bash
pvget CAM:GetStatus
```

returned:

```text
Timeout
CAM:GetStatus
```

Meanwhile:

```bash
caget CAM:GetStatus
```

could locate the record (although its string value could be empty).

**Investigation**

The `pvget` tool and PVAccess libraries were installed. The IOC initially did not include the PVA server registration. The IOC Makefile was extended with:

```makefile
streamdevice_camera_DBD += PVAServerRegister.dbd
streamdevice_camera_LIBS += pvAccessIOC
streamdevice_camera_LIBS += pvAccess
streamdevice_camera_LIBS += pvData
```

After rebuilding, the generated DBD contained:

```text
registrar(registerStartPVAServer)
```

However, `pvget` still timed out. A listening TCP socket on port 5075 and UDP discovery sockets on port 5076 showed that the PVA network server had started, but not that it could serve IOC records.

Trying explicit client discovery addresses (`127.0.0.1` and the Pi's LAN address) did not resolve the timeout.

**Decisive startup warning**

```text
ServerContext configured with no Providers will do nothing!
```

The PVA server was running **without a channel provider**. The PV name printed after `Timeout` was the requested name, not evidence that the request had succeeded.

## 14. Missing QSRV Provider — PVAccess Resolution

**Cause**

The PVA server alone did not expose ordinary IOC database records. The missing component was QSRV, which supplies a PVA provider for IOC records.

**Verification of installed components**

On the Raspberry Pi, the following files were present:

```text
<EPICS_BASE>/dbd/qsrv.dbd
<EPICS_BASE>/lib/<EPICS_HOST_ARCH>/libqsrv.so
```

**Solution**

In `streamdevice_cameraApp/src/Makefile`, add:

```makefile
streamdevice_camera_DBD += PVAServerRegister.dbd
streamdevice_camera_DBD += qsrv.dbd
```

Link the PVA and QSRV libraries along with existing asyn, StreamDevice and EPICS Base libraries:

```makefile
streamdevice_camera_LIBS += qsrv
streamdevice_camera_LIBS += pvAccessIOC
streamdevice_camera_LIBS += pvAccess
streamdevice_camera_LIBS += pvData
```

Rebuild from the IOC root:

```bash
make -j2
```

Verify the generated DBD:

```bash
grep -i -E 'qsrv|registerStartPVAServer' dbd/streamdevice_camera.dbd
```

The working build contained:

```text
registrar(QSRVRegistrar)
registrar(registerStartPVAServer)
```

Restart the IOC. The earlier no-provider warning was no longer present, and `pvget CAM:GetStatus` succeeded.

**Useful IOC-shell diagnostics for this installed version**

The PVAccess source registered:

```text
pvasr 1
pval 1
```

Commands such as `pvaSrv`, `pvaServerReport` and `pvaProviderList` were not registered in this build. `pvasr 1` displayed `Clients:` in the observed test; it was the startup warning, followed by the QSRV fix and successful `pvget`, that established the root cause.

## 15. PVA Enabled but Python TCP Service Not Running

**Symptom**

During IOC startup, asyn reported:

```text
CAM_PORT -1 autoConnect could not connect:
Can't connect to 127.0.0.1:5000: Operation now in progress
```

**Explanation**

This is separate from PVAccess. The IOC's asyn TCP port could not establish a connection to the Python service at that moment, typically because the Python server was not running.

**Check**

```bash
ss -ltnp | grep ':5000'
```

Start either the real server:

```bash
python3 -u acquisition/picamera2_server.py
```

or the simulator:

```bash
python3 acquisition/camera_server_simulator.py
```

Only one may bind to `127.0.0.1:5000` at a time. A PVA client may still read a stored IOC PV even when the underlying camera service is unavailable; successful PV discovery does not prove hardware communication.

## 16. Passive Status Reads Versus Event-Driven Monitoring — Historical Investigation

**Observed behavior**

With:

```text
field(SCAN, "Passive")
```

`caget CAM:GetStatus` and `pvget CAM:GetStatus` normally read the last value stored in the IOC. Neither automatically executes StreamDevice's `STATUS?` request.

To request record processing:

```bash
caput CAM:GetStatus.PROC 1
```

This writes to the standard EPICS processing field; the value `1` is a trigger, **not** a requested camera-status value.

With:

```text
field(SCAN, "1 second")
```

the IOC would poll the Python service periodically even when no user requests status. In the original server, `STATUS?` called `initialize_camera()`, so periodic scanning could also open the camera. The current Python server no longer initializes on `STATUS?`.

**Desired behavior**

A single user PV read should obtain a fresh status without periodic polling or a separate manual `.PROC` write.

**Status**

**Subsequent outcome (Milestone 4):** The IOC now uses `SCAN = "I/O Intr"` with a Python-sent `STATUS:<state>` notification and an input-only `monitorStatus` protocol. `caget` reads the latest stored status without `.PROC`; it does not force a fresh query. This is event-driven cached readback, not fresh-on-read processing. See Section 25.

**Configuration check**

The startup script used a macro argument containing `SCAN=1 second` during testing, while the documented source record explicitly contained `field(SCAN, "Passive")`. The macro does not override a literal `SCAN` field unless the database references that macro. Check the live IOC setting using:

```bash
caget CAM:GetStatus.SCAN
```

Document the actual committed database configuration rather than assuming that a macro changes a literal field.

## 17. Git Repository File Placement

**Symptom**

`git status` showed an unexpected `picamera2_server.py` in the repository root in addition to `acquisition/picamera2_server.py`.

**Cause and solution**

The root-level file was an earlier short camera-initialization test. The intended, more complete TCP server was under `acquisition/`.

Compare before deleting:

```bash
diff -u picamera2_server.py acquisition/picamera2_server.py
```

After confirming which file is the intended implementation, remove the accidental duplicate and review changes:

```bash
rm picamera2_server.py
git status
```

The original simulated server was renamed from `acquisition/camera_server.py` to `acquisition/camera_server_simulator.py` and preserved as a separate reference implementation.

## 18. TCP Reader Decoding Error After Switching to `readline()`

**Observed error**

```text
AttributeError: 'str' object has no attribute 'decode'. Did you mean: 'encode'?
```

The traceback occurred at:

```python
command = data.decode("utf-8").strip()
```

**Cause**

The original server used `connection.recv(1024)`, which returns bytes and therefore requires decoding. The revised server uses a text-mode socket reader:

```python
reader = connection.makefile("r", encoding="utf-8")
data = reader.readline()
```

`readline()` already returns a Python string because the reader decodes incoming bytes. Calling `.decode()` again raises `AttributeError`.

**Solution**

```python
command = data.strip()
```

Retain `connection.sendall(response.encode("utf-8"))` for outgoing responses, because `sendall()` expects bytes. After this correction, the `STATUS?` TCP test returned `CLOSED` without opening the camera.

## 19. TCP Command Framing and Terminators

**Potential issue investigated**

A single `recv(1024)` call is not guaranteed to return exactly one command. TCP is a byte stream: a command may arrive in pieces, or several commands may arrive in one read.

**Implementation**

The server now reads newline-delimited commands using:

```python
reader = connection.makefile("r", encoding="utf-8")
data = reader.readline()
if not data:
    break
command = data.strip()
response = process_command(command)
connection.sendall(response.encode("utf-8"))
```

StreamDevice uses `Terminator = LF` in the existing protocol. Each Python response also ends with `\n`. This establishes explicit message boundaries in both directions. A missing terminator can leave a reader waiting for a complete message.

**Verification**

The revised server successfully processed sequential commands over a persistent Netcat TCP connection. The expanded EPICS command protocols were subsequently implemented and tested during Milestone 4. See Sections 23–30.

**Remaining limitation:** `readline()` may wait indefinitely if a client sends no newline and keeps the connection open. Socket timeouts and exceptional-path connection cleanup remain future robustness work.

## 20. Camera State and Command Validation

**Behavior clarified during development**

`STATUS?` no longer initializes the camera. It returns the current application-maintained state, initially `CLOSED`. Camera operations such as `START` and `ACQUIRE` initialize the physical camera on demand.

The server uses `update_camera_status()` to manage transitions among `CLOSED`, `IDLE`, `STREAMING`, `ACQUIRING`, and `ERROR`. `PREVIEWING` is reserved for future functionality. A status is a software state, not an independent hardware-health measurement.

**Input validation**

Exposure is converted using `int()` and must be positive. Gain is converted using `float()` and checked to be finite and positive. Invalid strings such as `EXPOSURE abc` raise `ValueError`; invalid numerical settings are rejected before replacing stored requested values. The command handler catches ordinary exceptions and returns newline-terminated `ERROR:` responses instead of allowing them to terminate the TCP command loop.

Automatic exposure is represented as `1` for enabled and `0` for disabled. Named EPICS state selection was subsequently implemented with `mbbo` records for camera commands and automatic exposure.

**Remaining limitations:** Numeric validity is not the same as validation against the IMX219's supported control ranges. Command failure handling and hardware recovery require additional testing.

## 21. Image Acquisition and Resource Cleanup

**Verified behavior**

The Python TCP server successfully handled `ACQUIRE` with manual exposure and gain, saved timestamped JPEG/JSON pairs from the same Picamera2 completed request, and returned their paths through `LATEST_IMAGE_PATH?` and `LATEST_METADATA_PATH?`.

The camera was tested in two modes:

- A single acquisition starting from a stopped camera returned to `IDLE` afterward, while leaving the camera initialized.
- Repeated acquisition while already streaming returned to `STREAMING` after each successful capture and produced distinct file pairs.

The acquisition function releases its completed request in `finally`. If the acquisition itself started streaming, cleanup stops that streaming after completion or a handled error. A camera that was already streaming is normally left streaming. `CLOSE`, detected TCP disconnection, and normal server shutdown use centralized camera cleanup.

**Important distinction:** The latest-path commands return file paths on the Raspberry Pi, not image bytes or JSON contents. Requested exposure/gain readbacks are also different from the actual values recorded in image metadata.

**Remaining limitations:** The tests demonstrated successful acquisitions, not exhaustive camera-error recovery. Unexpected disconnections, partial file writes, camera-busy failures, and I/O Intr reliability under mixed traffic remain open areas. Status and path notifications have now been demonstrated through EPICS.

## 22. Future Troubleshooting Topics

As development continues, this guide will expand to cover:

- Camera initialization failures and device-busy conditions.
- Acquisition timeouts and recovery (single and repeated image acquisition now work in Python TCP tests).
- Exposure and analogue-gain sensor-range validation and failure recovery (basic Python TCP control is tested).
- Image-saving failures, partial files and metadata consistency (successful paired JPEG/JSON saving is tested).
- Unexpected TCP disconnects and recovery (newline framing is now implemented).
- EPICS alarm states and hardware-health reporting.
- Reliable synchronization and message routing when unsolicited events share a request-response TCP connection.
- Image-display connection failures, stale image PVs, and PVAccess publisher availability (basic Phoebus RGB image display is working).

## 23. EPICS `mbbo` Camera Command Mapping

**Design and verification**

A single `CAM:CameraCommand` `mbbo` record replaces separate Start/Stop/Acquire/Close output PVs. Its states `Start`, `Stop`, `Acquire`, and `Close` map to indices 0–3. StreamDevice converts the selected index to the uppercase wire command:

```text
cameraCommand {
    ReplyTimeout = 10000;
    out "%{START|STOP|ACQUIRE|CLOSE}";
    #in "OK";
}
```

`caput CAM:CameraCommand Start` and `Stop` operated the physical camera; `Acquire` saved JPEG/JSON pairs. Repeated writes of `Acquire` triggered additional captures even when the selected `mbbo` value was unchanged.

**Important limitation:** This is an *output-only* protocol; the commented `in "OK"` is inactive. Python still returns `OK\n` for these commands, which may remain as unsolicited traffic. A successful `caput` therefore does not by itself confirm successful acquisition. This protocol inconsistency is **not resolved** and should be revisited before treating the command channel as robust.

## 24. IOC-Shell Commands Versus EPICS Client Commands

**Symptom**

```text
epics> caget CAM:CameraCommand
Command 'caget' not registered.
```

**Cause and solution**

`epics>` is the IOC shell, not a Linux shell. Run `caget`, `caput`, `camonitor`, `pvget` and `pvput` from a separate terminal. In the IOC shell, use IOC commands such as `dbl` and `dbpr` for diagnostics. The error did not indicate a missing PV.

## 25. `SCAN = "I/O Intr"` Requires Actual Incoming Notifications

**Original limitation**

A passive `GetStatus` record using `out "STATUS?"; in "%s";` returned its last stored value until explicitly processed. `SCAN = "1 second"` would poll unnecessarily. Changing the `SCAN` field alone cannot observe a Python variable.

**Implemented approach**

The Python `update_camera_status()` function now sends a newline-terminated notification whenever its state changes:

```python
message = f"STATUS:{new_status}\n"
connection.sendall(message.encode("utf-8"))
```

StreamDevice listens with:

```text
monitorStatus {
    in "STATUS:%s";
}
```

The permanent `CAM:GetStatus` is a `stringin` record using `monitorStatus`, `SCAN = "I/O Intr"`, and an initial `VAL = "CLOSED"`. `camonitor` observed `STREAMING`, `ACQUIRING` and `IDLE`; ordinary `caget` returned the latest stored state without `.PROC`. This was tested over the **same** TCP connection as the command protocols, not a separate event port.

**Scope and limitation**

`VAL = "CLOSED"` reflects the expected startup lifecycle but is not a live handshake. The code closes the camera on a detected IOC disconnect, but startup races, missed notifications, abrupt disconnects and resynchronization are not comprehensively addressed. I/O Intr updates the IOC's cached value; it does not cause `caget` to query Python on demand.

## 26. Unsolicited Status Messages Mismatched the `OK` Response

**Observed IOC error**

```text
CAM_PORT CAM:CameraCommand: Input "STATUS:STREAMING"
CAM_PORT CAM:CameraCommand: mismatch after 0 bytes ""
CAM_PORT CAM:CameraCommand: got "STATUS:STR..." where "OK" was expected
```

**Why it happened**

While processing `START` or `ACQUIRE`, Python's centralized status updater transmitted `STATUS:...` before the command handler returned `OK`. The command protocol expected `in "OK"`, so it encountered a status notification instead. The I/O Intr status record could still show updates, but this did **not** mean the command protocol had completed cleanly.

**Experiment and current state**

Removing `in "OK"` made the command protocol output-only. Camera operations continued to work, but Python still sends `OK\n`. We have **not demonstrated** that all unsolicited `OK` and status messages are correctly dispatched under every ordering. Simply changing or removing Python return statements would not, by itself, prove correct shared-port routing.

**Next investigation:** Choose a consistent acknowledgement/notification protocol, verify asyn/StreamDevice dispatch behavior under load, and test errors and reconnects. A separate event connection is an alternative, not a requirement already adopted.

## 27. Rapid Status Transitions Sometimes Missing from `camonitor`

**Observed behavior**

When acquisition began from `CLOSED`, Python emitted `IDLE → STREAMING → ACQUIRING → IDLE`. Different monitor runs displayed only subsets of the rapid initial transitions. When the camera was already streaming, both `ACQUIRING` and the final `STREAMING` were consistently observed in the reported tests.

**Interpretation**

Closely spaced notifications, EPICS record processing, shared-port message dispatch and client monitor scheduling are plausible factors. The experiments did **not** isolate the precise cause. TCP preserves byte order, but that does not guarantee every intermediate application state appears as a separate monitor event.

**Outcome**

The final status was correct in the performed tests. No artificial delays were added. This is a **known timing/visibility limitation**, not proof of reliable delivery of every intermediate transition.

## 28. Parameter Readbacks Through `FLNK`

**Design choice**

The requested exposure, gain and auto-exposure settings change through their EPICS setter records. Rather than sending unsolicited notifications for each setter, the IOC uses forward links:

```text
SetExposure     → GetExposure
SetGain         → GetGain
SetAutoExposure → GetAutoExposure
```

For example, `SetExposure` includes:

```text
field(FLNK, "$(P)$(R)GetExposure")
```

The passive `GetExposure` record then sends `EXPOSURE?` to retrieve the stored Python setting. `camonitor` and `caget` confirmed updated values after `caput` without manual `.PROC` commands; the same was tested for gain and auto exposure.

**Why not I/O Intr?** These are requested values updated by the IOC's own setters, whereas camera status can change during a single operation. `FLNK` does not detect independent external changes. Actual sensor exposure/gain remain distinct from requested settings and are available in capture metadata.

## 29. Latest Image and Metadata Paths as I/O Intr Waveforms

**Implementation**

After successful acquisition, Python stores the two file paths and sends:

```text
IMAGE_PATH:<path>\n
METADATA_PATH:<path>\n
```

Input-only protocols `monitorLatestImagePath` and `monitorLatestMetadataPath` update `waveform` records configured with `FTVL = "CHAR"`, `NELM = "512"`, and `SCAN = "I/O Intr"`.

**Observed output**

By default, `camonitor` displayed numeric character codes ending in `0` (a null terminator). This is expected for character-array waveforms. The paths displayed correctly as strings with:

```bash
caget -S CAM:GetLatestImagePath
caget -S CAM:GetLatestMetadataPath
camonitor -S CAM:GetStatus CAM:GetLatestImagePath CAM:GetLatestMetadataPath
```

Simultaneous monitoring worked. The waveform avoids the conventional short-string capacity limit; it contains a **file path**, not JPEG image bytes. These path PVs do not themselves contain image bytes. Image display is now provided separately through the Python PVAccess publisher.

**Open issue:** Multiple notifications share the command connection; repeated acquisition and error-path reliability should be stress-tested.

## 30. Status Description: Whitespace Parsing, Wrong Message and Timeout

**First symptom — surplus input / CALC INVALID**

```text
CAM:GetStatusDescription: 82 bytes surplus input " is running (camera...."
CAM:GetStatusDescription: after 6 bytes: "Camera"
```

The original `in "%s"` read only the first whitespace-delimited word. Switching to a scanset consumed descriptions containing spaces:

```text
in "%[^\n]";
```

`caget CAM:GetStatusDescription.STAT` subsequently returned `NO_ALARM` in a successful test.

**Second symptom — incorrect content**

A monitor later displayed `STATUS:STREAMING` as the status description. A broad scanset can accept an unrelated unsolicited line on the shared TCP connection. To distinguish the intended response, Python was changed to return `DESCRIPTION:<text>\n`, and the protocol became:

```text
getStatusDescription {
    out "STATUS_DESC?";
    in "DESCRIPTION:%[^\n]";
}
```

**Third symptom — timeout**

```text
CAM_PORT CAM:GetStatusDescription: No reply within 1000 ms to "STATUS_DESC?<0a>"
```

A forward link from the I/O Intr status record triggered `STATUS_DESC?` during acquisition. The Python server processes commands sequentially and can be busy capturing and saving for more than one second. Shared-port notifications can also complicate matching. A later `IDLE` description succeeded, so this was intermittent rather than a permanently broken protocol.

**Current decision:** Remove the status-to-description `FLNK`. Keep `CAM:GetStatusDescription` passive and query it explicitly when needed. Increasing `ReplyTimeout` might reduce some timeouts but would not solve shared-port message routing. Automatic description updates remain postponed.

## 31. Camera Cleanup and Shared-Connection Failure Risk — Historical Implementation

The earlier `update_camera_status()` directly called `connection.sendall(...)`. It may also be called from `close_camera()` during detected disconnect or shutdown. A connection variable may exist but refer to an already closed socket; sending can raise `OSError` and interrupt cleanup. This risk motivated the later TCP connection-management refactoring; full disconnect and failure recovery still require testing.

Likewise, a command protocol that is output-only cannot use its missing acknowledgement to confirm failure. Python's `ERROR: ...` responses may also be unsolicited relative to such a protocol. These are **remaining robustness issues**, not tested fixes.

## 32. Final Verification and Outstanding Work

**Verified in Milestone 4**

- `mbbo` camera commands operated Start/Stop/Acquire and repeated acquisition through Channel Access.
- I/O Intr camera-status updates worked without periodic polling or manual `.PROC`.
- Image and metadata path PVs updated automatically; `caget -S` displayed readable paths.
- `FLNK` refreshed requested exposure, gain and automatic-exposure readbacks.
- Multiple PVs could be monitored simultaneously.

**Not yet established**

- Reliable parsing and acknowledgement handling under all mixed notification/command sequences.
- Automatic status-description updates during acquisition.
- Further reliability and performance testing of the working Phoebus interface and separate PVAccess RGB image publisher.
- Complete disconnect/reconnect recovery and error-path behavior.


## 33. PyEpics Import Resolved to the Wrong `epics` Module

**Symptom**

```text
AttributeError: module 'epics' has no attribute 'caget'
```

An earlier version check also failed because the imported module did not provide `__version__`.

**Cause and verification**

The repository contains an `epics/` directory, which Python can recognize as a namespace package when PyEpics is not installed. Importing `epics` therefore does not, by itself, confirm that the PyEpics library is available.

```bash
python -c "import epics; print(epics.__file__)"
python -m pip show pyepics
```

**Resolution**

A project-specific environment was created with access to system-installed Picamera2 dependencies:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install pyepics
python -c "import epics; print(epics.caget, epics.caput)"
```

The import then resolved to `.venv/lib/.../site-packages/epics/__init__.py`. The `.venv/` directory is excluded from Git. Because `--system-site-packages` exposes system packages, this environment is not fully isolated.

## 34. PyEpics Could Not Connect to a PV

**Symptom**

```text
cannot connect to CAM:GetStatus
None
```

**Cause in the observed test**

The IOC was not running. The PyEpics installation itself was functioning.

**Resolution**

Start the Python camera service and the IOC, then confirm the PV using a command-line client:

```bash
caget CAM:GetStatus
```

After the IOC started, `epics.caget("CAM:GetStatus")` worked. A successful Python import does not imply that an IOC is available on the network.

## 35. Exposure Readback Initially Returned an Old Value — Historical PV Names

**Symptom**

After `caput` through PyEpics requested an exposure of `20000` microseconds, an immediate `caget` of `CAM:GetExposure` returned `0`. A later terminal read returned `20000`.

**Investigation**

The Python server log showed both `EXPOSURE 20000` and `EXPOSURE?`, confirming that the setter and FLNK-triggered getter were issued. The likely explanation is that the readback record had not finished updating when the automation read it. The exact scheduling point was not instrumented.

**Current approach**

The automation waits for the requested value rather than assuming an immediate read is current:

```python
start = time.monotonic()
while True:
    value = epics.caget("CAM:GetExposure")
    if value == requested_exposure:
        break
    if time.monotonic() - start > 5:
        raise TimeoutError("Exposure readback did not update")
    time.sleep(0.05)
```

This historical example checks the requested value maintained by the Python server, **not** the sensor-applied exposure. In the 26 October interface, the requested readback was renamed to `CAM:ExposureRB`, while `CAM:GetExposure` now reports the latest frame-metadata value during streaming. The saved JSON metadata remains the source for the specific acquired frame.

## 36. Acquisition Completion and File-Path Monitoring

**Observed behavior**

A successful write to the output-only `CAM:CameraCommand` record does not establish that a JPEG has been saved. The automation therefore records the previous `CAM:GetLatestImagePath`, sends `Acquire`, and waits for a nonempty, changed image path. It then checks that `CAM:GetLatestMetadataPath` names the corresponding JSON file.

**Limitation**

This worked in the tested exposure sweeps but is not a complete acknowledgement protocol. Missed path notifications, server restarts, and error cases require additional handling. A timeout prevents the script from waiting indefinitely. Image and metadata files remain on the Raspberry Pi even if the automation runs on another computer.

For the current scanning workflow, see [EPICS Camera Scanning](notes/epics_camera_scanning.md). Historical characterization results are retained in [Implementation and Results](implementation_and_results.md).

## 37. Matplotlib Installation Warning in the Project Environment

**Symptom**

The analysis script initially failed with:

```text
ModuleNotFoundError: No module named 'matplotlib'
```

Installing Matplotlib inside the activated virtual environment succeeded, but pip reported a dependency warning involving `types-seaborn` and `pandas-stubs`.

**Outcome**

```bash
python -m pip install matplotlib
python -c "import numpy, matplotlib; from PIL import Image; print('Libraries available')"
```

The warning did not prevent the required plotting package from installing. No additional package was needed for the tested analysis.

## 38. Raspberry Pi Booted but Wi-Fi Was Disconnected

**Symptoms**

The headless Raspberry Pi could not be reached by SSH or Raspberry Pi Connect. The previously used IP address was unreachable, but the monitor showed a normal Linux login prompt.

**Diagnosis**

After connecting a keyboard, `nmcli device status` showed `wlan0` as disconnected. The usual Wi-Fi network was visible in `nmcli device wifi list`, but `nmcli connection show` did not list its saved connection profile.

**Resolution**

Reconnect through NetworkManager without placing the password in the shell command:

```bash
sudo nmcli --ask device wifi connect "<WIFI_SSID>" ifname wlan0
nmcli device status
nmcli -f NAME,TYPE,AUTOCONNECT connection show
hostname -I
```

Wi-Fi and SSH access were restored, and the saved Wi-Fi connection showed autoconnect enabled. This was a network configuration issue, not evidence that the EPICS application or SD card needed reinstalling. Avoid publishing real Wi-Fi credentials or private network details in documentation.

## 39. Expanded PVAccess Tests and Remaining Monitor Limitation

The expanded interface was tested using `pvget`, `pvput`, and `pvmonitor`. Camera commands, exposure, gain, automatic exposure, and acquisition-file paths worked in the reported tests.

However, both `camonitor` and `pvmonitor` occasionally failed to display the brief `ACQUIRING` state. The final state remained correct. The tests did not isolate whether intermediate events were missed in StreamDevice/asyn, record processing, or client monitor delivery.

**Current decision:** Keep this as a known limitation. Automated acquisition uses a changed image path and matching metadata path rather than requiring every intermediate status event. No artificial delay was added to force status visibility.

## 40. `p4p` Import Errors During Image-Publisher Setup

**Symptom**

The `p4p` package installed successfully, but the initial test imports failed:

```text
ImportError: cannot import name 'Server' from 'p4p.server.thread'
ImportError: cannot import name 'StaticProvider' from 'p4p.server.thread'
```

**Cause**

The requested classes were imported from the wrong module. Successful package installation does not mean every class is available from the same import path.

**Resolution**

The following imports worked with the installed `p4p` version:

```python
from p4p.server import Server, StaticProvider
from p4p.server.thread import SharedPV
```

A compatible prebuilt `p4p` 4.3.0 wheel was available for CPython 3.13 on the Raspberry Pi's ARM Linux environment. The package was installed inside the project's virtual environment. A separate test publisher successfully served an image array to `pvget` and Phoebus.

## 41. Phoebus Image Widget Displayed Incorrect RGB Colors

**Symptom**

The first RGB image displayed with incorrect colors or colored stripes, even though the PVAccess array could be read successfully.

**Cause investigated**

The Python publisher provides interleaved 8-bit RGB pixel values. Phoebus must interpret the array using a matching color mode and unsigned byte values.

**Working configuration**

| Image widget property | Value |
|---|---|
| PV Name | `pva://CAM:Image` |
| Data Width | `100` |
| Data Height | `100` |
| Color Mode | `TYPE_RGB1` |
| Unsigned Data | Enabled |

The standalone proof-of-concept used `CAM:ImageTest`; the renamed publisher uses `CAM:Image`. The combination of `TYPE_RGB1` and **Unsigned Data** produced the expected color image. The image is a resized display copy; the original JPEG is preserved.

## 42. Image PV Displays Black or Does Not Refresh

**Observed behavior and checks**

The image publisher initializes its image PV with a black array. A black display can therefore mean that no saved JPEG has been published yet; it does not by itself prove a Phoebus connection failure.

The separate `acquisition/pva_image_publisher.py` program reads `CAM:GetLatestImagePath` through PyEpics, loads the saved JPEG on the Raspberry Pi, and publishes the resized RGB array through `p4p`. It must be running independently of the camera TCP server and IOC.

If the image remains black or stale, check the publisher terminal for `Published image: ...`, `Image file not found`, or publication errors. Also confirm that Phoebus uses `pva://CAM:Image`, not the earlier test PV name, and that `CAM:GetLatestImagePath` changes after acquisition.

The current publisher checks the path periodically. It may not display every intermediate acquisition if several images are captured between checks. The JPEG files remain on the Raspberry Pi; Phoebus receives the resized pixel array, not the original file.

## 43. Exposure and Gain Readbacks Initially Displayed Zero — Historical PV Names

**Symptom**

After IOC startup, Phoebus and `caget` initially displayed zero for exposure and gain setpoints/readbacks. Writing a valid exposure or gain through EPICS updated both the setpoint and the FLNK-triggered readback correctly.

**Database change**

`PINI = "YES"` was added to the then-current passive `GetExposure`, `GetGain`, and `GetAutoExposure` readback records to request their values during IOC initialization. It was **not** added to the setter records: processing an output record at startup could send an unwanted initial value, such as zero, to the Python server.

The `EGU = "us"` field was also added to the exposure setter and readback records to identify the unit as microseconds.

**Limitation**

`PINI` only requests processing at IOC initialization. It does not guarantee a successful read if the TCP service is unavailable, automatically synchronize setter PV values, or handle later reconnections. The readback initialization should be checked after IOC startup. On 26 October, the requested-value readbacks became `ExposureRB` and `GainRB`; the new actual-value `GetExposure` and `GetGain` records use I/O Intr and are not initialized by PINI.

## 44. Intermittent `SetAutoExposure` Response Mismatch

**Observed error**

```text
CAM_PORT CAM:SetAutoExposure: Input "STATUS:IDLE"
CAM_PORT CAM:SetAutoExposure: mismatch after 0 bytes ""
CAM_PORT CAM:SetAutoExposure: got "STATUS:IDL..." where "OK" was expected
```

`setAutoExposure` sends `AUTO_EXPOSURE <value>` and expects `OK`. The same TCP connection also carries unsolicited status messages. In the observed case, StreamDevice encountered `STATUS:IDLE` where it expected the acknowledgement.

The requested setting and other camera functions worked in the reported test. Subsequent tests from both the terminal and Phoebus did not reproduce the mismatch. The exact timing and message-routing cause remain unresolved.

At the time of this observation, the protocol was left unchanged. On 26 October, `ExtraInput = Ignore;` was added globally for experimental testing. The option is not established as a solution to an unexpected status line arriving before `OK`.

## 45. TCP Connection Refactoring and Actual-Value Monitoring — 26 October 2026

**Reason for the change**

The original Python server used a shared global `connection` variable and direct `connection.sendall(...)` calls in several functions. Adding live camera-reported exposure and gain monitoring introduced a second execution thread that also needed to send notifications. The server was reorganized to manage the accepted socket through a small `TCPConnection` class with `set_connection()`, `send()`, and `clear_connection()` methods. Its lock coordinates writes from the main command thread and metadata worker. The design still uses one accepted IOC TCP connection on port 5000; no additional server or port was introduced.

**New measurement path**

Picamera2's `post_callback` reads `ExposureTime` and `AnalogueGain` from completed-frame metadata without saving images. A lightweight worker checks the latest values periodically and sends `ACTUAL_EXPOSURE:<value>` and `ACTUAL_GAIN:<value>` notifications when the change meets the configured thresholds. The initial thresholds are 10 microseconds for exposure and 0.01 for gain; they control reporting, not camera settings or measurement accuracy.

The EPICS interface now distinguishes requested and camera-reported values:

| PV | Source and processing |
|---|---|
| `CAM:ExposureRB` | Requested exposure stored in Python; passive readback via FLNK/PINI |
| `CAM:GainRB` | Requested gain stored in Python; passive readback via FLNK/PINI |
| `CAM:GetExposure` | Latest camera-reported exposure; I/O Intr notification |
| `CAM:GetGain` | Latest camera-reported gain; I/O Intr notification |

The corresponding requested-value TCP queries are now `EXPOSURE_RB?` and `GAIN_RB?`, rather than `EXPOSURE?` and `GAIN?`. Historical examples in earlier sections retain the original names to document the problems as encountered. The former `automation/exposure_sweep.py` used the old requested-readback name. It has since been replaced by `automation/camera_scan.py`, which uses `CAM:ExposureRB` for requested-setting verification; `CAM:GetExposure` reports frame metadata.

**Verification and remaining limitations**

The refactored Python server passed a syntax check and produced expected results in direct Netcat testing. After the StreamDevice protocol and database changes, the requested and actual readbacks were reported to work in Phoebus. This does not establish exhaustive reliability under concurrent notifications, disconnections, or long acquisitions.

`ExtraInput = Ignore;` is now enabled globally in `stream_camera.proto` as an experiment. `ReplyTimeout` and `ReadTimeout` were left commented out globally, retaining StreamDevice defaults where no local override applies. No new intermittent mismatch was reported in the latest Phoebus test, but the earlier shared-port issue is not considered resolved. The socket lock prevents overlapping writes from cooperating Python threads; it does not guarantee that a status or metadata notification cannot arrive before an expected `OK` response.

When the camera is not producing frames, actual-value PVs may retain their last reported values. Stale-value indication and reconnection synchronization remain future improvements. For implementation details, see [StreamDevice Camera IOC](streamdevice_ioc.md) and [TCP Connection and Metadata Monitoring](notes/tcp_connection_and_metadata_monitoring.md).

## 46. `SDIS CP` Triggered Unintended Setter Processing at IOC Startup — 27 October 2026

**Symptom**

After adding scan-mode interlocks, IOC initialization produced StreamDevice response mismatches for the ordinary exposure and gain setters:

```text
CAM_PORT CAM:SetGain: Input "ERROR: Analogue gain must be a finite, p..."
CAM_PORT CAM:SetGain: got "ERROR: Ana..." where "OK" was expected
CAM_PORT CAM:SetExposure: Input "ERROR: Exposure time must be positive..."
CAM_PORT CAM:SetExposure: got "ERROR: Exp..." where "OK" was expected
```

The camera server rejected invalid zero-valued settings. Both output records were confirmed to have `PINI = NO` and `SCAN = Passive`, so neither startup PINI processing nor periodic scanning explained the writes.

**Cause and tested correction**

The new `SDIS` links used the `CP` modifier, for example:

```text
field(SDIS, "$(P)$(R)ScanEnable CP")
field(DISV, "1")
```

`CP` can request processing when the linked scan-enable PV posts a monitor event. This is undesirable for camera output records whose default values should not be sent at IOC startup. Removing `CP` from the `SDIS` links on `SetExposure`, `SetGain`, `ScanSetExposure`, and `ScanSetGain` eliminated the observed startup errors:

```text
field(SDIS, "$(P)$(R)ScanEnable")
```

Keep `DISV = 1` on ordinary setters (disabled when scan mode is enabled) and `DISV = 0` on scan-specific setters (disabled when scan mode is off). The resulting interlocks were checked through Phoebus and behaved as expected in the reported tests.

**Limitation:** Record disabling prevents normal processing; it does not provide per-client access security or guarantee that a disabled record's `VAL` cannot be written.

## 47. Scan Waveform Returned 100 Values Despite Three Valid Points

**Symptom**

Writing three exposure values using:

```bash
caput -a CAM:ScanExposure 3 5000 10000 20000
```

was followed by `caget CAM:ScanExposure` displaying 100 values: the three supplied numbers and 97 zeros. The same behavior occurred with `CAM:ScanIntensity`.

**Investigation and outcome**

The waveform records have `FTVL = DOUBLE` and `NELM = 100`, allowing up to 100 scan points. The observed `NORD` fields correctly reported `3` after the three-element writes. Thus the IOC tracked the number of valid values, even though the default Channel Access client display included the full allocated array capacity.

```bash
caget CAM:ScanExposure.NORD
caget CAM:ScanIntensity.NORD
caget -# 3 CAM:ScanExposure
```

Do not remove `NELM` to solve this display issue; it sets the maximum waveform capacity. The scan program writes the growing numerical arrays, and `NORD` indicates the valid element count.

## 48. Phoebus XY Plot Included an Unwanted `(0, 0)` Point

**Symptom**

The XY Plot displayed the measured exposure–intensity points but also an extra point at the origin. Both waveform `NORD` fields reflected the expected valid measurement count. A later five-point exposure scan showed:

```text
pvget CAM:ScanExposure
[982,1984,2986,3988,4990]
```

while `caget CAM:ScanExposure` displayed those five values followed by zeros up to the 100-element waveform capacity.

**Tested workaround**

In the Phoebus XY Plot trace configuration, explicitly select PVAccess for both numerical waveforms:

```text
X PV: pva://CAM:ScanExposure
Y PV: pva://CAM:ScanIntensity
```

The operator confirmed that the unwanted origin point disappeared. For gain scans, use `pva://CAM:ScanGain` as the X PV and the same intensity waveform as Y. The trace type can be set to `Line` for a conventional characterization curve.

**Interpretation:** The observed difference between the CA and PVA array representations is consistent with Phoebus receiving trailing unused zeros through the original configuration. The tests establish that switching the plot to PVA fixed the visible problem; they do not establish that every CA client or every Phoebus configuration necessarily behaves this way.

## 49. Phoebus Display Responsiveness During Plot Testing

**Observation**

During scan-plot testing, Phoebus appeared unusually slow, and part of the plotted curve was temporarily not visible. No definitive cause was established. The user tested a simplified display to help isolate the behavior, but no performance measurements or confirmed resolution were recorded.

**Status:** Keep this as an open observation. If it recurs, compare a minimal XY Plot with the full camera dashboard, and distinguish plot redraw delays from delayed or missing PV updates before changing the IOC or scan program.

## 50. First Scan Measurement Used the Previous Camera Setting — 28 October 2026

**Symptom**

The scan completed, but the first exposure measurement was inconsistent with the requested starting point. In one four-point test, the reported actual exposure values were approximately `34990`, `9999`, `13326`, and `16653` microseconds. A gain scan also initially reported a value associated with the preceding setting.

**Investigation**

The scan originally waited for `CAM:ExposureRB` or `CAM:GainRB` after writing `CAM:ScanSetExposure` or `CAM:ScanSetGain`, then immediately requested acquisition. These requested-value readbacks confirm the settings held by the Python camera server; they do not prove that a completed camera frame has used the new setting. The scan already took its plotted X value from the acquired image's JSON metadata, so the plot was reporting the acquired frame rather than inventing an incorrect X value.

**Change and outcome**

The scan program now also waits for the corresponding camera-reported PV (`CAM:GetExposure` or `CAM:GetGain`) to approach the requested value before acquiring. The initial test tolerances were 100 microseconds for exposure and 0.05 for gain, with a 10-second timeout. The acquired image's own metadata remains the authoritative X value for that measurement. Exposure and gain scans subsequently worked in the reported tests.

**Limitation:** The live actual-value PV is updated periodically from completed-frame metadata and can be stale; Picamera2 may also have queued frames. This check improves synchronization but is not a general guarantee of frame freshness or exact requested-versus-applied equality.

## 51. Actual-Exposure Wait Timed Out When Camera Was IDLE

**Symptom**

```text
Scan failed: CAM:GetExposure did not reach 50000
```

A diagnostic check showed:

```text
CAM:ScanSetExposure  50000
CAM:ExposureRB       50000
CAM:GetExposure      10491
CAM:GetStatus        IDLE
```

**Cause**

The requested exposure had been accepted, but the camera was not streaming. `CAM:GetExposure` is updated from completed-frame metadata, so in `IDLE` it could retain an older value rather than advance toward the new request. Waiting for the actual PV before issuing an acquisition could therefore time out.

**Tested correction**

The scan controller starts the camera if it is not already streaming, and waits until `CAM:GetStatus` reports `STREAMING` before proceeding to the setting-verification and acquisition loop. This preserves the sequential PyEpics design without introducing another thread or TCP connection. Scanning subsequently worked in the observed tests.

**Important:** A status check is a synchronization step, not a guarantee that all pending TCP messages have been dispatched or that every queued frame is fresh. Retain a timeout and Stop Scan checks where appropriate.

## 52. Status Notifications Mismatched Scan Responses During IDLE-to-STREAMING Startup

**Symptom**

Although a scan could finish successfully, the IOC logged errors such as:

```text
CAM_PORT CAM:ScanSetExposure: Input "STATUS:IDLE"
CAM_PORT CAM:ScanSetExposure: got "STATUS:IDL..." where "OK" was expected
CAM_PORT CAM:ExposureRB: Input "STATUS:STREAMING" does not match format "%d"
CAM_PORT CAM:ScanSetExposure: got "STATUS:STR..." where "OK" was expected
```

**Investigation**

The Python server sends unsolicited `STATUS:` notifications over the same asyn TCP connection used for setter acknowledgements and numeric readbacks. Targeted testing found the errors when scans were initiated from `IDLE`, but not during the tested steady-streaming scans. This was consistent with status-transition notifications overlapping subsequent request-response transactions; the exact StreamDevice message-dispatch sequence was not instrumented.

**Tested correction**

After issuing `Start`, `camera_scan.py` now waits for `CAM:GetStatus` to report `STREAMING` before sending scan setpoints. The operator confirmed that the observed mismatch errors disappeared with this change. No change to `stream_camera.proto`, its `in "OK"` acknowledgements, or the single TCP connection was needed for this test.

**Remaining limitation:** The successful test does not prove that unsolicited notifications and command responses are always routed correctly under all timing, reconnect, or error conditions. `ExtraInput = Ignore;` is not a general-purpose notification router, and the output-only `cameraCommand` protocol still has an acknowledgement inconsistency with the Python server.

## 53. Scan and Phoebus Verification — 28 October 2026

Both exposure and gain scan modes were exercised successfully, including the corresponding Phoebus scan displays. Stop Scan was observed to interrupt the scan, and repeated scans were reported to work. The Stop Scan PV/button is not automatically reset after an interrupted scan; automatic reset was deliberately not added.

The repository now contains three Phoebus `.bob` displays under `phoebus/`: `epics_Camera_vision_main.bob`, `epics_Camera_vision_scan_exposure.bob`, and `epics_Camera_vision_scan_gain.bob`. The main display provides separate exposure/gain actions that select the scan type and open the corresponding display. These UI changes do not require additional camera TCP commands.

These checks establish the behavior observed in the tested workflows, not exhaustive performance, disconnect/reconnect, or long-duration reliability.

---

**Documentation status (28 October 2026):** Exposure and gain scans, scan-setting synchronization, saved JPEG/JSON acquisition, intensity calculation, CSV logging, live PVAccess XY plotting, Stop Scan interruption, and repeated scan operation have been demonstrated. Waiting for `STREAMING` resolved the observed startup response mismatches in the reported tests. The general single-port notification/acknowledgement ordering problem, stale-value indication, reconnect/error recovery, and Phoebus performance under broader conditions remain open areas for investigation.
