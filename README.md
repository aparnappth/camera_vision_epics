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
- PyEpics for automated EPICS measurements
- NumPy, Pillow, and Matplotlib for image analysis

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

Camera control and acquisition have been tested through Channel Access. The expanded camera interface has now been tested through both Channel Access and PVAccess. Brief intermediate status changes are not always visible in either monitor.

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

### 9. Testing the Expanded PVAccess Interface

QSRV makes ordinary IOC database records available through PVAccess as well as Channel Access. Camera commands, exposure, gain, automatic exposure, status, and acquisition-file paths were verified using `pvget`, `pvput`, and `pvmonitor`. The brief `ACQUIRING` state was occasionally absent from both `pvmonitor` and `camonitor` output. The cause has not been identified.

**Result:** The expanded PVAccess interface is working for the tested controls and readbacks. Rapid intermediate status monitoring remains a known limitation.

### 10. Automating Image Acquisition with PyEpics

`automation/exposure_sweep.py` acquires a series of images at different exposure times. It uses PyEpics to communicate with the IOC rather than calling Picamera2 directly. This separates measurement automation from camera hardware control and allows the script to run on the Raspberry Pi or on another computer with access to the IOC.

The script disables automatic exposure, sets a fixed requested gain, and then repeats the following steps for each exposure value:

1. Write the requested exposure through EPICS.
2. Wait for `CAM:GetExposure` to match the request. This is necessary because the `FLNK`-triggered readback can finish after the write returns.
3. Record the previous image path and send `Acquire`.
4. Wait for `CAM:GetLatestImagePath` to change, with a timeout.
5. Wait for the metadata path with the matching filename.
6. Save the requested exposure, readback, gain setting, and both paths as one row in a CSV log.

A change in the latest image path is used as the acquisition-completion indicator because the path is published after a successful image save and remains available for later reads. Unlike the short `ACQUIRING` state, it does not depend on observing a brief transition. This approach worked in the performed tests, but it is not a complete command-acknowledgement or failure-reporting system.

**Result:** An automated five-point exposure sweep was completed successfully, with matching image and metadata paths recorded in a CSV file.

### 11. Initial Exposure Verification and JPEG Analysis

Two scripts under `characterization/` handle exposure verification and image analysis:

- `check_exposure.py` reads the sweep CSV and each JSON metadata file, then compares the requested exposure with the exposure reported for the captured frame.
- `analyze_exposure_response.py` reads the JPEG images, converts them to 8-bit grayscale using Pillow, and uses NumPy to calculate the mean, minimum, maximum, and standard deviation of pixel intensity. Matplotlib saves a plot of mean intensity against the camera-reported exposure time.

Keeping acquisition and analysis in separate scripts allows saved datasets to be analyzed again without operating the camera. The analysis scripts select the latest timestamped sweep CSV when run from the repository root.

An initial five-point sweep requested exposure times of 5, 10, 20, 40, and 80 ms. The corresponding frame metadata reported 4,990, 9,999, 19,999, 39,999, and 79,999 µs. The largest difference was 10 µs (0.2%) at the shortest setting.

Additional sweeps were recorded under brighter illumination and after lens-focus adjustment. In the latest analyzed dataset, the mean grayscale intensity increased from 3.69 at 4.99 ms to 42.11 at 80 ms. The image-wide standard deviation also increased, but it includes differences in scene brightness and is not a direct measure of sensor noise.

These are **processed JPEG measurements** influenced by the camera image-processing pipeline and the scene. They demonstrate the acquisition and analysis workflow and an increase in JPEG brightness with exposure time. They do not establish intrinsic sensor linearity or noise performance. Region-of-interest (ROI), raw-sensor linearity, and noise studies are outside the scope of this initial analysis.

**Result:** Automated acquisition, exposure verification, basic image statistics, and exposure-response plotting have been tested.

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

## Local and Remote Operation

The physical camera and its Python server run on the Raspberry Pi. EPICS provides the interface that other computers can use to control the camera.

| Task or component | Where it runs or is stored |
|---|---|
| Picamera2, libcamera, and physical IMX219 | Raspberry Pi |
| Python camera TCP server and StreamDevice IOC | Raspberry Pi (current setup) |
| CA/PVA commands and monitoring | Raspberry Pi or a network-connected remote computer |
| PyEpics exposure-sweep automation | Raspberry Pi or a remote computer with EPICS access |
| Captured JPEG and JSON metadata | Saved on the Raspberry Pi |
| Exposure-sweep CSV log | Saved on the computer running the automation script |
| Exposure verification and JPEG analysis | Any computer that can access the CSV and its image/metadata files |
| Phoebus image display | Not implemented yet |

