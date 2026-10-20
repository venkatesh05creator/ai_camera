import json
import os

datastore_path = 'datastore/datastore_512_Dim.json'
output_datastore_path = 'datastore.json'
key_to_remove = "Chaitanya"

# Load existing datastore safely
datastore = {}
if os.path.exists(datastore_path):
    try:
        with open(datastore_path, 'r') as f:
            datastore = json.load(f)
        print(f"Datastore loaded successfully from: {datastore_path}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {datastore_path}: {e}")
        exit()
    except FileNotFoundError:
        print(f"Datastore file not found at: {datastore_path}")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while loading {datastore_path}: {e}")
        exit()
else:
    print(f"Datastore file does not exist at: {datastore_path}. Starting with an empty datastore.")

# Remove the unwanted key
if key_to_remove in datastore:
    del datastore[key_to_remove]
    print(f"Removed key: {key_to_remove}")
else:
    print(f"Key not found: {key_to_remove}")

# Save the updated datastore back to a *different* file
try:
    # Ensure the directory for the output file exists
    output_directory = os.path.dirname(output_datastore_path)
    if output_directory and not os.path.exists(output_directory):
        os.makedirs(output_directory)

    with open(output_datastore_path, 'w') as f:
        json.dump(datastore, f, indent=4)  # Added indent for better readability
    print(f"Datastore updated and saved to: {output_datastore_path}")
except IOError as e:
    print(f"Error writing updated datastore to {output_datastore_path}: {e}")
except Exception as e:
    print(f"An unexpected error occurred while saving to {output_datastore_path}: {e}")

print("Datastore update process completed.")