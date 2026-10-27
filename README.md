# EPICS-Controlled Camera Characterization and Vision Platform

An experimental camera-control and measurement platform built around a **Raspberry Pi Zero 2 W**, **Sony IMX219 CSI camera**, and **EPICS**. The system provides remote camera operation, automated exposure and gain scans, image acquisition with matching metadata, camera-setting monitoring, and visualization through Phoebus.

## Capabilities

- Control camera initialization, streaming, single-image acquisition, stopping, and closing through EPICS.
- Set exposure, analogue gain, and automatic exposure; monitor requested settings separately from camera-reported values.
- Acquire full-resolution JPEG images with JSON metadata from the same completed Picamera2 request.
- Run configurable exposure or gain scans through a PyEpics client, recording acquired images and scan results.
- Calculate mean grayscale JPEG intensity and publish exposure/gain and intensity arrays for Phoebus XY plots.
- Display the latest acquired image in Phoebus through a separate PVAccess image publisher.
- Access IOC records locally or from network-connected EPICS clients using Channel Access and PVAccess.

**Verification status:** Exposure scanning, image acquisition, intensity publication, scan interlocks, and PVAccess XY plotting have been tested. Gain scanning, Stop Scan behavior, repeated-scan robustness, and display performance need further verification.

## Hardware and Software

**Hardware:** Raspberry Pi Zero 2 W; Sony IMX219 8 MP CSI camera; LEDs and basic electronics for planned vision and monitoring experiments.

**Software:** EPICS Base R7.0.10, asyn R4-46, StreamDevice 2.8.26, QSRV/PVAccess, Python 3, Picamera2/libcamera, PyEpics, NumPy, Pillow, p4p, Phoebus Display Builder. Netcat supports direct TCP testing; VLC supports camera positioning. Matplotlib may be used for future offline analysis.

## System Architecture

```text
                  Phoebus / EPICS clients
                    Channel Access / PVAccess
                              |
                         EPICS IOC + QSRV
                              |
                        StreamDevice + asyn
                              |
                        TCP 127.0.0.1:5000
                              |
                    Python camera server
                              |
                      Picamera2 / libcamera
                              |
                           IMX219

  automation/camera_scan.py --PyEpics--> IOC scan/control/result PVs
             |                               |
             +-- reads saved JPEG/JSON       +-- scan waveform arrays
                 and calculates intensity         --> Phoebus XY Plot

  acquisition/pva_image_publisher.py --p4p--> CAM:Image
      (reads latest saved JPEG)                --> Phoebus Image widget
```

The camera server and IOC are separate processes on the Raspberry Pi. The server uses a `TCPConnection` class to manage **one accepted IOC TCP connection** and serialize outgoing writes. A Picamera2 frame callback collects applied exposure and gain metadata; a lightweight worker sends change-based notifications. StreamDevice I/O Intr updates the corresponding IOC readbacks.

The scan controller is a separate **sequential** PyEpics program. It reads scan configuration from IOC soft records, sets the scan-specific camera controls, acquires images, computes intensity, and publishes scan results. It does not create its own EPICS PVs.

The image publisher is a third, independent process. It reads locally saved JPEGs and publishes a resized 100 × 100 RGB array over PVAccess as `CAM:Image`. This is acquired-image visualization, **not live video**. An areaDetector-based implementation remains planned.

## EPICS Interface

### Camera control and readbacks

| PV | Purpose |
|---|---|
| `CAM:CameraCommand` | Start, Stop, Acquire, Close |
| `CAM:GetStatus` | Application-maintained camera state |
| `CAM:GetStatusDescription` | On-demand status description |
| `CAM:SetExposure`, `CAM:SetGain` | Normal requested camera settings |
| `CAM:ExposureRB`, `CAM:GainRB` | Requested-value readbacks |
| `CAM:GetExposure`, `CAM:GetGain` | Camera-reported exposure and gain from streaming metadata |
| `CAM:SetAutoExposure`, `CAM:GetAutoExposure` | Automatic-exposure control and readback |
| `CAM:GetLatestImagePath`, `CAM:GetLatestMetadataPath` | Paths of the latest saved acquisition files |

Camera status, actual exposure/gain, and acquisition paths use **I/O Intr** notifications. Requested-setting readbacks use **FLNK** from their setters and startup processing where configured. The status-description record remains passive.

### Scan control and results

| PV | Purpose |
|---|---|
| `CAM:ScanEnable` | Enable or disable scan mode |
| `CAM:ScanType` | Select Exposure or Gain |
| `CAM:ScanStartExposure`, `CAM:ScanEndExposure` | Exposure range in microseconds |
| `CAM:ScanStartGain`, `CAM:ScanEndGain` | Analogue-gain range |
| `CAM:ScanPoints` | Number of scan points (maximum 100) |
| `CAM:StartScan`, `CAM:StopScan` | Start and request interruption of a scan |
| `CAM:ScanSetExposure`, `CAM:ScanSetGain` | Scan-specific camera setters |
| `CAM:ScanStatus`, `CAM:ScanProgress` | Scan state and completed-point count |
| `CAM:ScanMeanIntensity` | Mean grayscale intensity of the latest measurement |
| `CAM:ScanExposure`, `CAM:ScanGain`, `CAM:ScanIntensity` | Numerical waveform arrays for XY plotting |