**Remote control does not transfer image files.** When a remote computer sends `Acquire`, the Raspberry Pi saves the image and metadata locally. The EPICS path PVs return file locations, not file contents. The CSV currently records absolute Raspberry Pi paths. Analysis on Windows or another computer requires access to the saved files and appropriate path handling. Portable dataset paths are not yet implemented.

The Python camera server uses the local loopback address `127.0.0.1:5000` to communicate with the IOC. Remote clients connect to the EPICS IOC, not directly to this camera-server port. Network discovery and firewall settings must allow the chosen EPICS protocol.

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

Generated acquisition files are intended to remain outside Git version control. Sweep CSV files and generated plots are stored under `data/exposure_sweeps/`, which is also excluded from Git.

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
- [x] Complete expanded PVAccess interface testing


### Milestone 5 — Initial Automation and Characterization

- [x] Create a project Python virtual environment and install PyEpics
- [x] Test PyEpics read and write access to the IOC
- [x] Automate exposure settings and verify FLNK-triggered readbacks
- [x] Detect new acquisitions using image and matching metadata paths
- [x] Complete an exposure sweep and save a CSV measurement log
- [x] Compare requested exposure with camera metadata
- [x] Measure basic JPEG intensity statistics and plot exposure response
- [ ] Perform controlled raw-sensor linearity, gain, and noise studies

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
├── automation/
│   └── exposure_sweep.py
├── characterization/
│   ├── check_exposure.py
│   └── analyze_exposure_response.py
├── data/
│   └── exposure_sweeps/  (local CSV logs and plots; ignored by Git)
├── .venv/  (local Python environment; ignored by Git)
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
- [Automated Acquisition and Initial Characterization](docs/notes/automated_acquisition_and_characterization.md) — PyEpics exposure sweeps, CSV logging, image analysis, measured results, and local/remote operation.

## Current Limitations and Open Questions

### Communication and Monitoring

- The Python camera server supports one active TCP client connection at a time.
- Image acquisition is synchronous, so the Python server cannot process new commands until the acquisition finishes.
- Camera commands, readbacks, and automatic notifications share the same TCP connection. Some protocol mismatches were observed during development. The implementation works in the performed tests, but communication under all conditions has not been verified.
- The output-only camera-command protocol does not wait for an acknowledgement. The Python server still sends `OK` responses, which may interfere with other messages and require further investigation.
- Rapid intermediate camera states, particularly `ACQUIRING`, are sometimes missed by `camonitor` and `pvmonitor`. The final status was correct in the performed tests, but the cause of the missed updates remains unknown.
- Automatic status-description updates were postponed after parsing and timeout issues. The readback remains passive because automatic updates are not essential for the current implementation.
- The status PV initially assumes `CLOSED`, based on the normal camera-server startup behavior. Synchronization after reconnection has not been fully tested.
- Camera status is maintained by the Python application rather than measured independently from the hardware.
- Basic error handling is implemented, but more extensive connection recovery, failure reporting, and sensor-parameter validation remain untested.

### Acquisition and Automation

- Exposure and gain readbacks represent the requested settings. The actual values applied during acquisition are available in the saved metadata.
- The automation detects acquisition completion when the latest image-path PV changes. Additional handling may be needed if a notification is missed or the server restarts.
- Images and metadata are saved on the Raspberry Pi. The EPICS PVs provide their file paths, not the file contents.
- The exposure-sweep CSV records absolute Raspberry Pi file paths. Remote analysis requires access to the files and appropriate path handling.

### Image Analysis and Characterization

- Images are saved as processed JPEG files rather than raw sensor data.
- The initial exposure-response measurements used processed JPEGs and scenes without fully controlled illumination. The results demonstrate the measurement workflow but do not establish the intrinsic linearity or noise performance of the IMX219.
- Full image transfer and display through EPICS/Phoebus have not yet been implemented.

### Python Environment

- The project uses a virtual environment created with `--system-site-packages` to access the Raspberry Pi camera libraries. This provides some dependency separation but is not fully isolated from system-installed packages.

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
- [x] Complete PVAccess testing for the expanded interface
- [x] Develop and test an initial automated exposure-sweep workflow

### Phase 4 — Camera Characterization and Vision

- [x] Verify applied exposure times using saved frame metadata
- [x] Complete initial processed-JPEG brightness-response analysis

- [ ] Perform controlled quantitative exposure and gain characterization using suitable sensor data
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

## Acknowledgements

OpenAI's ChatGPT was used as a learning and development assistant throughout this project, providing support with technical explanations, code development, troubleshooting, and documentation. The implementation was tested and validated through hands-on work with the Raspberry Pi, EPICS, and camera hardware.

## References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base](https://github.com/epics-base/epics-base)
- [asynDriver](https://github.com/epics-modules/asyn)
- [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice)
- [Picamera2](https://github.com/raspberrypi/picamera2)
- [libcamera](https://libcamera.org/)
- [areaDetector](https://areadetector.github.io/areaDetector/)
