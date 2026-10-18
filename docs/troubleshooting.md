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
~/projects/epics/base/dbd/qsrv.dbd
~/projects/epics/base/lib/linux-arm/libqsrv.so
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
- Full PVAccess testing of the expanded control interface and future Phoebus image display.

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

Simultaneous monitoring worked. The waveform avoids the conventional short-string capacity limit; it contains a **file path**, not JPEG image bytes. This does not yet provide image display in Phoebus.

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

## 31. Camera Cleanup and Shared-Connection Failure Risk

The current `update_camera_status()` directly calls `connection.sendall(...)`. It may also be called from `close_camera()` during detected disconnect or shutdown. A connection variable may exist but refer to an already closed socket; sending can raise `OSError` and interrupt cleanup. The current Python server does not fully guard this case.

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
- Full expanded-interface testing through PVAccess and Phoebus.
- Image-byte transfer through EPICS (the current PVs expose paths only).
- Complete disconnect/reconnect recovery and error-path behavior.

---

**Documentation status (18 October 2026):** Milestone 4 EPICS-controlled acquisition and readbacks have been demonstrated. This guide preserves earlier investigations and records unresolved communication limitations separately from verified results. Examples use documentation-only network addresses rather than a particular device's LAN IP.
