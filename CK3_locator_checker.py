import csv
import os
import sys
import re
import shutil

from PIL import Image


def get_folder_path(prompt):
    while True:
        path = input(prompt)
        if os.path.isdir(path):
            definition_path = os.path.join(path, "map_data", "definition.csv")
            if os.path.isfile(definition_path):
                print(f"Found definition.csv at: {definition_path}")
                return path
            else:
                print(
                    f"Error: 'definition.csv' not found in {os.path.join(path, 'map_data')}"
                )
        else:
            print("Error: Invalid directory. Please enter a valid path.")


def get_folder_paths():
    print("Enter the paths to the base game folder and the mod folder:")
    base_game_folder = get_folder_path("Reference folder path (e.g. G:\Steam\steamapps\common\Crusader Kings III\game): ")
    mod_folder = get_folder_path("Mod folder path: ")
    return base_game_folder, mod_folder


def should_ignore_line(parts):
    # Ensure there are enough parts to prevent IndexError
    if len(parts) < 5:
        return True  # Skip malformed lines
    province_name = parts[4]  # provinceName is the 5th value (index 4)
    # Check if province_name contains 'river' or 'impassable' (case-insensitive)
    if re.search(r"(river|impassable)", province_name, re.IGNORECASE):
        return True
    return False  # Do not exclude lines based on capital letters


def read_definition_file(folder):
    province_dict = {}
    file_path = os.path.join(folder, "map_data", "definition.csv")
    print(f"Reading file: {file_path}")
    with open(file_path, "r", encoding="utf-8-sig") as file:
        for line_num, line in enumerate(file, 1):
            original_line = line.rstrip("\n")  # Keep the original line for storage
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue  # Skip empty lines and comments
            parts = line_stripped.split(";")
            if len(parts) < 6:
                print(f"Warning: Skipping malformed line {line_num}: {line_stripped}")
                continue  # Skip malformed lines
            # Check if line should be ignored
            if should_ignore_line(parts):
                continue
            province_id = parts[0]
            province_dict[province_id] = original_line
    print(f"Total provinces read from {file_path}: {len(province_dict)}")
    return province_dict


def compare_definitions(base_def, mod_def):
    differing_lines = {}
    all_province_ids = set(base_def.keys()) | set(mod_def.keys())
    print(f"Total unique province IDs to compare: {len(all_province_ids)}")
    for province_id in all_province_ids:
        base_line = base_def.get(province_id)
        mod_line = mod_def.get(province_id)
        if base_line != mod_line:
            # Use the mod line if available; otherwise, use the base line
            if mod_line is not None:
                differing_lines[province_id] = mod_line
            elif base_line is not None:
                differing_lines[province_id] = base_line
    print(f"Total differences found: {len(differing_lines)}")
    return differing_lines


# 1) Script first compares definition.csv of base game and mod folder
# and creates new_definition.csv containing only the mismatching lines.
def compare_definition(base_game_folder, mod_folder):
    base_definition = read_definition_file(base_game_folder)
    mod_definition = read_definition_file(mod_folder)

    differing_lines = compare_definitions(base_definition, mod_definition)

    if not differing_lines:
        print("No differences found between the definition.csv files.")
    else:
        output_file = "new_definition.csv"
        with open(output_file, "w", encoding="utf-8") as f:
            # Sort by ProvinceID for consistency
            def sort_key(pid):
                pid_clean = pid.lstrip("#")
                return int(pid_clean) if pid_clean.isdigit() else pid_clean

            sorted_ids = sorted(differing_lines.keys(), key=sort_key)
            for province_id in sorted_ids:
                f.write(differing_lines[province_id] + "\n")
        print(f"Differences have been written to {output_file}")


# Function to get the definition data for easy lookup
def read_definition_csv(definition_path):
    province_data = {}
    with open(definition_path, "r") as file:
        reader = csv.reader(file, delimiter=";")
        for row in reader:
            if len(row) < 5 or row[0].startswith("#"):
                continue
            province_id = row[0]
            province_data[province_id] = row
    return province_data


