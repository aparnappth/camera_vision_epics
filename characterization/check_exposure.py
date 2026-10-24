
import csv
import json
from pathlib import Path

# Find the latest exposure-sweep CSV
csv_files = sorted(Path("data/exposure_sweeps").glob("exposure_sweep_*.csv"))

if not csv_files:
    raise FileNotFoundError("No exposure-sweep CSV files found")

csv_path = csv_files[-1]

print(f"Reading: {csv_path}\n")

print(f"{'Requested (us)':>15} {'Actual (us)':>15} {'Difference (us)':>17} {'Error (%)':>12}")

# Read each acquisition recorded in the CSV
with open(csv_path, newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        requested = int(row["requested_exposure_us"])

        # Load the metadata associated with this image
        with open(row["metadata_path"]) as metadata_file:
            metadata = json.load(metadata_file)

        actual = metadata["ExposureTime"]

        difference = actual - requested
        error_percent = difference / requested * 100

        print(
            f"{requested:15d} "
            f"{actual:15d} "
            f"{difference:17d} "
            f"{error_percent:12.3f}"
        )
