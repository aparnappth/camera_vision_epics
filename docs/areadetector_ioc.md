# areaDetector Camera IOC

This document describes the implementation and verification of the areaDetector-based image acquisition path in the camera project. It explains the IOC configuration, standard database templates, Python camera client, custom RGB analysis plugin, vision database, and Phoebus display. The implementation was tested on a Raspberry Pi Zero 2 W with a Sony IMX219 camera. The guide retains the original single-frame experiment and documents its subsequent extension to continuous acquisition and LED recognition.

The installation of EPICS Base and the support modules is described separately in [EPICS Environment Setup](epics_setup.md). The existing TCP/StreamDevice implementation remains independent; see [StreamDevice Camera IOC](streamdevice_ioc.md).

## 1. Objective and Scope

The existing camera system acquires JPEG images through a Python TCP server and StreamDevice. Its LED-monitoring workflow requests an acquisition approximately every three seconds, which delays detection of changes. The areaDetector experiment investigates an alternative in-memory image path, without developing a custom C++ camera driver.

**Verified scope:** The original single-frame test transferred an RGB image through PyEpics, `NDDriverStdArrays`, and `NDPluginStdArrays` for Phoebus display. The subsequent continuous acquisition test transferred successive frames and supported parallel image display and custom `NDPluginRGB` analysis. RGB channel means, HSV colour counts, EPICS LED classification, alarms, and Phoebus monitoring were verified during repeated LED-state tests.

## 2. System Architecture

The current areaDetector workflow uses a Python camera client and two parallel NDArray plugins. Image visualization and RGB analysis receive the same upstream NDArray stream independently.

```text
Sony IMX219 CSI camera
         |
         v
Picamera2 / libcamera
         |
         | RGB frame (320 x 240 x 3)
         v
acquisition/tests/test_areadetector_continuous.py
         |
         | PyEpics / Channel Access: AD:Input:ArrayIn
         v
NDDriverStdArrays (STDARRAYS)
         |
         | UInt8, RGB1 NDArray
         +-----------------------------+
         |                             |
         v                             v
NDPluginStdArrays (IMAGE1)      NDPluginRGB (RGB1)
         |                             |
         |                        RGB means and
         |                        HSV segmentation
         |                             |
         v                             v
AD:Image1:ArrayData        AD:RGB1:ColorCounts_RBV
         |                     [Red, Yellow, Green]
         |                             |
         |                             v
         |                          vision.db
         |                  subArray / calc / mbbi
         |                             |
         +--------------+--------------+
                        |
                        v
                  Phoebus display
```

The original single-frame experiment used `acquisition/tests/test_areadetector_image.py` with the same `STDARRAYS -> IMAGE1 -> Phoebus` path, but captured only one image per run. That milestone is retained in Sections 7–12; Sections 13–17 describe the continuous extension.

The camera client and IOC are separate processes on the Pi. The IOC does **not** control the IMX219 directly: Python acquires frames using Picamera2, and `NDDriverStdArrays` receives pixel arrays through an EPICS waveform. No intermediate JPEG is required for this path.

`STDARRAYS`, `IMAGE1`, and `RGB1` are user-selected **asyn port identifiers**, not TCP ports. `AD:Input:`, `AD:Image1:`, and `AD:RGB1:` are PV prefixes created by database macros.

## 3. Tested Environment and Repository Layout

| Component | Tested version / configuration |
|---|---|
| Hardware | Raspberry Pi Zero 2 W; Sony IMX219 CSI camera |
| OS | 32-bit Raspberry Pi OS 13 (Trixie), `armv7l` |
| EPICS host architecture | `linux-arm` |
| EPICS Base | R7.0.10 |
| asyn | R4-46 |
| ADCore | R3-14 (reported at runtime as 3.14.0) |
| NDDriverStdArrays | R1-3 (reported at runtime as 1.3.0) |
| busy | R1-7-4 |
| libcamera | 0.7.2 |
| Python | Picamera2, NumPy, PyEpics in the project's environment |

The support modules are installed outside the project repository under `~/projects/epics/support/modules/`. The project stores its own IOC source and a copy of the relevant upstream database templates:

