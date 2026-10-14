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

In WSL, set the discovery address (replace the example with the current Pi IP):

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=192.168.0.176
```

Test:

```bash
caget CAM:GetStatus
```

Remote Channel Access was successfully established using explicit address configuration. The WSL client talks to the IOC, not directly to the Python camera server.

## 7. Bash Environment Variable Syntax Error

**Error**

```text
-bash: export: `192.168.0.176': not a valid identifier
```

**Cause**

A space was inserted after `=`:

```bash
export EPICS_CA_ADDR_LIST= 192.168.0.176
```

**Solution**

Use an assignment with no spaces around `=`:

```bash
export EPICS_CA_ADDR_LIST=192.168.0.176
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

The running code initially lacked the diagnostic print statement. Add it after decoding the command:

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

The camera initialization message appears only on the first successful initialization in a server session, while the command message appears for each received request.

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

## 16. Passive Status Reads Versus Periodic Polling — Open Design Issue

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

the IOC would poll the Python service periodically even when no user requests status. Because the Python handler calls `initialize_camera()` for `STATUS?`, periodic scanning can also open the camera without an explicit client read.

**Desired behavior**

A single user PV read should obtain a fresh status without periodic polling or a separate manual `.PROC` write.

**Status**

Unresolved architectural requirement. Neither enabling PVAccess/QSRV nor setting `PINI` or `SCAN` alone provides read-triggered StreamDevice processing. No workaround was adopted as the final interface.

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

## 18. Future Troubleshooting Topics

As development continues, this guide will expand to cover:

- Camera initialization failures and device-busy conditions.
- Actual image acquisition and acquisition timeouts.
- Exposure and analogue-gain control.
- Image saving and metadata handling.
- TCP message framing, unexpected disconnects and recovery.
- EPICS alarm states and hardware-health reporting.
- On-demand fresh PV read behavior without continuous polling.

---

**Documentation status:** Covers the Milestone 1 simulated TCP service and Milestone 2 Picamera2 initialization, Channel Access and PVAccess/QSRV integration. Image acquisition and advanced camera controls remain planned.
