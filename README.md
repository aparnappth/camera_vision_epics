# EPICS-Controlled Camera Characterization and Vision Platform

An experimental camera-control, characterization, and computer-vision platform using a Raspberry Pi Zero 2 W, Sony IMX219 camera, and EPICS (Experimental Physics and Industrial Control System).

**This project investigates two independent EPICS integration approaches for the same camera:**

1. **StreamDevice-based camera control and characterization:** A Python camera server communicates with an EPICS IOC over TCP/IP using StreamDevice and asyn. It supports camera control, JPEG acquisition, exposure/gain scans, and periodic LED monitoring.
2. **areaDetector-based continuous image processing:** A separate Python acquisition client sends in-memory RGB frames to an areaDetector IOC. Standard plugins and a custom C++ `NDPluginRGB` plugin provide image display, HSV segmentation, and EPICS database-based LED classification.

The approaches have separate IOCs, acquisition workflows, and PV namespaces. **They are tested independently, not operated simultaneously**, because both access the same physical IMX219 camera. Neither replaces the other, and a quantitative performance comparison remains future work.

## Project Objectives

- Explore conventional StreamDevice/asyn and areaDetector/NDArray IOC architectures.
- Implement remote camera control, exposure/gain characterization, and image acquisition.
- Develop computer-vision monitoring of a simulated device using an RGB LED.
- Display measurements and status through Phoebus.
- Understand integration trade-offs, callback processing, and experimental limitations.

The system is a learning and experimental development platform, not a calibrated camera-characterization instrument or production monitoring solution.

## Two EPICS Integration Approaches

| Feature | Approach 1: StreamDevice | Approach 2: areaDetector |
|---|---|---|
| IOC | `streamdevice_camera_ioc` | `areadetector_camera_ioc` |
| Camera interface | Python TCP camera server | Picamera2 acquisition client |
| EPICS integration | StreamDevice + asyn | NDDriverStdArrays + asyn |
| Acquisition | JPEG + matching JSON metadata | Continuous in-memory RGB frames |
| Image processing | Python / Pillow / NumPy | C++ `NDPluginRGB` |
| LED classification | Python `vision/led_monitor.py` | EPICS `vision.db` |
| Image display | Independent PVAccess publisher | NDPluginStdArrays |
| PV namespace | `CAM:` | `AD:` |
| Focus | Camera control and characterization | NDArray processing and vision monitoring |

## Hardware and Software

**Hardware:** Raspberry Pi Zero 2 W; Sony IMX219 8 MP CSI camera; digital touch sensor on BCM GPIO 17; RGB LED on BCM GPIO 22 (red), 23 (green), and 24 (blue). Phoebus is used remotely on Windows.

**Software:** EPICS Base R7.0.10, asyn R4-46, StreamDevice 2.8.26, ADCore R3-14, NDDriverStdArrays R1-3, busy R1-7-4, QSRV/PVAccess, Picamera2/libcamera, Python 3, PyEpics, NumPy, Pillow, p4p, gpiozero, and Phoebus. Netcat was used for TCP testing and VLC for camera positioning.

---

# Approach 1 — StreamDevice-Based Camera Control and Characterization

## Architecture

```text
Phoebus / CA and PVA clients
          |
  StreamDevice IOC (CAM:)
          |
   StreamDevice + asyn
          |
   TCP 127.0.0.1:5000
          |
acquisition/picamera2_server.py
          |
    Picamera2 / IMX219
          |
     JPEG + JSON
          |
   +------+------+------------------+
   |             |                  |
camera_scan.py  led_monitor.py  pva_image_publisher.py
   |             |                  |
Scan PVs       LED PVs        pva://CAM:Image
   +-------------+------------------+
                 |
               Phoebus
```

The camera server is the process controlling the IMX219 in this workflow. The scan controller and vision monitor use EPICS to request acquisitions and analyze saved files; the image publisher reads the latest JPEG and publishes resized pixels separately through PVAccess.