```text

camera_vision_epics/

├── acquisition/tests/test_areadetector_image.py

├── acquisition/tests/test_areadetector_continuous.py

├── epics/areadetector_camera/

│   └── areadetector_camera_ioc/

│       ├── configure/RELEASE

│       ├── areadetector_cameraApp/

│       │   ├── src/Makefile

│       │   ├── src/NDPluginRGB.cpp

│       │   ├── src/NDPluginRGB.h

│       │   ├── src/NDPluginRGB.dbd

│       │   └── Db/

│       │       ├── Makefile

│       │       ├── ADBase.template

│       │       ├── NDArrayBase.template

│       │       ├── NDDriverStdArrays.template

│       │       ├── NDPluginBase.template

│       │       ├── NDStdArrays.template

│       │       ├── NDPluginRGB.template

│       │       └── vision.db

│       └── iocBoot/iocareadetector_camera/st.cmd

└── phoebus/epics_Camera_vision_areadetector.bob

```

Generated `bin/`, `db/`, `dbd/`, `lib/`, and `O.*` directories are excluded from Git by the IOC's `.gitignore`. The support-module sources and compiled libraries are not vendored into this repository.

## 4. Create the Separate IOC Application

From the camera project root, the application was created using the standard EPICS tools:

```bash

mkdir -p epics/areadetector_camera/areadetector_camera_ioc

cd epics/areadetector_camera/areadetector_camera_ioc

makeBaseApp.pl -t ioc areadetector_camera

makeBaseApp.pl -i -t ioc areadetector_camera

```

When prompted for the application name, enter `areadetector_camera`. This generates the usual EPICS `configure/`, application source, and `iocBoot/` structure. The areaDetector IOC is deliberately separate from the working StreamDevice camera IOC so that both implementations can be tested independently.

## 5. Configure IOC Dependencies and Build

The IOC's `configure/RELEASE` must point to the already built support modules. For the tested installation, the relevant entries are:

```makefile

SUPPORT=/home/aparna/projects/epics/support/modules

EPICS_BASE=/home/aparna/projects/epics/base

ASYN=$(SUPPORT)/asyn

ADCORE=$(SUPPORT)/ADCore

NDDRIVERSTDARRAYS=$(SUPPORT)/NDDriverStdArrays

BUSY=$(SUPPORT)/busy

```

Adjust these absolute paths on another machine. The common support-module locations are maintained separately in `~/projects/epics/support/modules/RELEASE.local`, as explained in [EPICS Environment Setup](epics_setup.md).

The application `areadetector_cameraApp/src/Makefile` includes the standard IOC entry point and registration source. Its additional DBD inputs are:

```makefile

areadetector_camera_DBD += base.dbd

areadetector_camera_DBD += asyn.dbd

areadetector_camera_DBD += ADSupport.dbd

areadetector_camera_DBD += NDPluginSupport.dbd

areadetector_camera_DBD += NDDriverStdArraysSupport.dbd

areadetector_camera_DBD += busyRecord.dbd

areadetector_camera_DBD += busySupport.dbd

```

`busyRecord.dbd` defines the `busy` record type. **`busySupport.dbd` is also necessary**: it registers the `asynInt32` device support used by the `PreAllocBuffers` records in ADCore's standard templates. Adding only `busyRecord.dbd` produced an invalid-device-support error at IOC startup.

The corresponding library order is:

```makefile

areadetector_camera_LIBS += NDDriverStdArrays

areadetector_camera_LIBS += NDPlugin

areadetector_camera_LIBS += ADBase

areadetector_camera_LIBS += busy

areadetector_camera_LIBS += asyn

areadetector_camera_LIBS += $(EPICS_BASE_IOC_LIBS)

```

The Makefile also retains the generated `areadetector_camera_registerRecordDeviceDriver.cpp` and `areadetector_cameraMain.cpp` entries. Build the IOC after the external modules have been built:

```bash

make -j1

ls -l bin/linux-arm/areadetector_camera

```

The single-job build limits memory pressure on the Pi Zero 2 W. The executable and the `NDDriverStdArraysRegister` / `NDStdArraysRegister` registrations were verified during development. The later custom plugin adds `NDPluginRGB.cpp` to the IOC sources and `NDPluginRGB.dbd` to its DBD inputs; `NDPluginRGB.dbd` contains `registrar(NDRGBRegister)`. Verify the generated IOC DBD contains that registrar after building.

## 6. Standard Database Templates

