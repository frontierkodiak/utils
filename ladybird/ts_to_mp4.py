import os
import json
import subprocess
from glob import glob
from tqdm import tqdm

def safe_remove(filepath):
    """Remove the file if it exists, ignoring if not present."""
    if os.path.exists(filepath):
        os.remove(filepath)

def gather_second_directories(base_dir: str):
    """
    Gather all second-level directories (*S) under *H/*M directories.
    Return a list of these second directories for processing.

    This helper function just collects the "S" directories so we can
    iterate over them with tqdm to show progress more easily.
    """
    second_dirs = []
    hour_dirs = sorted([d for d in glob(os.path.join(base_dir, '*H')) if os.path.isdir(d)])
    for hdir in hour_dirs:
        minute_dirs = sorted([d for d in glob(os.path.join(hdir, '*M')) if os.path.isdir(d)])
        for mdir in minute_dirs:
            sdirs = sorted([d for d in glob(os.path.join(mdir, '*S')) if os.path.isdir(d)])
            second_dirs.extend(sdirs)
    return second_dirs

def gather_ts_segments(base_dir: str):
    """
    Recursively traverse the directory structure starting from `base_dir`,
    identify directories with meta.json and .ts files, and build a list of
    (timestamp, ts_filepath) segments.

    We now know from experimentation that:
    - Each second-level directory (like 0H/0M/0S) contains ~10 .ts files and a meta.json
      that might have 60 increments (0.0167s apart).
    - We must truncate increments if they exceed the number of .ts files.
    - Each .ts file contains four HEVC tile streams that will need to be arranged in a 2x2 grid.

    We'll return a sorted list of (timestamp, ts_file_path) for all segments.

    We'll use tqdm to track overall progress as we process all "S" directories.
    """
    segments = []
    second_dirs = gather_second_directories(base_dir)
    print(f"Found a total of {len(second_dirs)} second-level directories. Processing...")

    for sdir in tqdm(second_dirs, desc="Processing second directories"):
        meta_file = os.path.join(sdir, 'meta.json')
        if not os.path.isfile(meta_file):
            # no meta.json, skip
            continue

        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
        except Exception:
            # couldn't load meta.json
            continue

        if "Time" not in meta or "x0" not in meta["Time"] or "xi-x0" not in meta["Time"]:
            # Invalid meta structure
            continue

        x0 = meta["Time"]["x0"]
        increments = meta["Time"]["xi-x0"]

        ts_files = sorted([f for f in glob(os.path.join(sdir, '*.ts')) if '.ts:' not in f])
        if not ts_files:
            # no ts files, skip
            continue

        # If increments are more than ts_files, truncate increments
        if len(increments) > len(ts_files):
            increments = increments[:len(ts_files)]

        # If still mismatch, skip
        if len(ts_files) != len(increments):
            continue

        # Associate each ts with its timestamp
        for i, ts_file in enumerate(ts_files):
            segment_timestamp = x0 + increments[i]
            segments.append((segment_timestamp, ts_file))

    return segments

def write_concat_file(segments, output_path):
    """
    Given a sorted list of (timestamp, ts_file_path) segments, write them out to a file
    suitable for the ffmpeg concat demuxer.

    The concat demuxer file syntax:
    file '/full/path/to/segment1.ts'
    file '/full/path/to/segment2.ts'
    ...
    """
    with open(output_path, 'w') as f:
        for _, seg_path in segments:
            abs_path = os.path.abspath(seg_path)
            f.write(f"file '{abs_path}'\n")

def main():
    BASE_DIR = "/home/caleb/ladybird_failed_copy"
    print(f"Using base directory: {BASE_DIR}")

    # Clean up old output files if they exist.
    # We do this to ensure we start fresh if a previous run was aborted.
    safe_remove("file_list.txt")
    safe_remove("fullres.mp4")
    safe_remove("output_4k.mp4")
    safe_remove("output_1080p.mp4")

    # Step 1: Gather all segments from the directory structure
    all_segments = gather_ts_segments(BASE_DIR)

    if not all_segments:
        print("No segments found after processing all directories.")
        return

    # Step 2: Sort segments by timestamp
    all_segments.sort(key=lambda x: x[0])
    print(f"Found a total of {len(all_segments)} segments.")

    # Step 3: Write out concat file for ffmpeg
    concat_file = "file_list.txt"
    write_concat_file(all_segments, concat_file)
    print(f"Concat file written to {concat_file}.")

    # At this point, we have a large number of .ts files representing possibly ~1m50s or more.
    # Each .ts has 4 HEVC streams (tiles) representing patches of a huge frame.
    #
    # We will now run ffmpeg to:
    #   - Concatenate all .ts files into one continuous input stream.
    #   - Use a filter_complex to stack the tiles into a full frame:
    #       top-left: [0:v:0]
    #       top-right: [0:v:1]
    #       bottom-left: [0:v:2]
    #       bottom-right: [0:v:3]
    #
    # The combined output ("fullres.mp4") will be massive and extremely high-resolution.
    # This might be slow and memory-intensive.
    #
    # Then, we produce two downscaled copies for more practical viewing:
    # - output_4k.mp4 (downscaled to ~3840 wide)
    # - output_1080p.mp4 (downscaled to ~1920 wide)
    #
    # The ffmpeg command for full resolution:
    # ffmpeg -f concat -safe 0 -i file_list.txt \
    #   -filter_complex "[0:v:0][0:v:1]hstack=2[top];[0:v:2][0:v:3]hstack=2[bottom];[top][bottom]vstack=2" \
    #   -c:v libx264 -crf 18 -preset slow fullres.mp4
    #
    # Note: Consider adding -pix_fmt yuv420p if playback issues occur.

    fullres_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-filter_complex", "[0:v:0][0:v:1]hstack=2[top];[0:v:2][0:v:3]hstack=2[bottom];[top][bottom]vstack=2",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow", "fullres.mp4"
    ]
    print("Running ffmpeg to create fullres.mp4 (this may take a long time)...")
    subprocess.run(fullres_cmd, check=True)

    # Create 4K downscaled version
    downscale_4k_cmd = [
        "ffmpeg", "-y",
        "-i", "fullres.mp4",
        "-vf", "scale=3840:-2",
        "output_4k.mp4"
    ]
    print("Creating a 4K downscaled version (output_4k.mp4)...")
    subprocess.run(downscale_4k_cmd, check=True)

    # Create 1080p downscaled version
    downscale_1080p_cmd = [
        "ffmpeg", "-y",
        "-i", "fullres.mp4",
        "-vf", "scale=1920:-2",
        "output_1080p.mp4"
    ]
    print("Creating a 1080p downscaled version (output_1080p.mp4)...")
    subprocess.run(downscale_1080p_cmd, check=True)

    print("All steps completed successfully.")
    print("You now have: fullres.mp4, output_4k.mp4, and output_1080p.mp4.")

if __name__ == "__main__":
    main()
