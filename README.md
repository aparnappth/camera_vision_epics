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

The project will explore two EPICS integration approaches.

### 1. Conventional EPICS IOC

```text
EPICS Channel Access
         |
   Conventional IOC
         |
 StreamDevice + asyn
         |
   Python TCP service
         |
      Picamera2
         |
      libcamera
         |
       IMX219
```

The initial communication interface has been implemented and tested. Picamera2-based acquisition is planned.

### 2. areaDetector IOC (Planned)

```text
EPICS
   |
areaDetector
   |
Camera-specific driver
   |
Camera software interface
   |
IMX219
```

This implementation will explore areaDetector's standard acquisition interface, image arrays, and processing plugins.

## Current Progress

**Milestone 1: EPICS-to-Python communication — completed**

- EPICS Base R7.0.10 installed and configured.
- asyn R4-46 installed.
- StreamDevice 2.8.26 library built.
- Conventional EPICS IOC created and compiled.
- Python TCP server implemented.
- StreamDevice protocol and EPICS database configured.
- On-demand `CAM:GetStatus` communication tested.
- Remote Channel Access verified from Windows/WSL.

The current Python server returns a fixed `IDLE` status. Camera acquisition and physical camera-state monitoring are not yet implemented.

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   └── troubleshooting.md
├── acquisition/
├── characterization/
├── vision/
└── epics/
    └── streamdevice_camera/
```

## Documentation

- [EPICS Environment Setup](docs/epics_setup.md) — Installing EPICS Base, asyn, and StreamDevice on Raspberry Pi.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC architecture, database records, protocol configuration, Python TCP communication, and testing.
- [Troubleshooting](docs/troubleshooting.md) — Common installation, build, networking, and IOC configuration issues.

## Development Roadmap

### Phase 1 — EPICS Communication

- [x] Install EPICS Base and support modules
- [x] Create conventional StreamDevice IOC
- [x] Establish Python TCP communication
- [x] Verify local and remote PV access

### Phase 2 — Camera Acquisition

- [ ] Integrate Picamera2
- [ ] Implement camera acquisition commands
- [ ] Configure exposure and gain
- [ ] Implement acquisition status and image saving

### Phase 3 — Characterization and Vision

- [ ] Quantitative camera characterization
- [ ] Automated acquisition workflows
- [ ] LED recognition
- [ ] Hand-gesture experiments
- [ ] Hardware monitoring and alarms

### Phase 4 — areaDetector

- [ ] Set up areaDetector
- [ ] Investigate camera-driver integration
- [ ] Explore NDArray and processing plugins
- [ ] Compare conventional IOC and areaDetector approaches

## References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)