The project uses the standard upstream templates rather than manually recreating areaDetector records. Copies of five templates were placed in `areadetector_cameraApp/Db/`:

```text

NDDriverStdArrays.template -> ADBase.template -> NDArrayBase.template

NDStdArrays.template       -> NDPluginBase.template -> NDArrayBase.template

```

The original single-frame experiment loaded these two top-level templates. Their included templates supply common detector, NDArray, and plugin records. Do not load the included templates independently with the same PV prefixes: that would duplicate records.

The files were copied from the installed **ADCore R3-14** and **NDDriverStdArrays R1-3** sources and registered in `areadetector_cameraApp/Db/Makefile`:

```makefile

DB += ADBase.template

DB += NDArrayBase.template

DB += NDDriverStdArrays.template

DB += NDPluginBase.template

DB += NDStdArrays.template

```

After `make -j1`, these are installed into the IOC's generated `db/` directory. The copies are version-specific; if upgrading the upstream modules, review their templates and macros before replacing them. Preserve upstream attribution and licensing.

The key waveforms are `AD:Input:ArrayIn` (input, asyn `NDSA_ARRAY_DATA`) and `AD:Image1:ArrayData` (output, asyn `STD_ARRAY_DATA`). Their database macros use `TYPE=Int8` because the installed asyn device support is called `asynInt8ArrayOut` / `asynInt8ArrayIn`; `asynUInt8ArrayOut` / `asynUInt8ArrayIn` are not available. The NDArray itself can still be configured as **UInt8**. The client preserves byte patterns when reinterpreting NumPy `uint8` as `int8`.

## 7. IOC Startup Configuration

The `st.cmd` file is located at `iocBoot/iocareadetector_camera/st.cmd`. The following is the **original single-frame configuration**; see Section 13 for the current additions:

```text

#!../../bin/linux-arm/areadetector_camera

# Set before Channel Access is initialized.

epicsEnvSet("EPICS_CA_MAX_ARRAY_BYTES", "1000000")

dbLoadDatabase("../../dbd/areadetector_camera.dbd")

areadetector_camera_registerRecordDeviceDriver(pdbbase)

NDDriverStdArraysConfig("STDARRAYS", 10, 20000000, 0, 0)

NDStdArraysConfigure("IMAGE1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)

epicsEnvSet("EPICS_DB_INCLUDE_PATH", "../../db")

dbLoadRecords("../../db/NDDriverStdArrays.template", "P=AD:,R=Input:,PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")

dbLoadRecords("../../db/NDStdArrays.template", "P=AD:,R=Image1:,PORT=IMAGE1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")

iocInit()

```

The two `Config` commands create the asyn driver and plugin. The plugin's upstream NDArray port is `STDARRAYS`. `EPICS_DB_INCLUDE_PATH` allows the database parser to resolve nested template includes. `NDARRAY_PORT=STDARRAYS` is also required by the output plugin template; omitting it caused an undefined-macro error and an attempted connection to an empty port name.

`NELEMENTS=230400` sets each waveform's **maximum element capacity**, not the active image dimensions. For a 320 × 240 RGB frame, `320 × 240 × 3 = 230400` bytes. `EPICS_CA_MAX_ARRAY_BYTES=1000000` provides sufficient Channel Access message capacity; the Python client must also set this variable before initializing PyEpics. Larger images require reviewing both limits and memory use.

Run the IOC from its boot directory:

```bash

cd epics/areadetector_camera/areadetector_camera_ioc/iocBoot/iocareadetector_camera

../../bin/linux-arm/areadetector_camera st.cmd

```

The IOC should start without database, device-support, or asyn connection errors. `iocRun: All initialization complete` **alone** does not prove the templates loaded: inspect the earlier startup messages. At the IOC shell, `dbl` lists loaded PVs and `asynReport(1, "STDARRAYS")` reports driver state.

## 8. Python Configuration and Single-Frame Acquisition

The test program is `acquisition/tests/test_areadetector_image.py`. It is run separately from the IOC, from the project root, in the Python environment containing Picamera2, NumPy, and PyEpics.

The program configures areaDetector through PyEpics **before** opening the camera. This avoids hard-coding experiment-specific RGB dimensions and acquisition settings into the copied upstream database templates. Its required settings are:

