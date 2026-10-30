
"""Test full-image colour detection using the latest EPICS camera image."""

from pathlib import Path

import epics
import numpy as np
from PIL import Image

# EPICS PV
IMAGE_PATH_PV = "CAM:GetLatestImagePath"

# Output directory
OUTPUT_DIR = Path("data/vision")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Read the latest image path from EPICS
image_path = epics.caget(IMAGE_PATH_PV, as_string=True)

if not image_path or image_path == "NONE":
    raise RuntimeError("No acquired image path available from EPICS")

image_path = Path(image_path)

if not image_path.is_file():
    raise FileNotFoundError(f"Image not found: {image_path}")

print(f"Analyzing image: {image_path}")

# Load image and convert to HSV
with Image.open(image_path) as image:
    rgb_image = image.convert("RGB")
    hsv_image = rgb_image.convert("HSV")

rgb = np.asarray(rgb_image)
hsv = np.asarray(hsv_image)

# Pillow HSV channels range from 0 to 255
hue = hsv[:, :, 0]
saturation = hsv[:, :, 1]
value = hsv[:, :, 2]

# Initial experimental thresholds
bright_coloured = (saturation > 100) & (value > 100)

red_mask = (
    ((hue < 15) | (hue > 240))
    & bright_coloured
)

yellow_mask = (
    (hue >= 25) & (hue <= 50)
    & bright_coloured
)

green_mask = (
    (hue >= 55) & (hue <= 115)
    & bright_coloured
)


def classify_led(red_count, yellow_count, green_count):
    """Experimental LED status classification."""

    total = red_count + yellow_count + green_count

    if total < 1000:
        return "UNKNOWN"

    red_green_ratio = red_count / max(green_count, 1)
    yellow_fraction = yellow_count / total

    if red_green_ratio > 20 and yellow_fraction < 0.05:
        return "FAULT"

    elif yellow_fraction > 0.10:
        return "WARNING"

    elif red_green_ratio < 0.2 and yellow_fraction < 0.02:
        return "NORMAL"

    else:
        return "UNKNOWN"


# Save diagnostic images
for name, mask in {
    "red": red_mask,
    "yellow": yellow_mask,
    "green": green_mask,
}.items():

    result = np.zeros_like(rgb)
    result[mask] = rgb[mask]

    output_path = OUTPUT_DIR / f"{image_path.stem}_{name}.png"
    Image.fromarray(result).save(output_path)

    print(f"{name.upper()}: {np.count_nonzero(mask)} pixels")
    print(f"Saved: {output_path}")

print("Colour segmentation completed.")

red_count = np.count_nonzero(red_mask)
yellow_count = np.count_nonzero(yellow_mask)
green_count = np.count_nonzero(green_mask)

status = classify_led(red_count, yellow_count, green_count)


# Diagnostic colour measurements
total = red_count + yellow_count + green_count

red_green_ratio = red_count / max(green_count, 1)

yellow_fraction = yellow_count / total if total > 0 else 0

print("\nColour analysis:")
print(f"Red/Green ratio: {red_green_ratio:.4f}")
print(f"Yellow fraction: {yellow_fraction:.4f}")
print(f"Total coloured pixels: {total}")


print(f"Detected LED status: {status}")
