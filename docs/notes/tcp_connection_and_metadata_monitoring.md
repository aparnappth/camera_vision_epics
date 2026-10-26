# TCP Connection Management and Camera Metadata Monitoring

**Project:** EPICS-Controlled Camera Characterization and Vision Platform  
**Implementation checkpoint:** 26 October 2026  
**Source:** `acquisition/picamera2_server.py`  
**Related guide:** [StreamDevice Camera IOC](../streamdevice_ioc.md)

## 1. Objective

The Python camera server originally sent TCP messages directly through a global `connection` socket. As the application grew, status notifications, acquisition file paths, command replies, and camera-reported exposure/gain values all needed to use that same socket. The implementation was refactored to centralize socket writes in a small `TCPConnection` class and to collect frame metadata without making the Picamera2 callback perform network I/O.

**The EPICS architecture is unchanged:** one conventional IOC uses StreamDevice/asyn to communicate with the Python camera server over `127.0.0.1:5000`. The independent `pva_image_publisher.py` remains separate.

## 2. Responsibilities of the three components

```text
Picamera2 completed frame
         |
         v
frame_callback(request)  -- reads metadata, stores latest values
         |
         v
actual_exposure / actual_gain
         |
         v
monitor_actual_settings() -- lightweight worker, compares with last sent values
         |
         v
tcp.send("ACTUAL_EXPOSURE:...\n") / tcp.send("ACTUAL_GAIN:...\n")
         |
         v
Single TCP connection -> StreamDevice input-only protocols -> I/O Intr PVs
```

The main command loop also uses `tcp.send()` for command replies. Camera status and file-path notifications use the same method. No new socket, port, or IOC is created by the metadata worker.

## 3. Understanding the `TCPConnection` class

The class groups the active socket reference and the operations that act on it:

```python
class TCPConnection:
    def __init__(self):
        self.connection = None
        self.lock = threading.Lock()

    def set_connection(self, connection):
        with self.lock:
            self.connection = connection

    def send(self, message):
        # False means no active connection was registered.
        # Socket errors are allowed to propagate to the caller.
        with self.lock:
            if self.connection is None:
                return False
            self.connection.sendall(message.encode("utf-8"))
            return True

    def clear_connection(self):
        with self.lock:
            self.connection = None


tcp = TCPConnection()
```

### 3.1 `class`, object and `self`

`class TCPConnection:` defines a new Python type. `tcp = TCPConnection()` creates one *instance* of that type. The name `self` refers to the particular instance on which a method is called. `self.connection` is therefore data owned by `tcp`, whereas the argument named `connection` in `set_connection(self, connection)` is a temporary local reference passed into that method.

`__init__()` runs automatically when the instance is created. Setting `self.connection = None` means no client socket has been registered yet; it **does not** create a socket or connect to the IOC. `self.lock = threading.Lock()` creates a mutual-exclusion lock owned by this instance.

### 3.2 Registering the existing connection

The listening server still uses the normal socket API:

```python
connection, address = server.accept()
tcp.set_connection(connection)
```

`server.accept()` returns the accepted client socket. `set_connection()` only stores that socket inside the class. The class does not call `bind()`, `listen()` or `accept()` itself.

### 3.3 Sending a message

For example:

```python
tcp.send("STATUS:STREAMING\n")
```

The method acquires the lock, checks whether a socket has been registered, encodes the string as UTF-8 bytes and calls `sendall()`. It returns `False` if no connection is registered and `True` if `sendall()` completes without raising an exception. **`True` does not mean StreamDevice successfully interpreted the message**; it only describes the local send operation.

If `sendall()` raises `OSError`, the exception propagates. The calling function must decide whether to log, recover or terminate. A `False` result and an exception are deliberately different outcomes.

### 3.4 Why use `with self.lock:`?

Both the command-handling thread and the metadata worker can send through the same socket. A lock ensures that cooperating callers of `tcp.send()` do not execute their socket writes concurrently. `with` releases the lock automatically, including when an exception occurs.

**A lock does not decide which message should arrive first.** A metadata notification can still precede an expected `OK` reply, causing a StreamDevice protocol mismatch. The lock protects the Python-side write operation, not the entire EPICS request/response transaction.

### 3.5 Clearing the connection

```python
tcp.clear_connection()
connection.close()
```

`clear_connection()` sets the stored reference to `None` while holding the lock, preventing later worker calls from starting a send through that reference. It **does not itself close the socket**. The main server loop remains responsible for closing the accepted socket and its reader. A previously initiated send can still fail during disconnection.

## 4. Picamera2 frame callback

The callback is registered when the camera object is initialized:

```python
camera = Picamera2(camera_id)
camera.post_callback = frame_callback
```

Its purpose is to retrieve camera-reported values from completed frames:

```python
def frame_callback(request):
    global actual_exposure, actual_gain

    metadata = request.get_metadata()
    new_exposure = metadata.get("ExposureTime")
    new_gain = metadata.get("AnalogueGain")

    if new_exposure is not None:
        actual_exposure = new_exposure
    if new_gain is not None:
        actual_gain = new_gain
```

The callback **does not save an image, send TCP data or wait for a network reply**. This keeps the frame-processing path lightweight. These are camera-reported applied settings associated with frames, not independent measurements of physical exposure or gain.

The latest values are stored in Python variables; they are not the same as the requested settings (`exposure_time` and `analogue_gain`). When the camera is stopped, the most recently stored values can remain in memory and must not be interpreted as fresh measurements.

## 5. Lightweight metadata-monitoring worker

