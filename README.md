# EPICS-Controlled Camera Characterization and Vision Platform

A Raspberry Pi Zero 2 W and Sony IMX219-based experimental platform for developing camera-control systems, automated image acquisition, quantitative sensor characterization, and computer-vision applications using EPICS.

The project explores the integration of physical camera hardware with scientific control and measurement software, progressing from basic device communication to EPICS-controlled acquisition, event-driven monitoring, and automated characterization.

## Project Objectives

The project focuses on four areas:

- **EPICS-based camera control:** Develop and compare conventional StreamDevice-based and areaDetector-based camera control systems.
- **Camera characterization:** Investigate sensor performance through quantitative measurements of exposure response, analogue gain, noise, and image uniformity.
- **Computer vision:** Explore image-processing applications, including LED recognition and hand-gesture detection.
- **Hardware monitoring:** Integrate basic electronic components, monitoring, and alarm functionality with EPICS.

## Hardware and Software

### Hardware

- Raspberry Pi Zero 2 W
- Sony IMX219 8 MP CSI camera
- LEDs and basic electronic components for future experiments

### Software

- EPICS Base R7.0.10
- asyn R4-46
- StreamDevice 2.8.26
- PVAccess and QSRV
- Python 3
- Picamera2 and libcamera
- Netcat for independent TCP communication testing
- VLC for camera positioning and live preview

## System Architecture

The project investigates two approaches to integrating camera hardware with EPICS.

### 1. Conventional EPICS IOC — Current Implementation

```text
                    EPICS Clients
                          |
                +---------+---------+
                |                   |
          Channel Access        PVAccess
          caget / caput         pvget / pvput
                |                   |
                +---------+---------+
                          |
                    EPICS IOC
                    with QSRV
                          |
                  StreamDevice + asyn
                          |
                 TCP Communication
                  127.0.0.1:5000
                          |
                 Python Camera Server
                          |
                       Picamera2
                          |
                       libcamera
                          |
                     Sony IMX219
```

The conventional IOC uses StreamDevice and asyn to communicate with a separate Python camera server over TCP/IP.

The Python server manages camera initialization, configuration, streaming, exposure and gain settings, image acquisition, metadata saving, and resource cleanup.

The IOC provides camera-control PVs, parameter readbacks, operating-status monitoring, and the paths of the latest acquired image and metadata files.

The implementation uses a combination of **I/O Intr processing** and **EPICS forward links (FLNK)** to keep readback PVs updated without continuous application-level polling.

Both command-response communication and unsolicited acquisition/status notifications use the existing TCP connection on port 5000.

Camera control and acquisition have been tested through Channel Access. PVAccess support was previously established through QSRV; the expanded control interface has not yet undergone a complete PVAccess test.

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

This approach will investigate standard EPICS camera-control interfaces, NDArray image transport, image-processing plugins, and the differences between conventional device integration and areaDetector.

## Implementation and Results

### 1. Establishing EPICS-to-Python Communication

The project began by developing a conventional EPICS IOC using StreamDevice and asyn to communicate with a Python-based camera simulator over TCP/IP.

A simple `STATUS?` command was implemented to establish the communication chain between EPICS database records, StreamDevice, asyn, and the Python server.

The system was tested locally on the Raspberry Pi and remotely from Windows Subsystem for Linux (WSL).

PVAccess support was subsequently integrated using QSRV, allowing ordinary IOC database records to be accessed through both Channel Access and PVAccess.

**Result:** A working conventional EPICS IOC capable of communicating with a Python device service through TCP/IP, with CA and PVA client access.

### 2. Integrating the Physical IMX219 Camera

The initial Python simulator was preserved, and a separate camera server was developed using Picamera2 and libcamera.

The server identifies the physical IMX219 camera by its model name and provides reusable functions for camera initialization, configuration, streaming, and resource cleanup.

The camera lifecycle was redesigned so that initialization occurs only when a camera operation requires it, rather than when the status is queried.

The camera object remains initialized between acquisitions, while streaming can be started and stopped independently.