# Function to read locator files and gather province IDs with coordinates
def read_locator_file(locator_path, image_height):
    province_info = {}
    with open(locator_path, "r") as file:
        current_id = None
        for line in file:
            line = line.strip()
            if line.startswith("id="):
                current_id = line.split("=")[1].strip()
            elif line.startswith("position={") and current_id:
                position_data = line.split("{")[1].split("}")[0].strip().split()
                if len(position_data) == 3:
                    x = int(float(position_data[0]))
                    y = image_height - int(float(position_data[2]))
                    province_info[current_id] = (x, y)
                current_id = None
    return province_info


# Function to write data to output CSV
def write_output_csv(output_path, province_data, province_info, locator_file_name):
    with open(output_path, "a", newline="") as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=";")
        csv_writer.writerow([f"Locator File: {locator_file_name}"])
        csv_writer.writerow(["ProvinceID", "R", "G", "B", "X", "Y", "ProvinceName"])
        for province_id, (x, y) in province_info.items():
            if province_id in province_data:
                csv_writer.writerow(
                    province_data[province_id][:4]
                    + [x, y]
                    + [province_data[province_id][4]]
                )
        csv_writer.writerow([])  # Add an empty line for better readability


# 2) Iterate through locator files both in base game and mod folder and
# create big data files mapdata_base.csv and mapdata_modded.csv which
# contain ProvinceID;R;G;B;X;Y;ProvinceName for every locator ID (sorted
# for each file). the X Y coordinates are extracted from the ID and the
# mathematical inversion for the Y-coordinate based on province.png
# height applied. The R;G;B values are read directly from the province
# map using these coordinates, since they do not always match the ones
# provided in definition.csv file
# Main script to read paths and process data
def get_rgb(base_game_folder, mod_folder):
    base_definition_path = os.path.join(base_game_folder, "map_data", "definition.csv")
    mod_definition_path = os.path.join(mod_folder, "map_data", "definition.csv")
    province_image_path = os.path.join(base_game_folder, "map_data", "provinces.png")

    base_locator_files = [
        "building_locators.txt",
        "combat_locators.txt",
        "other_stack_locators.txt",
        "player_stack_locators.txt",
        "siege_locators.txt",
        "special_building_locators.txt",
    ]

    base_locator_folder = os.path.join(
        base_game_folder, "gfx", "map", "map_object_data"
    )
    mod_locator_folder = os.path.join(mod_folder, "gfx", "map", "map_object_data")

    # Read the definition CSVs
    base_province_data = read_definition_csv(base_definition_path)
    mod_province_data = read_definition_csv(mod_definition_path)

    # Get the height of the provinces.png image
    with Image.open(province_image_path) as img:
        image_height = img.height

    # Read locator files and gather province IDs with coordinates
    base_province_info = {}
    mod_province_info = {}

    for locator_file in base_locator_files:
        base_locator_path = os.path.join(base_locator_folder, locator_file)
        mod_locator_path = os.path.join(mod_locator_folder, locator_file)

        if os.path.exists(base_locator_path):
            base_province_info[locator_file] = read_locator_file(
                base_locator_path, image_height
            )
        if os.path.exists(mod_locator_path):
            mod_province_info[locator_file] = read_locator_file(
                mod_locator_path, image_height
            )

    # Create output folder if it doesn't exist
    output_folder = "output"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Write output CSVs
    base_output_path = os.path.join(output_folder, "mapdata_base.csv")
    mod_output_path = os.path.join(output_folder, "mapdata_modded.csv")

    # Clear the output files if they already exist
    open(base_output_path, "w").close()
    open(mod_output_path, "w").close()

    for locator_file, province_info in base_province_info.items():
        write_output_csv(
            base_output_path, base_province_data, province_info, locator_file
        )
    for locator_file, province_info in mod_province_info.items():
        write_output_csv(
            mod_output_path, mod_province_data, province_info, locator_file
        )

    print(f"Output files created in '{output_folder}' folder.")


