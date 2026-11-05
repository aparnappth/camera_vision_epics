# NDPluginRGB — Custom areaDetector RGB Analysis Plugin

## 1. Purpose and scope

`NDPluginRGB` is a custom C++ areaDetector plugin developed for the Raspberry Pi Zero 2 W / Sony IMX219 camera project. It analyzes incoming RGB images **in memory** and publishes general-purpose colour measurements through EPICS. The application-specific interpretation of those measurements as LED states is deliberately implemented in `vision.db`, not in this plugin.

The plugin was developed after investigating `NDPluginROI`, `NDPluginStats`, and `NDPluginProcess`. ROI can crop or select image dimensions, and Stats can calculate statistics over its input, but the installed versions did not directly provide the required red/yellow/green HSV pixel segmentation. Using a custom plugin allowed a single pass over each RGB frame without a fixed spatial ROI, which is useful when the camera is positioned manually between experiments.

This is **not** a camera driver: Picamera2 acquires the frames, PyEpics sends them to `NDDriverStdArrays`, and `NDPluginRGB` receives the resulting NDArrays.

## 2. Processing architecture

```text
IMX219 → Picamera2 → Python/PyEpics → AD:Input:ArrayIn
                                           |
                                  NDDriverStdArrays
                                      STDARRAYS
                                           |
                          +----------------+----------------+
                          |                                 |
                    IMAGE1 plugin                      RGB1 plugin
                    image waveform                     NDPluginRGB
                          |                                 |
                        Phoebus                  validate RGB1 / UInt8
                                                     RGB means
                                                     RGB → HSV
                                                     colour counts
                                                          |
                                     +--------------------+------------------+
                                     |                                       |
                              diagnostic scalar PVs              ColorCounts_RBV
                                                                     [R, Y, G]
                                                                          |
                                                                       vision.db
                                                                          |
                                                               LEDStatus / LEDState
```

The plugin's upstream asyn port is `STDARRAYS`; the plugin's own asyn port is `RGB1`. `IMAGE1` and `RGB1` are parallel consumers of the same input stream.

## 3. Source files and integration

| File | Role |
|---|---|
| `areadetector_cameraApp/src/NDPluginRGB.h` | Class declaration, asyn parameter names, member indices and counters |
| `areadetector_cameraApp/src/NDPluginRGB.cpp` | Plugin constructor, frame processing, HSV conversion, IOC-shell configuration and registration |
| `areadetector_cameraApp/src/NDPluginRGB.dbd` | Registers `NDRGBRegister` with the IOC |
| `areadetector_cameraApp/src/Makefile` | Compiles and links the plugin source and includes its DBD |
| `areadetector_cameraApp/Db/NDPluginRGB.template` | EPICS records for plugin controls and measurements |
| `iocBoot/iocareadetector_camera/st.cmd` | Creates `RGB1` and loads its database records |

The relevant startup configuration is:

```text
NDRGBConfigure("RGB1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)
dbLoadRecords("../../db/NDPluginRGB.template", "P=AD:,R=RGB1:,PORT=RGB1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1")
```

Both commands appear before `iocInit()`. The plugin must also have callbacks enabled (`AD:RGB1:EnableCallbacks=1`) to process incoming images. Build the IOC from its root using `make -j1`; verify the generated DBD includes `registrar(NDRGBRegister)`.

## 4. Inheritance, configuration and asyn interfaces

`NDPluginRGB` derives from `NDPluginDriver` and overrides `processCallbacks(NDArray *pArray)`. Its constructor forwards the usual areaDetector plugin configuration parameters: port name, callback queue size, blocking-callback setting, upstream NDArray port/address, buffer and memory limits, thread priority, stack size and maximum thread count.

The implementation enables the `asynInt32`, `asynFloat64`, `asynInt32Array`, and `asynGenericPointer` interfaces and their interrupt masks. It registers named asyn parameters with `createParam()` and initializes scalar measurements. `connectToArrayPort()` connects to the upstream NDArray source. `NDRGBConfigure()` constructs the plugin and calls `start()`, while `NDRGBRegister` exposes the configuration command to the IOC shell.

The `asynGenericPointer` interface is used for receiving NDArrays. Scalar integer and floating-point parameters supply diagnostic readbacks; `asynInt32Array` publishes the complete colour-count triplet.

## 5. NDArray format and validation

