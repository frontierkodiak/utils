#!/bin/bash

# --- Configuration ---
# Path to the SINGLE dataset JSON file on this server (blade)
# Uncomment the dataset you want to process:
# DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/mammalia.json"
DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/amphibia.json"
# DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/reptilia.json"
# DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/pta.json"
# DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/aves.json"
# DATA_FILE="/home/caleb/repo/polliFormer/work/active/assets/datasets/angiospermae.json"

# The base directory on the destination machine (carbon)
LOCAL_BASE_DIR_ON_CARBON="/Users/carbon/Data/ibrida/v0r1/images/non_localized"
# SSH user and hostname for the destination machine (carbon)
REMOTE_USER_ON_CARBON="carbon"
REMOTE_HOST_ON_CARBON="carbon" # Or the IP address/Tailscale name if 'carbon' doesn't resolve
DESTINATION="$REMOTE_USER_ON_CARBON@$REMOTE_HOST_ON_CARBON"
# Number of samples per dataset
SAMPLE_SIZE=250

# --- Signal Handling ---
interrupted=0
trap 'handle_interrupt' SIGINT SIGTERM

handle_interrupt() {
  echo "" # Newline after ^C
  echo "Interrupt signal received. Cleaning up and exiting..."
  interrupted=1
  # Optional: kill any running rsync processes started by this script if needed
  # pkill -P $$ rsync # Kills rsync processes whose parent is this script's PID
}

# --- Script Logic ---

echo "Starting sample rsync process from this server ($HOSTNAME) to $DESTINATION:$LOCAL_BASE_DIR_ON_CARBON"
echo "Using dataset definition file: $DATA_FILE"
echo "Sample size: $SAMPLE_SIZE files"
echo "Press Ctrl+C to interrupt."
echo ""

# Check if jq is installed on blade
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed on this server ($HOSTNAME). Please install it (e.g., sudo apt-get install jq)."
    exit 1
fi

# Check if the JSON file exists on blade
if [ ! -f "$DATA_FILE" ]; then
    echo "Error: Dataset file not found: $DATA_FILE"
    echo "Please ensure the file exists and the path is correct."
    exit 1
fi

# --- Extract Dataset Info ---
# Use jq to directly extract name and image directory from the single JSON object
dataset_name=$(jq -r '.name' "$DATA_FILE")
source_dir_on_blade=$(jq -r '.local_image_dir' "$DATA_FILE")

# Validate extracted info
if [ -z "$dataset_name" ] || [ "$dataset_name" == "null" ]; then
    echo "Error: Could not extract 'name' from $DATA_FILE"
    exit 1
fi
if [ -z "$source_dir_on_blade" ] || [ "$source_dir_on_blade" == "null" ]; then
    echo "Error: Could not extract 'local_image_dir' from $DATA_FILE"
    exit 1
fi

echo "--- Processing dataset: $dataset_name ---"
echo "  Source directory on $HOSTNAME: $source_dir_on_blade"

# Check if SSH works to the destination by attempting to create the base directory there
echo "Checking SSH access and ensuring base destination directory exists on $REMOTE_HOST_ON_CARBON..."
ssh "$DESTINATION" "mkdir -p \"$LOCAL_BASE_DIR_ON_CARBON\""
ssh_check_exit_code=$?

if [ $ssh_check_exit_code -ne 0 ]; then
    echo "Error: Failed to connect or create base directory on $DESTINATION."
    echo "Please ensure SSH access is set up from $HOSTNAME to $DESTINATION (user '$REMOTE_USER_ON_CARBON')"
    echo "(check 'ssh $DESTINATION' works without a password) and that you have write permissions."
    exit 1
fi
echo "SSH access verified."

# Construct the destination directory name on carbon from the dataset name (lowercase first word)
# Use awk on the extracted dataset_name variable
dest_sub_dir_on_carbon=$(echo "$dataset_name" | awk '{print tolower($1)}')
dest_dir_on_carbon="$LOCAL_BASE_DIR_ON_CARBON/$dest_sub_dir_on_carbon"

# Ensure the specific dataset destination directory exists on carbon
echo "  Ensuring destination directory exists on $REMOTE_HOST_ON_CARBON: $dest_dir_on_carbon"
ssh "$DESTINATION" "mkdir -p \"$dest_dir_on_carbon\""
ssh_mkdir_exit_code=$?
if [ $ssh_mkdir_exit_code -ne 0 ]; then
    echo "  Error: Failed to create destination directory $dest_dir_on_carbon on $DESTINATION."
    exit 1
fi
echo "  Destination directory ready."

echo "  Getting list of $SAMPLE_SIZE random files from local path: $source_dir_on_blade..."

# Check if source directory exists locally
if [ ! -d "$source_dir_on_blade" ]; then
    echo "  Error: Source directory '$source_dir_on_blade' not found on $HOSTNAME."
    exit 1
fi

# Find random files
local_find_shuf_command="find \"$source_dir_on_blade\" -type f 2>/dev/null | shuf -n \"$SAMPLE_SIZE\" 2>/dev/null"
selected_files_list=$(eval "$local_find_shuf_command")
find_shuf_exit_code=${PIPESTATUS[0]}

# Check results of find/shuf
if [ $find_shuf_exit_code -ne 0 ] && [ -z "$selected_files_list" ]; then
     echo "  Warning: 'find' command failed (exit code $find_shuf_exit_code) and no files were selected from '$source_dir_on_blade'."
     echo "  Command attempted: $local_find_shuf_command"
     exit 1 # Exit if find failed AND nothing was selected
fi

if [ -z "$selected_files_list" ]; then
    echo "  Warning: Found 0 files or selected 0 files for $dataset_name from '$source_dir_on_blade'."
    echo "  Command attempted: $local_find_shuf_command"
    echo "  This might mean the source directory is empty, has fewer than $SAMPLE_SIZE files, or a permissions issue occurred."
    echo "  Exiting as there are no files to rsync."
    exit 0 # Exit gracefully if no files found/selected
fi

num_selected_files=$(echo "$selected_files_list" | wc -l | awk '{print $1}')
echo "  Selected $num_selected_files files. Starting rsync..."

# --- Rsync Loop ---
# Loop through selected files and rsync individually
files_processed=0
while IFS= read -r source_file_path; do
    # Check if interrupted during file transfer loop
    if [ "$interrupted" -eq 1 ]; then
        echo "Interrupt detected during file transfers. Stopping."
        break # Exit the file loop
    fi

    if [ -n "$source_file_path" ]; then
       files_processed=$((files_processed + 1))
       echo -ne "  Transferring file $files_processed/$num_selected_files: $(basename "$source_file_path")\\r" # Progress indicator

       # Use simpler quoting for destination
       rsync -avz "$source_file_path" "$DESTINATION:$dest_dir_on_carbon/"
       rsync_exit_code=$?
       if [ $rsync_exit_code -ne 0 ] && [ "$interrupted" -eq 0 ]; then # Don't warn if interrupted
           echo "" # Newline after progress indicator
           echo "    Warning: rsync failed for '$source_file_path' to '$DESTINATION:$dest_dir_on_carbon/' (Exit code: $rsync_exit_code)"
           # Consider whether to 'continue' or 'break' on error
       fi
    fi
done < <(echo "$selected_files_list")

echo "" # Final newline after progress indicator or loop completion

# --- Final Status ---
if [ "$interrupted" -eq 1 ]; then
  echo "Script execution was interrupted."
  exit 130 # Standard exit code for script terminated by Ctrl+C
else
  echo "--- Finished processing $dataset_name ---"
  echo "Sample rsync process completed."
fi

exit 0