Camera status is managed centrally using application-defined operating states.

**Result:** A Python TCP service capable of managing the physical IMX219 camera without repeatedly opening and closing it for every acquisition.

### 3. Developing and Testing Still-Image Acquisition

Before integrating image acquisition into the TCP server, a standalone Picamera2 test was developed.

The test established the complete still-image acquisition sequence, including camera configuration, streaming, image capture, and cleanup.

Picamera2's `capture_request()` method was used to obtain a completed camera request containing both image data and associated acquisition metadata.

The image is saved as a JPEG, while its metadata is saved separately in JSON format. Both originate from the same completed request.

Timestamp-based filenames associate each image with its corresponding metadata.

Manual exposure time and analogue gain were tested, and the actual applied values were verified using the acquisition metadata.

The image orientation was also corrected by 180°, and VLC was used separately for camera positioning.

**Result:** Successful full-resolution image acquisition with matching metadata, manual acquisition settings, and explicit resource management.

### 4. Developing the Python TCP Camera-Control Server

The Python camera server was expanded from a single status-query service into a camera-control interface.

The implementation supports:

- Camera initialization, starting, stopping, and closing.
- Automatic and manual exposure control.
- Requested exposure-time and analogue-gain settings and readbacks.
- Single-image acquisition with matching metadata.
- Repeated image acquisition while the camera remains streaming.
- Retrieval of the latest saved image and metadata file paths.
- Centralized camera-state management.
- Basic input validation and error reporting.
- Camera cleanup on detected TCP disconnection and server shutdown.

Camera operations are organized into reusable functions, while a separate command processor interprets incoming TCP commands.

Newline-delimited communication is used to identify complete commands and responses.

The expanded Python server was tested independently using Netcat.

Both single-image acquisition and repeated acquisition while streaming were verified, including image saving, metadata retrieval, and restoration of the previous streaming state.

**Result:** A functional Python TCP camera-control server with independently tested acquisition and parameter-control capabilities.

### 5. Integrating Camera Control into EPICS

The previously tested Python camera operations were integrated into the conventional EPICS IOC by extending `stream_camera.proto` and `camera.db`.

A single `mbbo` record, `CAM:CameraCommand`, was implemented for four camera operations:

- `Start`
- `Stop`
- `Acquire`
- `Close`

The predefined EPICS states are converted by StreamDevice into the uppercase text commands understood by the Python server.

An `mbbo` record was selected instead of `stringout` to provide predefined operator choices and a convenient interface for future Phoebus controls.

The command record represents the last requested operation, while a separate status PV reports the camera's operating state.

Exposure time, analogue gain, and automatic-exposure controls were integrated using appropriate numerical and enumerated EPICS record types.

**Result:** Successful control of the physical IMX219 through EPICS, including repeated image acquisition and automatic/manual camera settings.

### 6. Implementing Event-Driven Camera Status Monitoring

The initial EPICS status record used passive processing and required an explicit processing request to obtain a fresh value.

This was extended to use StreamDevice's **I/O Intr** mechanism.

The Python server now publishes a status notification whenever its internal camera state changes.

An input-only StreamDevice protocol receives these notifications and updates `CAM:GetStatus` automatically.

The implementation was tested using `caget` and `camonitor`, confirming that the latest stored status can be retrieved without manually processing the record or configuring periodic status queries.

The camera-status record is initialized to `CLOSED`, consistent with the normal Python server startup state.

Tests also demonstrated intermediate acquisition transitions such as `ACQUIRING`, although rapidly occurring transitions were not always individually visible in the EPICS monitor.

**Result:** Event-driven EPICS camera-status monitoring using the existing TCP connection, without adding a separate notification port.

### 7. Implementing Parameter Readbacks Using Forward Links

Exposure time, analogue gain, and automatic-exposure settings are controlled through EPICS output records.

Each setter record uses an EPICS forward link (`FLNK`) to trigger processing of its corresponding readback record after the setting operation.

This allows the IOC to request and store the updated value without requiring manual `.PROC` commands or periodic polling.

