# EPICS-Controlled Camera Scanning — Learning Note

**Project:** EPICS-Controlled Camera Characterization and Vision Platform  
**Implementation:** `automation/camera_scan.py`  
**Updated:** 27 October 2026

## 1. Purpose and scope

`camera_scan.py` is a sequential PyEpics client that runs exposure or analogue-gain scans using the existing StreamDevice IOC and Python Picamera2 camera server. It reads scan settings from IOC soft records, sets camera controls through dedicated scan PVs, acquires JPEG/JSON pairs, measures mean grayscale JPEG intensity, publishes scan arrays for Phoebus, and writes a CSV log.

The script does **not** communicate with Picamera2 directly. It communicates with the IOC using EPICS Channel Access. The camera server continues to own camera hardware and file acquisition.

**Verified:** an exposure scan, file acquisition, intensity reporting, waveform updates, and a Phoebus XY plot. **Still to verify thoroughly:** gain scanning, Stop Scan, repeated scans, reconnection/error recovery, and Phoebus responsiveness.

## 2. Data and command flow

```text
Phoebus / caput
    | ScanEnable, ScanType, ranges, ScanPoints, StartScan, StopScan
    v
EPICS IOC (camera.db)
    |                           ^
    | PyEpics get/put           | PyEpics status, progress, arrays
    v                           |
automation/camera_scan.py ------+
    | Set scan exposure/gain; request Acquire
    v
IOC StreamDevice/asyn -> TCP camera server -> Picamera2 / IMX219
    |                                         |
    | latest image and metadata paths        | saved JPEG + JSON
    +-----------------------------------------+
    |
    v
camera_scan.py: read matching files -> grayscale mean -> CSV + PV arrays
    |
    v
Phoebus XY Plot: pva://CAM:ScanExposure or ScanGain vs pva://CAM:ScanIntensity
```

The `pva://` plot connections read the IOC's waveform records through QSRV. They are not a new image publisher and do not add a second camera TCP connection.

## 3. Why use `epics.PV()` objects?

The script creates named PV objects once:

```python
PV_SCAN_ENABLE = epics.PV("CAM:ScanEnable")
PV_SCAN_SET_EXPOSURE = epics.PV("CAM:ScanSetExposure")
PV_EXPOSURE_RB = epics.PV("CAM:ExposureRB")
```

It then reads and writes them with `.get()` and `.put()`:

```python
if PV_SCAN_ENABLE.get() == 1:
    PV_SCAN_SET_EXPOSURE.put(20000, wait=True)
```

This is equivalent in purpose to repeated `epics.caget()` and `epics.caput()` calls, but explicit objects make the scan code easier to follow. `wait=True` waits for the Channel Access put operation to complete; it does **not** by itself prove that the camera applied the requested setting. The script separately checks the requested-value readback and then uses the captured frame's metadata for the actual measurement.

The small `put(pv, value)` helper checks the return status and raises an exception on a failed write.

## 4. Scan-control PVs

| PV | Type | Function |
|---|---|---|
| `CAM:ScanEnable` | `bo` | Enables scan mode; separate from starting a scan |
| `CAM:ScanType` | `mbbo` | Exposure or Gain |
| `CAM:ScanStartExposure`, `CAM:ScanEndExposure` | `longout` | Exposure range in microseconds |
| `CAM:ScanStartGain`, `CAM:ScanEndGain` | `ao` | Gain range, dimensionless |
| `CAM:ScanPoints` | `longout` | Number of measurement points (1–100 in Python) |
| `CAM:StartScan`, `CAM:StopScan` | `bo` | Command flags read by the Python loop |
| `CAM:ScanSetExposure`, `CAM:ScanSetGain` | `longout`, `ao` | Dedicated scan setters using the existing StreamDevice protocols |
| `CAM:ExposureRB`, `CAM:GainRB` | `longin`, `ai` | Requested settings stored in the camera server |

Normal setters `CAM:SetExposure` and `CAM:SetGain` are distinct from the scan-specific setters. Both routes use the same camera hardware, but database interlocks control which records can process.

### Database interlocks

For the normal exposure setter:

```text
field(SDIS, "$(P)$(R)ScanEnable")
field(DISV, "1")
```

For the scan exposure setter:

```text
field(SDIS, "$(P)$(R)ScanEnable")
field(DISV, "0")
```

