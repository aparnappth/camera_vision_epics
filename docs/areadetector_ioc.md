# areaDetector Camera IOC

This document describes the implementation and verification of the areaDetector-based image acquisition path in the camera project. It explains the IOC configuration, standard database templates, Python camera client, and Phoebus display. The implementation was tested on a Raspberry Pi Zero 2 W with a Sony IMX219 camera.

The installation of EPICS Base and the support modules is described separately in [EPICS Environment Setup](epics_setup.md). The existing TCP/StreamDevice implementation remains independent; see [StreamDevice Camera IOC](streamdevice_ioc.md).

## 1. Objective and Scope

The existing camera system acquires JPEG images through a Python TCP server and StreamDevice. Its LED-monitoring workflow requests an acquisition approximately every three seconds, which delays detection of changes. The areaDetector experiment investigates an alternative in-memory image path, without developing a custom C++ camera driver.

**Verified scope:** one RGB image can be captured directly from Picamera2, sent from Python over EPICS Channel Access to `NDDriverStdArrays`, converted to an NDArray, passed through `NDPluginStdArrays`, and displayed in Phoebus. The Python test configures the necessary IOC PVs automatically. The IOC can accept successive single-frame test runs when configured in continuous acquisition mode.

**Not yet verified:** sustained frame streaming, throughput, end-to-end latency, and whether this path improves LED-monitoring response time. areaDetector does not, by itself, eliminate Channel Access transport overhead.

## 2. System Architecture

```text
Sony IMX219 CSI camera
         |
         v
Picamera2 / libcamera
         |
         | RGB frame in NumPy memory (320 x 240 x 3)
         v
acquisition/tests/test_areadetector_image.py
         |
         | PyEpics / Channel Access: AD:Input:ArrayIn
         v
areaDetector IOC on Raspberry Pi
  NDDriverStdArrays, asyn port STDARRAYS
         |
         | NDArray callback, UInt8, RGB1
         v
  NDPluginStdArrays, asyn port IMAGE1
         |
         | Channel Access: AD:Image1:ArrayData
         v
Phoebus Image widget on Windows
```

The camera client and IOC are separate processes on the Pi. The IOC does **not** control the IMX219 directly: Python acquires frames using Picamera2, and `NDDriverStdArrays` receives the resulting pixel array as an EPICS waveform. No intermediate JPEG is needed for this test.

The input and plugin port names (`STDARRAYS`, `IMAGE1`) are user-selected **asyn port identifiers**, not TCP ports. The PV prefixes (`AD:Input:`, `AD:Image1:`) are separate names created by database macros.

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
├── epics/areadetector_camera/
│   └── areadetector_camera_ioc/
│       ├── configure/RELEASE
│       ├── areadetector_cameraApp/
│       │   ├── src/Makefile
│       │   └── Db/
│       │       ├── Makefile
│       │       ├── ADBase.template
│       │       ├── NDArrayBase.template
│       │       ├── NDDriverStdArrays.template
│       │       ├── NDPluginBase.template
│       │       └── NDStdArrays.template
│       └── iocBoot/iocareadetector_camera/st.cmd
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

The single-job build limits memory pressure on the Pi Zero 2 W. The executable and the `NDDriverStdArraysRegister` / `NDStdArraysRegister` registrations were verified during development.

## 6. Standard Database Templates

The project uses the standard upstream templates rather than manually recreating areaDetector records. Copies of five templates were placed in `areadetector_cameraApp/Db/`:

```text
NDDriverStdArrays.template -> ADBase.template -> NDArrayBase.template
NDStdArrays.template       -> NDPluginBase.template -> NDArrayBase.template
```

Only the two top-level templates are loaded for this experiment. Their included templates supply common detector, NDArray, and plugin records. Do not load the included templates independently with the same PV prefixes: that would duplicate records.

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

The tested `st.cmd` is located at `iocBoot/iocareadetector_camera/st.cmd`. Its relevant configuration is:

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

## 12. Current Limitations and Possible Extensions

The implementation has been verified for a single captured RGB frame, with the driver configured to accept successive tests. It is **not yet a continuously streaming camera system**. Python still initiates acquisition and transfers the frame through a Channel Access waveform; areaDetector adds an NDArray/plugin stage rather than a direct libcamera camera driver.

Possible extensions include repeated in-memory Picamera2 acquisition, measuring acquisition/transfer/display latency and CPU/memory use on the Pi Zero 2 W, experimenting with areaDetector ROI and statistics plugins, and integrating colour-based LED monitoring. These are investigation goals, not demonstrated performance improvements.

## 13. Related Documentation

- [EPICS Environment Setup](epics_setup.md) — installing EPICS Base, asyn, StreamDevice, ADCore, NDDriverStdArrays, and busy.
- [StreamDevice Camera IOC](streamdevice_ioc.md) — the existing TCP/StreamDevice camera-control path.
- [Implementation and Results](implementation_and_results.md) — project-wide verified functionality and limitations.
- [README](../README.md) — overall project overview and instructions.

## 14. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [areaDetector ADCore](https://github.com/areaDetector/ADCore)
- [NDDriverStdArrays](https://github.com/areaDetector/NDDriverStdArrays)
- [EPICS busy module](https://github.com/epics-modules/busy)
- [Picamera2 documentation](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
