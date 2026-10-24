
import csv
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image


# Find the latest exposure-sweep CSV file
csv_files = sorted(
    Path("data/exposure_sweeps").glob("exposure_sweep_*.csv")
)

if not csv_files:
    raise FileNotFoundError("No exposure-sweep CSV files found")

csv_path = csv_files[-1]

print(f"Reading: {csv_path}\n")


# Store exposure times and image statistics
exposure_times = []
mean_intensities = []
min_intensities = []
max_intensities = []
std_intensities = []


# Read the acquisition information
with open(csv_path, newline="") as file:

    reader = csv.DictReader(file)

    for row in reader:

        # Read actual exposure time from metadata
        with open(row["metadata_path"]) as metadata_file:
            metadata = json.load(metadata_file)

        actual_exposure = metadata["ExposureTime"]

        # Open JPEG and convert it to grayscale
        with Image.open(row["image_path"]) as image:
            grayscale = image.convert("L")
            pixels = np.asarray(grayscale)

        # Calculate image statistics
        mean_intensity = np.mean(pixels)
        min_intensity = np.min(pixels)
        max_intensity = np.max(pixels)
        std_intensity = np.std(pixels)

        # Store the results
        exposure_times.append(actual_exposure)
        mean_intensities.append(mean_intensity)
        min_intensities.append(min_intensity)
        max_intensities.append(max_intensity)
        std_intensities.append(std_intensity)

        print(
            
            f"Exposure: {actual_exposure} us, "
            f"Mean: {mean_intensity:.2f}, "
            f"Min: {min_intensity}, "
            f"Max: {max_intensity}, "
            f"Std: {std_intensity:.2f}"

        )


# Plot exposure response
plt.figure()

plt.plot(
    exposure_times,
    mean_intensities,
    marker="o"
)

plt.xlabel("Actual exposure time (us)")
plt.ylabel("Mean grayscale intensity (0-255)")
plt.title("IMX219 JPEG Exposure Response")

plt.grid(True)
plt.tight_layout()

# Save the plot for later analysis
plot_path = csv_path.with_name(
    csv_path.stem + "_response.png"
)

plt.savefig(plot_path, dpi=150)

print(f"\nPlot saved to: {plot_path}")

plt.show()

