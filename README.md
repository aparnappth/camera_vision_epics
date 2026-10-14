# EPICS-Controlled Camera Characterization and Vision Platform

A Raspberry Pi Zero 2 W and Sony IMX219-based project exploring camera control, quantitative camera characterization, computer vision, and integration with the EPICS control system.

## Project Objectives

This project focuses on four areas:

- **EPICS-based camera control:** Develop and compare conventional EPICS and areaDetector-based camera control systems.
- **Camera characterization:** Investigate sensor performance through quantitative measurements of exposure response, gain, noise, and image uniformity.
- **Computer vision:** Explore image-processing applications, including LED recognition and hand-gesture detection.
- **Hardware monitoring:** Integrate basic electronic components, monitoring, and alarm functionality with EPICS.

## Hardware

- Raspberry Pi Zero 2 W
- Sony IMX219 8 MP CSI camera
- LEDs and basic electronic components

## System Architecture

The project explores two EPICS integration approaches.

### 1. Conventional EPICS IOC — In Development

```text
EPICS Clients
    |
    +-- Channel Access (caget / caput)
    |
    +-- PVAccess (pvget / pvput)
    |
    v
EPICS IOC + QSRV
    |
StreamDevice + asyn
    |
Custom TCP command protocol
    |
Python camera server
    |
Picamera2
    |
libcamera
    |
Sony IMX219
```

The conventional IOC supports Channel Access and PVAccess. The Python service initializes the physical camera automatically when the first supported camera-status request is received.

Image acquisition and camera-parameter control through EPICS are not yet implemented.

### 2. areaDetector IOC — Planned

```text
EPICS Clients
    |
areaDetector
    |
Camera-specific driver
    |
Camera software interface
    |
IMX219
```

This implementation will investigate camera-driver integration, standard acquisition PVs, NDArray data structures, and image-processing plugins.

## Current Progress

### Milestone 1 — EPICS-to-Python Communication

- [x] Install EPICS Base R7.0.10
- [x] Install asyn R4-46 and StreamDevice 2.8.26
- [x] Create and compile a conventional EPICS IOC
- [x] Implement a Python TCP camera simulator
- [x] Establish StreamDevice/asyn TCP communication
- [x] Implement the `STATUS?` command
- [x] Verify local and remote Channel Access

### Milestone 2 — Picamera2 Integration and PVAccess

- [x] Verify IMX219 detection through Picamera2
- [x] Inspect camera properties and available controls
- [x] Preserve the original Python camera simulator
- [x] Develop a separate Picamera2 TCP server
- [x] Identify the camera by model name
- [x] Implement automatic camera initialization on the first `STATUS?` request
- [x] Reuse the initialized camera object for subsequent requests
- [x] Implement TCP connection handling and shutdown cleanup
- [x] Enable PVAccess server support
- [x] Integrate QSRV as the IOC database provider
- [x] Verify camera-status access through Channel Access and PVAccess

**Current functionality:** The IOC can communicate with the Python service, initialize the physical IMX219, and retrieve the software-maintained camera status.

Actual image acquisition has not yet been implemented.

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       └── epics_device_integration.md
├── acquisition/
│   ├── camera_server_simulator.py
│   └── picamera2_server.py
├── characterization/
├── vision/
└── epics/
    └── streamdevice_camera/
        └── streamdevice_camera_ioc/
```

## Documentation

### Setup and Implementation

- [EPICS Environment Setup](docs/epics_setup.md) — Installation and configuration of EPICS Base, asyn, and StreamDevice.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC architecture, Python TCP communication, Picamera2 integration, database records, and CA/PVA configuration.
- [Troubleshooting](docs/troubleshooting.md) — Installation, compilation, networking, and IOC configuration issues encountered during development.

### Learning Notes

- [Understanding EPICS Device Integration](docs/notes/epics_device_integration.md) — Hardware drivers, EPICS device support, StreamDevice, asyn, Python APIs, and areaDetector.

The learning notes document concepts and architectural decisions explored during development.

## Current Limitations and Open Design Questions

- The camera is initialized through Picamera2 but image acquisition is not yet implemented.
- Camera status is maintained by the Python service and does not independently measure camera hardware health.
- The TCP server currently handles one active client connection at a time.
- TCP command framing and error recovery require further improvement.
- Exposure and analogue-gain control through EPICS are not yet implemented.
- Fresh status retrieval through a single PV read, without periodic polling or an explicit `.PROC` write, remains an open design requirement.

The current StreamDevice record uses passive processing. A normal `caget` or `pvget` reads the stored PV value rather than automatically requesting an updated status from Python.

Detailed discussion is maintained in the [StreamDevice IOC documentation](docs/streamdevice_ioc.md).

## Development Roadmap

### Phase 1 — EPICS Communication

- [x] Establish StreamDevice/asyn communication
- [x] Implement a simulated camera service
- [x] Verify local and remote Channel Access

### Phase 2 — Physical Camera Integration

- [x] Integrate Picamera2
- [x] Implement camera initialization and status handling
- [x] Enable PVAccess with QSRV
- [ ] Implement image acquisition
- [ ] Implement exposure and gain control
- [ ] Implement image saving and acquisition metadata

### Phase 3 — Camera Characterization and Vision

- [ ] Quantitative sensor characterization
- [ ] Automated image acquisition workflows
- [ ] LED recognition
- [ ] Hand-gesture experiments
- [ ] Hardware monitoring and alarms

### Phase 4 — areaDetector

- [ ] Set up areaDetector
- [ ] Investigate IMX219-compatible driver integration
- [ ] Explore NDArray and image-processing plugins
- [ ] Compare conventional StreamDevice and areaDetector approaches

## Development and Documentation Approach

The project is developed incrementally, with working milestones committed to GitHub.

Implementation guides document reproducible configurations, learning notes explain underlying EPICS concepts, and troubleshooting records problems encountered during development.

Documentation is updated as the implementation evolves, with completed functionality distinguished from planned work.

## References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)