The worker is a second Python thread inside the **same process**, not a second TCP connection. It periodically examines the latest values stored by the callback:

```python
METADATA_CHECK_INTERVAL = 0.2  # seconds
GAIN_CHANGE_THRESHOLD = 0.01
# Optional, if enabled in the current source:
# EXPOSURE_CHANGE_THRESHOLD = 10  # microseconds
```

A simplified version of its change-detection logic is:

```python
previous_exposure = None
previous_gain = None

# Inside the worker's repeating loop, while camera is streaming:
exposure = actual_exposure
gain = actual_gain

if exposure is not None and exposure != previous_exposure:
    if tcp.send(f"ACTUAL_EXPOSURE:{exposure}\n"):
        previous_exposure = exposure

if gain is not None and (
    previous_gain is None
    or abs(gain - previous_gain) >= GAIN_CHANGE_THRESHOLD
):
    if tcp.send(f"ACTUAL_GAIN:{gain}\n"):
        previous_gain = gain
```

The actual worker also sleeps between checks, tests whether the camera is streaming, and handles socket errors. The values called `previous_exposure` and `previous_gain` represent **last successfully sent values**, not necessarily the immediately preceding frame.

An optional exposure threshold can replace the exact exposure comparison:

```python
if exposure is not None and (
    previous_exposure is None
    or abs(exposure - previous_exposure) >= EXPOSURE_CHANGE_THRESHOLD
):
    ...
```

Use the threshold only if it is present in the actual committed code. Thresholds reduce notification traffic but do not change the sensor settings or the saved acquisition metadata. A gain threshold of `0.01` and an illustrative exposure threshold of `10 µs` are not calibrated error tolerances.

### 5.1 Starting the worker

```python
metadata_thread = threading.Thread(
    target=monitor_actual_settings,
    daemon=True
)
metadata_thread.start()
```

`target=monitor_actual_settings` passes the function itself; adding parentheses would call it immediately. `.start()` begins executing the function in another thread while the main thread continues accepting and processing TCP commands. `daemon=True` means this worker does not prevent the process from exiting, but it is not a substitute for graceful thread shutdown.

## 6. From TCP notifications to EPICS PVs

The Python worker sends newline-terminated messages such as:

```text
ACTUAL_EXPOSURE:19999
ACTUAL_GAIN:1.25
```

The matching StreamDevice input-only protocols are:

```text
monitorActualExposure {
    in "ACTUAL_EXPOSURE:%d";
}

monitorActualGain {
    in "ACTUAL_GAIN:%f";
}
```

The associated `camera.db` records use `SCAN = "I/O Intr"`. They receive incoming values rather than initiating queries. This is the same EPICS processing concept already used for camera-status and file-path notifications.

| EPICS PV | Source | Processing |
|---|---|---|
| `CAM:SetExposure` | Requested exposure command | StreamDevice output |
| `CAM:ExposureRB` | Requested exposure stored in Python | Passive readback, FLNK/PINI |
| `CAM:GetExposure` | Latest camera-reported exposure | StreamDevice I/O Intr |
| `CAM:SetGain` | Requested gain command | StreamDevice output |
| `CAM:GainRB` | Requested gain stored in Python | Passive readback, FLNK/PINI |
| `CAM:GetGain` | Latest camera-reported gain | StreamDevice I/O Intr |

The requested-value queries were renamed to `EXPOSURE_RB?` and `GAIN_RB?`. Actual values are published as notifications; no additional actual-value query command is required in this implementation.

## 7. Testing performed and current limits

The refactored Python server was syntax-checked and tested directly using Netcat. The updated exposure/gain PVs were subsequently tested through Phoebus, and the user reported that the controls and monitoring worked as expected.

The tested setup retained one TCP connection and used a common `tcp.send()` path. The separate image publisher was not modified.

Known limitations:

- The main command loop and metadata worker share the same TCP connection. The write lock prevents concurrent sends from these cooperating code paths, **not** mismatches between unsolicited notifications and command acknowledgements.
- `ExtraInput = Ignore;` was enabled in the global StreamDevice configuration as an experiment; it has not been established as a fix for notifications arriving before `OK`. `ReplyTimeout` and `ReadTimeout` were left commented out globally.
- The actual-value PVs may retain stale values after the camera stops; explicit validity or alarm handling remains future work.
- The worker checks values periodically and may skip intermediate changes. It is intended for monitoring the latest setting, not recording every frame's metadata.
- `sendall()` can fail on disconnect. Full recovery and reconnection synchronization have not been verified.
- The old exposure-sweep script must use `CAM:ExposureRB` when checking the requested setting; `CAM:GetExposure` now means camera-reported applied exposure.

## 8. Why this refactoring was chosen

The main benefit is **separation of responsibilities**: the camera callback reads metadata, the worker decides when a change is worth reporting, and the TCP connection object handles socket access. This reduces repeated socket-management code without introducing another server or changing the conventional EPICS IOC architecture.

The planned EPICS-triggered exposure scan is a separate next step. Its soft PVs, database-level interlocks, dedicated `CAM:ScanSetExposure`, and live intensity plot have **not** been implemented as part of this metadata-monitoring change.

## References

- [StreamDevice Camera IOC](../streamdevice_ioc.md)
- [Automated Acquisition and Initial Characterization](automated_acquisition_and_characterization.md)
- [PVAccess Image Publisher](pva_image_publisher.md)
- [Python threading documentation](https://docs.python.org/3/library/threading.html)
- [Python socket documentation](https://docs.python.org/3/library/socket.html)