Forward links were selected for these parameters because their requested values are normally changed through the corresponding EPICS setter records.

This differs from camera status, which can change multiple times during a single operation and is therefore handled using I/O Intr.

**Result:** Successfully tested automatic readbacks for exposure, gain, and automatic-exposure settings.

### 8. Implementing Automatic Acquisition-File Readbacks

The Python server stores the paths of the latest successfully acquired image and metadata files.

After a successful acquisition, it sends separate notifications containing the JPEG and JSON file paths.

StreamDevice receives these notifications through input-only protocols and updates the corresponding EPICS waveform records using I/O Intr.

Character-array waveform records were selected because complete file paths can exceed the capacity of conventional EPICS string records.

The paths can be displayed as readable strings using the `-S` option of EPICS client tools.

Simultaneous monitoring of camera status, image path, and metadata path was successfully tested.

**Result:** EPICS automatically provides the latest saved image and metadata locations following acquisition, without manual readback processing.

## Current EPICS Camera Interface

| PV | Record type | Purpose |
|---|---|---|
| `CAM:CameraCommand` | `mbbo` | Start, Stop, Acquire, Close |
| `CAM:GetStatus` | `stringin` | Current camera operating status |
| `CAM:GetStatusDescription` | `waveform` | Human-readable status description |
| `CAM:SetExposure` | `longout` | Requested exposure time |
| `CAM:GetExposure` | `longin` | Exposure setting readback |
| `CAM:SetGain` | `ao` | Requested analogue gain |
| `CAM:GetGain` | `ai` | Gain setting readback |
| `CAM:SetAutoExposure` | `mbbo` | Enable or disable automatic exposure |
| `CAM:GetAutoExposure` | `mbbi` | Automatic-exposure readback |
| `CAM:GetLatestImagePath` | `waveform` | Latest JPEG file path |
| `CAM:GetLatestMetadataPath` | `waveform` | Latest JSON metadata path |

### Record Processing Strategy

| PV category | Mechanism |
|---|---|
| Camera operating status | I/O Intr |
| Camera commands | Passive output |
| Exposure, gain, auto-exposure setters | Passive output |
| Exposure, gain, auto-exposure readbacks | Passive, triggered by FLNK |
| Latest image and metadata paths | I/O Intr |
| Status description | Passive, explicitly processed when required |

The status-description readback is intentionally kept passive. Automatic updating through a forward link was investigated but postponed after timeout and message-handling issues were observed during acquisition.

The detailed implementation and design decisions are documented in [StreamDevice Camera IOC](docs/streamdevice_ioc.md).

## Current Camera Functionality

### Camera Operating States

| State | Meaning |
|---|---|
| `CLOSED` | Camera is not initialized |
| `IDLE` | Camera is initialized but not streaming |
| `STREAMING` | Camera is running and producing frames |
| `ACQUIRING` | Image acquisition is in progress |
| `PREVIEWING` | Live preview is active (reserved for future implementation) |
| `ERROR` | A camera operation has failed |

These are application-level states maintained by the Python server, not independent measurements of hardware health.

### Supported Python TCP Commands

| Category | Commands |
|---|---|
| Status | `STATUS?`, `STATUS_DESC?` |
| Camera lifecycle | `START`, `STOP`, `CLOSE` |
| Acquisition | `ACQUIRE` |
| Exposure | `EXPOSURE <value>`, `EXPOSURE?` |
| Analogue gain | `GAIN <value>`, `GAIN?` |
| Automatic exposure | `AUTO_EXPOSURE 0/1`, `AUTO_EXPOSURE?` |
| File readbacks | `LATEST_IMAGE_PATH?`, `LATEST_METADATA_PATH?` |

The Python TCP server listens on `127.0.0.1:5000`.

Exposure time is specified in microseconds. Automatic exposure uses `1` for Enable and `0` for Disable.

The image-path commands return the locations of the latest successfully saved files on the Raspberry Pi, not the image data itself.

## Acquisition Output

