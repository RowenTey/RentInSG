#!/bin/bash

# Specify the directory path
target_directory="/home/ec2-user/FYP-RentInSG"

# Change to the specified directory
cd "$target_directory" || { echo "Failed to change to directory: $target_directory"; exit 1; }

# Set log directory and file prefix
log_directory="$target_directory/logs/s3_uploader"
log_prefix="s3_uploader"

# Create log directory if it doesn't exist
mkdir -p "$log_directory"

# Get the current date and time
current_date=$(date +"%Y-%m-%d")

# Set log file name with timestamp
log_file="$log_directory/${log_prefix}_${current_date}.log"

# Run the Python file and append output to the log file
venv/bin/python utils/upload_to_s3.py >> "$log_file" 2>&1

# Remove old log files that are more than 7 days old
find "$log_directory" -name "${log_prefix}_*.log" -mtime +7 -exec rm {} \;