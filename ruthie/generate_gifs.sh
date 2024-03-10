#!/bin/zsh

base_dir="/Users/caleb/Documents/ruthie/repeat_scans/imgs"
output_dir="/Users/caleb/Documents/ruthie/repeat_scans/gifs"

# Ensure output_dir exists
mkdir -p "$output_dir"

# Set the directories
subdirs=("black" "blue" "purple")

# Set the frame durations
durations=(2 3 4)

# Set the transition options
transitions=("none" "fade")

# Set the order options
orders=("forward" "reverse")

# Loop through each directory
for subdir in "${subdirs[@]}"
do
  dir="$base_dir/$subdir" # Correctly handle spaces in directory names

  # Loop through each duration
  for duration in "${durations[@]}"
  do
    # Loop through each transition
    for transition in "${transitions[@]}"
    do
      # Loop through each order
      for order in "${orders[@]}"
      do
        # Initialize an array to hold the input files
        input_files=()
        
        # Get the list of JPG files in the directory
        if [ "$order" = "forward" ]; then
          jpg_files=($(find "$dir" -name '*jpg' -print | sort))
        else
          jpg_files=($(find "$dir" -name '*jpg' -print | sort -r))
        fi

        input_files=("${jpg_files[@]}")

        # Print the input files
        echo "Input files: ${input_files[@]}"

        # Set the output filename
        output_file="${output_dir}/${subdir}_${duration}s_${transition}_${order}.gif"
        
        # Generate the GIF using ImageMagick
        if [ "$transition" = "none" ]; then
          convert -delay $((duration * 100)) -loop 0 "${input_files[@]}" "$output_file"
        else
          convert -delay $((duration * 100)) -loop 0 -dispose previous -layers optimize "${input_files[@]}" "$output_file"
        fi
        
        echo "Generated: $output_file"
      done
    done
  done
done