The tested input is a **320 × 240, unsigned 8-bit, RGB1** NDArray. Its dimensions are `[3, 320, 240]`, with three colour components in the fastest-varying dimension. The memory layout is:

```text
R0 G0 B0  R1 G1 B1  R2 G2 B2 ...
```

For 320 × 240 pixels, the array contains `320 × 240 × 3 = 230400` byte elements. The plugin checks the number of dimensions, `NDUInt8` data type, `NDColorModeRGB1`, first-dimension size of three, non-null pixel data, nonzero width and height, and consistency between dimensions and total element count. Size/overflow checks guard against invalid array geometry and count overflow.

A valid frame increments `ValidCount_RBV` and sets `ValidFrame_RBV` to Valid. An unsupported frame increments `InvalidCount_RBV`, sets the validity readback to Invalid, and clears the published colour measurements. Frame validity means the *array format* is supported; it does not mean that an LED was detected.

## 6. RGB channel means

For each valid frame, the plugin accumulates red, green and blue component values over all pixels. It reports:

\[
\overline{R}=\frac{1}{N}\sum_{i=1}^{N}R_i,\quad
\overline{G}=\frac{1}{N}\sum_{i=1}^{N}G_i,\quad
\overline{B}=\frac{1}{N}\sum_{i=1}^{N}B_i.
\]

The readbacks are `AD:RGB1:RedMean_RBV`, `GreenMean_RBV`, and `BlueMean_RBV`. Each lies between 0 and 255 for valid 8-bit images. These are **full-image means**, including background pixels, so they are useful for diagnostics but less selective than pixel-level colour segmentation.

Initial tests showed green-channel dominance under green illumination and red-channel dominance under red illumination, supporting the tested channel ordering. The Python acquisition path performs a channel reversal before sending data; colour ordering should be rechecked if the Picamera2 format or acquisition code changes.

## 7. RGB-to-HSV conversion

Each pixel is converted to hue, saturation and value using normalized RGB components. Let `max = max(r,g,b)`, `min = min(r,g,b)` and `delta = max-min`, with `r,g,b` normalized to `[0,1]`. The value is `max`, and saturation is `delta/max` when `max > 0`, otherwise zero. Hue is determined by the dominant RGB component, normalized to a turn of the colour wheel, and scaled to approximately `[0,255]`.

The implementation truncates the scaled HSV components to integers. It was adapted from the earlier Pillow-based `vision/led_monitor.py` segmentation, but exact equality with Pillow at every threshold boundary has **not** been exhaustively established. The raw RGB frame also differs from a JPEG-derived image because JPEG compression can change pixel values.

The tested colour masks are:

| Colour | Hue range (8-bit scale) | Additional requirements |
|---|---|---|
| Red | `H < 15` or `H > 240` | `S > 100` and `V > 100` |
| Yellow | `25 <= H <= 50` | `S > 100` and `V > 100` |
| Green | `55 <= H <= 115` | `S > 100` and `V > 100` |

A pixel contributes to at most one of these three colour counts. Pixels outside the ranges are not counted. The masks apply to the **whole image**; there is no spatial LED-localization or tracking step. Consequently, other bright coloured objects in the scene can affect the counts.

## 8. Published EPICS measurements

| PV suffix under `AD:RGB1:` | Type | Meaning |
|---|---|---|
| `ValidFrame_RBV` | binary input | Latest frame passed format validation |
| `ValidCount_RBV` | integer | Number of valid frames |
| `InvalidCount_RBV` | integer | Number of invalid frames |
| `RedMean_RBV` | floating point | Full-image mean red intensity |
| `GreenMean_RBV` | floating point | Full-image mean green intensity |
| `BlueMean_RBV` | floating point | Full-image mean blue intensity |
| `RedCount_RBV` | integer | Red HSV-mask pixel count |
| `YellowCount_RBV` | integer | Yellow HSV-mask pixel count |
| `GreenCount_RBV` | integer | Green HSV-mask pixel count |
| `ColoredCount_RBV` | integer | Sum of the three counts |
| `ColorCounts_RBV` | integer waveform | `[red, yellow, green]` from one processed frame |

The combined waveform is backed by an `asynInt32Array` callback and a record configured with `FTVL=LONG`, `NELM=3` and `SCAN="I/O Intr"`. A verified read returned `ColorCounts_RBV.NORD = 3`.

