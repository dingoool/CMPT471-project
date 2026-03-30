#!/bin/bash

VIDEO_NAME="mv.mp4"
NUM_SERVERS=$1

if [ "$#" -ne 1 ]; then
  echo "Usage: ./create_content.sh <num_servers>"
  exit 1
fi

rm -rf content
mkdir -p content/server1/sample1

echo "Generating DASH segments..."
ffmpeg -i "$VIDEO_NAME" \
  -map 0:v \
  -codec:v libx264 \
  -f dash \
  -seg_duration 2 \
  content/server1/sample1/manifest.mpd

echo "Converting MPD to JSON..."
python3 mpd_to_json.py \
  content/server1/sample1/manifest.mpd \
  content/server1/sample1/manifest.json \
  sample1

echo "Copying content to other servers..."
for ((i=2;i<=NUM_SERVERS;i++)); do
  mkdir -p content/server$i
  cp -r content/server1/sample1 content/server$i/
done

echo "Done"