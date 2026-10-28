# Implementation and Results

**EPICS-Controlled Camera Characterization and Vision Platform**  
**Development record through 28 October 2026**

This document records the implementation stages, design decisions, tests and observed results of the project. It complements the [project overview](../README.md), the [StreamDevice IOC implementation guide](streamdevice_ioc.md), and the [troubleshooting record](troubleshooting.md). Earlier experiments are retained as historical results even where their scripts have since been retired.

The currently active scan controller is `automation/camera_scan.py`. Exposure and gain scans, Stop Scan, repeated scanning, and live Phoebus plotting have been exercised successfully. Broader communication and display-performance testing remains open.

---


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
- Requested exposure-time and analogue-gain settings and separate requested-value readbacks.
- Camera-reported exposure and gain monitoring from completed-frame metadata while streaming.
- Single-image acquisition with matching metadata.
- Repeated image acquisition while the camera remains streaming.
- Retrieval of the latest saved image and metadata file paths.
- Centralized camera-state management.
- Basic input validation and error reporting.
- Camera cleanup on detected TCP disconnection and server shutdown.

Camera operations remain organized into reusable functions, while a separate command processor interprets incoming TCP commands. The refactored `TCPConnection` class centralizes socket registration, message encoding, serialized writes, and connection detachment. The frame callback stores metadata without network writes; a lightweight worker sends changed values at a configured check interval, with thresholds for exposure and gain.

Newline-delimited communication is used to identify complete commands and responses.

The expanded Python server was tested independently using Netcat.

Both single-image acquisition and repeated acquisition while streaming were verified, including image saving, metadata retrieval, and restoration of the previous streaming state.

**Result:** A functional Python TCP camera-control server with independently tested acquisition and parameter-control capabilities.

### 4.1 Refactoring TCP Communication and Monitoring Actual Settings (26 October 2026)

The Python camera server was refactored to use a small `TCPConnection` class rather than direct socket writes from multiple functions. The class manages the accepted socket and a thread lock; it does not create a second server or TCP connection. All outgoing messages use a common sending method. The lock prevents overlapping writes from the main command loop and metadata worker, but does not guarantee that unsolicited notifications will be matched correctly by StreamDevice during command-response transactions.

Picamera2's `post_callback` reads `ExposureTime` and `AnalogueGain` from completed-frame metadata while streaming. A lightweight worker checks the latest stored values and sends `ACTUAL_EXPOSURE:<value>` and `ACTUAL_GAIN:<value>` notifications when changes exceed the configured thresholds. These values are camera-reported applied settings, not independent hardware-register measurements.

The requested-value TCP queries were renamed to `EXPOSURE_RB?` and `GAIN_RB?`. The corresponding EPICS records are `CAM:ExposureRB` and `CAM:GainRB`; `CAM:GetExposure` and `CAM:GetGain` now report actual values using input-only StreamDevice protocols and I/O Intr. This behavior was tested through Phoebus.

**Result:** Requested and camera-reported exposure/gain values are available separately, with change-driven actual-value monitoring through the existing IOC.

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

### 10. Automating Image Acquisition with PyEpics — Historical Workflow

The initial `automation/exposure_sweep.py` used PyEpics to acquire images at a fixed list of exposure times, wait for requested-setting readbacks and matching JPEG/JSON paths, and write a CSV measurement log. A five-point exposure sweep was successfully tested. This was the first automation milestone and established the acquisition-completion approach used by the later scan controller.

**Historical implementation:** `exposure_sweep.py` has been renamed and developed into `automation/camera_scan.py`. The original script is no longer an active repository file; Git history preserves the earlier version. Its former requested-setting readback `CAM:GetExposure` is now `CAM:ExposureRB`.

The current scan controller is described in Section 13 below.

### 11. Initial Exposure Verification and JPEG Analysis — Historical Results

The earlier `characterization/check_exposure.py` compared requested exposure times against values in the matching JSON metadata. `characterization/analyze_exposure_response.py` calculated grayscale JPEG mean, minimum, maximum and standard deviation and generated an exposure-response plot. These scripts were retired on 27 October 2026 and are recoverable from Git history; they are **not part of the current repository**.