| PV | Value | Reason |
|---|---|---|
| `AD:Input:SizeX` | `320` | Width |
| `AD:Input:SizeY` | `240` | Height |
| `AD:Input:NDimensions` | `3` | RGB1 uses three dimensions |
| `AD:Input:Dimensions` | `[3, 320, 240]` | Channels, width, height |
| `AD:Input:DataType` | `1` (UInt8) | Unsigned pixel values |
| `AD:Input:ColorMode` | `2` (RGB1) | Interleaved colour components |
| `AD:Input:CallbackMode` | `0` (On update) | Generate callback on array update |
| `AD:Input:AppendMode` | `0` | Full frame per waveform write |
| `AD:Input:ImageMode` | `2` (Continuous) | Permit successive test frames |
| `AD:Input:ArrayCallbacks` | `1` | Enable NDArray callbacks |
| `AD:Image1:EnableCallbacks` | `1` | Enable plugin input |
| `AD:Input:Acquire` | `1` | Allow driver to accept incoming arrays |

The code writes `Dimensions` as a NumPy `int32` array. It verifies critical scalar readbacks, but does not rely on `Dimensions_RBV`: this driver version stores the written dimension array internally without publishing an equivalent array readback. `asynReport(1, "STDARRAYS")` confirmed `nDimensions: 3` and `array dimensions: [3 320 240]`.

`Acquire` is a long-running acquisition command. During testing, `caput(..., wait=True)` timed out even though `Acquire_RBV` showed `Acquiring`. The working program issues the start command with `wait=False` and checks the acquisition state separately. The readback should be checked with a bounded wait, not assumed to update instantaneously.

The Picamera2 portion follows the project's earlier `test_camera_acquisition.py`: it opens `Picamera2(0)`, applies a 180-degree transform (`Transform(hflip=1, vflip=1)`), configures a 320 × 240 `RGB888` still stream, enables automatic exposure (`AeEnable=True`), waits briefly for exposure adjustment, and uses `capture_request()` to retrieve the frame and metadata from the same request. It extracts the array with `request.make_array("main")` rather than saving a JPEG. The frame is validated as shape `(240, 320, 3)` and `uint8`.

The tested implementation reverses the three colour channels before transmission to obtain the desired Phoebus colour appearance:

```python

frame_rgb = np.ascontiguousarray(frame[:, :, ::-1])

pixels_int8 = frame_rgb.reshape(-1).view(np.int8)

```

This conversion is specific to the tested Picamera2 format and display interpretation; verify colour order with known coloured objects if camera formats or widget settings change. Python writes the flattened array to `AD:Input:ArrayIn` and verifies an increase in `AD:Image1:ArrayCounter_RBV` and an output waveform `.NORD` of 230400. A successful `caput` alone does **not** prove NDArray delivery.

The program releases the captured request, stops streaming, and closes the camera in a `finally` block. Stop the existing `picamera2_server.py` (or any VLC camera-stream source) before running the test: two separate processes should not attempt to control the IMX219 simultaneously.

Run from the project root:

```bash

source .venv/bin/activate

export EPICS_CA_MAX_ARRAY_BYTES=1000000

python acquisition/tests/test_areadetector_image.py

```

The `.venv` path is the tested project layout; adjust it if the Python environment is elsewhere. The IOC must already be running. The Python program is a **single-frame test** even though it sets the driver to Continuous mode.

## 9. Phoebus Image Display

The Windows Phoebus display is `phoebus/epics_Camera_vision_areadetector.bob`. It is separate from the existing StreamDevice display. The Image widget is configured to read the areaDetector output waveform over **Channel Access**, not the earlier `CAM:Image` PVAccess publisher.

| Image widget property | Tested configuration |
|---|---|
| PV Name | `ca://AD:Image1:ArrayData` |
| Data Width | `320` |
| Data Height | `240` |
| Color Mode | `TYPE_RGB1` |
| Unsigned Data | Enabled |
| Auto-scale | Disabled |
| Minimum / Maximum | `0` / `255` |

An early display appeared as coloured horizontal noise when its dimensions were still configured for the previous 100 × 100 image. Setting 320 × 240 resolved the layout. An apparent colour mismatch was also affected by the driver having stopped after one image in **Single** mode: the widget was still showing the previous frame, so a changed Python colour conversion initially seemed ineffective. After switching to Continuous mode and verifying that counters increased, the updated image was displayed and camera focus was adjusted using a separate VLC view.