Each successful acquisition generates a JPEG image and a matching JSON metadata file:

```text
acquisition/images/
├── image_YYYYMMDD_HHMMSS_microseconds.jpg
└── image_YYYYMMDD_HHMMSS_microseconds_metadata.json
```

The metadata can include exposure time, analogue gain, digital gain, sensor timestamps, frame duration, color gains, and other available camera parameters.

Image and metadata are retrieved from the same completed Picamera2 request.

Generated acquisition files are intended to remain outside Git version control.

## Development Progress

### Milestone 1 — EPICS Communication

- [x] Install and configure EPICS Base, asyn, and StreamDevice
- [x] Create and compile a conventional EPICS IOC
- [x] Implement a Python TCP camera simulator
- [x] Establish StreamDevice/asyn communication
- [x] Verify local and remote Channel Access

### Milestone 2 — Physical Camera and PVAccess Integration

- [x] Detect and initialize the IMX219 using Picamera2
- [x] Develop a separate Python camera server
- [x] Implement camera-status communication
- [x] Enable PVAccess using QSRV
- [x] Verify status access through Channel Access and PVAccess

### Milestone 3 — Camera Acquisition and Python TCP Control

- [x] Develop standalone Picamera2 acquisition tests
- [x] Capture images and matching metadata
- [x] Test manual exposure and analogue gain
- [x] Implement camera lifecycle and acquisition functions
- [x] Implement the expanded Python TCP command interface
- [x] Verify single and repeated image acquisition through TCP
- [x] Verify exposure, gain, status, and file-path readbacks

### Milestone 4 — EPICS-Controlled Acquisition and Monitoring

- [x] Extend StreamDevice protocol definitions
- [x] Add EPICS camera-control and acquisition records
- [x] Implement the `mbbo` camera-command interface
- [x] Verify camera lifecycle and image acquisition through Channel Access
- [x] Implement I/O Intr camera-status monitoring
- [x] Implement FLNK-based exposure and gain readbacks
- [x] Implement FLNK-based automatic-exposure readback
- [x] Implement I/O Intr image and metadata path readbacks
- [x] Verify simultaneous monitoring of multiple PVs
- [ ] Complete expanded PVAccess interface testing
- [ ] Resolve remaining shared-port communication robustness issues
- [ ] Implement reliable automatic status-description updates

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       ├── epics_device_integration.md
│       └── test_picamera2_acquisition.md
├── acquisition/
│   ├── camera_server_simulator.py
│   ├── picamera2_server.py
│   ├── tests/
│   │   └── test_camera_acquisition.py
│   └── images/
│       └── (generated image and metadata files)
├── characterization/
├── vision/
└── epics/
    └── streamdevice_camera/
        └── streamdevice_camera_ioc/
