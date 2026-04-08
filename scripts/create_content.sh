#!/bin/bash

VIDEO_NAME="mv.mp4"
NUM_SERVERS=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ "$#" -ne 1 ]; then
  echo "Usage: ./create_content.sh <num_servers>"
  exit 1
fi

if [ ! -f "$ROOT_DIR/$VIDEO_NAME" ]; then
  echo "Error: Video file '$VIDEO_NAME' not found in project root."
  echo "Please place the video at: $ROOT_DIR/$VIDEO_NAME"
  exit 1
fi

rm -rf "$ROOT_DIR/content"
mkdir -p "$ROOT_DIR/content/server1/sample1"

echo "Generating DASH segments..."
ffmpeg -i "$ROOT_DIR/$VIDEO_NAME" \
  -map 0:v \
  -codec:v libx264 \
  -f dash \
  -seg_duration 2 \
  "$ROOT_DIR/content/server1/sample1/manifest.mpd"

echo "Converting MPD to JSON..."
python3 "$SCRIPT_DIR/mpd_to_json.py" \
  "$ROOT_DIR/content/server1/sample1/manifest.mpd" \
  "$ROOT_DIR/content/server1/sample1/manifest.json" \
  sample1

echo "Copying content to other servers..."
for ((i=2;i<=NUM_SERVERS;i++)); do
  mkdir -p "$ROOT_DIR/content/server$i"
  cp -r "$ROOT_DIR/content/server1/sample1" "$ROOT_DIR/content/server$i/"
done

echo "Done"