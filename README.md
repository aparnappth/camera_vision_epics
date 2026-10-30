# EPICS-Controlled Camera Characterization and Vision Platform

An experimental camera-control and computer-vision platform built using a Raspberry Pi Zero 2 W, Sony IMX219 camera, and EPICS (Experimental Physics and Industrial Control System).

The platform currently supports remote camera control, image acquisition, adjustment of camera settings, and automated exposure and gain scans to study the camera's response to different settings. It also demonstrates camera-based device status monitoring using computer vision. A touch-controlled RGB LED serves as a simulated device representing normal, warning, and fault conditions. The camera identifies these states by analyzing the LED colour, and the results are displayed through Phoebus, a graphical interface for controlling and monitoring the system through EPICS.

## Capabilities

- Control camera initialization, streaming, single-image acquisition, stopping, and closing through EPICS.
- Set exposure, analogue gain, and automatic exposure; monitor requested settings separately from camera-reported values.
- Acquire full-resolution JPEG images with JSON metadata from the same completed Picamera2 request.
- Run configurable exposure or gain scans through a PyEpics client, recording acquired images and scan results.
- Calculate mean grayscale JPEG intensity and publish exposure/gain and intensity arrays for Phoebus XY plots.
- Display the latest acquired image in Phoebus through a separate PVAccess image publisher.
- Use version-controlled Phoebus displays for main camera control and dedicated exposure/gain scan windows.
- Access IOC records locally or from network-connected EPICS clients using Channel Access and PVAccess.
- Operate a standalone touch-controlled RGB LED with NORMAL (green), WARNING (yellow), and FAULT (red) states.
- Monitor the LED through periodic camera acquisition, full-image HSV colour analysis, EPICS status PVs, and Phoebus indicators.

**Verification status:** Exposure and gain scans, image acquisition, intensity publication, scan interlocks, Stop Scan interruption, and PVAccess XY plotting have been tested. The standalone touch/LED controller, camera-based LED classification, periodic EPICS monitoring, automatic-exposure activation, scan/vision coordination, and Phoebus LED status display have also been tested. Further stress testing of TCP message handling, classification under changing scenes, and Phoebus responsiveness remains useful.

## Hardware and Software

**Hardware:** Raspberry Pi Zero 2 W; Sony IMX219 8 MP CSI camera; digital touch sensor on BCM GPIO 17; RGB LED on GPIO 22 (red), 23 (green), and 24 (blue). A buzzer is a possible later extension.

**Software:** EPICS Base R7.0.10, asyn R4-46, StreamDevice 2.8.26, QSRV/PVAccess, Python 3, Picamera2/libcamera, PyEpics, NumPy, Pillow, p4p, gpiozero, Phoebus Display Builder. Netcat supports direct TCP testing; VLC supports camera positioning. Matplotlib may be used for future offline analysis.

## System Architecture

The platform consists of a camera-control system, independent Python programs for automated measurements and image analysis, and a graphical interface for remote operation. The components communicate through EPICS, while the Raspberry Pi manages the physical camera and connected hardware.

```text
                         Phoebus / EPICS clients
                       (Remote control and display)
                                   |
                         Channel Access / PVAccess
                                   |
                           EPICS IOC + QSRV
                         (Control and data PVs)
                                   |
                           StreamDevice + asyn
                                   |
                           TCP 127.0.0.1:5000
                                   |
                            Python camera server
                          acquisition/picamera2_server.py
                                   |
                            Picamera2 / libcamera
                                   |
                              IMX219 camera
                                   |
                           Acquired JPEG + JSON
                                   |
                  +----------------+----------------+
                  |                |                |
                  v                v                v
             Camera scan      LED recognition    Image publisher
             camera_scan.py   led_monitor.py     pva_image_publisher.py
                  |                |                |
             Mean intensity   LED colour       Resized RGB image
             Exposure/gain    and status       published via p4p
             scan results          |                |
                  |                |                |
                  v                v                v
             EPICS scan       EPICS vision       CAM:Image
             result PVs       status PVs         (PVAccess)
                  |                |                |
                  v                v                v
             Phoebus XY       Phoebus LED        Phoebus Image
                plots         status display        widget


    Independent hardware used for vision monitoring:

        Touch sensor --> led_controller.py --> RGB LED
                                                  |
                                      Observed by IMX219 camera
```

### Camera control and communication

The Python camera server (`acquisition/picamera2_server.py`) manages the IMX219 camera through Picamera2 and libcamera. It handles camera initialization, streaming, exposure and gain settings, and image acquisition.

The EPICS IOC communicates with the Python server through StreamDevice and asyn over a local TCP connection. It exposes process variables (PVs) for camera control, settings, status monitoring, and measurement results. Phoebus and other EPICS clients access these PVs through Channel Access or PVAccess.

