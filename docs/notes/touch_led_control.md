# Touch Sensor and RGB LED Status Indicator — Implementation and Learning Note

**Project:** EPICS-Controlled Camera Characterization and Vision Platform  
**Implementation:** `hardware/touch_led/`  
**Date:** 29 October 2026

## 1. Purpose and scope

This note documents a standalone Raspberry Pi GPIO experiment developed as the hardware basis for a planned camera-based LED recognition and alarm system. A digital touch sensor controls an RGB LED: the colour indicates how long the sensor has remained continuously active.

**Verified on the Raspberry Pi:** the touch sensor test, RGB LED colour test, and combined NORMAL/WARNING/FAULT behaviour, including returning to green on release. **Not yet implemented:** camera-based LED recognition, EPICS detection PVs, Phoebus visual alarms, and a physical buzzer.

The GPIO program is independent of the EPICS IOC, `picamera2_server.py`, and the PVAccess image publisher. It does not publish EPICS process variables or access the camera.

## 2. Source files

| File | Responsibility |
|---|---|
| `hardware/touch_led/test_touch.py` | Verify sensor activation and release using GPIO callbacks. |
| `hardware/touch_led/test_rgb_led.py` | Verify red, green, blue, yellow, and OFF output states. |
| `hardware/touch_led/led_controller.py` | Combine sensor input and LED output into a duration-dependent status indicator. |

## 3. GPIO configuration

The scripts use **BCM GPIO numbering** and the Python `gpiozero` library.

| Component | BCM GPIO | Configuration |
|---|---|---|
| Digital touch sensor | 17 | `DigitalInputDevice(17, pull_up=False)` |
| RGB LED red channel | 22 | `RGBLED(red=22, ...)` |
| RGB LED green channel | 23 | `RGBLED(green=23, ...)` |
| RGB LED blue channel | 24 | `RGBLED(blue=24, ...)` |

The RGB LED is configured with `pwm=True`. The standalone LED test explicitly uses `active_high=True`; the combined controller uses the `RGBLED` default. These settings describe the software configuration, not a complete wiring diagram. The supplied scripts do not specify resistor values, the sensor module model, or the LED's physical pinout.

## 4. Independent touch sensor test

`test_touch.py` creates a `DigitalInputDevice` and registers callbacks:

```python
touch = DigitalInputDevice(17, pull_up=False)
touch.when_activated = lambda: print("Touched")
touch.when_deactivated = lambda: print("Released")
pause()
```

`when_activated` and `when_deactivated` register functions to run on changes in the input state. The `lambda` expressions are short callback functions; they are **not** executed when assigned. `signal.pause()` keeps the program running so the callbacks can operate.

This test verifies input transitions only. It does not measure touch duration or control the LED.

## 5. Independent RGB LED test

`test_rgb_led.py` creates an `RGBLED` with red, green, and blue channels on GPIO 22, 23, and 24. It cycles continuously through these outputs, each for two seconds:

| Printed state | `led.color` |
|---|---|
| RED | `(1, 0, 0)` |
| GREEN | `(0, 1, 0)` |
| BLUE | `(0, 0, 1)` |
| YELLOW | `(1.0, 0.5, 0.0)` |
| OFF | `led.off()` |

An RGB tuple gives the relative drive level of the red, green, and blue channels, normally from 0 to 1. With PWM enabled, the intermediate green value `0.5` is possible. The resulting perceived colour and brightness depend on the physical LED and circuit; these tuples are not calibrated colour measurements.

The program catches `KeyboardInterrupt` and calls `led.close()` in `finally` to release its GPIO resources.

## 6. Combined touch-controlled indicator

`led_controller.py` continuously reads `touch.is_active` and chooses an LED colour and status according to the duration of uninterrupted activation.

| Sensor condition | Status | LED colour |
|---|---|---|
| Inactive | NORMAL | Green `(0, 1, 0)` |
| Active for less than 1 second | NORMAL | Green `(0, 1, 0)` |
| Active for at least 1 second and at most 6 seconds | WARNING | Yellow `(1, 0.5, 0)` |
| Active for more than 6 seconds | FAULT | Red `(1, 0, 0)` |