The same arrangement applies to gain. Thus normal setters process when scanning is disabled; scan setters process when scanning is enabled. **Do not add `CP` to these `SDIS` links:** testing showed that `CP` caused unintended processing of output records with initial zero values at IOC startup. Removing `CP` eliminated the observed errors.

`SDIS` prevents normal record processing; it is not a user-authentication or exclusive-ownership mechanism. Other clients may still write the scan-specific setter, and writes to disabled records may still change their stored `VAL` without executing the device command. The current auto-exposure setter has no database-level scan interlock.

## 5. Simple sequential control loop

The current design deliberately uses **no custom threads, callbacks, or `threading.Event()` objects**. Its main loop polls for commands:

```python
while True:
    enabled = PV_SCAN_ENABLE.get()
    if enabled == 1 and last_enable != 1:
        put(PV_SET_AUTO_EXPOSURE, 0)
    last_enable = enabled

    if PV_START_SCAN.get() == 1:
        put(PV_START_SCAN, 0)  # acknowledge request
        if enabled == 1:
            put(PV_STOP_SCAN, 0)
            run_scan()
        else:
            print("Scan is not enabled")
    time.sleep(0.1)
```

`last_enable` detects the transition into scan mode so that the program does not repeatedly send the same auto-exposure command on every idle iteration. `StartScan` is reset to zero as soon as its request is recognized, allowing a later button press to request another scan. `StopScan` is cleared before a new scan.

`run_scan()` blocks the main loop until the scan finishes. It checks `StopScan` and `ScanEnable` inside its own measurement/wait loops, so a stop can be recognized without adding a Python thread. Stopping is cooperative: a camera acquisition already in progress is not forcibly interrupted.

At startup the program clears stale Start/Stop requests and sets the status to IDLE. The operator must keep the program running for Phoebus scan commands to have an effect.

## 6. Reading and validating scan parameters

`scan_settings()` reads `ScanType`, `ScanPoints`, and the appropriate start/end PVs. It validates that the point count is between 1 and 100, the range values are finite and positive, and the scan type is supported.

```python
values = np.linspace(start, end, points)
```

For exposure scans, values are rounded to integer microseconds and duplicate rounded values are rejected. Gain scans retain floating-point values. These checks are **software validation**, not complete validation against the IMX219's camera-control limits.

No separate fixed-gain PV is required for an exposure scan; the camera uses its previously configured gain. Likewise, a gain scan does not require an additional fixed-exposure PV.

## 7. Acquisition and measurement

For each requested value, the program:

1. Writes `CAM:ScanSetExposure` or `CAM:ScanSetGain`.
2. Waits until `CAM:ExposureRB` or `CAM:GainRB` matches the requested setting (gain uses a small tolerance).
3. Reads the previous `CAM:GetLatestImagePath`, sends `Acquire`, and waits for a changed image path.
4. Waits for the corresponding `CAM:GetLatestMetadataPath`.
5. Opens the JSON and extracts `ExposureTime` or `AnalogueGain` for the **captured frame**.
6. Opens the JPEG, converts it to 8-bit grayscale, and calculates the image-wide mean.
7. Appends a CSV row and updates scan-result PVs.

The mean-intensity calculation is conceptually:

```python
with Image.open(image_path) as image:
    intensity = float(np.asarray(image.convert("L"), dtype=np.float64).mean())
```

This measures processed JPEG brightness, not raw sensor response. It is affected by the scene and camera image-processing pipeline. The X value plotted for a point comes from the matching JSON metadata, not from the requested setpoint or the asynchronously updated `CAM:GetExposure`/`CAM:GetGain` PV.

The changed-image-path method is a practical acquisition-completion signal, not a complete command acknowledgement. The script uses timeouts to avoid waiting indefinitely.

## 8. Scan status, progress, and waveforms

| PV | Record type | Contents |
|---|---|---|
| `CAM:ScanStatus` | `mbbo` | IDLE, RUNNING, COMPLETED, STOPPED, ERROR |
| `CAM:ScanProgress` | `longout` | Number of completed points |
| `CAM:ScanMeanIntensity` | `ao` | Mean intensity of the latest completed image |
| `CAM:ScanExposure` | `waveform` DOUBLE | Actual exposure values from acquired frames |
| `CAM:ScanGain` | `waveform` DOUBLE | Actual gain values from acquired frames |
| `CAM:ScanIntensity` | `waveform` DOUBLE | Corresponding mean intensities |