The Phoebus client must be able to reach the Pi's Channel Access server and receive an array of this size. Confirm the Windows Channel Access configuration and array-byte limit if the PV connects but the full image cannot be read.

## 10. Verification Procedure and Results

1. Start the areaDetector IOC and confirm no database-load or asyn connection errors.

2. Ensure the existing camera server and other Picamera2 clients are stopped.

3. Run `acquisition/tests/test_areadetector_image.py` from the project environment.

4. Confirm that the output plugin's array counter increases and `.NORD` equals 230400.

5. Open the Phoebus areaDetector display and confirm a recognizable RGB image with the expected orientation and colours.

Useful checks from a separate terminal:

```bash

caget AD:Input:Acquire_RBV

caget AD:Input:ImageMode_RBV

caget AD:Input:ArrayCounter_RBV

caget AD:Image1:ArrayCounter_RBV

caget AD:Image1:ArrayData.NORD

caget AD:Image1:EnableCallbacks_RBV

caget AD:Image1:NDArrayPort_RBV

```

**Observed successful test:** Picamera2 produced a `(240, 320, 3)` `uint8` frame; Python transferred 230400 elements; the plugin array counter increased from 0 to 1; and `AD:Image1:ArrayData.NORD` reported 230400. The image was displayed in Phoebus. Actual exposure and gain were reported from capture metadata and varied with lighting. No sustained frame-rate or latency result has been established.

## 11. Troubleshooting Observed During Development

| Symptom | Cause established during testing | Resolution |
|---|---|---|
| `Record type 'busy' ... not found` | IOC lacked the busy record definition | Build busy module and add `busyRecord.dbd` |
| `PreAllocBuffers.DTYP ... asynInt32 ... no such device support for 'busy'` | `busyRecord.dbd` alone does not register the asyn busy support | Also add `busySupport.dbd` and link `busy` |
| `asynUInt8ArrayOut/In` not found | asyn device support uses the `Int8` naming | Load templates with `TYPE=Int8,FTVL=CHAR`; use NDArray `UInt8` separately |
| `NDARRAY_PORT` undefined / array port empty | Required output template macro missing | Add `NDARRAY_PORT=STDARRAYS` to output `dbLoadRecords` |
| `Dimensions_RBV` remains zero | Driver stores dimensions internally without an equivalent readback update | Inspect `asynReport(1, "STDARRAYS")` |
| `caput` succeeds, but counters remain zero | Driver returns success without accepting image when `Acquire=0` | Start acquisition before sending frame |
| First frame succeeds, next frame ignored | Driver was in Single image mode and returned to Done | Select Continuous mode and start acquisition |
| `Acquire` put-completion timeout | `wait=True` waited for completion of an ongoing acquisition | Issue start with `wait=False`; verify acquisition state |
| Image appears as horizontal colour noise | Phoebus image dimensions did not match transmitted data | Set width 320, height 240, RGB1 |
| Changed colour conversion seems ineffective | Output had not updated because acquisition had stopped | Check array counters before comparing images |

When troubleshooting, distinguish the EPICS waveform write from actual driver processing. `AD:Input:ArrayIn.NORD=230400` and `NO_ALARM` show the input waveform contains the expected number of elements, but do not establish that an NDArray callback was generated. Check both input and plugin counters.

## 12. Original Single-Frame Milestone and Limitations

Sections 1–11 document the original single-frame proof of concept and its historical verification. That milestone was subsequently extended to repeated in-memory Picamera2 acquisition and LED recognition, described below. The Python client still acquires the camera frames and transfers them through a Channel Access waveform; there is no direct libcamera areaDetector driver in this project.

## 13. Continuous Acquisition and Current IOC Configuration

The continuous client is `acquisition/tests/test_areadetector_continuous.py`. It repeatedly captures 320 × 240 RGB frames with Picamera2 and writes the flattened pixel bytes to `AD:Input:ArrayIn`. It uses the same basic RGB1 arrangement as the original test: UInt8 NDArray data and dimensions `[3, 320, 240]`. The camera must not be simultaneously opened by the StreamDevice Python camera server, VLC, or another Picamera2 process.

The current `st.cmd` adds the following commands **before** `iocInit()`:

```text

NDRGBConfigure("RGB1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)

dbLoadRecords("../../db/NDPluginRGB.template", "P=AD:,R=RGB1:,PORT=RGB1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1")

dbLoadRecords("../../db/vision.db")

```