Releasing the sensor resets the timing reference and immediately selects NORMAL at the next loop iteration. The threshold for FAULT is strictly **greater than** six seconds, not greater than or equal to six seconds.

### 6.1 Measuring elapsed time with `time.monotonic()`

```python
if touch_start is None:
    touch_start = time.monotonic()
duration = time.monotonic() - touch_start
```

`touch_start` starts as `None`, meaning there is no active touch interval. The first active iteration stores a monotonic timestamp; subsequent active iterations calculate the elapsed time from the same timestamp. A monotonic clock is appropriate for elapsed-time measurement because it is not affected by changes to the wall clock.

When the sensor becomes inactive, `touch_start = None` ensures the next activation starts a new interval rather than accumulating time across separate touches.

### 6.2 Polling rather than callbacks

The combined controller uses:

```python
while True:
    # Read touch input and choose the state.
    time.sleep(0.05)
```

This is **polling**: the program checks the input approximately every 50 milliseconds. By contrast, the independent touch test uses callbacks on activation and deactivation. The 50 ms sleep reduces repeated checks, but does not guarantee an exact 50 ms sampling period or millisecond-precise threshold transitions.

### 6.3 Updating only when the colour changes

```python
if color != current_color:
    led.color = color
    current_color = color
    print(f"Status: {status}")
```

`current_color` remembers the last colour applied by the program. This condition avoids repeated LED writes and repeated console messages while the selected state remains unchanged. At startup `current_color` is `None`, so the first iteration applies the initial colour and prints its status.

### 6.4 Cleanup

```python
except KeyboardInterrupt:
    print("\nProgram stopped")
finally:
    led.off()
    led.close()
    touch.close()
```

Ctrl+C raises `KeyboardInterrupt`, which is handled without an unformatted traceback. The `finally` block switches off the LED and closes both GPIO devices. This describes the normal interruption path; it does not guarantee cleanup after power loss or forced process termination.

## 7. Running and verifying

From the repository root on the Raspberry Pi, run the scripts **one at a time**, since the LED test and combined controller use the same GPIO outputs:

```bash
python3 hardware/touch_led/test_touch.py
python3 hardware/touch_led/test_rgb_led.py
python3 hardware/touch_led/led_controller.py
```

Use the Python environment in which `gpiozero` and its GPIO backend are available. Stop the running program with Ctrl+C before starting another program that uses the same pins.

**Reported physical verification (29 October 2026):** the touch activation/release messages, the RGB LED colour cycle, and the combined green → yellow → red progression were tested successfully. Releasing the sensor returned the combined controller to green. No quantitative latency, brightness, or colour-classification measurements were recorded.

## 8. Relationship to the planned EPICS vision platform

The standalone LED controller produces a **physical optical signal**. The planned vision system should detect that signal through the IMX219 camera rather than infer FAULT directly from the touch sensor's GPIO state.

A possible future workflow is:

```text
Touch sensor -> standalone LED controller -> RGB LED
                                            |
                                       Optical image
                                            |
                                      IMX219 camera
                                            |
                                 Vision recognition (planned)
                                            |
                                  EPICS detection state (planned)
                                            |
                                 Phoebus visual alarm (planned)
                                            |
                                   Buzzer (later phase)
```

No camera-recognition algorithm, EPICS alarm PV, or buzzer implementation is claimed by this milestone. The frame-acquisition method and EPICS integration approach remain design decisions for subsequent work.

## 9. Result and next steps

**Result:** A tested, standalone, three-state touch-controlled RGB LED indicator with a one-second WARNING threshold and a greater-than-six-second FAULT threshold.

**Next development stage:** design and test camera-based detection of the red LED, then integrate the detection result with EPICS and a Phoebus visual alarm. Physical buzzer actuation is deferred until the visual monitoring path has been verified.

## Related documentation

- [Project README](../../README.md)
- [Implementation and Results](../implementation_and_results.md)
- [StreamDevice Camera IOC](../streamdevice_ioc.md)
- [Troubleshooting](../troubleshooting.md)
