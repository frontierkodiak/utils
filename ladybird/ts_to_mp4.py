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
            
def try_encode_with_fallback(input_args, output_path, filter_complex, force_hardware=False, force_software=False):
    """Try hardware encoding first, fall back to software if it fails."""
    
    # Base command elements that don't change between encoders
    base_cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex
    ]
    
    # Only try hardware if not forcing software
    if not force_software:
        nvenc_cmd = [
            *base_cmd,
            "-c:v", "h264_nvenc",
            "-preset", "p7",
            "-qp", "18",
            output_path
        ]
        
        try:
            print("Attempting hardware-accelerated encoding with NVENC...")
            subprocess.run(nvenc_cmd, check=True)
            print("Hardware encoding successful!")
            return True
        except subprocess.CalledProcessError as e:
            if force_hardware:
                print(f"Hardware encoding failed and --force-hardware was specified: {str(e)}")
                return False
            print(f"Hardware encoding failed: {str(e)}")
            print("Falling back to software encoding...")
    
    # Only try software if not forcing hardware
    if not force_hardware:
        software_cmd = [
            *base_cmd,
            "-c:v", "libx264",
            "-preset", "slow",  # Quality/speed tradeoff
            "-crf", "18",      # Quality level (lower = better, 18-28 is typical range)
            output_path
        ]
        
        try:
            print("Attempting software encoding with libx264...")
            subprocess.run(software_cmd, check=True)
            print("Software encoding successful!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Software encoding failed: {str(e)}")
            return False
    
    return False

def main():
    # Basic CLI argument parsing
    import argparse
    parser = argparse.ArgumentParser(description='Process NFL camera .ts files into merged MP4.')
    parser.add_argument('--force-hardware', action='store_true', help='Only use hardware encoding')
    parser.add_argument('--force-software', action='store_true', help='Only use software encoding')
    args = parser.parse_args()

    BASE_DIR = "/home/caleb/ladybird_failed_copy"
    OUTPUT_DIR = os.path.join(BASE_DIR, "processed")
    print(f"Using base directory: {BASE_DIR}")
    print(f"Outputs will be saved to: {OUTPUT_DIR}")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Update output paths to use OUTPUT_DIR
    concat_file = os.path.join(OUTPUT_DIR, "file_list.txt")
    fullres_path = os.path.join(OUTPUT_DIR, "fullres.mp4")
    output_4k_path = os.path.join(OUTPUT_DIR, "output_4k.mp4")
    output_1080p_path = os.path.join(OUTPUT_DIR, "output_1080p.mp4")

    # Clean up old output files if they exist
    safe_remove(concat_file)
    safe_remove(fullres_path)
    safe_remove(output_4k_path)
    safe_remove(output_1080p_path)

    # Step 1: Gather all segments from the directory structure
    all_segments = gather_ts_segments(BASE_DIR)

    if not all_segments:
        print("No segments found after processing all directories.")
        return

    # Step 2: Sort segments by timestamp
    all_segments.sort(key=lambda x: x[0])
    print(f"Found a total of {len(all_segments)} segments.")

    # Step 3: Write out concat file for ffmpeg
    write_concat_file(all_segments, concat_file)
    print(f"Concat file written to {concat_file}.")

    # At this point, we have a large number of .ts files representing possibly ~1m50s or more.
    # Each .ts has 4 HEVC streams (tiles) representing patches of a huge frame.
    #
    # Tile Layout & Overlap Structure:
    # - Each frame is divided into a 2x2 grid of tiles
    # - Adjacent tiles overlap by 64 pixels
    # - To correct this, we crop 32px from each overlapping edge:
    #   * top-left:     crop 32px from right and bottom edges
    #   * top-right:    crop 32px from left and bottom edges
    #   * bottom-left:  crop 32px from top and right edges
    #   * bottom-right: crop 32px from top and left edges
    #
    # We will now run ffmpeg to:
    #   1. Concatenate all .ts files into one continuous input stream
    #   2. Crop overlapping regions from each tile
    #   3. Stack the tiles into a full frame:
    #       top-left:     [0:v:0] - cropped right/bottom
    #       top-right:    [0:v:1] - cropped left/bottom
    #       bottom-left:  [0:v:2] - cropped top/right
    #       bottom-right: [0:v:3] - cropped top/left
    #
    # The combined output ("fullres.mp4") will be massive and extremely high-resolution.
    # This might be slow and memory-intensive.

    # Setup for encoding
    input_args = ["-f", "concat", "-safe", "0", "-i", concat_file]
    filter_complex = (
        "[0:v:0]crop=iw-32:ih-32:0:0[tl];"
        "[0:v:1]crop=iw-32:ih-32:32:0[tr];"
        "[0:v:2]crop=iw-32:ih-32:0:32[bl];"
        "[0:v:3]crop=iw-32:ih-32:32:32[br];"
        "[tl][tr]hstack=2[top];"
        "[bl][br]hstack=2[bottom];"
        "[top][bottom]vstack=2"
    )

    print("Running ffmpeg to create fullres.mp4 (this may take a long time)...")
    if not try_encode_with_fallback(
        input_args, 
        fullres_path, 
        filter_complex,
        force_hardware=args.force_hardware,
        force_software=args.force_software
    ):
        print("Encoding failed. Check logs for details.")
        return

    # Create 4K downscaled version (using same encoder choice as fullres)
    print(f"Creating a 4K downscaled version ({output_4k_path})...")
    if not try_encode_with_fallback(
        ["-i", fullres_path],
        output_4k_path,
        "scale=3840:-2",
        force_hardware=args.force_hardware,
        force_software=args.force_software
    ):
        print("4K downscaling failed. Check logs for details.")
        return

    # Create 1080p downscaled version
    print(f"Creating a 1080p downscaled version ({output_1080p_path})...")
    if not try_encode_with_fallback(
        ["-i", fullres_path],
        output_1080p_path,
        "scale=1920:-2",
        force_hardware=args.force_hardware,
        force_software=args.force_software
    ):
        print("1080p downscaling failed. Check logs for details.")
        return

    print("All steps completed successfully.")
    print(f"Output files are in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