Normal exposure and gain setters are disabled from processing when scan mode is enabled; scan-specific setters are enabled in that mode. These interlocks use EPICS `SDIS` and `DISV` **without `CP`**, to avoid unintended setter processing. They do not provide exclusive client authorization. Automatic exposure is disabled by the scan program and checked before measurement; its setter is not currently database-interlocked.

The waveform records use `FTVL=DOUBLE`, `NELM=100`, and `NORD` to track valid elements. In Phoebus, configure the XY Plot with **`pva://CAM:ScanExposure` or `pva://CAM:ScanGain`** as X and **`pva://CAM:ScanIntensity`** as Y. PVAccess plotting was tested without the spurious origin point observed with Channel Access waveform display.

## Operating the Platform

The camera server, IOC, and optional image publisher run on the Raspberry Pi. The scan program currently also runs on the Pi because it reads the acquired JPEG and JSON files directly. Remote CA/PVA clients and Phoebus can control and monitor the IOC; the scan program's EPICS commands themselves do not require local execution, but its file-based image analysis does.

From the repository root, the camera server and scan program can be started in separate terminals:

```bash
source .venv/bin/activate
python -u acquisition/picamera2_server.py
```

```bash
source .venv/bin/activate
python -u automation/camera_scan.py
```

Build the IOC from `epics/streamdevice_camera/streamdevice_camera_ioc/` with `make -j2`, then start its existing `iocBoot/iocstreamdevice_camera/st.cmd`. Start the image publisher separately when acquired-image display is needed. See the [IOC implementation guide](docs/streamdevice_ioc.md) for configuration and startup details.

For a scan, select the scan type, set the corresponding start/end values and point count, enable scan mode, and issue Start Scan. The program saves JPEG/JSON acquisitions, writes scan CSV results under `data/scan/`, and updates the IOC result PVs. The plotted X values come from the metadata associated with each acquired image, not merely the requested setting.

## Data and Repository Structure

```text
camera_vision_epics/
├── README.md
├── acquisition/
│   ├── camera_server_simulator.py
│   ├── picamera2_server.py
│   ├── pva_image_publisher.py
│   ├── tests/test_camera_acquisition.py
│   └── images/                       # Generated JPEG/JSON files
├── automation/
│   └── camera_scan.py
├── data/
│   └── scan/                         # Generated CSV data, ignored by Git
├── docs/
│   ├── implementation_and_results.md
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/                        # Focused technical learning notes
├── vision/                           # Future computer-vision work
└── epics/streamdevice_camera/streamdevice_camera_ioc/
```

Captured JPEG and JSON metadata files are saved on the Raspberry Pi. File-path PVs expose their locations, **not their contents**. Scan CSVs are written on the computer running the scan program. Generated data and the project virtual environment are excluded from version control.

## Current Limitations

- The camera TCP server supports one active IOC connection. Commands and unsolicited notifications share it; a write lock prevents overlapping writes but does not guarantee StreamDevice message ordering. Global `ExtraInput = Ignore;` is enabled experimentally, not established as a fix for all mismatches.
- Image acquisition is synchronous; the server does not handle other camera commands during a blocking acquisition. The output-only camera command protocol does not wait for an acknowledgement, although Python still sends `OK`.
- Brief intermediate camera states may not appear in every monitor update. Camera-reported exposure/gain PVs may retain stale values after streaming stops; validity signaling and reconnection synchronization remain incomplete.
- Stop Scan is cooperative rather than an immediate camera-capture interrupt. Gain scans, stop behavior, repeated scans, and Phoebus performance require further testing.
- Mean intensity is calculated from processed JPEGs. These results are not raw-sensor linearity, noise, or calibrated characterization measurements.
- The image publisher transfers a reduced-resolution RGB array, not full-resolution files or live video. It can miss intermediate acquisitions between path checks.
- File-based scan analysis currently requires access to JPEG/JSON files on the Raspberry Pi. Remote file transfer and portable dataset paths are not implemented.

## Planned Work

- Verify gain scanning, Stop Scan, repeated scans, and scan/Phoebus reliability.
- Investigate in-memory image analysis without saving every frame.
- Develop LED recognition and later hand-gesture detection.
- Extend electronic hardware monitoring and EPICS alarms.
- Revisit controlled camera characterization, including ROI, gain, noise, uniformity, and potentially raw-sensor measurements.
- Investigate areaDetector, NDArray transport, and image-processing plugins.

## Documentation

- [Implementation and Results](docs/implementation_and_results.md) — Development history, experimental milestones, and verified outcomes.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC, database, protocol, communication, and integration details.
- [EPICS Environment Setup](docs/epics_setup.md) — Installation and build configuration.
- [Troubleshooting](docs/troubleshooting.md) — Observed problems, resolutions, and open issues.
- [Technical Notes](docs/notes/) — Individual camera, EPICS, Python, and image-publishing concepts.

## Acknowledgements

OpenAI's ChatGPT was used as a learning and development assistant for technical explanations, code development, troubleshooting, and documentation. The platform has been tested through hands-on work with the Raspberry Pi, EPICS, and camera hardware.

## References

[EPICS Documentation](https://docs.epics-controls.org/) · [EPICS Base](https://github.com/epics-base/epics-base) · [asyn](https://github.com/epics-modules/asyn) · [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice) · [Picamera2](https://github.com/raspberrypi/picamera2) · [libcamera](https://libcamera.org/) · [areaDetector](https://areadetector.github.io/areaDetector/)