An initial five-point sweep requested 5, 10, 20, 40 and 80 ms. Frame metadata reported 4,990, 9,999, 19,999, 39,999 and 79,999 µs, respectively; the largest difference was 10 µs (0.2%) at the shortest setting. In a later analyzed dataset, mean grayscale intensity increased from 3.69 at 4.99 ms to 42.11 at 80 ms.

These results concern **processed JPEG images** under non-fully-controlled illumination, not intrinsic sensor linearity or noise. More rigorous characterization will be designed separately when that phase begins.

### 12. Phoebus Camera Control and Image Display

A Phoebus Display Builder screen provides camera operations, exposure and gain controls, automatic-exposure selection, status readbacks, and the latest JPEG and metadata paths using the existing IOC PVs.

For image display, the separate Python PVAccess publisher makes `CAM:Image` available without adding an image waveform to `camera.db` or changing `stream_camera.proto`. The publisher uses the latest saved image path to detect new acquisitions and publishes a resized RGB array. The Phoebus Image widget has been tested with `pva://CAM:Image`, width and height set to 100, `TYPE_RGB1`, and unsigned data enabled.

The camera database includes `EGU = "us"` for exposure setpoint and readback records and `PINI = "YES"` for the requested-setting exposure, gain, and automatic-exposure readbacks. Actual exposure and gain instead use I/O Intr notifications from the metadata worker. Startup processing requests values from the Python server when communication is available; it does not automatically synchronize the corresponding setter PVs or guarantee recovery after reconnection.

**Result:** Camera operation and automatic updates of acquired RGB images have been demonstrated in Phoebus. The publisher remains an independent process that must be running for image display to update.

### 13. EPICS-Controlled Camera Scanning (27 October 2026)

The active `automation/camera_scan.py` is a sequential PyEpics scan controller. It uses `epics.PV()` objects and a simple polling loop rather than application-created threads or callbacks. `CAM:ScanEnable` selects scan mode; `CAM:StartScan` requests a scan; and `CAM:StopScan` is checked during the workflow. The controller disables automatic exposure, reads scan settings, sets exposure or gain using dedicated scan setter PVs, acquires JPEG/JSON pairs, calculates mean grayscale JPEG intensity, publishes scalar progress and waveform results, and saves CSV logs under `data/scan/`.

Exposure and gain have separate start/end parameter PVs because they use different units and numeric types. During scan mode, EPICS `SDIS`/`DISV` interlocks prevent normal exposure and gain setter *processing*, while allowing `CAM:ScanSetExposure` and `CAM:ScanSetGain`. The `SDIS` links deliberately omit `CP`: including it caused unwanted processing of zero-valued setters during IOC initialization. `CAM:SetAutoExposure` is not interlocked; the scan program disables AE and checks its readback.

For each completed point, the X-axis value comes from the matching captured frame's metadata, and the Y-axis value is the mean intensity of its saved JPEG. The IOC stores the growing scan arrays in `waveform` records (`FTVL=DOUBLE`, `NELM=100`), with `NORD` identifying the number of valid values. In Phoebus, explicit `pva://` X and Y PVs eliminated an unwanted `(0, 0)` point observed with Channel Access waveform display.

**Verified on 27 October:** Exposure scan execution, saved-image acquisition, intensity calculation, waveform publication, database interlocks and a Phoebus XY plot. Gain scanning and additional control tests were completed on 28 October (Section 14).

### 13.1 Scan verification details and remaining work

The scan database uses separate scan-specific exposure and gain setters, a scan enable record, start/stop requests, separate exposure/gain range records, a point count, status/progress records, and waveform arrays for exposure, gain and mean intensity. The output waveforms are soft IOC records; the PyEpics scan program publishes data without adding new StreamDevice commands.

During testing, the IOC initially attempted to send zero-valued exposure and gain settings at startup. The setters had `PINI=NO` and `SCAN=Passive`; removing `CP` from the `SDIS` links eliminated the unintended processing in the observed test. The database-level interlocks were subsequently tested through Phoebus. These interlocks suppress record processing, not all writes to a record's `VAL` field, and do not provide exclusive scan ownership.