The plugin updates scalar asyn parameters with `setIntegerParam()` / `setDoubleParam()` and publishes scalar notifications with `callParamCallbacks()`. It then calls `doCallbacksInt32Array()` with a three-element array containing the counts for the current frame (zeros for an invalid frame). The array callback is the **frame-consistent publication unit**: one read of this waveform retrieves a complete triplet. Sequential reads of separate scalar PVs can span different camera frames.

## 9. NDArray ownership and the reference-counting incident

An early implementation passed the incoming NDArray to:

```cpp
NDPluginDriver::endProcessCallbacks(pArray, false, true);
```

During continuous acquisition the IOC reported:

```text
NDArrayPool:release ERROR, reference count < 0
CRITICAL ERROR Thread IMAGE1_Plugin_1 can't proceed, suspending.
```

The plugin was intended only to calculate measurements, not to create or forward an output image. The implementation was corrected to retain `beginProcessCallbacks(pArray)` for standard bookkeeping but **not** call `endProcessCallbacks()` on the incoming array or manually release it. The upstream callback infrastructure manages that input's lifetime. Subsequent continuous acquisition ran normally, with valid-frame counts increasing and no recurrence of the observed release error during the reported tests.

This observation supports the correction for the tested version, but does not establish that every future callback or ownership modification is safe. If the plugin later produces a transformed NDArray, output allocation, reference counting and callback ownership must be designed and tested explicitly.

## 10. Experimental verification

The plugin was exercised using a physical RGB LED with a repeated green → yellow → red → green sequence. Example single-waveform results were:

| LED state | Red count | Yellow count | Green count |
|---|---:|---:|---:|
| Green | 0 | 0 | 25680 |
| Yellow | 661 | 4865 | 4041 |
| Red | 16033 | 528 | 0 |
| Green again | 0 | 0 | 24580 |

The measured counts showed the expected colour-dependent trends. The waveform reported `NORD=3`; valid-frame counts increased, and invalid-frame counts remained zero in the cited tests. A later EPICS database implementation used the counts to classify red, green, yellow and off states. That downstream classification is described in [areaDetector Camera IOC](../areadetector_ioc.md), not implemented in `NDPluginRGB`.

To inspect the plugin during acquisition:

```bash
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
```

## 11. Design boundaries and limitations

- **General analysis versus application logic:** The plugin computes image statistics and HSV colour counts. LED-specific thresholds for NORMAL, WARNING, FAULT and UNKNOWN belong to `vision.db`.
- **No spatial ROI:** The plugin analyzes the entire frame, allowing manual repositioning but increasing susceptibility to background objects.
- **HSV calibration:** Thresholds are based on controlled experiments; arbitrary scenes, lighting changes, camera auto-exposure, and different LED spectra require further validation.
- **No colour tracking:** Counts do not locate the LED or distinguish it from similarly coloured objects.
- **Not a performance benchmark:** Sustained throughput, end-to-end latency, CPU/memory utilization and long-duration reliability have not been systematically measured.
- **Downstream synchronization:** The waveform itself contains one-frame counts, but `vision.db` uses independently CP-triggered `subArray` and `calc` records. This does not guarantee atomic downstream classification; brief intermediate states were observed near some LED transitions.
- **Stale state:** If acquisition stops, the most recent EPICS measurements can remain visible. A freshness timeout has not yet been implemented.

## 12. Potential improvements

Future work could add configurable HSV thresholds, optional spatial masking, controlled colour calibration, a processed-image or segmentation-mask output, frame identifiers and timestamps, performance measurements, and explicit synchronization or snapshot processing for downstream LED classification. Any new NDArray output path should include reference-counting tests.

## 13. Related documentation and sources

- [areaDetector Camera IOC](../areadetector_ioc.md) — IOC setup, continuous acquisition, `vision.db`, alarms and Phoebus.
- [Implementation and Results](../implementation_and_results.md) — project development milestones and measurements.
- [Troubleshooting](../troubleshooting.md) — observed errors and fixes.
- [`vision/led_monitor.py`](../../vision/led_monitor.py) — original Pillow-based HSV segmentation and classification reference.
- [areaDetector ADCore](https://github.com/areaDetector/ADCore) — upstream plugin framework.
- [EPICS Base documentation](https://docs.epics-controls.org/) — IOC and database records.

The implementation described here corresponds to the custom plugin developed and tested with ADCore R3-14 and EPICS Base R7.0.10. Consult the actual source files when changing interfaces or upgrading dependencies.
