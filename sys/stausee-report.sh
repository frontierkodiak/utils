#!/bin/bash

OUTPUT_FILE="/home/caleb/stausee-report.txt"

echo "=== Stausee Pool Report $(date '+%Y-%m-%d %H:%M:%S') ===" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Overall pool status and configuration
echo "=== Pool Status ===" >> "$OUTPUT_FILE"
zpool status stausee-pool >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "=== Pool Properties ===" >> "$OUTPUT_FILE"
zpool get all stausee-pool >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Get list of datasets
datasets=$(zfs list -H -o name | grep '^stausee-pool/')

echo "=== Dataset Properties ===" >> "$OUTPUT_FILE"
for ds in $datasets; do
    echo "" >> "$OUTPUT_FILE"
    echo "--- Dataset: $ds ---" >> "$OUTPUT_FILE"
    echo "* Basic Properties:" >> "$OUTPUT_FILE"
    zfs get quota,used,available,referenced,compression,compressratio "$ds" >> "$OUTPUT_FILE"
    
    echo "* Cache Settings:" >> "$OUTPUT_FILE"
    zfs get primarycache,secondarycache,logbias "$ds" >> "$OUTPUT_FILE"
    
    echo "* Performance Settings:" >> "$OUTPUT_FILE"
    zfs get recordsize,sync,atime,xattr,copies "$ds" >> "$OUTPUT_FILE"
    
    echo "* Mount Settings:" >> "$OUTPUT_FILE"
    zfs get mountpoint,mounted,canmount "$ds" >> "$OUTPUT_FILE"
done

echo "" >> "$OUTPUT_FILE"
echo "=== Pool I/O Statistics ===" >> "$OUTPUT_FILE"
zpool iostat stausee-pool >> "$OUTPUT_FILE"

echo "Report generated at $OUTPUT_FILE"
