#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <path_to_labels_file>"
    exit 1
fi

labels_file="$1"

# Extract task names from the metainfo section
task_names=$(grep -oP '"name": "\K\d+' "$labels_file")

# Count total number of samples
total_samples=$(grep -c '"img_path"' "$labels_file")

# Iterate over task names and count samples with labels
for task in $task_names; do
    task_label="L$task"
    samples_with_label=$(grep -c "\"$task_label\":" "$labels_file")
    percentage=$(awk -v swl="$samples_with_label" -v ts="$total_samples" 'BEGIN {printf "%.2f", (swl / ts) * 100}')
    echo "Task $task_label: $samples_with_label out of $total_samples samples (${percentage}%)"
done