The original `NDDriverStdArraysConfig("STDARRAYS", ...)`, `NDStdArraysConfigure("IMAGE1", ...)`, and corresponding standard template loads remain enabled. `NDROIConfigure` and `NDStatsConfigure`, along with their template loads, are retained as commented-out experiments. Thus `IMAGE1` and `RGB1` receive arrays in parallel from `STDARRAYS`; `RGB1` is not downstream of the ROI or statistics plugins.

`areadetector_cameraApp/Db/Makefile` installs `NDPluginRGB.template` and `vision.db`. `areadetector_cameraApp/src/Makefile` compiles `NDPluginRGB.cpp` and incorporates `NDPluginRGB.dbd` into the generated IOC DBD. The existing areaDetector, asyn, and EPICS Base libraries remain dependencies.

The startup script sets `EPICS_DB_INCLUDE_PATH` to `../../db` and `EPICS_CA_MAX_ARRAY_BYTES` to `1000000`. The Python process must also use a sufficiently large Channel Access array-byte limit before creating its CA context. Set it in the client environment as needed:

```bash

export EPICS_CA_MAX_ARRAY_BYTES=1000000

```

The plugin's `EnableCallbacks` must be enabled to process arrays; a configured plugin does not necessarily start with callbacks enabled. Verify the input driver is acquiring and array callbacks are enabled before starting the continuous client.

## 14. Custom NDPluginRGB: Implementation and Measurements

`NDPluginRGB` is a measurement-only C++ plugin derived from `NDPluginDriver`. It is intentionally general-purpose: it reports RGB image statistics and HSV colour counts, while application-specific LED interpretation remains in `vision.db`.

The class implements `processCallbacks(NDArray *pArray)` and calls `NDPluginDriver::beginProcessCallbacks(pArray)` for standard plugin bookkeeping. It validates the incoming array as a three-dimensional `NDUInt8` RGB1 image with three interleaved colour components, checks the dimensions and element count, and rejects unsupported input. For valid frames it reads pixels as `R, G, B, R, G, B, ...`, computes per-channel means, converts each pixel to HSV, and counts colour-matched pixels. It updates scalar asyn parameters and emits one three-element `asynInt32Array` callback per processed frame.

**NDArray ownership:** The plugin does not create an output NDArray, call `endProcessCallbacks()` on the input, or manually release the incoming array. An early implementation forwarded the input to `endProcessCallbacks()` and produced `NDArrayPool:release ERROR, reference count < 0` and a suspended plugin thread. Removing that forwarding call resolved the observed error in subsequent acquisition tests. This ownership decision must be reconsidered if the plugin is later extended to publish processed NDArrays.

The colour thresholds were adapted from the earlier Pillow-based JPEG classifier, using HSV components on an approximately 0–255 scale:

| Detected colour | Hue condition | Additional condition |
|---|---|---|
| Red | `H < 15` or `H > 240` | `S > 100` and `V > 100` |
| Yellow | `25 <= H <= 50` | `S > 100` and `V > 100` |
| Green | `55 <= H <= 115` | `S > 100` and `V > 100` |

The C++ conversion truncates scaled HSV components to integers. Its agreement with Pillow at threshold boundaries has not been exhaustively verified, and raw RGB frames can differ from previously analyzed JPEGs because of compression and acquisition settings. The thresholds are currently implementation constants, not general calibration parameters.

| PV | Meaning |
|---|---|
| `AD:RGB1:ValidFrame_RBV` | Whether the most recent processed frame met the input-format checks |
| `AD:RGB1:ValidCount_RBV` / `InvalidCount_RBV` | Counts of accepted/rejected frames |
| `AD:RGB1:RedMean_RBV`, `GreenMean_RBV`, `BlueMean_RBV` | Full-image channel means, each in the 0–255 range for valid 8-bit input |
| `AD:RGB1:RedCount_RBV`, `YellowCount_RBV`, `GreenCount_RBV` | Individual HSV-segmented pixel counts |
| `AD:RGB1:ColoredCount_RBV` | Sum of the three colour counts |
| `AD:RGB1:ColorCounts_RBV` | Three-element waveform `[red, yellow, green]` calculated from one frame |

