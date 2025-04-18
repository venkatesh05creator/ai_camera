import json

# Load existing datastore
try:
    with open('datastore.json', 'r') as f:
        datastore = json.load(f)
except FileNotFoundError:
    print("Datastore file not found.")
    exit()

# Remove the unwanted key
key_to_remove = "(venv) chaitanyakartik@Chaitanyas-MacBook-Air:~/Projects/face_recognition_test $ main2.py"
if key_to_remove in datastore:
    del datastore[key_to_remove]
    print(f"Removed key: {key_to_remove}")
else:
    print(f"Key not found: {key_to_remove}")

# Save the updated datastore back to the file
with open('datastore.json', 'w') as f:
    json.dump(datastore, f)

print("Datastore updated successfully.")