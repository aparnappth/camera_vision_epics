## Choosing an EPICS Device Integration Approach

The appropriate method for integrating an instrument into EPICS depends on the communication interface provided by the instrument.

| Instrument interface | EPICS integration approach |
|---|---|
| SCPI or another command/response protocol over TCP/IP or serial | StreamDevice with asyn |
| Existing EPICS-compatible device driver | Use the existing driver directly |
| Manufacturer-specific C/C++ SDK | Use an EPICS driver or develop a suitable integration layer |
| Python API | Use a Python-based IOC or an intermediate service |
| areaDetector-compatible camera driver | Use areaDetector and its camera-specific driver |

### Why StreamDevice was chosen for this project

The IMX219 camera is accessed through the Linux camera stack using libcamera. Picamera2 provides a Python interface to libcamera.

Unlike many laboratory instruments that support SCPI, Picamera2 does not provide a built-in text-based TCP command interface that StreamDevice can communicate with directly.

Therefore, this project uses an intermediate Python TCP server:

```text
EPICS IOC
    |
StreamDevice + asyn
    |
Custom TCP command protocol
    |
Python camera_server.py
    |
Picamera2 API
    |
libcamera
    |
IMX219
```

The Python server interprets text commands received from StreamDevice and translates them into Picamera2 API calls.

For example, a future exposure-setting operation could translate:

```text
EXPOSURE 5000
```

into:

```python
picam2.set_controls({"AeEnable": False, "ExposureTime": 5000})
```

This is a planned operation, not part of the current implementation.

### When StreamDevice is unnecessary

If an instrument already has a compatible EPICS driver, that driver can communicate with the instrument without requiring StreamDevice.

For example, an EPICS camera driver may communicate directly with a manufacturer's camera SDK while exposing standardized EPICS PVs.

A Linux hardware driver alone does not provide EPICS integration. An EPICS-compatible software interface is still required.

### Alternative implementation

A separate areaDetector-based implementation is planned for this project.

It will investigate whether a suitable camera driver can be used or adapted for the IMX219 and explore areaDetector's standard acquisition, NDArray and plugin architecture.

The two approaches will be maintained separately to support learning and comparison.