```

## Documentation

### Setup and Implementation

- [EPICS Environment Setup](docs/epics_setup.md) — Installation and configuration of EPICS Base, asyn, and StreamDevice.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC architecture, Python TCP communication, camera control, record processing, I/O Intr, FLNK, and CA/PVA configuration.
- [Troubleshooting](docs/troubleshooting.md) — Installation, compilation, networking, protocol parsing, and communication issues encountered during development.

### Learning Notes

- [Understanding EPICS Device Integration](docs/notes/epics_device_integration.md) — EPICS device support, hardware drivers, StreamDevice, asyn, Python APIs, and areaDetector.
- [Standalone Picamera2 Acquisition Test](docs/notes/test_picamera2_acquisition.md) — Still-image acquisition, camera configuration, metadata, exposure/gain settings, and resource management.

## Current Limitations and Open Questions

- The Python camera server processes one active TCP client connection at a time.
- Acquisition is synchronous and blocks the Python command loop until completion.
- Command-response communication and unsolicited notifications share the same TCP connection. Some protocol mismatches and timing-dependent behavior were observed during development.
- The output-only camera-command protocol does not wait for acquisition-completion acknowledgement. The Python server still generates `OK` responses, which require further protocol review.
- Rapid intermediate status transitions are not always individually visible in EPICS monitors, although final states were correct in the performed tests.
- The status-description readback is passive. Automatic updates were postponed after parsing and timeout issues.
- The initial `CLOSED` value of the status PV assumes the normal Python server startup and disconnect lifecycle; reconnection synchronization is not fully implemented.
- Camera status is maintained by the Python application rather than independently reporting hardware health.
- Requested exposure and gain readbacks do not necessarily represent the actual sensor values; acquisition metadata provides the applied values.
- Images are saved as processed JPEG files rather than raw sensor data.
- The latest image and metadata PVs return file paths, not the file contents.
- Full image transfer and display through EPICS/Phoebus have not yet been implemented.
- More extensive camera-error recovery, TCP connection cleanup, and sensor-parameter validation remain future improvements.

## Development Roadmap

### Phase 1 — EPICS Communication

- [x] Establish StreamDevice/asyn communication
- [x] Implement and test the simulated camera service
- [x] Verify Channel Access and PVAccess

### Phase 2 — Camera Integration and Python Acquisition

- [x] Integrate Picamera2 and the physical IMX219
- [x] Implement camera lifecycle management
- [x] Implement still-image acquisition and metadata saving
- [x] Implement manual and automatic exposure settings
- [x] Test the Python TCP camera-control interface

### Phase 3 — EPICS-Controlled Acquisition and Monitoring

- [x] Extend `stream_camera.proto` with camera commands
- [x] Add camera-control and acquisition PVs to `camera.db`
- [x] Verify camera operations through Channel Access
- [x] Implement I/O Intr status and acquisition-path updates
- [x] Implement FLNK-based parameter readbacks
- [ ] Complete PVAccess testing for the expanded interface
- [ ] Improve communication reliability and error reporting
- [ ] Develop automated acquisition workflows

### Phase 4 — Camera Characterization and Vision

- [ ] Quantitative exposure and gain characterization
- [ ] Sensor noise and image-uniformity measurements
- [ ] Raw image acquisition and analysis
- [ ] LED recognition and hand-gesture experiments
- [ ] Hardware monitoring and alarms

### Phase 5 — Phoebus and Image Visualization

- [ ] Develop a Phoebus camera-control interface
- [ ] Display camera status and acquisition settings
- [ ] Investigate transferring image arrays through EPICS
- [ ] Display the latest acquired image in Phoebus
- [ ] Evaluate image-transfer performance on Raspberry Pi Zero 2 W

### Phase 6 — areaDetector

- [ ] Set up areaDetector
- [ ] Investigate IMX219-compatible driver integration
- [ ] Explore NDArray image transport and processing plugins
- [ ] Compare conventional StreamDevice and areaDetector approaches

## Development and Documentation Approach

The project is developed incrementally, beginning with standalone hardware and software tests before integrating functionality into EPICS.

Working implementations are tested and committed to GitHub.

Implementation guides document reproducible configurations and design decisions, learning notes explain underlying concepts, and troubleshooting records problems encountered during development.

Completed functionality is distinguished from planned work and known limitations.

## References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)
# EPICS-Controlled Camera Characterization and Vision Platform

A Raspberry Pi Zero 2 W and Sony IMX219-based experimental platform for developing camera-control systems, automated image acquisition, quantitative sensor characterization, and computer-vision applications using EPICS.

The project explores the integration of physical camera hardware with scientific control and measurement software, progressing from basic device communication to automated acquisition and characterization.

## Project Objectives

The project focuses on four areas:

- **EPICS-based camera control:** Develop and compare conventional StreamDevice-based and areaDetector-based camera control systems.
- **Camera characterization:** Investigate sensor performance through quantitative measurements of exposure response, analogue gain, noise, and image uniformity.
- **Computer vision:** Explore image-processing applications, including LED recognition and hand-gesture detection.
- **Hardware monitoring:** Integrate basic electronic components, monitoring, and alarm functionality with EPICS.

## Hardware and Software

### Hardware

- Raspberry Pi Zero 2 W
- Sony IMX219 8 MP CSI camera
- LEDs and basic electronic components for future experiments

### Software

- EPICS Base R7.0.10
- asyn R4-46
- StreamDevice 2.8.26
- PVAccess and QSRV
- Python 3
- Picamera2 and libcamera
- Netcat for independent TCP communication testing
- VLC for camera positioning and live preview

## System Architecture

The project investigates two approaches to integrating camera hardware with EPICS.

### 1. Conventional EPICS IOC — Current Implementation

```text
                    EPICS Clients
                          |
                +---------+---------+
                |                   |
          Channel Access        PVAccess
          caget / caput         pvget / pvput
                |                   |
                +---------+---------+
                          |
                    EPICS IOC
                    with QSRV
                          |
                  StreamDevice + asyn
                          |
                 TCP Command Protocol
                          |
                 Python Camera Server
                          |
                       Picamera2
                          |
                       libcamera
                          |
                     Sony IMX219
