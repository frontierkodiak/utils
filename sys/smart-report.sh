#!/bin/bash

# /home/caleb/repo/utils/sys/smart-report.sh

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    exec sudo "$0" "$@"
fi

# Create reports directory if it doesn't exist
REPORT_DIR="/home/caleb/reports/disks"
mkdir -p "$REPORT_DIR"
chown caleb:caleb "$REPORT_DIR"

# Generate filename with date
DATE=$(date '+%Y-%m-%d')
OUTPUT_FILE="$REPORT_DIR/smart-report-$DATE.txt"

echo "=== SMART Drive Report $(date '+%Y-%m-%d %H:%M:%S') ===" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Function to get drive info and SMART status
check_drive() {
    local drive=$1
    local name=$2
    
    echo "=== Drive $name ($drive) ===" >> "$OUTPUT_FILE"
    
    # Get PARTUUID
    echo "--- PARTUUID ---" >> "$OUTPUT_FILE"
    local partuuid=$(lsblk -no PARTUUID "${drive}1")
    echo "PARTUUID: $partuuid" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Get basic drive info
    echo "--- Drive Information ---" >> "$OUTPUT_FILE"
    smartctl -i "$drive" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Get SMART health summary
    echo "--- SMART Health Summary ---" >> "$OUTPUT_FILE"
    smartctl -H "$drive" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Get detailed SMART attributes
    echo "--- SMART Attributes ---" >> "$OUTPUT_FILE"
    smartctl -A "$drive" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Get error logs
    echo "--- Error Log ---" >> "$OUTPUT_FILE"
    smartctl -l error "$drive" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
}

# Check NVMe drives
for drive in /dev/nvme?n1; do
    if [ -e "$drive" ]; then
        check_drive "$drive" "$(basename $drive)"
    fi
done

# Check SATA/SAS drives
for drive in /dev/sd?; do
    if [ -e "$drive" ]; then
        # Get drive serial number
        serial=$(smartctl -i "$drive" | grep "Serial Number" | awk '{print $NF}')
        check_drive "$drive" "$(basename $drive) - $serial"
    fi
done

# Set correct ownership of output file
chown caleb:caleb "$OUTPUT_FILE"

# Keep only the last 365 days of reports
find "$REPORT_DIR" -name "smart-report-*.txt" -mtime +365 -delete

echo "Report generated at $OUTPUT_FILE"