## Camera Control and Acquisition

`acquisition/picamera2_server.py` supports initialization, streaming, stopping, closing, manual exposure and gain, automatic exposure, status reporting, and JPEG acquisition. A Picamera2 completed request supplies the image and its matching JSON metadata. Requested exposure/gain values are distinguished from camera-reported values obtained from completed-frame metadata. The Python server uses a `TCPConnection` helper to serialize writes over the shared IOC connection.

## Automated Characterization

`automation/camera_scan.py` runs configurable exposure and gain scans through PyEpics. It applies each requested setting, checks requested and camera-reported readbacks, captures a JPEG/JSON pair, calculates mean grayscale JPEG intensity, and publishes scan progress and numerical arrays. Phoebus XY plots use the acquired frame metadata for the X-axis rather than assuming the requested setting was applied. Results are saved as CSV files under `data/scan/`.

These are processed-JPEG measurements, not calibrated raw-sensor noise, linearity, or gain characterization.

## Periodic LED Monitoring

The standalone `hardware/touch_led/led_controller.py` drives a simulated status indicator: green (NORMAL), yellow (WARNING), and red (FAULT), based on touch duration. `vision/led_monitor.py` requests saved JPEG acquisitions approximately every three seconds, segments bright saturated colours in HSV using Pillow/NumPy, and publishes LED status and diagnostic ratios through soft IOC records. The monitor coordinates with the scan workflow and enables automatic exposure when entering vision mode.

The independent `acquisition/pva_image_publisher.py` publishes a resized 100 × 100 image at `pva://CAM:Image`. This is periodic still-image monitoring, not continuous frame analysis.

---

# Approach 2 — areaDetector-Based Continuous Image Processing

## Architecture

```text
Sony IMX219 / Picamera2
          |
test_areadetector_continuous.py
          |
      PyEpics / CA
          |
 NDDriverStdArrays (STDARRAYS)
          |
     UInt8 RGB1 NDArray
          |
    +-----+--------------------+
    |                          |
NDPluginStdArrays           NDPluginRGB
  (IMAGE1)                   (RGB1)
    |                          |
Image waveform            RGB statistics
    |                     HSV segmentation
    |                          |
    |                 ColorCounts_RBV [R,Y,G]
    |                          |
    |                       vision.db
    |                  subArray / calc / mbbi
    |                          |
    +-------------+------------+
                  |
                Phoebus
```

This is a **separate IOC and camera acquisition process**, not an extension of the StreamDevice TCP server. It does not save an intermediate JPEG for analysis. The standard `IMAGE1` and custom `RGB1` plugins receive NDArrays independently from `STDARRAYS`.

## Image Acquisition

The original `acquisition/tests/test_areadetector_image.py` verified a single 320 × 240 RGB image. The later `acquisition/tests/test_areadetector_continuous.py` repeatedly captures frames and transfers them through `AD:Input:ArrayIn`.

| Property | Configuration |
|---|---|
| Width / height | 320 × 240 |
| Channels | 3 |
| Dimensions | `[3, 320, 240]` |
| NDArray type | UInt8 |
| Colour mode | RGB1 |
| Image mode | Continuous |
| Elements per frame | 230,400 |

The Python client configures the driver and callback PVs before acquisition. `NDDriverStdArrays` creates NDArrays; `NDPluginStdArrays` publishes the image for the Phoebus Image widget at `ca://AD:Image1:ArrayData`.

## Custom `NDPluginRGB`

The custom C++ plugin derives from `NDPluginDriver`, validates incoming RGB1 NDArrays, calculates mean red/green/blue channel values, converts pixels to HSV, and counts bright saturated red, yellow, and green pixels. Experimental hue thresholds on an approximately 0–255 scale are red (`H < 15` or `H > 240`), yellow (`25 <= H <= 50`), and green (`55 <= H <= 115`), with saturation and value both greater than 100.