```

The conventional IOC uses StreamDevice and asyn to communicate with a separate Python camera service over TCP/IP.

The Python server manages camera initialization, configuration, acquisition settings, streaming, image capture, and resource cleanup.

The IOC currently supports the previously implemented status communication through Channel Access and PVAccess. The expanded Python camera-control interface has been tested independently and is awaiting integration into the EPICS database and StreamDevice protocol.

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

This approach will investigate standard EPICS camera-control interfaces, NDArray image transport, image-processing plugins, and the differences between conventional device integration and areaDetector.

## Implementation and Results

### 1. Establishing EPICS-to-Python Communication

The project began by developing a conventional EPICS IOC using StreamDevice and asyn to communicate with a Python-based camera simulator over TCP/IP.

A simple `STATUS?` command was implemented to establish the communication chain between EPICS database records, StreamDevice, asyn, and the Python server.

The system was tested locally on the Raspberry Pi and remotely from Windows Subsystem for Linux (WSL).

PVAccess support was subsequently integrated using QSRV, allowing the same IOC database records to be accessed through both Channel Access and PVAccess.

**Result:** A working conventional EPICS IOC capable of communicating with a Python device service through TCP/IP, with CA and PVA client access.

### 2. Integrating the Physical IMX219 Camera

The initial Python simulator was preserved, and a separate camera server was developed using Picamera2 and libcamera.

The server identifies the physical IMX219 camera by its model name and provides reusable functions for camera initialization, configuration, streaming, and resource cleanup.

The camera lifecycle was redesigned so that initialization occurs only when a camera operation requires it, rather than when the status is queried.

The camera object remains initialized between acquisitions, while streaming can be started and stopped independently.

Camera status is managed centrally using application-defined operating states.

**Result:** A Python TCP service capable of managing the physical IMX219 camera without repeatedly opening and closing it for every acquisition.

### 3. Developing and Testing Still-Image Acquisition

Before integrating image acquisition into the TCP server, a standalone Picamera2 test was developed.

The test established the complete still-image acquisition sequence, including camera configuration, streaming, image capture, and cleanup.

Picamera2's `capture_request()` method was used to obtain a completed camera request containing both image data and the associated acquisition metadata.

The image is saved as a JPEG, while its metadata is saved separately in JSON format. Both originate from the same completed request.

Timestamp-based filenames associate each image with its corresponding metadata.

Manual exposure time and analogue gain were tested, and the actual applied values were verified using the acquisition metadata.

The image orientation was also corrected by 180°, and VLC was used separately for camera positioning.

**Result:** Successful full-resolution image acquisition with matching metadata, manual acquisition settings, and explicit resource management.

### 4. Developing the Python TCP Camera-Control Server

The Python camera server was expanded from a single status-query service into a more complete camera-control interface.

The implementation now supports:

- Camera initialization, starting, stopping, and closing.
- Automatic and manual exposure control.
- Requested exposure-time and analogue-gain settings and readbacks.
- Single-image acquisition with matching metadata.
- Repeated image acquisition while the camera remains streaming.
- Retrieval of the latest saved image and metadata file paths.
- Centralized camera-state management.
- Basic input validation and error reporting.
- Camera cleanup on detected TCP disconnection and server shutdown.

Camera operations are organized into reusable functions, while a separate command processor interprets incoming TCP commands.

Newline-delimited communication is used to identify complete commands and responses.

**Result:** A functional Python TCP camera-control server with acquisition and parameter-control capabilities.

### 5. Testing the Complete Python Camera Interface

The expanded Python server was tested independently of EPICS using Netcat.

The tests verified camera lifecycle commands and transitions between `CLOSED`, `IDLE`, and `STREAMING`.

Exposure time, analogue gain, and automatic-exposure settings were successfully written and read through TCP commands.

Image acquisition was tested in two operating conditions:

- **Single-image acquisition:** The camera starts when acquisition is requested, captures and saves the image and metadata, then stops streaming while remaining initialized.
- **Acquisition during streaming:** The camera remains running while multiple images are acquired and saved.

The latest image and metadata paths were retrieved through TCP readback commands.

Actual exposure and gain values were verified using metadata saved with the acquired images.

**Result:** The Python camera server successfully performs the planned camera-control and acquisition operations and is ready for the next stage of EPICS integration.

The expanded commands have not yet been tested through the IOC.

## Current Camera Functionality

### Camera Operating States

| State | Meaning |
|---|---|
| `CLOSED` | Camera is not initialized |
| `IDLE` | Camera is initialized but not streaming |
| `STREAMING` | Camera is running and producing frames |
| `ACQUIRING` | Image acquisition is in progress |
| `PREVIEWING` | Live preview is active (reserved for future implementation) |
| `ERROR` | A camera operation has failed |

These are application-level states maintained by the Python server.

### Supported Python TCP Commands

| Category | Commands |
|---|---|
| Status | `STATUS?`, `STATUS_DESC?` |
| Camera lifecycle | `START`, `STOP`, `CLOSE` |
| Acquisition | `ACQUIRE` |
| Exposure | `EXPOSURE <value>`, `EXPOSURE?` |
| Analogue gain | `GAIN <value>`, `GAIN?` |
| Automatic exposure | `AUTO_EXPOSURE 0/1`, `AUTO_EXPOSURE?` |
| File readbacks | `LATEST_IMAGE_PATH?`, `LATEST_METADATA_PATH?` |

The Python TCP server listens on `127.0.0.1:5000`.

Exposure time is specified in microseconds. Automatic exposure uses `1` for Enable and `0` for Disable.

The image-path commands return the locations of the latest successfully saved files on the Raspberry Pi, not the image data itself.

## Acquisition Output

Each successful acquisition generates a JPEG image and a matching JSON metadata file:

```text
acquisition/images/
├── image_YYYYMMDD_HHMMSS_microseconds.jpg
└── image_YYYYMMDD_HHMMSS_microseconds_metadata.json
```

The metadata can include exposure time, analogue gain, digital gain, sensor timestamps, frame duration, color gains, and other available camera parameters.

Image and metadata are retrieved from the same completed Picamera2 request.

Generated acquisition files are intended to remain outside Git version control.

## Development Progress

### Milestone 1 — EPICS Communication

- [x] Install and configure EPICS Base, asyn, and StreamDevice
- [x] Create and compile a conventional EPICS IOC
- [x] Implement a Python TCP camera simulator
- [x] Establish StreamDevice/asyn communication
- [x] Verify local and remote Channel Access

### Milestone 2 — Physical Camera and PVAccess Integration

- [x] Detect and initialize the IMX219 using Picamera2
- [x] Develop a separate Python camera server
- [x] Implement camera-status communication
- [x] Enable PVAccess using QSRV
- [x] Verify status access through Channel Access and PVAccess

### Milestone 3 — Camera Acquisition and Python TCP Control

- [x] Develop standalone Picamera2 acquisition tests
- [x] Capture images and matching metadata
- [x] Test manual exposure and analogue gain
- [x] Implement camera lifecycle and acquisition functions
- [x] Implement the expanded Python TCP command interface
- [x] Verify single and repeated image acquisition through TCP
- [x] Verify exposure, gain, status, and file-path readbacks
- [ ] Integrate the expanded commands into the EPICS IOC

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── docs/
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       ├── epics_device_integration.md
│       └── test_picamera2_acquisition.md
├── acquisition/
│   ├── camera_server_simulator.py
│   ├── picamera2_server.py
│   ├── tests/
│   │   └── test_camera_acquisition.py
│   └── images/
│       └── (generated image and metadata files)
├── characterization/
├── vision/
└── epics/
    └── streamdevice_camera/
        └── streamdevice_camera_ioc/
```

