#!/bin/bash

# Script to search for Shai-Hulud or Sha1-Hulud in home directory
# Usage: ./scan-for-sandworm.sh

# Generate output filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="sandworm_scan_results_${TIMESTAMP}.txt"

echo "Searching for 'Shai-Hulud' or 'Sha1-Hulud' in home directory..."
echo "Starting from: $HOME"
echo "This may take a while..."
echo "Results will be saved to: $OUTPUT_FILE"
echo ""

# Save header to file
{
  echo "Sandworm Scan Results"
  echo "===================="
  echo "Scan date: $(date)"
  echo "Search location: $HOME"
  echo "Search patterns: Shai-Hulud, Sha1-Hulud"
  echo ""
  echo "Results:"
  echo "--------"
} > "$OUTPUT_FILE"

# Use grep with extended regex to search for both patterns
# -r: recursive search
# -i: case-insensitive
# -n: show line numbers
# -H: show filenames
# --color=never: no color codes in file output
# --exclude: exclude this script file itself from results
grep -rinH \
  --color=never \
  --exclude='scan-for-sandworm.sh' \
  -E 'Shai-Hulud|Sha1-Hulud' \
  "$HOME" 2>/dev/null | tee -a "$OUTPUT_FILE"

# Add footer to file
{
  echo ""
  echo "--------"
  echo "Scan completed: $(date)"
} >> "$OUTPUT_FILE"

echo ""
echo "Search complete!"
echo "Results saved to: $OUTPUT_FILE"