The plugin publishes `AD:RGB1:RedMean_RBV`, `GreenMean_RBV`, `BlueMean_RBV`, individual colour counts, and a three-element `AD:RGB1:ColorCounts_RBV` waveform ordered **[red, yellow, green]**. Each waveform callback contains counts from one processed NDArray.

An early implementation encountered `NDArrayPool:release ERROR, reference count < 0`. The measurement-only plugin was corrected not to forward or manually release the incoming NDArray. See the [NDPluginRGB technical guide](docs/notes/ndplugin_rgb.md).

## `vision.db` Classification and Alarms

The application-specific classification is performed using standard EPICS records, without another custom C++ classification function. Three CP-linked `subArray` records extract red, yellow, and green counts from the combined waveform. `calc` records compute total coloured pixels, red/green ratio, yellow fraction, and the numerical LED status. An `mbbi` record provides readable names.

| Condition, evaluated in order | Status | Code |
|---|---|---:|
| Total coloured pixels < 1000 | UNKNOWN / OFF | 0 |
| R/G > 20 and yellow fraction < 0.05 | FAULT | 3 |
| Yellow fraction > 0.10 | WARNING | 2 |
| R/G < 0.2 and yellow fraction < 0.02 | NORMAL | 1 |
| Otherwise | UNKNOWN | 0 |

`AD:Vision:LEDStatus` is the numerical classification and alarm source. Its thresholds assign NO_ALARM to UNKNOWN and NORMAL, MINOR to WARNING, and MAJOR to FAULT. `AD:Vision:LEDState` provides human-readable state names without duplicating alarm severity settings.

**Synchronization caveat:** The combined waveform represents one frame, but the downstream independently CP-triggered `subArray` and `calc` records do not guarantee an atomic single-frame snapshot. Brief intermediate UNKNOWN transitions were observed near some LED changes.

## Experimental Verification

Representative combined waveform counts were:

| Physical LED | Red | Yellow | Green |
|---|---:|---:|---:|
| Green | 0 | 0 | 25,680 |
| Yellow | 661 | 4,865 | 4,041 |
| Red | 16,033 | 528 | 0 |
| Green again | 0 | 0 | 24,580 |

Repeated tests followed **FAULT → NORMAL → WARNING → UNKNOWN/OFF** at approximately 10-second intervals. The system recognized the intended states in the controlled scene. Quantified latency, sustained throughput, long-duration reliability, and calibrated colour accuracy remain unverified.

---

## EPICS Interfaces

### StreamDevice IOC — `CAM:`

| PV or group | Purpose |
|---|---|
| `CAM:CameraCommand`, `CAM:GetStatus` | Camera commands and state |
| `CAM:SetExposure`, `CAM:SetGain` | Requested camera settings |
| `CAM:ExposureRB`, `CAM:GainRB` | Requested-value readbacks |
| `CAM:GetExposure`, `CAM:GetGain` | Camera-reported metadata values |
| `CAM:SetAutoExposure`, `CAM:GetAutoExposure` | Automatic exposure |
| `CAM:ScanEnable`, `CAM:StartScan`, `CAM:StopScan` | Scan control |
| `CAM:ScanExposure`, `CAM:ScanGain`, `CAM:ScanIntensity` | Scan waveforms |
| `CAM:VisionEnable`, `CAM:VisionStatus`, `CAM:LEDStatus` | Periodic vision monitoring |
| `CAM:LEDRedGreenRatio`, `CAM:LEDYellowFraction` | Vision diagnostics |

### areaDetector IOC — `AD:`

| PV or group | Purpose |
|---|---|
| `AD:Input:ArrayIn`, `AD:Input:Acquire`, `AD:Input:ImageMode` | Input image and acquisition |
| `AD:Input:ArrayCounter_RBV` | Input frame counter |
| `AD:Image1:ArrayData`, `AD:Image1:ArrayCounter_RBV` | Image output |
| `AD:RGB1:EnableCallbacks`, `AD:RGB1:ValidFrame_RBV` | RGB plugin control and validation |
| `AD:RGB1:ValidCount_RBV`, `AD:RGB1:InvalidCount_RBV` | Frame counters |
| `AD:RGB1:RedMean_RBV`, `GreenMean_RBV`, `BlueMean_RBV` | Channel means |
| `AD:RGB1:ColorCounts_RBV` | Combined colour-count waveform |
| `AD:Vision:Total`, `RedGreenRatio`, `YellowFraction` | Derived measurements |
| `AD:Vision:LEDStatus`, `AD:Vision:LEDState` | Classification and state display |