## Documentation

### Setup and Implementation

- [EPICS Environment Setup](docs/epics_setup.md) — Installation and configuration of EPICS Base, asyn, and StreamDevice.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC architecture, TCP communication, Picamera2 integration, database records, and CA/PVA configuration.
- [Troubleshooting](docs/troubleshooting.md) — Installation, compilation, networking, and IOC configuration issues encountered during development.

### Learning Notes

- [Understanding EPICS Device Integration](docs/notes/epics_device_integration.md) — EPICS device support, hardware drivers, StreamDevice, asyn, Python APIs, and areaDetector.
- [Standalone Picamera2 Acquisition Test](docs/notes/test_picamera2_acquisition.md) — Still-image acquisition, camera configuration, metadata, exposure/gain settings, and resource management.

## Current Limitations

- The expanded Python camera-control commands are not yet integrated into the StreamDevice protocol and EPICS database.
- Camera status is maintained by the Python application rather than independently reporting hardware health.
- The Python TCP server processes one active client connection at a time.
- Acquisition is synchronous and blocks the command loop until completion.
- The existing passive EPICS status record returns its stored value rather than automatically requesting an updated camera state.
- Automatic status updates through EPICS I/O Intr remain a future development task.
- Exposure and gain readbacks currently represent requested settings; actual values are available in acquisition metadata.
- Images are saved as processed JPEG files rather than raw sensor data.
- Live preview through the EPICS camera server has not yet been implemented.
- Camera-control recovery and more extensive sensor-parameter validation require further development.