The camera server and IOC run as separate processes on the Raspberry Pi. The server uses a `TCPConnection` class to manage the single IOC TCP connection and serialize outgoing messages. Camera-reported exposure and gain values are collected from frame metadata and published to the IOC through StreamDevice I/O Intr notifications.

### Automated camera scanning

The independent `automation/camera_scan.py` program communicates with the IOC through PyEpics. It performs configurable exposure and gain scans by adjusting camera settings, acquiring images, and calculating mean grayscale intensity from saved JPEG files.

The program verifies requested settings against their readbacks and waits for the camera-reported exposure or gain to approach the requested value before acquisition. Results are published to IOC soft records and displayed as XY plots in Phoebus. The associated JPEG images, JSON metadata, and scan CSV files are retained on the Raspberry Pi.

### Camera-based LED status monitoring

A touch-controlled RGB LED serves as a simulated device for testing the platform's computer-vision capabilities. The standalone `hardware/touch_led/led_controller.py` program changes the LED between green (NORMAL), yellow (WARNING), and red (FAULT) based on touch duration. This program operates independently of EPICS.

The IMX219 camera observes the LED. The separate `vision/led_monitor.py` program uses PyEpics to request a new image approximately every three seconds, reads the saved JPEG and matching metadata, and analyzes the image using HSV colour segmentation.

The detected status and numerical colour measurements are published to IOC soft records and displayed in Phoebus. When vision monitoring is enabled, the program first checks whether a camera scan is running. If a scan is in progress, it waits for the scan to finish before disabling scan mode and starting LED monitoring. It also automatically enables the camera's automatic exposure setting before acquiring images. New camera scans are prevented from starting while vision monitoring is enabled.

### Image visualization

The independent `acquisition/pva_image_publisher.py` program reads the latest acquired JPEG and publishes a resized 100 × 100 RGB image as `CAM:Image` using the `p4p` PVAccess library.

Phoebus displays the image through its Image widget. Image pixels are transferred separately from the StreamDevice TCP connection used for camera commands.

The current implementation displays acquired images rather than continuous live video. Both the camera scanner and LED monitor use saved images for analysis.

### Design approach

The system separates camera hardware control, automated measurements, image processing, and visualization into independent programs. The camera server remains the only process accessing the physical IMX219 camera, while the scan and vision programs communicate through the existing EPICS IOC.

This arrangement allows measurement and vision functionality to be developed and tested independently without changing the underlying camera-control interface.

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

### LED vision monitoring

| PV | Purpose |
|---|---|
| `CAM:VisionEnable` | Enable or disable periodic LED monitoring |
| `CAM:VisionStatus` | IDLE, RUNNING, ERROR, or WAITING |
| `CAM:LEDStatus` | UNKNOWN, NORMAL, WARNING, or FAULT |
| `CAM:LEDRedGreenRatio` | Red-to-green segmented-pixel ratio |
| `CAM:LEDYellowFraction` | Yellow-pixel fraction among detected colour pixels |

These are soft IOC records updated by `vision/led_monitor.py` through PyEpics. No vision-specific StreamDevice commands or additional camera TCP connection are required. Vision monitoring waits for an active scan to complete before disabling scan mode and starting acquisition; new scans are prevented while vision monitoring is enabled. Both directions were tested in the current setup.

## Phoebus Displays

The version-controlled displays are in `phoebus/`:

- `epics_Camera_vision_main.bob` — main camera controls, LED vision-monitoring controls and indicators, and navigation to the scan displays.
- `epics_Camera_vision_scan_exposure.bob` — exposure scan configuration and exposure–intensity plot.
- `epics_Camera_vision_scan_gain.bob` — gain scan configuration and gain–intensity plot.

The main display provides separate actions for exposure and gain scanning. These select `CAM:ScanType` and open the corresponding scan display. It also provides LED vision-monitoring controls and detected-status visualization. The scan plots use PVAccess waveform PVs, and the acquired-image widget requires the independent `pva_image_publisher.py` process.

## Operating the Platform

The camera server, IOC, optional image publisher, scan program, touch/LED controller, and vision monitor run on the Raspberry Pi in the current setup. The scan and vision programs require local access to the acquired JPEG and JSON files. Remote CA/PVA clients and Phoebus can control and monitor the IOC; the scan program's EPICS commands themselves do not require local execution, but its file-based image analysis does.

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

To run the standalone touch/LED indicator, use another Raspberry Pi terminal from the repository root:

```bash
source .venv/bin/activate
python -u hardware/touch_led/led_controller.py
```

The LED is green when the sensor is inactive, yellow after at least one second of continuous touch, and red after more than six seconds. Releasing the sensor returns it to green.

For camera-based LED monitoring, start the camera server and IOC first, then run the vision program in a separate terminal:

```bash
source .venv/bin/activate
python -u vision/led_monitor.py
```