A test write of three waveform elements resulted in `NORD=3` for both X and Y arrays, while ordinary `caget` displayed the entire 100-element capacity with trailing zeros. `pvget` returned only the valid values. Using `pva://CAM:ScanExposure` and `pva://CAM:ScanIntensity` in the Phoebus XY Plot removed the unwanted point at `(0, 0)`. Some Phoebus display slowness was also observed, but its cause has not been established.

The current saved-image scan requires access to the JPEG and JSON files stored on the Raspberry Pi. The earlier standalone characterization scripts and the `data/exposure_sweeps/` directory were retired during repository cleanup; the old analysis results above remain historical evidence, not a description of active scripts. Generated scan CSV files are now stored under `data/scan/` and excluded from Git.

**Follow-up:** The scan behavior was tested further on 28 October (Section 14). Broader disconnection recovery and Phoebus performance characterization remain open.

### 14. Scan Synchronization, Gain Scanning and Phoebus Displays (28 October 2026)

Exposure and gain scans were tested through the current sequential `automation/camera_scan.py` controller. Both scan types produced saved JPEG/JSON pairs, mean-intensity results, CSV logs, and growing waveform arrays for Phoebus XY plots. Stop Scan interrupted an active scan, and repeated scan operation was also tested. The Stop Scan command PV is not automatically reset after interruption; this behavior was deliberately left unchanged.

#### 14.1 Requested versus camera-applied settings

Early scan results showed that the first acquired frame could retain the setting from a preceding operation. A requested-setting readback (`CAM:ExposureRB` or `CAM:GainRB`) confirms the value stored by the Python camera server but does not prove that the camera has applied it to a completed frame. The scan controller was updated to wait for `CAM:GetExposure` or `CAM:GetGain` to approach the requested setting before acquisition. Provisional tolerances of 100 microseconds for exposure and 0.05 for analogue gain were used during testing. The saved image's matching JSON metadata remains the source of the actual X-axis value in the scan results.

An initial test timed out waiting for `CAM:GetExposure` to reach 50000 microseconds. Investigation showed that `CAM:ExposureRB` reported 50000, but `CAM:GetExposure` retained an older value and `CAM:GetStatus` was `IDLE`. The actual-value PVs depend on frame metadata and do not refresh without streaming frames. The controller therefore starts streaming when necessary and waits for the IOC status to report `STREAMING` before proceeding with setting verification and acquisition.

#### 14.2 Observed shared-TCP message mismatches

When scans began from `IDLE`, StreamDevice sometimes received `STATUS:IDLE` or `STATUS:STREAMING` where a setter expected `OK`, or where a requested-value readback expected a number. Tests found that the errors occurred during the transition into streaming, not during the checked steady-streaming scan operations. Waiting for `CAM:GetStatus` to report `STREAMING` before continuing resolved the observed errors in subsequent tests. No additional TCP connection or change to `stream_camera.proto` was introduced. This is a tested synchronization improvement, not proof that all shared-port notification ordering issues are resolved.

#### 14.3 Phoebus scan interface

Three Phoebus `.bob` displays were added to the repository under `phoebus/`:

- `epics_Camera_vision_main.bob` — main camera-control display.
- `epics_Camera_vision_scan_exposure.bob` — exposure-scan controls and plot.
- `epics_Camera_vision_scan_gain.bob` — gain-scan controls and plot.

The main display provides separate actions for exposure and gain scans, selecting the corresponding scan type and opening the relevant display. The XY plots use `pva://CAM:ScanExposure` or `pva://CAM:ScanGain` for X and `pva://CAM:ScanIntensity` for Y. The three display files were committed to GitHub and synchronized with the Raspberry Pi repository.

**Result:** Exposure and gain scanning, frame-setting verification, cooperative stopping, repeated scan operation, and the separate Phoebus scan displays were tested successfully. Further work may investigate resilience under communication failures and the previously observed Phoebus responsiveness issue.

### Possible Future Extensions

The following are exploratory options rather than scheduled implementation work:

- Perform in-memory image acquisition and intensity analysis without saving every frame.
- Explore continuous image streaming through EPICS instead of displaying only the latest saved image.
- Extend image processing and analysis beyond image-wide mean grayscale intensity.
- Improve communication recovery and synchronization across IOC or camera-server disconnects.
