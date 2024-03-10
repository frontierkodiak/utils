import os
import glob
import argparse
from PIL import Image

def sort_numerically(files):
    """Sort files numerically based on the leading number in the filename."""
    return sorted(files, key=lambda x: int(os.path.basename(x).split('_')[0]))

def generate_fade_frames(image1, image2, steps=10):
    """Generate frames for a fade transition from image1 to image2."""
    fade_frames = []
    for step in range(steps):
        alpha = step / float(steps)
        blended = Image.blend(image1.convert("RGBA"), image2.convert("RGBA"), alpha)
        fade_frames.append(blended)
    return fade_frames

def generate_gif_with_fade(input_files, output_file, target_duration, transition_steps=10):
    """Generate a GIF from input files with a fade transition, targeting a specific duration for the entire GIF."""
    images = [Image.open(file).convert("RGBA") for file in input_files]
    
    # Resize images to match the size of the first image
    base_width, base_height = images[1].size
    resized_images = [image.resize((base_width, base_height), Image.LANCZOS) for image in images]   
     
    # Calculate the total number of frames including transitions
    total_frames = len(resized_images) + (len(resized_images) - 1) * transition_steps
    duration_per_frame = target_duration / total_frames
    
    final_frames = []
    for i in range(len(resized_images) - 1):
        final_frames.append(resized_images[i])
        fade_frames = generate_fade_frames(resized_images[i], resized_images[i+1], steps=transition_steps)
        final_frames.extend(fade_frames)
    final_frames.append(resized_images[-1])  # Add the last image
    
    final_frames[0].save(output_file, save_all=True, append_images=final_frames[1:], duration=duration_per_frame, loop=0)

def main():
    parser = argparse.ArgumentParser(description="Generate GIFs with optional fade transition.")
    parser.add_argument("--base-dir", required=True, help="Base directory containing image subdirectories.")
    parser.add_argument("--output-dir", required=True, help="Directory to save generated GIFs.")
    parser.add_argument("--subdirs", nargs='+', required=True, help="Subdirectories to process.")
    parser.add_argument("--target-duration", type=int, default=5000, help="Target duration for the entire GIF in milliseconds.")
    parser.add_argument("--transition", choices=["none", "fade"], default="none", help="Type of transition between frames.")
    parser.add_argument("--transition-steps", type=int, default=10, help="Number of steps for the fade transition.")
    parser.add_argument("--order", choices=["forward", "reverse"], default="forward", help="Order of frames in the GIF.")
    
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for subdir in args.subdirs:
        dir_path = os.path.join(args.base_dir, subdir)
        jpg_files = glob.glob(os.path.join(dir_path, '*.jpg'))
        if args.order == "forward":
            sorted_files = sort_numerically(jpg_files)
        else:
            sorted_files = sort_numerically(jpg_files)[::-1]
            
        duration_str = f"{int(args.target_duration/1000)}s"

        if args.transition == "none":
            output_file = os.path.join(args.output_dir, f"{subdir}_{duration_str}_{args.order}.gif")
            generate_gif_with_fade(sorted_files, output_file, args.target_duration, 1)  # Use 1 step for no transition
        else:
            output_file = os.path.join(args.output_dir, f"{subdir}_{duration_str}_{args.transition}_{args.transition_steps}fadeSteps_{args.order}.gif")
            generate_gif_with_fade(sorted_files, output_file, args.target_duration, args.transition_steps)
        print(f"Generated: {output_file}")

if __name__ == "__main__":
    main()