Enable `CAM:VisionEnable` from the main Phoebus display, or use `caput CAM:VisionEnable 1`. The program waits for any running scan to finish, disables scan mode, enables automatic exposure, and acquires and analyzes images approximately every three seconds. `CAM:LEDStatus` reports UNKNOWN, NORMAL, WARNING, or FAULT. Disable monitoring with `caput CAM:VisionEnable 0`. Start `acquisition/pva_image_publisher.py` separately if you also want the latest acquired image displayed in Phoebus. The experimental colour-analysis script `vision/test_led_detection.py` processes the latest acquired image once and writes diagnostic masks under `data/vision/`; it does not start continuous monitoring.

For a scan, use the main Phoebus display to open the exposure or gain scan window, set the corresponding start/end values and point count, enable scan mode, and issue Start Scan. The scan program ensures the camera is streaming and waits for the applied setting before acquisition. It saves JPEG/JSON acquisitions, writes scan CSV results under `data/scan/`, and updates the IOC result PVs point by point. The plotted X values come from the metadata associated with each acquired image, not merely the requested setting. Stop Scan requests a cooperative interruption; the Stop PV is not automatically reset after interruption.

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
├── hardware/
│   └── touch_led/
│       ├── led_controller.py
│       ├── test_rgb_led.py
│       └── test_touch.py
├── vision/
│   ├── led_monitor.py
│   └── test_led_detection.py
├── phoebus/
│   ├── epics_Camera_vision_main.bob
│   ├── epics_Camera_vision_scan_exposure.bob
│   └── epics_Camera_vision_scan_gain.bob
├── data/
│   ├── scan/                         # Generated CSV data, ignored by Git
│   └── vision/                       # Generated diagnostic images, ignored by Git
├── docs/
│   ├── implementation_and_results.md
│   ├── epics_setup.md
│   ├── streamdevice_ioc.md
│   ├── troubleshooting.md
│   └── notes/                        # Focused technical learning notes
└── epics/streamdevice_camera/streamdevice_camera_ioc/
```

The repository is organized into separate directories for camera control, EPICS integration, automated scanning, image processing, hardware experiments, Phoebus displays, and documentation. Python source code and configuration files are version-controlled, while generated data, including acquired JPEG images, JSON metadata, scan results, and vision-analysis outputs, are stored separately and excluded from Git.

## Current Limitations

- The camera server uses a single TCP connection to communicate with the EPICS IOC. During image acquisition, rapid camera status changes may not always be captured or displayed by EPICS monitoring clients. However, the final camera status is reported correctly in the tested scenarios.
- Mean intensity is calculated from processed JPEGs. These results are not raw-sensor linearity, noise, or calibrated characterization measurements.
- The image publisher transfers a reduced-resolution RGB array, not full-resolution files or live video. 
- File-based scan and vision analysis currently require access to JPEG/JSON files on the Raspberry Pi. Remote file transfer and portable dataset paths are not implemented.
- LED recognition uses periodic still-image acquisition approximately every three seconds, not continuous frame processing. Changes can be detected only after a new acquisition and analysis; short-lived states may be missed. HSV thresholds were tested in a controlled scene and are not yet validated against arbitrary backgrounds or LED absence.


## Possible Future Extensions

- Investigate continuous frame-based LED recognition to reduce the delay from periodic still-image acquisition.
- Explore a separate areaDetector-based implementation, including a suitable IMX219 driver, NDArray transport, and image-processing plugins, and compare it with the current StreamDevice approach.
- Extend the visual LED status monitoring with a physical buzzer alarm and investigate hand-gesture recognition.
- Revisit controlled camera characterization, including ROI, gain, noise, uniformity, and potentially raw-sensor measurements.

## Documentation

- [Implementation and Results](docs/implementation_and_results.md) — Development history, experimental milestones, and verified outcomes.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — IOC, database, protocol, communication, and integration details.
- [EPICS Environment Setup](docs/epics_setup.md) — Installation and build configuration.
- [Troubleshooting](docs/troubleshooting.md) — Observed problems, resolutions, and open issues.
- [Technical Notes](docs/notes/) — Individual camera, EPICS, Python, image-publishing, touch/LED control, and vision-monitoring concepts.

## Acknowledgements

OpenAI's ChatGPT was used as a learning and development assistant for technical explanations, code development, troubleshooting, and documentation. The platform has been tested through hands-on work with the Raspberry Pi, EPICS, and camera hardware.

## References

[EPICS Documentation](https://docs.epics-controls.org/) · [EPICS Base](https://github.com/epics-base/epics-base) · [asyn](https://github.com/epics-modules/asyn) · [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice) · [Picamera2](https://github.com/raspberrypi/picamera2) · [libcamera](https://libcamera.org/) · [areaDetector](https://areadetector.github.io/areaDetector/)
