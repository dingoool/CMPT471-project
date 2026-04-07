import os
import json
import xml.etree.ElementTree as ET
import sys

def convert_mpd_to_json(mpd_path, output_path, content_name):
    tree = ET.parse(mpd_path)
    root = tree.getroot()

    # DASH uses namespaces → need this
    ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}

    # Find SegmentTemplate
    seg_template = root.find('.//mpd:SegmentTemplate', ns)

    if seg_template is None:
        print("No SegmentTemplate found")
        return

    init_template = seg_template.attrib.get("initialization")
    media_template = seg_template.attrib.get("media")
    start_number = int(seg_template.attrib.get("startNumber", 1))

    # Extract RepresentationID (usually 0)
    representation = root.find('.//mpd:Representation', ns)
    rep_id = representation.attrib.get("id", "0")

    # Build init file name
    init_file = init_template.replace("$RepresentationID$", rep_id)

    # Count chunk files from directory
    folder = os.path.dirname(mpd_path)
    chunk_files = sorted([f for f in os.listdir(folder) if f.endswith(".m4s") and "chunk" in f])

    segments = [init_file]

    for i in range(len(chunk_files)):
        number = start_number + i
        filename = media_template \
            .replace("$RepresentationID$", rep_id) \
            .replace("$Number%05d$", f"{number:05d}")
        segments.append(filename)

    manifest = {
        "content": content_name,
        "num_segments": len(segments),
        "segments": segments
    }

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Created {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 mpd_to_json.py <mpd_path> <output_json> <content_name>")
        exit(1)

    convert_mpd_to_json(sys.argv[1], sys.argv[2], sys.argv[3])