The Python program writes growing arrays after each completed point:

```python
x_values.append(actual)
intensities.append(intensity)
put(x_pv, np.asarray(x_values, dtype=np.float64))
put(PV_SCAN_INTENSITY, np.asarray(intensities, dtype=np.float64))
```

The IOC waveform record uses `FTVL=DOUBLE` and `NELM=100`: it allocates capacity for up to 100 values. `NORD` reports the valid number of elements (for example, 3 after a three-point scan). EPICS does not append points automatically; Python maintains the lists and writes the updated arrays.

At the beginning of a scan, the script writes a one-element `NaN` array as a non-plottable placeholder. This is **not** a truly empty array. X and Y arrays are written in separate PV operations, so their updates are not atomic.

## 9. Phoebus XY Plot and the CA/PVA difference

For exposure scans, configure the XY Plot trace as:

```text
X PV: pva://CAM:ScanExposure
Y PV: pva://CAM:ScanIntensity
```

For gain scans:

```text
X PV: pva://CAM:ScanGain
Y PV: pva://CAM:ScanIntensity
```

During testing, `caget` displayed all 100 allocated waveform positions, including trailing zeros, even though `NORD` indicated the correct valid count. `pvget` returned only the valid measured values. The original Phoebus plot displayed an unwanted point at `(0, 0)`; using the explicit `pva://` waveform connections removed it in the tested setup. A `Line` trace is appropriate for the response curve.

Phoebus responsiveness was reported as slow during some plotting tests. The cause has not been established; it should not be attributed to PVA without further isolation.

## 10. CSV output and file locations

The current scan-data directory is:

```text
data/scan/
```

The CSV is named `exposure_scan_YYYYMMDD_HHMMSS.csv` or `gain_scan_YYYYMMDD_HHMMSS.csv`. Rows include scan type, requested value, requested readback, actual frame value, mean intensity, image path, and metadata path. Each row is flushed after acquisition. The JPEG and JSON files are stored separately under `acquisition/images/` on the Raspberry Pi.

Because this version opens the image and metadata paths directly, **run the scan program on the Raspberry Pi** (or a machine with access to those same paths). The image publisher is a separate process and is not required for CSV acquisition or intensity calculation.

Generated files are excluded from Git. The old `automation/exposure_sweep.py`, the old characterization scripts, and the `data/exposure_sweeps/` workflow have been retired; their experimental findings remain in `docs/implementation_and_results.md`.

## 11. Running and checking the program

Start the Python camera server and IOC, then in a separate Raspberry Pi terminal:

```bash
cd ~/projects/hobby/camera/camera_vision_epics
source .venv/bin/activate
python -u automation/camera_scan.py
```

For a small exposure scan, set ScanEnable to Enable, ScanType to Exposure, start/end exposures to 5000/20000 microseconds, and ScanPoints to 3. Press Start Scan. Check:

```bash
caget CAM:ScanStatus
caget CAM:ScanProgress
caget CAM:ScanExposure.NORD
caget CAM:ScanIntensity.NORD
pvget CAM:ScanExposure
pvget CAM:ScanIntensity
```

Expect three completed points and a completed status for a successful three-point scan. Use the `pva://` PV names in the Phoebus XY Plot. These are test settings, not a calibrated sensor-characterization procedure.

## 12. Limitations and next validation

- Gain scans are implemented in the scan logic but require dedicated end-to-end testing.
- Stop Scan and repeated-scan behavior require more testing; stop requests are checked cooperatively.
- The scan program does not provide strict exclusive ownership of scan setters.
- Automatic exposure is disabled on entering scan mode and checked before running, but the current database does not prevent another client from re-enabling it.
- Waveform X/Y writes are separate; temporary mismatch during refresh is possible.
- The program saves processed JPEGs rather than measuring raw sensor data or in-memory frames.
- File-path notifications, command acknowledgements, reconnections, and Phoebus responsiveness need further robustness testing.

For IOC record and protocol details, see [StreamDevice Camera IOC](../streamdevice_ioc.md). For the chronology and earlier measurement results, see [Implementation and Results](../implementation_and_results.md). For observed problems and fixes, see [Troubleshooting](../troubleshooting.md).