The `CAM:` and `AD:` PV groups belong to **different IOCs** and are not interchangeable.

## Phoebus Displays

| Display | Approach / purpose |
|---|---|
| `phoebus/epics_Camera_vision_main.bob` | StreamDevice camera control and periodic LED monitoring |
| `phoebus/epics_Camera_vision_scan_exposure.bob` | StreamDevice exposure scan |
| `phoebus/epics_Camera_vision_scan_gain.bob` | StreamDevice gain scan |
| `phoebus/epics_Camera_vision_areadetector.bob` | areaDetector image, LED state, and diagnostics |

The areaDetector image widget uses `ca://AD:Image1:ArrayData` at 320 × 240, `TYPE_RGB1`, unsigned 8-bit interpretation.

## Operating the Platform

**Do not run the two camera acquisition approaches at the same time.** Stop the StreamDevice Python camera server, VLC capture, and other Picamera2 clients before starting the areaDetector acquisition client.

### Approach 1 — StreamDevice

Build and start the StreamDevice IOC as described in [StreamDevice Camera IOC](docs/streamdevice_ioc.md). From the repository root, start the Python server:

```bash
source .venv/bin/activate
python -u acquisition/picamera2_server.py
```

For scanning or periodic LED monitoring, run the appropriate separate process:

```bash
python -u automation/camera_scan.py
# Or, in another workflow:
python -u vision/led_monitor.py
```

Enable periodic monitoring using `caput CAM:VisionEnable 1`. For the independent image publisher, run `python -u acquisition/pva_image_publisher.py`.

### Approach 2 — areaDetector

From the areaDetector IOC root:

```bash
cd epics/areadetector_camera/areadetector_camera_ioc
make -j1
cd iocBoot/iocareadetector_camera
../../bin/linux-arm/areadetector_camera st.cmd
```

In a separate terminal, enable RGB callbacks:

```bash
caput AD:RGB1:EnableCallbacks 1
```

Then from the **repository root** run:

```bash
source .venv/bin/activate
export EPICS_CA_MAX_ARRAY_BYTES=1000000
python acquisition/tests/test_areadetector_continuous.py
```

Open `phoebus/epics_Camera_vision_areadetector.bob`. Monitor the LED state with `camonitor AD:Vision:LEDState`. The original single-frame experiment remains available as `python acquisition/tests/test_areadetector_image.py`.

## Repository Structure

```text
camera_vision_epics/
├── README.md
├── acquisition/
│   ├── camera_server_simulator.py
│   ├── picamera2_server.py
│   ├── pva_image_publisher.py
│   ├── tests/
│   │   ├── test_camera_acquisition.py
│   │   ├── test_areadetector_image.py
│   │   └── test_areadetector_continuous.py
│   └── images/                   # Generated JPEG/JSON
├── automation/camera_scan.py
├── hardware/touch_led/
│   ├── led_controller.py
│   ├── test_rgb_led.py
│   └── test_touch.py
├── vision/
│   ├── led_monitor.py
│   └── test_led_detection.py
├── phoebus/
│   ├── epics_Camera_vision_main.bob
│   ├── epics_Camera_vision_scan_exposure.bob
│   ├── epics_Camera_vision_scan_gain.bob
│   └── epics_Camera_vision_areadetector.bob
├── epics/
│   ├── streamdevice_camera/streamdevice_camera_ioc/
│   └── areadetector_camera/areadetector_camera_ioc/
│       ├── areadetector_cameraApp/src/
│       │   ├── NDPluginRGB.cpp
│       │   ├── NDPluginRGB.h
│       │   └── NDPluginRGB.dbd
│       ├── areadetector_cameraApp/Db/
│       │   ├── NDPluginRGB.template
│       │   └── vision.db
│       └── iocBoot/iocareadetector_camera/st.cmd
├── data/
│   ├── scan/                     # Generated CSV
│   └── vision/                   # Generated masks
└── docs/
    ├── epics_setup.md
    ├── streamdevice_ioc.md
    ├── areadetector_ioc.md
    ├── implementation_and_results.md
    ├── troubleshooting.md
    └── notes/
        ├── ndplugin_rgb.md
        └── ...
```