## Development Roadmap

### Phase 1 — EPICS Communication

- [x] Establish StreamDevice/asyn communication
- [x] Implement and test the simulated camera service
- [x] Verify Channel Access and PVAccess

### Phase 2 — Camera Integration and Python Acquisition

- [x] Integrate Picamera2 and the physical IMX219
- [x] Implement camera lifecycle management
- [x] Implement still-image acquisition and metadata saving
- [x] Implement manual and automatic exposure settings
- [x] Test the Python TCP camera-control interface

### Phase 3 — EPICS-Controlled Acquisition

- [ ] Extend `stream_camera.proto` with the new camera commands
- [ ] Add camera-control and acquisition PVs to `camera.db`
- [ ] Verify camera operations through Channel Access and PVAccess
- [ ] Investigate I/O Intr updates for camera status and readbacks
- [ ] Develop automated acquisition workflows

### Phase 4 — Camera Characterization and Vision

- [ ] Quantitative exposure and gain characterization
- [ ] Sensor noise and image-uniformity measurements
- [ ] Raw image acquisition and analysis
- [ ] LED recognition and hand-gesture experiments
- [ ] Hardware monitoring and alarms

### Phase 5 — areaDetector

- [ ] Set up areaDetector
- [ ] Investigate IMX219-compatible driver integration
- [ ] Explore NDArray image transport and processing plugins
- [ ] Compare conventional StreamDevice and areaDetector approaches

## Development and Documentation Approach

The project is developed incrementally, beginning with standalone hardware and software tests before integrating functionality into EPICS.

Working implementations are tested and committed to GitHub. Implementation guides document reproducible configurations, learning notes explain underlying concepts, and troubleshooting records problems encountered during development.

Completed functionality is distinguished from planned work.

## References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)
