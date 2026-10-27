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
- p4p for publishing image arrays through PVAccess
- Phoebus Display Builder for camera controls and acquired-image display

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

The Python server manages camera initialization, configuration, streaming, exposure and gain settings, image acquisition, metadata saving, and resource cleanup. Its TCP communication is organized through a `TCPConnection` class, which manages the single accepted IOC connection and serializes writes from the command loop and metadata-monitoring worker.

The IOC provides camera-control PVs, parameter readbacks, operating-status monitoring, and the paths of the latest acquired image and metadata files.

The implementation uses a combination of **I/O Intr processing** and **EPICS forward links (FLNK)** to keep readback PVs updated without continuous application-level polling.

Command responses, camera-status notifications, acquisition-file paths, and actual exposure/gain notifications share the existing TCP connection on port 5000. A Picamera2 frame callback records the latest applied exposure and gain from completed-frame metadata; a lightweight worker checks these values periodically and publishes changes through StreamDevice I/O Intr. The worker does not open another TCP connection.

Camera control and acquisition have been tested through Channel Access. The expanded camera interface has now been tested through both Channel Access and PVAccess. Brief intermediate status changes are not always visible in either monitor.

### 2. Separate PVAccess Image Publisher — Current Implementation

```text
                  Phoebus on Windows
                    /          \
          Camera controls     RGB image display
                 |                  |
          Channel Access       PVAccess
                 |                  |
         EPICS IOC + QSRV       CAM:Image
                 |                  |
          StreamDevice       Python p4p publisher
                 |                  |
          TCP port 5000    Latest saved JPEG file
                 |                  |
          Python camera server ----+
                 |
              Picamera2
                 |
                IMX219
```

`acquisition/pva_image_publisher.py` is a separate Python program. It reads the latest JPEG path from `CAM:GetLatestImagePath` through PyEpics, opens the saved image on the Raspberry Pi, resizes it to 100 × 100 pixels, and publishes interleaved 8-bit RGB values as `CAM:Image` through p4p. The publisher checks the path periodically and updates the PV when a new image is available. Phoebus displays this array using its Image widget (`TYPE_RGB1`, unsigned data enabled).

The publisher is started separately from the camera server and IOC. This keeps image transfer independent of the existing StreamDevice TCP connection. The original full-resolution JPEG and matching metadata are preserved. This is acquired-image display, not live video streaming.

### 3. areaDetector IOC — Planned

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

For the chronological development record, experiments and measured results, see [Implementation and Results](docs/implementation_and_results.md).

## Current EPICS Camera Interface

| PV | Record type | Purpose |
|---|---|---|
| `CAM:CameraCommand` | `mbbo` | Start, Stop, Acquire, Close |
| `CAM:GetStatus` | `stringin` | Camera operating status |
| `CAM:GetStatusDescription` | `waveform` | Status description (passive) |
| `CAM:SetExposure` / `CAM:ExposureRB` | `longout` / `longin` | Normal exposure setter / requested-setting readback |
| `CAM:GetExposure` | `longin` | Camera-reported exposure from streaming frame metadata |
| `CAM:SetGain` / `CAM:GainRB` | `ao` / `ai` | Normal gain setter / requested-setting readback |
| `CAM:GetGain` | `ai` | Camera-reported gain from streaming frame metadata |
| `CAM:SetAutoExposure` / `CAM:GetAutoExposure` | `mbbo` / `mbbi` | Automatic exposure control and readback |
| `CAM:GetLatestImagePath` / `CAM:GetLatestMetadataPath` | `waveform` | Latest JPEG and JSON paths (CHAR arrays) |
| `CAM:ScanEnable` | `bo` | Enable scan mode and normal-setter interlocks |
| `CAM:ScanType` | `mbbo` | Exposure or Gain |
| `CAM:ScanStartExposure` / `CAM:ScanEndExposure` | `longout` | Exposure range in µs |
| `CAM:ScanStartGain` / `CAM:ScanEndGain` | `ao` | Gain range |
| `CAM:ScanPoints` | `longout` | Number of scan points (maximum 100 in current waveforms) |
| `CAM:StartScan` / `CAM:StopScan` | `bo` | Scan requests |
| `CAM:ScanSetExposure` / `CAM:ScanSetGain` | `longout` / `ao` | Scan-specific camera setters |
| `CAM:ScanStatus` | `mbbo` | IDLE, RUNNING, COMPLETED, STOPPED, ERROR |
| `CAM:ScanProgress` | `longout` | Number of completed points |
| `CAM:ScanMeanIntensity` | `ao` | Latest completed mean grayscale intensity |
| `CAM:ScanExposure` / `CAM:ScanGain` | `waveform` | Exposure/gain X arrays |
| `CAM:ScanIntensity` | `waveform` | Mean-intensity Y array |

### Record Processing Strategy

Camera status, actual exposure/gain and latest acquisition paths use StreamDevice I/O Intr. Requested-setting readbacks use passive records triggered by setter FLNK (with startup `PINI` for applicable readbacks). Scan configuration, status, progress and result arrays are soft IOC records updated through PyEpics; scan-specific hardware setters use the existing StreamDevice protocols. The scan setter interlocks use `SDIS` without `CP`.

