# EPICS-Based LED Vision Monitoring — Implementation and Learning Note

**Project:** EPICS-Controlled Camera Characterization and Vision Platform  
**Implementation:** `vision/test_led_detection.py`, `vision/led_monitor.py`  
**Development checkpoint:** 30 October 2026

## 1. Purpose and scope

This note documents the experimental camera-based recognition of the touch-controlled RGB LED and its integration into the existing EPICS platform. The independent `hardware/touch_led/led_controller.py` sets the physical LED to green (NORMAL), yellow (WARNING), or red (FAULT) based on touch duration. The vision program infers the state from camera images; it does **not** read the touch sensor GPIO or the LED controller's internal state.

The working implementation uses periodic saved-image acquisition, not continuous image-frame analysis. The colour classifier is a proof of concept under the tested background and lighting conditions, not a validated general-purpose LED detector.

## 2. Existing components and data flow

```text
Touch sensor -> led_controller.py -> physical RGB LED
                                         |
                                         v
                                   IMX219 camera
                                         |
                       Picamera2 / picamera2_server.py
                                         ^
                                         |
                        StreamDevice/asyn + EPICS IOC
                                         ^
                                         |
                    vision/led_monitor.py (PyEpics client)
                      | request Acquire approximately every 3 s
                      | read latest JPEG + matching JSON paths
                      | analyze JPEG and publish status/results
                      v
                  EPICS vision soft records -> Phoebus

acquisition/pva_image_publisher.py -> CAM:Image -> Phoebus Image widget
```

The existing camera server retains exclusive responsibility for opening and controlling Picamera2. The vision program uses the IOC's existing acquisition command and latest-file-path PVs. The separate PVAccess image publisher continues to provide the latest acquired image for display. No new StreamDevice camera command or second Picamera2 connection was added for vision monitoring.

## 3. Independent image-analysis experiment

The first script, `vision/test_led_detection.py`, reads `CAM:GetLatestImagePath` through PyEpics and opens the JPEG from the Raspberry Pi filesystem. It converts the image to RGB and then to Pillow HSV, analyzes the **entire image** (no fixed ROI), and saves diagnostic masks under `data/vision/`.

Pillow's HSV channels use integer values from 0 to 255. The initial experimental masks were:

```python
bright_coloured = (saturation > 100) & (value > 100)
red_mask = ((hue < 15) | (hue > 240)) & bright_coloured
yellow_mask = (hue >= 25) & (hue <= 50) & bright_coloured
green_mask = (hue >= 55) & (hue <= 115) & bright_coloured
```

`np.count_nonzero(mask)` counts pixels passing each mask. Each diagnostic PNG retains matching pixels and sets the rest to black. These masks identify colours across the scene, not the LED as a distinct object; reflections and other coloured objects can contribute.

### 3.1 Reference-image observations

Initial acquisitions with automatic exposure enabled gave the following pixel counts:

| Physical LED state | Red pixels | Yellow pixels | Green pixels |
|---|---:|---:|---:|
| Green | 417 | 80 | 30,146 |
| Yellow | 6,852 | 1,765 | 3,036 |
| Red | 57,666 | 473 | 209 |

The green and red examples were strongly separated by their red/green count ratios. Yellow was more difficult: the physical yellow setting mixes red and green LED channels (`(1, 0.5, 0)`), while the captured appearance varies with exposure, colour processing, reflections, and potentially sensor contact stability.

### 3.2 Derived measurements

The program calculates:

```python
total = red_count + yellow_count + green_count
red_green_ratio = red_count / max(green_count, 1)
yellow_fraction = yellow_count / total if total > 0 else 0
```

The denominator guard prevents division by zero. The yellow fraction is a proportion of the three **masked** pixel counts, not a fraction of all image pixels.

## 4. Experimental LED classification

An initial classifier prioritized a low red/green ratio as NORMAL. Some visibly yellow or flickering acquisitions were therefore reported as NORMAL. Additional testing demonstrated that yellow pixels could be substantial even when the red/green ratio was low. The classification rules were revised to examine FAULT and WARNING before NORMAL:

```python
if total < 1000:
    status = UNKNOWN
elif red_green_ratio > 20 and yellow_fraction < 0.05:
    status = FAULT
elif yellow_fraction > 0.10:
    status = WARNING
elif red_green_ratio < 0.2 and yellow_fraction < 0.02:
    status = NORMAL
else:
    status = UNKNOWN
```

The thresholds are empirical starting values. UNKNOWN is used when the measurements do not fit the tested patterns; it is not a proven LED-absence detector.

### 4.1 Verification of revised rules

The following test acquisitions were reported to produce the expected classifications:

| Acquisition time | R/G ratio | Yellow fraction | Reported classification |
|---|---:|---:|---|
| 12:28:19 | 0.1157 | 0.0005 | NORMAL |
| 12:29:02 | 2.3691 | 0.1254 | WARNING |
| 12:29:50 | 1.5597 | 0.1390 | WARNING |
| 12:30:34 | 978.0571 | 0.0112 | FAULT |

These tests support the classifier's behaviour in the exercised setup. They do not establish robustness under different backgrounds, strong camera movement, LED absence, or changing illumination.

## 5. EPICS vision soft records

The existing `camera.db` was extended with soft records; the vision program reads and writes them through PyEpics. These records do not use StreamDevice `DTYP` or a TCP `OUT` link.

