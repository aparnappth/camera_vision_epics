# PVAccess Image Publisher — Implementation and Learning Guide

## Purpose

The image publisher displays images acquired by the IMX219 camera in Phoebus. Camera control and image display use separate services so that transferring image pixels does not add traffic to the existing StreamDevice TCP connection.

The conventional EPICS IOC controls acquisition and provides the path of the latest saved JPEG. The Python program `acquisition/pva_image_publisher.py` reads that path, prepares a smaller RGB image, and publishes its pixel values as a PVAccess process variable (PV).

This is **acquired-image display**, not continuous live video streaming. The full-resolution JPEG and matching JSON metadata remain on the Raspberry Pi.

## Architecture

```text
Phoebus on a remote computer
   |                           |
   | CA/PVA camera controls    | PVA image pixels
   v                           v
Conventional EPICS IOC       CAM:Image
   |                           ^
   | StreamDevice / asyn       | Python p4p server
   | TCP 127.0.0.1:5000        |
   v                           |
picamera2_server.py      pva_image_publisher.py
   |                           ^
   | Save JPEG + JSON          | Read saved JPEG
   v                           |
acquisition/images/ -----------+

The publisher also reads CAM:GetLatestImagePath from the IOC using PyEpics.
```

The camera server, conventional IOC, and image publisher are independent processes on the Raspberry Pi. Phoebus can run on another computer that has network access to the EPICS PVs.

## Why a separate publisher?

The camera server already handles text commands, responses, and status/file-path notifications over one TCP connection. Adding binary image data to that connection would require a new transfer protocol and could complicate the existing message-handling limitations.

The `p4p` library provides a PVAccess server directly from Python. This allows image data to reach Phoebus without adding an image waveform record to `camera.db`, a second StreamDevice port, or a binary TCP protocol. The conventional IOC remains responsible for camera control and acquisition.

## Requirements

The Raspberry Pi project environment uses Python with `numpy`, `Pillow`, `pyepics`, and `p4p`. The image-publisher proof of concept used `p4p` 4.3.0. Phoebus is used on the remote computer.

With the project virtual environment active, imports can be checked using:

```bash
python -c "import epics, numpy; from PIL import Image; from p4p.server import Server, StaticProvider; from p4p.server.thread import SharedPV; print('Imports available')"
```

`Server` and `StaticProvider` are imported from `p4p.server`, while `SharedPV` is imported from `p4p.server.thread` in the tested environment.

## Image PV and pixel format

The published PV is `CAM:Image`. Its value is a one-dimensional array of unsigned 8-bit numbers, created with `NTScalar("aB")`.

For the initial display, each saved JPEG is resized to **100 × 100 pixels** and converted to RGB. Every pixel contains three values: red, green, and blue. The resulting NumPy array has shape `(100, 100, 3)` and contains 30,000 bytes before PVAccess transport overhead.

The array is flattened in interleaved order:

```text
R1 G1 B1 R2 G2 B2 R3 G3 B3 ...
```

The original JPEG is not overwritten. Resizing limits the amount of data needed for this first visualization experiment.

## Important Python concepts

### Reading the latest path through EPICS

The publisher uses PyEpics to read `CAM:GetLatestImagePath`:

```python
image_path = epics.caget("CAM:GetLatestImagePath", as_string=True)
```

`as_string=True` asks PyEpics to interpret the character waveform as readable text instead of returning individual character codes. The returned path refers to a file stored on the Raspberry Pi; the PV itself does not contain the JPEG bytes.

### Preparing an RGB array

```python
with Image.open(image_path) as image:
    rgb = image.convert("RGB")
    resized = rgb.resize((100, 100))
    pixels = np.asarray(resized, dtype=np.uint8)

pixel_array = pixels.flatten()
```

`Image.open()` opens the saved JPEG. The `with` statement closes the file when the block finishes. `convert("RGB")` ensures three color channels. `resize()` creates a smaller display image. `np.asarray()` converts the image to a NumPy array, and `flatten()` arranges the values in one dimension for publication.

### Publishing a PVAccess value

The essential `p4p` objects have different roles:

- `NTScalar("aB")` defines the PV value as an array of unsigned bytes.
- `SharedPV` holds the published value and supports updates.
- `StaticProvider` registers the PV name `CAM:Image`.
- `Server` makes that provider accessible to PVAccess clients.

The publisher begins with an all-zero RGB array, which appears black in Phoebus until an image is published. A new image is sent using the equivalent of:

```python
image_pv.post(image_type.wrap(pixel_array))
```

`wrap()` constructs a value of the declared PVAccess type. `post()` updates the PV so connected clients can receive the new array.

### Detecting a new acquisition

The current implementation checks `CAM:GetLatestImagePath` periodically, approximately every 0.5 seconds. It compares the current path with the last successfully published path. When they differ, it attempts to read and publish the new JPEG. The remembered path is updated only after successful publication, allowing a later attempt if loading fails.

This is **polling the EPICS path PV**, not scanning the image directory. It is also not an event-driven PyEpics monitor callback. If multiple acquisitions finish between checks, the publisher may show only the most recent image.

## Running the system

Start the following processes on the Raspberry Pi, in separate terminals:

1. `acquisition/picamera2_server.py` — controls the camera and saves files.
2. The conventional StreamDevice IOC — provides control and latest-path PVs.
3. `acquisition/pva_image_publisher.py` — reads the latest path and publishes `CAM:Image`.

From the repository root, with the project virtual environment active, the publisher is started with:

```bash
python acquisition/pva_image_publisher.py
```

It remains running while image updates are needed. It does not need to be restarted after each acquisition.

## Phoebus configuration

Add an **Image** widget and use the following tested settings:

| Property | Value |
|---|---|
| PV Name | `pva://CAM:Image` |
| Data Width | `100` |
| Data Height | `100` |
| Color Mode | `TYPE_RGB1` |
| Unsigned Data | Enabled |

The `TYPE_RGB1` setting works with the interleaved RGB array created by `pixels.flatten()`. Enabling **Unsigned Data** is important because the array contains `uint8` values from 0 to 255. Interpreting high byte values as signed can produce incorrect colors.

## Verified behavior

An initial standalone publisher (`test_pva_image.py`) successfully published a saved IMX219 JPEG through PVAccess. `pvget` returned the numerical array, and the Phoebus Image widget displayed the acquired image. RGB display was verified using `TYPE_RGB1` with Unsigned Data enabled.

The publisher was then kept as a separate program and renamed `pva_image_publisher.py`. The image-update workflow was tested with Phoebus camera acquisition and was reported working after correcting a local configuration mistake. The unrelated minor mistake is not part of this implementation guide.

The working display demonstrates that a simple PVAccess numerical array is sufficient for this initial Phoebus image widget setup. A structured `NTNDArray` was not needed for this test.

## Local and remote operation

The publisher must be able to open the JPEG path returned by the IOC. In the current setup, it runs on the Raspberry Pi, where the camera server saves the images. Phoebus receives the pixel array over PVAccess and does not need direct access to the Raspberry Pi file path.

The control IOC and publisher provide different PVs. The conventional IOC exposes `CAM:GetLatestImagePath`; the Python `p4p` server exposes `CAM:Image`. These are separate PV providers even though Phoebus displays them in the same interface.

## Limitations and future considerations

- The displayed image is resized to 100 × 100 pixels; it is not the full-resolution JPEG.
- The publisher transfers the latest **processed JPEG** image, not raw sensor data.
- It checks the latest-path PV periodically rather than subscribing to a monitor callback.
- Intermediate acquisitions can be skipped when several images are saved between checks.
- The publisher depends on the IOC's latest-path PV and access to the corresponding local file.
- An initial black image indicates that the PV is available, not that a JPEG has been loaded.
- Network discovery and connection settings may need adjustment on other networks.
- This is an initial image-display implementation, not an areaDetector or NTNDArray pipeline.

The image publisher remains independent of the StreamDevice control connection. Any future changes to update frequency, resolution, or image transport can be evaluated without changing the existing camera-control protocol.

## Related documentation

- [Project README](../../README.md)
- [StreamDevice Camera IOC](../streamdevice_ioc.md)
- [Automated Acquisition and Initial Characterization](automated_acquisition_and_characterization.md)
- [Troubleshooting](../troubleshooting.md)