def get_province_ids(definition_file):
    province_ids = set()
    with open(definition_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if parts:
                province_id = parts[0].strip().lstrip("#")
                if province_id.isdigit():
                    province_ids.add(int(province_id))
    return province_ids


def create_updated_locator_files(
    base_game_path, mod_folder_path, province_ids, locator_files
):
    # Create the output directory
    output_dir = os.path.join(os.getcwd(), "updated_locators")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Created output directory: {output_dir}")

    base_locator_dir = os.path.join(base_game_path, "gfx", "map", "map_object_data")
    mod_locator_dir = os.path.join(mod_folder_path, "gfx", "map", "map_object_data")

    for locator_file in locator_files:
        base_file_path = os.path.join(base_locator_dir, locator_file)
        mod_file_path = os.path.join(mod_locator_dir, locator_file)
        output_file_path = os.path.join(output_dir, locator_file)

        # Copy the base game locator file to the output directory
        if not os.path.isfile(base_file_path):
            print(f"Base locator file not found: {base_file_path}")
            continue
        shutil.copy(base_file_path, output_file_path)
        print(f"Copied {locator_file} to {output_file_path}")

        # If the mod locator file doesn't exist, skip processing
        if not os.path.isfile(mod_file_path):
            print(f"Mod locator file not found: {mod_file_path}. Skipping.")
            continue

        # Read the mod locator file and extract the id blocks for the specified province IDs
        mod_id_blocks = extract_id_blocks(mod_file_path, province_ids)

        # Replace the corresponding id blocks in the output file
        update_locator_file(output_file_path, mod_id_blocks)


def extract_id_blocks(locator_file_path, province_ids):
    id_blocks = {}
    with open(locator_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regular expression to match id blocks
    id_block_pattern = re.compile(r"\{\s*id=(\d+)(.*?)\}", re.DOTALL)

    for match in id_block_pattern.finditer(content):
        id_num = int(match.group(1))
        if id_num in province_ids:
            block = match.group(0)
            # Add " #Modded" after id=xxx line
            modded_block = re.sub(r"(id=\d+)", r"\1 #Modded", block, count=1)
            id_blocks[id_num] = modded_block
    return id_blocks


def update_locator_file(locator_file_path, mod_id_blocks):
    with open(locator_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Function to replace id blocks in the content
    def replace_id_block(match):
        id_num = int(match.group(1))
        if id_num in mod_id_blocks:
            print(f"Updating id block {id_num}")
            return mod_id_blocks[id_num]
        else:
            return match.group(0)

    # Regular expression to match id blocks
    id_block_pattern = re.compile(r"\{\s*id=(\d+)(.*?)\}", re.DOTALL)

    # Replace id blocks
    updated_content = id_block_pattern.sub(replace_id_block, content)

    # Write the updated content back to the file
    with open(locator_file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print(f"Updated locator file: {locator_file_path}")


# 3) Copy all locator files from base folder and replace/add locator IDs
# from mod file, based on the differences from step 1)
def locator_files(base_game_path, mod_folder_path):
    # Locator files to process
    locator_files = [
        "building_locators.txt",
        "combat_locators.txt",
        "other_stack_locators.txt",
        "player_stack_locators.txt",
        "siege_locators.txt",
        "special_building_locators.txt",
    ]

    # Get province IDs from new_definition.csv
    definition_file = os.path.join(os.getcwd(), "new_definition.csv")
    if not os.path.isfile(definition_file):
        print("'new_definition.csv' not found in the current directory.")
        return

    province_ids = get_province_ids(definition_file)
    print(f"Total province IDs to process: {len(province_ids)}")

    # Process locator files
    create_updated_locator_files(
        base_game_path, mod_folder_path, province_ids, locator_files
    )


# Function to parse mapdata CSV files
def parse_mapdata(file_path):
    print(f"Parsing mapdata from '{file_path}'")
    mapdata = {}
    current_section = None
    with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile, delimiter=";")
        for row in reader:
            if not row:
                continue
            if row[0].startswith("Locator File:"):
                current_section = row[0].split(":", 1)[1].strip()
                current_section = current_section.strip().lower()
                print(f"Found section '{current_section}'")
                mapdata[current_section] = {}
                continue
            if row[0] == "ProvinceID":
                continue  # Skip header
            if current_section:
                province_id = row[0]
                try:
                    mapdata[current_section][province_id] = {
                        "R": int(row[1]),
                        "G": int(row[2]),
                        "B": int(row[3]),
                        "X": int(row[4]),
                        "Y": int(row[5]),
                        "ProvinceName": row[6],
                    }
                except Exception as e:
                    print(
                        f"Error parsing row {row} in section '{current_section}': {e}"
                    )
    return mapdata


# Function to remove id blocks from locator content
def remove_blocks(content, blocks_to_remove):
    new_content = ""
    last_index = 0
    for start, end in sorted(blocks_to_remove):
        new_content += content[last_index:start]
        last_index = end
    new_content += content[last_index:]
    return new_content


# Helper function to parse id blocks
def parse_id_blocks(content, instances_start, instances_end):
    id_blocks = []
    index = instances_start
    content_length = instances_end
    while index < content_length:
        # Skip any whitespace
        while index < content_length and content[index].isspace():
            index += 1
        if index >= content_length or content[index] != "{":
            break  # No more blocks
        block_start = index
        brace_count = 1
        index += 1
        while index < content_length and brace_count > 0:
            if content[index] == "{":
                brace_count += 1
            elif content[index] == "}":
                brace_count -= 1
            index += 1
        block_end = index
        block_text = content[block_start:block_end]
        # Extract province_id and is_modded
        id_match = re.search(r"id\s*=\s*(\d+)", block_text)
        if not id_match:
            print(f"No id found in block starting at position {block_start}")
            continue
        province_id = id_match.group(1)
        is_modded = "#Modded" in block_text
        id_blocks.append(
            {
                "text": block_text,
                "province_id": province_id,
                "start": block_start,
                "end": block_end,
                "is_modded": is_modded,
            }
        )
    return id_blocks


# 4) Iterate through the updated locator files, assign each ID their
# R;G;B;X;Y value from the files from step 2), differentiating if the id
# block is from base or from mod (latter is marked with a #Modded in the
# updated locator file). Do another RGB check against the
# provinces_modded.png map in the script directory. If the RGB matches
# the expectations, do nothing. If there is a mismatch, write it in a
# new output file and remove the ID block from the locator file, so it
# can be re-generated by elvain using the map tool
def final():
    # Paths (adjust if necessary)
    # Check if running as a PyInstaller executable
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    locator_dir = os.path.join(script_dir, "updated_locators")
    mapdata_base_path = os.path.join(script_dir, "output", "mapdata_base.csv")
    mapdata_modded_path = os.path.join(script_dir, "output", "mapdata_modded.csv")
    image_path = os.path.join(script_dir, "provinces_modded.png")
    output_file_path = os.path.join(script_dir, "output.txt")

    # Load the image
    try:
        image = Image.open(image_path)
        image_width, image_height = image.size
        print(f"Loaded image '{image_path}' with size {image_width}x{image_height}")
    except Exception:
        print("Error loading image")
        raise

    # Load mapdata files
    mapdata_base = parse_mapdata(mapdata_base_path)
    mapdata_modded = parse_mapdata(mapdata_modded_path)

    # Prepare output file
    output_file = open(output_file_path, "w", encoding="utf-8")

    # Iterate through locator files
    for locator_filename in os.listdir(locator_dir):
        if not locator_filename.endswith(".txt"):
            continue
        locator_path = os.path.join(locator_dir, locator_filename)
        print(f"Processing locator file '{locator_filename}'")
        with open(locator_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Find the instances block
        instances_match = re.search(r"instances\s*=\s*{", content)
        if not instances_match:
            print(f"No instances block found in '{locator_filename}'")
            continue  # No instances block found
        instances_start = instances_match.end()
        brace_count = 1
        index = instances_start
        content_length = len(content)

        # Find the end of the instances block
        while index < content_length and brace_count > 0:
            if content[index] == "{":
                brace_count += 1
            elif content[index] == "}":
                brace_count -= 1
            index += 1
        instances_end = index
        print(
            f"Instances block found from {instances_start} to {instances_end} in '{locator_filename}'"
        )

        # Parse id blocks
        id_blocks = parse_id_blocks(content, instances_start, instances_end)

        if not id_blocks:
            print(f"No id blocks found in '{locator_filename}'")
            continue

        print(f"Found {len(id_blocks)} id blocks in '{locator_filename}'")

        # Process each id block
        blocks_to_remove = []
        for block in id_blocks:
            province_id = block["province_id"]
            is_modded = block["is_modded"]
            mapdata = mapdata_modded if is_modded else mapdata_base

            # Normalize locator filename
            locator_key = os.path.basename(locator_filename).strip().lower()
            print(
                f"Processing ProvinceID {province_id} in '{locator_key}' (Modded: {is_modded})"
            )

            if locator_key not in mapdata:
                output_file.write(f"Locator key '{locator_key}' not found in mapdata\n")
                print(f"Locator key '{locator_key}' not found in mapdata")
                continue

            if province_id not in mapdata[locator_key]:
                output_file.write(
                    f"ProvinceID {province_id} not found in mapdata for '{locator_key}'\n"
                )
                print(
                    f"ProvinceID {province_id} not found in mapdata for '{locator_key}'"
                )
                blocks_to_remove.append((block["start"], block["end"]))
                continue

            province_data = mapdata[locator_key][province_id]
            expected_rgb = (province_data["R"], province_data["G"], province_data["B"])
            x, y = province_data["X"], province_data["Y"]
            province_name = province_data["ProvinceName"]

            # Check if coordinates are within image bounds
            if not (0 <= x < image_width and 0 <= y < image_height):
                output_file.write(
                    f"Coordinates out of bounds for ProvinceID {province_id} ({province_name}) in '{locator_key}'\n"
                )
                print(
                    f"Coordinates out of bounds for ProvinceID {province_id} ({province_name}) in '{locator_key}'"
                )
                blocks_to_remove.append((block["start"], block["end"]))
                continue

            # Get the actual RGB value from the image
            try:
                actual_rgb = image.getpixel((x, y))
                if isinstance(actual_rgb, int):
                    # Grayscale image, replicate value across RGB channels
                    actual_rgb = (actual_rgb, actual_rgb, actual_rgb)
                elif len(actual_rgb) == 4:
                    actual_rgb = actual_rgb[:3]  # Ignore alpha channel
                elif len(actual_rgb) == 1:
                    actual_rgb = (actual_rgb[0], actual_rgb[0], actual_rgb[0])
            except Exception as e:
                output_file.write(
                    f"Error getting pixel for ProvinceID {province_id} ({province_name}): {e}\n"
                )
                print(
                    f"Error getting pixel for ProvinceID {province_id} ({province_name}): {e}"
                )
                blocks_to_remove.append((block["start"], block["end"]))
                continue

            # Compare RGB values
            if actual_rgb != expected_rgb:
                output_file.write(
                    f"Mismatch in '{locator_key}' for ProvinceID {province_id} ({province_name}): Expected RGB {expected_rgb}, got {actual_rgb}\n"
                )
                print(
                    f"Mismatch for ProvinceID {province_id} ({province_name}): Expected RGB {expected_rgb}, got {actual_rgb}"
                )
                blocks_to_remove.append((block["start"], block["end"]))
            else:
                print(
                    f"ProvinceID {province_id} ({province_name}) matches expected RGB {expected_rgb}"
                )

        # Remove the blocks from content
        if blocks_to_remove:
            print(
                f"Removing {len(blocks_to_remove)} id blocks from '{locator_filename}'"
            )
            content = remove_blocks(content, blocks_to_remove)
            # Write the updated content back to the locator file
            with open(locator_path, "w", encoding="utf-8") as file:
                file.write(content)
        else:
            print(f"No id blocks to remove from '{locator_filename}'")

    output_file.close()
    print("Processing complete. Check 'output.txt' for details.")


def main():
    try:
        base_game_folder, mod_folder = get_folder_paths()
        compare_definition(base_game_folder, mod_folder)
        get_rgb(base_game_folder, mod_folder)
        locator_files(base_game_folder, mod_folder)
        final()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