| PV | Record type | Meaning / states |
|---|---|---|
| `CAM:VisionEnable` | `bo` | Disable (0), Enable (1) |
| `CAM:LEDStatus` | `mbbo` | UNKNOWN (0), NORMAL (1), WARNING (2), FAULT (3) |
| `CAM:VisionStatus` | `mbbo` | IDLE (0), RUNNING (1), ERROR (2), WAITING (3) |
| `CAM:LEDRedGreenRatio` | `ao` | Latest red/green pixel-count ratio |
| `CAM:LEDYellowFraction` | `ao` | Latest yellow fraction |

`CAM:LEDStatus` is initialized to UNKNOWN rather than NORMAL, so a missing first measurement is not presented as a confirmed healthy state. The Python program writes UNKNOWN when monitoring is interrupted or an acquisition/analysis error occurs.

The result records are distinct from camera hardware control PVs. They hold the outcome of image analysis rather than command the camera directly.

## 6. Automated monitoring loop

`vision/led_monitor.py` is a separate sequential PyEpics client. While `CAM:VisionEnable` is enabled, it requests acquisitions at a nominal three-second interval. The main steps are:

1. Check that vision monitoring is requested and that camera scanning is not active.
2. If scan mode is enabled, wait for an active scan to finish, then disable `CAM:ScanEnable` and verify the handover.
3. Enable automatic exposure once on entering vision mode, using `CAM:SetAutoExposure`; check `CAM:GetAutoExposure` for the requested-value readback.
4. Read the previous `CAM:GetLatestImagePath` and issue `CAM:CameraCommand = Acquire` (enum index 2).
5. Wait for a changed image path and the matching metadata JSON path, subject to a timeout.
6. Load the JPEG, count HSV mask pixels, classify the LED, and read the JSON for exposure/gain context.
7. Write `CAM:LEDRedGreenRatio`, `CAM:LEDYellowFraction`, and `CAM:LEDStatus`.
8. Continue until monitoring is disabled or interrupted.

The JSON metadata describes the camera settings associated with the acquired frame. **LED colour is determined from JPEG pixels, not from metadata.** The image and metadata files remain on the Raspberry Pi; the vision program therefore runs where those paths are accessible.

The three-second interval is measured between requested acquisition starts where possible; acquisition, waiting, analysis and EPICS communication add processing time. The program does not start overlapping acquisition requests.

### 6.1 Camera scan coordination

`CAM:ScanEnable` selects scan mode, whereas `CAM:ScanStatus` indicates whether a scan is RUNNING or has reached another state. Vision monitoring waits for an active scan to finish before taking over camera operation and disabling scan mode. The user reported successful testing of this handover and prevention of new scans while vision monitoring was enabled.

This is application-level coordination between the PyEpics programs. The project previously established that EPICS `SDIS`/`DISV` prevents record **processing**, but is not sufficient by itself to prevent writes to a soft-record `VAL` that an external Python client polls.

### 6.2 Automatic exposure

The scan workflow disables automatic exposure for controlled measurements. The vision workflow instead enables automatic exposure on entry because the reference-image classification was developed under that condition. It checks the requested automatic-exposure readback before proceeding. The user verified that this transition works. A requested-setting readback does not independently prove that auto-exposure has settled on a particular frame.

## 7. Phoebus integration

LED monitoring controls and status visualization were added to the **existing** `phoebus/epics_Camera_vision_main.bob` display on Windows, rather than creating a separate LED-monitor `.bob` file. The display uses the new vision PVs alongside the existing camera controls and image widget. The user reported the integrated display working as expected.

The existing `acquisition/pva_image_publisher.py` still publishes the latest saved image as `pva://CAM:Image`. This is an acquired-image display, not live video. A displayed FAULT state is a visual status indication; the physical buzzer has not yet been implemented.

## 8. Current limitations

- **Periodic acquisition and latency:** The vision program analyzes a saved still image approximately every three seconds, not every camera frame. A physical LED transition may take almost a full interval plus acquisition, processing and EPICS update time to appear. Short states can be missed.
- **Experimental classification:** Full-image colour masks include reflections and background objects. The thresholds were tested under a limited set of conditions and do not guarantee identification of the physical LED in arbitrary scenes.
- **No independent LED-presence verification:** UNKNOWN captures some ambiguous cases but does not prove the LED is present or absent.
- **File-based processing:** Every cycle depends on JPEG/JSON saving and matching file-path notifications. The existing camera-command acknowledgement and shared-TCP routing limitations remain relevant.
- **Monitoring process availability:** The Python monitor must remain running. IOC PVs alone do not autonomously acquire or classify images, and abrupt process loss may leave a stale last value without an independent heartbeat mechanism.

## 9. Possible future extensions

The following are exploratory possibilities, not completed features or a committed implementation schedule:

- Investigate continuous in-memory frame analysis to reduce detection delay and repeated file I/O.
- Explore an **areaDetector-based** IMX219 implementation, including availability or adaptation of a suitable driver, NDArray frame transport, and image-processing plugins. Compare this architecture with the current custom TCP/StreamDevice system; removal of that TCP path alone does not guarantee faster detection.
- Evaluate stronger LED localization, classification robustness, and explicit monitoring-health or stale-data indication.
- Extend the Phoebus visual indication to a physical buzzer alarm after evaluating the required response behaviour.

## 10. Related documentation

- [Project README](../../README.md)
- [Implementation and Results](../implementation_and_results.md)
- [StreamDevice Camera IOC](../streamdevice_ioc.md)
- [EPICS Camera Scanning](epics_camera_scanning.md)
- [PVAccess Image Publisher](pva_image_publisher.md)
- [Touch Sensor and RGB LED Control](touch_led_control.md)
- [Troubleshooting](../troubleshooting.md)