Source code, EPICS configurations, Phoebus displays, and documentation are version-controlled. Generated images, metadata, scan results, temporary files, and build artifacts are excluded where configured.

## Verification Status and Limitations

**Verified StreamDevice functionality:** camera control and readbacks, JPEG/JSON acquisition, exposure/gain scanning, scan interlocks and cooperative stopping, Phoebus XY plotting, periodic HSV LED recognition, and scan/vision coordination.

**Verified areaDetector functionality:** single-frame and continuous RGB acquisition, Channel Access image transfer, NDArray callbacks, Phoebus image display, custom RGB statistics/HSV segmentation, combined colour-count waveform, database LED classification, and alarm visualization.

**Open limitations:**

- No quantitative frame-rate, latency, CPU, or memory comparison between the two approaches.
- StreamDevice scanning/vision uses saved JPEG/JSON files, and the shared TCP connection has not been stress-tested for all message orderings and failure modes.
- areaDetector uses Python and Channel Access frame transfer rather than a direct libcamera hardware driver.
- HSV thresholds were tested in a controlled scene, not calibrated for arbitrary backgrounds or illumination.
- Independently CP-triggered downstream calculations lack a formal atomic same-frame guarantee; occasional intermediate UNKNOWN transitions were observed.
- No stale-data timeout for the areaDetector LED state after acquisition stops.
- Long-duration reliability and performance benchmarking remain open.

## Possible Future Extensions

- Measure and compare frame rate, latency, and resource usage.
- Investigate strict same-frame database synchronization.
- Calibrate HSV segmentation and explore spatial ROI/object detection.
- Add acquisition-health and stale-state monitoring.
- Extend camera characterization to raw-sensor noise, gain, and uniformity.
- Explore a physical buzzer alarm and additional vision applications.

## Documentation

- [Implementation and Results](docs/implementation_and_results.md) — Development history and verification.
- [StreamDevice Camera IOC](docs/streamdevice_ioc.md) — TCP protocols, camera control, and IOC configuration.
- [areaDetector Camera IOC](docs/areadetector_ioc.md) — NDArray pipeline, plugin integration, and vision database.
- [NDPluginRGB Technical Guide](docs/notes/ndplugin_rgb.md) — C++ implementation and NDArray ownership.
- [areaDetector Single-Frame Test](docs/notes/test_areadetector_image.md) — Original acquisition milestone.
- [EPICS Environment Setup](docs/epics_setup.md) — Dependencies and builds.
- [Troubleshooting](docs/troubleshooting.md) — Investigations, fixes, and open issues.
- [Technical Notes](docs/notes/) — Focused learning notes.

## Acknowledgements

OpenAI's ChatGPT was used as a learning and development assistant for explanations, code development, troubleshooting, and documentation. The project was developed and tested through hands-on work with the Raspberry Pi, IMX219, EPICS, and Phoebus.

## References

[EPICS Documentation](https://docs.epics-controls.org/) · [EPICS Base](https://github.com/epics-base/epics-base) · [asyn](https://github.com/epics-modules/asyn) · [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice) · [Picamera2](https://github.com/raspberrypi/picamera2) · [libcamera](https://libcamera.org/) · [areaDetector](https://areadetector.github.io/areaDetector/)