The status-description readback remains passive because earlier automatic processing caused timeout and message-matching issues. See [StreamDevice Camera IOC](docs/streamdevice_ioc.md) for details.

## Local and Remote Operation

The IMX219, Picamera2 camera server and StreamDevice IOC run on the Raspberry Pi. Remote CA/PVA clients can operate the IOC, while the camera TCP service remains bound to `127.0.0.1:5000`.

| Component or task | Current location |
|---|---|
| Physical camera, Python TCP server and IOC | Raspberry Pi |
| CA/PVA monitoring and camera commands | Pi or network-connected remote client |
| `automation/camera_scan.py` (saved-JPEG intensity analysis) | Raspberry Pi, because it reads local JPEG and JSON files |
| Acquired JPEG/JSON pairs | `acquisition/images/` on Raspberry Pi |
| Scan CSV logs | `data/scan/` on Raspberry Pi in the tested workflow |
| Separate p4p image publisher | Raspberry Pi, reads locally saved JPEGs |
| Phoebus controls, image display and XY plot | Remote client; scan arrays use explicit `pva://` PVs |

**Remote EPICS control is not remote file transfer.** The earlier PyEpics sweep could issue remote acquisition commands, but the current `camera_scan.py` calculates intensity from saved files and therefore runs locally on the Pi unless full-resolution image and metadata access is provided remotely. The publisher transfers only a resized RGB display array through PVAccess.

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
| Exposure | `EXPOSURE <value>`, `EXPOSURE_RB?` |
| Analogue gain | `GAIN <value>`, `GAIN_RB?` |
| Automatic exposure | `AUTO_EXPOSURE 0/1`, `AUTO_EXPOSURE?` |
| File readbacks | `LATEST_IMAGE_PATH?`, `LATEST_METADATA_PATH?` |
| Unsolicited applied-value notifications | `ACTUAL_EXPOSURE:<value>`, `ACTUAL_GAIN:<value>` (server to IOC) |

The Python TCP server listens on `127.0.0.1:5000`.

Exposure time is specified in microseconds. Automatic exposure uses `1` for Enable and `0` for Disable.

The image-path commands return the locations of the latest successfully saved files on the Raspberry Pi, not the image data itself. Actual-value notifications are outgoing server messages rather than query commands.

## Acquisition Output

Each successful acquisition generates a JPEG image and a matching JSON metadata file:

```text
acquisition/images/
├── image_YYYYMMDD_HHMMSS_microseconds.jpg
└── image_YYYYMMDD_HHMMSS_microseconds_metadata.json
```

The metadata can include exposure time, analogue gain, digital gain, sensor timestamps, frame duration, color gains, and other available camera parameters.

Image and metadata are retrieved from the same completed Picamera2 request.

Generated acquisition files are intended to remain outside Git version control. Current scan CSV files are generated under `data/scan/` and excluded from Git. The former `data/exposure_sweeps/` directory has been retired.

## Development Progress

| Stage | Current status |
|---|---|
| EPICS communication, IMX219 integration and camera control | Completed and tested |
| CA/PVA monitoring, acquisition and requested/actual readbacks | Completed and tested |
| Initial exposure characterization | Completed historically; original scripts retired |
| Phoebus control and separate RGB image publisher | Demonstrated |
| EPICS-controlled camera scanning | Exposure scan, CSV logging and PVAccess XY plotting tested |
| Gain scanning, Stop Scan and repeated-scan reliability | Implemented; further verification needed |
| LED recognition, advanced characterization and areaDetector | Planned |

See [Implementation and Results](docs/implementation_and_results.md) for the full milestone record.

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── docs/
│   ├── implementation_and_results.md
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/
│       ├── epics_device_integration.md
│       ├── test_picamera2_acquisition.md
│       ├── tcp_connection_and_metadata_monitoring.md
│       ├── automated_acquisition_and_characterization.md
│       └── pva_image_publisher.md
├── acquisition/
│   ├── camera_server_simulator.py
│   ├── picamera2_server.py
│   ├── pva_image_publisher.py
│   ├── tests/
│   │   └── test_camera_acquisition.py
│   └── images/                 # generated JPEG/JSON; ignored
├── automation/
│   └── camera_scan.py
├── data/
│   └── scan/                   # generated CSV; ignored
├── .venv/                      # local virtual environment; ignored
├── vision/
└── epics/
    └── streamdevice_camera/
        └── streamdevice_camera_ioc/