The waveform is implemented with an `asynInt32Array` callback and a `waveform` record with `FTVL=LONG`, `NELM=3`, and `SCAN="I/O Intr"`. `NORD=3` was verified. Unlike three sequential `caget` operations, one waveform read provides the three colour counts published together for one frame. It does not by itself make later, independently processed database records atomic.

## 15. vision.db: Database-Only LED Classification

The application-specific classification uses standard EPICS record types and does **not** require a separate C++ classification function. The verified `vision.db` contains three `subArray` records, diagnostic `calc` records, a numerical `LEDStatus` `calc`, and a human-readable `LEDState` `mbbi`.

Each `subArray` uses `DTYP="Soft Channel"`, `FTVL="LONG"`, `MALM=3`, `NELM=1`, and an `INP` link of `AD:RGB1:ColorCounts_RBV CP`. Their `INDX` values are 0, 1, and 2 for red, yellow, and green. The extracted element appears at the beginning of each subArray output buffer. The `calc` records use `CP` links to the extracted outputs and remain `SCAN="Passive"`; the waveform's update drives processing through the link chain.

| Record | Calculation or purpose |
|---|---|
| `AD:Vision:Red`, `Yellow`, `Green` | One-element colour-count extraction |
| `AD:Vision:Total` | `A+B+C`, with A=red, B=yellow, C=green |
| `AD:Vision:RedGreenRatio` | `A/MAX(B,1)`, with A=red, B=green |
| `AD:Vision:YellowFraction` | `B/MAX(A+B+C,1)`, with A=red, B=yellow, C=green |
| `AD:Vision:LEDStatus` | Numerical classification from red, yellow, green |
| `AD:Vision:LEDState` | Human-readable state mapping for Phoebus |

The classification rules, in order, match the earlier Python algorithm:

1. If the total is below 1000, return UNKNOWN (0).

2. If red/green exceeds 20 and yellow fraction is below 0.05, return FAULT (3).

3. Otherwise, if yellow fraction exceeds 0.10, return WARNING (2).

4. Otherwise, if red/green is below 0.2 and yellow fraction is below 0.02, return NORMAL (1).

5. Otherwise, return UNKNOWN (0).

`LEDStatus` is the authoritative numerical classification and carries the EPICS alarm thresholds. The current database uses `HIGH=1.5, HSV=MINOR` and `HIHI=2.5, HHSV=MAJOR`, so WARNING is MINOR, FAULT is MAJOR, and NORMAL/UNKNOWN are not assigned an alarm by these thresholds. `LEDState` maps values 0–3 to `UNKNOWN`, `NORMAL`, `WARNING`, and `FAULT` without duplicating alarm severity configuration. Phoebus widgets requiring alarm severity should use `LEDStatus` or explicitly verify alarm propagation; `LEDState` is primarily a readable state indication.

**Processing caveat:** The three `subArray` records and downstream calculations are independently CP-triggered. They can process more than once for a frame update and can transiently combine values from different frames. This was observed as occasional rapid UNKNOWN transitions near physical state changes. Functional tests were successful, but this architecture is not a formal same-frame guarantee for `LEDStatus`. A synchronized snapshot/processing mechanism is a future improvement if strict atomic classification becomes necessary.

## 16. Continuous Operation, Phoebus, and Verification

Start the IOC from its boot directory and check the startup log for database or asyn errors. With the camera free and the IOC running, enable the RGB plugin and launch the continuous client from the repository root:

```bash

caput AD:RGB1:EnableCallbacks 1

# In the project Python environment, from the repository root:

python acquisition/tests/test_areadetector_continuous.py

```

The continuous client configures the input driver and transfers successive frames. `IMAGE1` displays the camera image; `RGB1` analyzes each incoming frame. Do not run the StreamDevice camera server or another camera-consuming process concurrently.

Useful diagnostics:

```bash

caget AD:Input:Acquire_RBV

caget AD:RGB1:NDArrayPort_RBV

caget AD:RGB1:EnableCallbacks_RBV

caget AD:RGB1:ValidFrame_RBV

caget AD:RGB1:ValidCount_RBV

caget AD:RGB1:InvalidCount_RBV

caget AD:RGB1:RedMean_RBV

caget AD:RGB1:GreenMean_RBV

caget AD:RGB1:BlueMean_RBV

caget AD:RGB1:ColorCounts_RBV

caget AD:RGB1:ColorCounts_RBV.NORD

caget AD:Vision:Total

caget AD:Vision:RedGreenRatio

caget AD:Vision:YellowFraction

caget AD:Vision:LEDStatus

caget AD:Vision:LEDState

caget AD:Vision:LEDStatus.SEVR

```

