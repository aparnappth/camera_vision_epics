# Single-Frame areaDetector Image Acquisition Test

**Source:** [`acquisition/tests/test_areadetector_image.py`](https://github.com/aparnappth/camera_vision_epics/blob/main/acquisition/tests/test_areadetector_image.py)  
**Verified:** 2 November 2026  
**Scope:** One RGB frame per execution; not a live streaming application.

## 1. Purpose

This program tests the complete image-data path from the Sony IMX219 camera to an EPICS areaDetector IOC and Phoebus, without saving an intermediate JPEG. It reuses the Picamera2 camera setup established in `acquisition/tests/test_camera_acquisition.py`, but replaces image-file saving with an in-memory NumPy array transferred through Channel Access.

The program also configures the relevant areaDetector PVs on each run, avoiding manual `caput` commands after an IOC restart. The IOC must already be running, and the IOC's database waveform capacities and startup configuration must already support the chosen image size.

```text
IMX219 -> Picamera2 -> NumPy RGB bytes -> PyEpics Channel Access
       -> AD:Input:ArrayIn -> NDDriverStdArrays (STDARRAYS)
       -> NDArray -> NDPluginStdArrays (IMAGE1)
       -> AD:Image1:ArrayData -> Phoebus Image widget
```

## 2. Dependencies and configuration constants

The script uses `os` for the Channel Access environment variable, `time` for exposure settling and polling, NumPy for array conversion, PyEpics for PV access, Picamera2 for acquisition, and `libcamera.Transform` for orientation.

Before importing PyEpics, it sets:

```python
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = "1000000"
```

This allows a sufficiently large Channel Access array in the Python client. The IOC must also be configured with an adequate limit. The test image has width 320, height 240 and three colour channels:

```python
WIDTH = 320
HEIGHT = 240
CHANNELS = 3
EXPECTED_ELEMENTS = WIDTH * HEIGHT * CHANNELS  # 230400
```

The source builds PV names from `AD:Input:` and `AD:Image1:` prefixes. `AD:Input:ArrayIn` is the input waveform; `AD:Image1:ArrayCounter_RBV` and `AD:Image1:ArrayData.NORD` are used to verify downstream processing.

The script defines the areaDetector enumeration values `ND_UINT8=1`, `COLOR_RGB1=2`, `CALLBACK_ON_UPDATE=0` and `IMAGE_MODE_CONTINUOUS=2`.

## 3. EPICS helper functions

`put_pv(name, value)` calls `epics.caput(..., wait=True, timeout=10)` and raises `RuntimeError` if the put does not report success. This is used for ordinary configuration PVs and the image waveform.

`verify_pv(name, expected)` calls `epics.caget(..., as_string=False)`, rejects missing values, and compares the numerical readback to the expected value. This verifies selected scalar settings; it is not proof that every internal driver parameter has been updated.

## 4. Automatic areaDetector configuration

`configure_areadetector()` runs before the camera is opened.

First it writes `AD:Input:Acquire=0`, stopping the driver while its image settings are changed. It then configures:

| PV suffix | Value | Reason |
|---|---:|---|
| `Input:SizeX` | 320 | Image width |
| `Input:SizeY` | 240 | Image height |
| `Input:NDimensions` | 3 | RGB1 NDArray has three dimensions |
| `Input:DataType` | 1 (`UInt8`) | Unsigned 8-bit NDArray pixels |
| `Input:ColorMode` | 2 (`RGB1`) | Interleaved RGB colour format |
| `Input:CallbackMode` | 0 | Generate callbacks on array updates |
| `Input:AppendMode` | 0 | Each write represents a fresh array, not an append |
| `Input:ImageMode` | 2 | Keep the driver ready for subsequent images |
| `Input:ArrayCallbacks` | 1 | Enable NDArray callbacks |
| `Image1:EnableCallbacks` | 1 | Enable processing by the output plugin |

Next it sends the dimension array `[3, 320, 240]` as `np.int32` to `AD:Input:Dimensions`. The first dimension is the channel count in the RGB1 layout, followed by width and height.

It checks the width, height, number of dimensions, data type, colour mode, image mode and plugin enable readbacks. It deliberately does **not** use `Dimensions_RBV` as a validation condition: in the tested NDDriverStdArrays version, the driver stored dimensions internally without updating that array readback. The internal values were verified during development using `asynReport(1, "STDARRAYS")` in the IOC shell.

Finally, it starts acquisition with `epics.caput(..., wait=False)` and, after a short delay, checks `AD:Input:Acquire_RBV=1`. This differs from ordinary configuration writes because `wait=True` previously timed out on the long-running acquisition operation even though the IOC had entered the `Acquiring` state.

**Important:** `ImageMode=Continuous` does not make this Python program stream frames. It only leaves the driver accepting additional images. The script still captures and sends one frame per invocation.

## 5. Camera initialization and image acquisition

`main()` first calls `configure_areadetector()`. It then creates `Picamera2(0)` and a still configuration with:

```python
main={"size": (320, 240), "format": "RGB888"}
transform=Transform(hflip=1, vflip=1)
```

Both flips implement the 180-degree orientation used in the earlier camera-acquisition test. Automatic exposure is enabled with `camera.set_controls({"AeEnable": True})`.

After starting the camera, the script waits two seconds to allow exposure control to settle. It captures one completed request using `camera.capture_request()`. The frame array and metadata are extracted from that same request using `request.make_array("main")` and `request.get_metadata()`.

It prints the array shape, dtype, camera-reported exposure time and analogue gain. It requires the frame shape to be `(240, 320, 3)` and dtype `np.uint8`, raising an error otherwise. The two-second wait is a practical settling delay, not proof that exposure has converged.

## 6. Pixel conversion for the areaDetector waveform

The current tested code reverses the final axis of the Picamera2 array:

```python
frame_rgb = np.ascontiguousarray(frame[:, :, ::-1])
pixels = frame_rgb.reshape(-1)
pixels_int8 = pixels.view(np.int8)
```

`frame[:, :, ::-1]` reverses the three colour channels. `np.ascontiguousarray()` makes the resulting pixel buffer contiguous, and `reshape(-1)` flattens the image into 230,400 elements in row-major order.

The final `.view(np.int8)` changes the NumPy interpretation from unsigned to signed 8-bit **without changing the underlying byte patterns**. This is necessary because the installed asyn waveform device support uses `asynInt8ArrayOut`, whereas the NDArray itself is configured as `UInt8`.

The channel reversal was used in the working Phoebus test. It should not be treated as a universally correct Picamera2 conversion for every format or version; colour accuracy was assessed visually, not with a calibrated reference target.

## 7. Sending and verifying the image

The program reads `AD:Image1:ArrayCounter_RBV` before transfer, then writes the flattened signed-byte array to `AD:Input:ArrayIn` through PyEpics. A successful put confirms that the waveform write completed, but by itself does not prove that the driver created an NDArray.

The script therefore polls the plugin counter for up to five seconds, checking every 0.1 seconds. If the counter does not increase, it raises an error. After a counter increase, it reads `AD:Image1:ArrayData.NORD` and requires exactly 230,400 elements.

These checks establish that the output plugin processed a new array of the expected length. They do **not** perform a pixel-by-pixel comparison of input and output data, measure transfer latency, or establish sustained streaming performance.

During the verified test, the plugin counter increased and the output waveform reported 230,400 elements. Phoebus displayed a recognizable image using `ca://AD:Image1:ArrayData`, width 320, height 240, `TYPE_RGB1` and unsigned data.

## 8. Resource cleanup

The acquisition and transfer operations are inside `try/finally`. The `finally` block releases the captured request, stops the camera if it is running, and closes the Picamera2 object. This allows the IMX219 to be used afterward by other programs, such as the existing camera server or a VLC preview workflow.

Only one process should actively control the physical camera at a time. The areaDetector IOC can remain running because this IOC receives images through EPICS and does not open the IMX219 directly.

## 9. Running the test

Start the areaDetector IOC first. From the project root on the Raspberry Pi:

```bash
source .venv/bin/activate
export EPICS_CA_MAX_ARRAY_BYTES=1000000
python acquisition/tests/test_areadetector_image.py
```

Ensure the separate `picamera2_server.py` or another camera preview process is not using the IMX219. The test should configure the IOC, acquire one frame, report a plugin counter increase, and verify the output element count. A new IOC restart requires the Python configuration routine to run again before image transfer.

Useful independent checks:

```bash
caget AD:Input:Acquire_RBV
caget AD:Input:ImageMode_RBV
caget AD:Image1:EnableCallbacks_RBV
caget AD:Input:ArrayCounter_RBV
caget AD:Image1:ArrayCounter_RBV
caget AD:Image1:ArrayData.NORD
```

## 10. Known limitations and next work

- One frame is captured per run; sustained continuous capture has not yet been implemented.
- The code checks plugin counter progression and element count, not byte-for-byte data identity.
- The configured waveform capacity is fixed for the 320 × 240 RGB test. Changing resolution also requires checking the IOC waveform capacities and Channel Access array limits.
- The script sets acquisition to continuous mode but does not stop the IOC acquisition state when it exits; only the camera is stopped and closed.
- The fixed 0.2-second acquisition-state check and two-second auto-exposure delay may need more robust polling and settling criteria in future versions.
- Colour correctness has been visually assessed but not quantitatively validated.
- Frame rate, latency, CPU use, memory use and dropped-frame behaviour have not yet been measured.

For the IOC implementation and dependency installation, see [areaDetector Camera IOC](../areadetector_ioc.md), [EPICS Environment Setup](../epics_setup.md), and [Troubleshooting](../troubleshooting.md). For the verified development record, see [Implementation and Results](../implementation_and_results.md).