```

The old `characterization/` scripts and `automation/exposure_sweep.py` are no longer active files. The `data/scan/` directory may not appear in GitHub when empty because its generated contents are ignored.

## Documentation

### Setup and Implementation

- [Implementation and Results](docs/implementation_and_results.md) — Chronological milestones, design decisions, experiments and verified outcomes.

- [EPICS Environment Setup](docs/epics_setup.md) — Dependencies and installation.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC architecture, protocols, records and integration.
- [Troubleshooting](docs/troubleshooting.md) — Recorded problems, resolutions and open issues.

### Learning Notes

- [Understanding EPICS Device Integration](docs/notes/epics_device_integration.md).
- [Standalone Picamera2 Acquisition Test](docs/notes/test_picamera2_acquisition.md).
- [TCP Connection and Metadata Monitoring](docs/notes/tcp_connection_and_metadata_monitoring.md).
- [Automated Acquisition and Initial Characterization](docs/notes/automated_acquisition_and_characterization.md) — Historical measurements; legacy scripts retired.
- [PVAccess Image Publisher](docs/notes/pva_image_publisher.md).

A separate learning note for the new sequential scan controller is planned.

## Current Limitations and Open Questions

### Communication and Monitoring

- The camera server accepts one active IOC TCP connection. Command responses and unsolicited status, path and applied-setting notifications share that connection. The TCP lock prevents overlapping writes but does not guarantee StreamDevice message routing or response ordering.
- `ExtraInput = Ignore;` is enabled experimentally in `stream_camera.proto`; it has not been proven to resolve unsolicited-message mismatches. Global `ReplyTimeout` and `ReadTimeout` overrides remain commented out.
- The output-only camera-command protocol does not consume Python's `OK` response. Brief intermediate states such as `ACQUIRING` can be missed by CA/PVA monitors. Status-description updates remain passive.
- Actual exposure/gain PVs can retain their last values after streaming stops; initial synchronization, reconnection and error recovery need further testing.

### Scanning and Data

- The sequential scan controller reads saved JPEG/JSON files locally on the Pi. It does not yet provide an in-memory image-measurement mode or remote full-resolution file access.
- Exposure scanning, waveform publication and Phoebus XY plotting were tested. Gain scanning, Stop Scan and repeated scans require further verification. The current scan arrays support up to 100 points.
- `SDIS` blocks normal setter processing during scan mode but does not provide strict write access control; another client could still write scan-specific setters. Automatic exposure is disabled by the scan program, but its setter is not database-interlocked.
- Waveform arrays use `NELM=100` and report valid lengths via `NORD`. In observed tests, `caget` displayed trailing zeros while `pvget` returned valid-length data. Explicit `pva://` links in the Phoebus XY Plot eliminated an unwanted origin point. Phoebus display responsiveness needs investigation.
- Generated JPEG/JSON and scan CSV files are intentionally excluded from Git and were cleared after testing. The scan program's CSV paths refer to files on the Pi.

### Characterization and Image Display

- Mean intensity is calculated from processed 8-bit grayscale JPEGs, not raw sensor data. Controlled sensor linearity, noise, ROI and gain characterization remain future work.
- The earlier standalone characterization scripts were retired; their historical results remain documented and recoverable from Git.
- The separate image publisher provides a reduced-resolution RGB array, not live video or full-resolution NTNDArray transport. Periodic path checking can miss intermediate acquisitions.
- The project virtual environment uses `--system-site-packages` to access camera libraries and is not fully isolated.

## Development Roadmap

### Phase 1–5 — EPICS Integration, Acquisition, Characterization and Phoebus

- [x] Establish CA/PVA and StreamDevice/asyn communication.
- [x] Integrate Picamera2, still acquisition and matching metadata.
- [x] Complete initial historical JPEG characterization.
- [x] Add Phoebus controls and separate PVAccess RGB image display.

### Phase 6 — Actual Camera-Setting Readbacks

- [x] Refactor shared TCP communication and implement metadata monitoring.
- [x] Distinguish requested and actual exposure/gain PVs.

### Phase 7 — EPICS-Controlled Camera Scans (Current)

- [x] Implement scan soft PVs, dedicated exposure/gain setters and `SDIS` interlocks.
- [x] Implement sequential scan controller and saved-image mean-intensity analysis.
- [x] Verify exposure scanning and live waveform plotting through PVAccess.
- [ ] Test gain scans, Stop Scan, repeated scans and Phoebus performance.
- [ ] Consider an in-memory acquisition/measurement mode.

### Phase 8 — LED Recognition

- [ ] Define and test LED recognition using acquired images.

### Phase 9 — Hand-Gesture Recognition

- [ ] Explore hand-gesture detection and image processing.

### Phase 10 — Hardware Monitoring and Alarms

- [ ] Integrate electronic components and EPICS alarm monitoring.

### Phase 11 — Advanced Sensor Characterization (Deferred)

- [ ] Design new offline characterization tools for controlled exposure/gain response, ROI, uniformity and noise.
- [ ] Investigate raw sensor data and suitable analysis methods.

### Phase 12 — areaDetector

- [ ] Investigate IMX219 driver integration, NDArray transport and plugins.
- [ ] Compare the conventional IOC with areaDetector.

## Development and Documentation Approach

The project is developed incrementally, beginning with standalone hardware and software tests before integrating functionality into EPICS.

Working implementations are tested and committed to GitHub; detailed milestones and results are maintained in [Implementation and Results](docs/implementation_and_results.md). The sequential scan controller and exposure scan have now been tested; gain scanning and other remaining checks are explicitly marked as pending.

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