The Windows display `phoebus/epics_Camera_vision_areadetector.bob` now combines the RGB image with LED monitoring. The image widget still uses `ca://AD:Image1:ArrayData` with width 320, height 240, RGB1, and unsigned 8-bit interpretation. The vision state and diagnostics use the `AD:Vision:` records; the numerical `LEDStatus` is the source for its configured alarm thresholds.

**Observed HSV waveform results** (order `[red, yellow, green]`):

| Physical state | Red | Yellow | Green | Expected LED status |
|---|---:|---:|---:|---|
| Green | 0 | 0 | 25680 | NORMAL |
| Yellow | 661 | 4865 | 4041 | WARNING |
| Red | 16033 | 528 | 0 | FAULT |
| Green again | 0 | 0 | 24580 | NORMAL |

All waveform reads reported `NORD=3`. In later repeated tests, the state sequence followed FAULT → NORMAL → WARNING → UNKNOWN/OFF at approximately 10-second intervals. A longer `camonitor AD:Vision:LEDState` log also showed a few near-simultaneous intermediate UNKNOWN transitions; therefore it is accurate to report successful functional recognition, not perfect atomic classification. The original full-image RGB mean measurements also changed in the expected direction for red, yellow, and green illumination.

**Alarm and stale-state limitations:** UNKNOWN/OFF is not necessarily a hardware fault; the current alarm thresholds treat it as no alarm. When acquisition stops, the last published state may remain visible; a timeout or freshness indication has not yet been implemented. No calibrated latency, sustained frame-rate, CPU utilization, or long-duration reliability benchmark has been established.

## 17. Additional Troubleshooting and Future Work

| Symptom | Investigation and outcome |
|---|---|
| `NDArrayPool:release ERROR, reference count < 0` and suspended `IMAGE1_Plugin_1` thread | The first custom plugin implementation called `endProcessCallbacks()` with the incoming NDArray. The measurement-only implementation was corrected to publish scalar/array measurements without forwarding or releasing that input; subsequent acquisition tests ran normally. |
| `AD:RGB1:ValidCount_RBV` remains zero | Check `AD:RGB1:EnableCallbacks_RBV`, the upstream `NDArrayPort_RBV`, driver acquisition state, and input array callbacks. |
| ROI/Stats template errors or missing `STATS1_TS` port | These were encountered during exploratory standard-plugin testing. The unused ROI/Stats startup lines are now commented out. |
| `ColorCounts_RBV.NORD` is not 3 | Verify `asynInt32Array` registration, waveform `NELM=3`, `FTVL=LONG`, `SCAN="I/O Intr"`, and that the plugin is receiving valid frames. |
| Sum of separately read colour PVs differs from `ColoredCount_RBV` | Separate client reads can sample different incoming frames. Use the combined waveform to inspect a frame-consistent count triplet. |
| Very brief intermediate UNKNOWN status | Multiple CP-triggered subArray/calc evaluations can occur near transitions; physical threshold ambiguity is also possible. Do not claim atomic downstream synchronization without further testing. |
| No new image in Phoebus | Check driver/plugin array counters, `IMAGE1` callback enable, image dimensions, Channel Access connectivity, and camera ownership. |

## 18. Related Documentation

- [EPICS Environment Setup](epics_setup.md) — installing EPICS Base, asyn, StreamDevice, ADCore, NDDriverStdArrays, and busy.

- [StreamDevice Camera IOC](streamdevice_ioc.md) — the existing TCP/StreamDevice camera-control path.

- [Implementation and Results](implementation_and_results.md) — project-wide verified functionality and limitations.

- [README](../README.md) — overall project overview and instructions.

## 19. References

- [EPICS Documentation](https\://docs.epics-controls.org/)

- [areaDetector ADCore](https\://github.com/areaDetector/ADCore)

- [NDDriverStdArrays](https\://github.com/areaDetector/NDDriverStdArrays)

- [EPICS busy module](https\://github.com/epics-modules/busy)

- [Picamera2 documentation](https\://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
