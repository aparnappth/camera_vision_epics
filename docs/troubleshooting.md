# Troubleshooting — EPICS Camera Project

This document records problems encountered during the development of the EPICS-controlled camera platform and explains how they were investigated and resolved.

For installation instructions, see [EPICS Environment Setup](epics_setup.md). For the IOC implementation, see [StreamDevice Camera IOC](streamdevice_ioc.md).

## 1. StreamDevice Example IOC Linker Error

**Error**

During the StreamDevice 2.8.26 build:

```text
undefined reference to `pvar_func_vxi11RegisterCommands'
collect2: error: ld returned 1 exit status
```

**Cause investigated**

The StreamDevice example IOC referenced a VXI-11 registration function that was not exported by the installed asyn shared library.

VXI-11 is a protocol used by certain laboratory instruments. It is not required for this project's TCP/IP camera service.

**Outcome**

The StreamDevice library itself compiled and installed successfully:

```text
libstream.so
libstream.a
```

The example IOC was left unchanged. The project's own IOC subsequently compiled and linked successfully.

The underlying VXI-11 registration mismatch was not resolved.

## 2. StreamDevice Protocol File Not Installed

**Symptom**

After running `make`, the installed `db/` directory contained `camera.db`, but not `stream_camera.proto`.

**Cause**

The original protocol file was located in a separate `protocol/` directory, and the installation rule did not install it as intended.

**Solution**

Move the protocol source into:

```text
streamdevice_cameraApp/Db/stream_camera.proto
```

Configure `streamdevice_cameraApp/Db/Makefile`:

```makefile
DB += camera.db
DB += stream_camera.proto
```

Rebuild:

```bash
make -j2
```

Verify:

```bash
ls db
```

Both files should appear.

## 3. EPICS Database Syntax Error

**Error**

During IOC startup:

```text
ERROR: syntax error
at or before 'field' in file "../../db/camera.db"
```

The database contained an incorrectly written field:

```text
field(field(INP, "@stream_camera.proto getStatus CAM_PORT")
```

**Solution**

Correct the source database:

```text
field(INP, "@stream_camera.proto getStatus $(PORT)")
```

Rebuild the IOC and restart it.

Always edit the source file under `streamdevice_cameraApp/Db/`, rather than the installed copy in `db/`.

## 4. Python TCP Port Already in Use

**Error**

```text
OSError: [Errno 98] Address already in use
```

**Cause**

The Python server had been suspended using `Ctrl+Z` rather than terminated.

The suspended process still held the TCP socket bound to port 5000.

**Solution**

Check shell jobs:

```bash
jobs
```

Resume the suspended job:

```bash
fg %1
```

Then stop it using `Ctrl+C`.

If necessary, inspect listening TCP sockets:

```bash
ss -ltnp | grep ':5000'
```

Avoid starting multiple Python server processes on the same address and port.

## 5. Empty EPICS Status Value

**Symptom**

```bash
caget CAM:GetStatus
```

returned the PV name without a visible status value.

**Cause**

The record was configured for passive processing and had not yet successfully retrieved a status.

**Solution**

Trigger record processing:

```bash
caput CAM:GetStatus.PROC 1
```

Then read:

```bash
caget CAM:GetStatus
```

Expected response:

```text
CAM:GetStatus    IDLE
```

A normal `caget` reads the stored PV value and does not necessarily request a fresh measurement.

## 6. Remote Channel Access Timeout from WSL

**Error**

```text
Channel connect timed out: 'CAM:GetStatus.PROC' not found.
```

**Cause**

The WSL EPICS client could not discover the Raspberry Pi IOC using the current network configuration.

**Solution**

First verify that the PV works locally on the Raspberry Pi.

Find the Pi's current IP address:

```bash
hostname -I
```

Then configure WSL:

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=xxx.xxxx
```

Replace the example address with the Pi's current IP address.

Test:

```bash
caget CAM:GetStatus
```

Remote Channel Access was successfully established using explicit address configuration.

## 7. Bash Environment Variable Syntax Error

**Error**

```text
-bash: export: `xxxxxx': not a valid identifier
```

**Cause**

A space was inserted after the assignment operator:

```bash
export EPICS_CA_ADDR_LIST= xxxxx
```

**Solution**

Remove the space:

```bash
export EPICS_CA_ADDR_LIST=xxxxx
```

Bash variable assignments must not contain spaces around `=`.

## 8. EPICS Commands Not Found in WSL

**Symptom**

```bash
which caget
```

returned no path.

**Cause**

EPICS Base was installed but its executable directory was not included in the shell's `PATH`.

**Solution**

The existing standalone EPICS Base installation was located at:

```text
~/EPICS/epics-base
```

Add the following to `~/.bashrc`:

```bash
export EPICS_BASE="$HOME/EPICS/epics-base"
export PATH="$EPICS_BASE/bin/linux-x86_64:$PATH"
```

Apply:

```bash
source ~/.bashrc
```

Verify:

```bash
which caget
```

This avoids requiring activation of a Conda environment for ordinary EPICS client commands.

## 9. Linux Terminal and Process Management

Some useful commands encountered during development:

| Command       | Purpose                             |
| ------------- | ----------------------------------- |
| `pwd`         | Show the current directory          |
| `cd ..`       | Move to the parent directory        |
| `Ctrl+C`      | Interrupt a foreground program      |
| `Ctrl+Z`      | Suspend a foreground program        |
| `jobs`        | List shell jobs                     |
| `fg %1`       | Resume job 1 in the foreground      |
| `which caget` | Locate an executable through `PATH` |
| `git status`  | Inspect repository changes          |

Suspending a server is not the same as terminating it. Suspended processes can continue holding operating-system resources.

## 10. Future Troubleshooting Topics

As the project develops, this document will be expanded to cover:

- Picamera2 initialization and camera access
- Acquisition timeouts
- Camera-busy conditions
- Exposure and gain configuration
- Image-saving failures
- TCP disconnections and recovery
- EPICS alarms and error reporting

---

**Documentation status:** Covers issues encountered during the initial EPICS-to-Python communication milestone.
