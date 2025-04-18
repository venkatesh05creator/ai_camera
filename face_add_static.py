import cv2
import numpy as np
import tensorflow as tf # Or import tflite_runtime.interpreter as tflite
import json
import time
import os
import argparse # To handle command-line arguments

from config import MODEL_CONFIGS

CASCADE_PATH = 'models/haarcascade_frontalface_default.xml' # Common cascade path

def run_static_face_add(model_name: str, image_paths: list):
    """
    Detects faces in static images, generates embeddings using the specified
    model, and adds them to the corresponding datastore.

    Args:
        model_name (str): The name of the model configuration to use.
        image_paths (list): A list of paths to image files.
    """
    # --- 1. Load Configuration ---
    if model_name not in MODEL_CONFIGS:
        print(f"Error: Model configuration '{model_name}' not found.")
        print(f"Available configurations: {list(MODEL_CONFIGS.keys())}")
        return

    config = MODEL_CONFIGS[model_name]
    model_path = config['model_path']
    datastore_path = config['datastore_path']
    input_size = config['input_size']
    image_mean = config['image_mean']
    image_std = config['image_std']

    print(f"--- Using Model for Static Add: {model_name} ---")
    print(f"Model Path: {model_path}")
    print(f"Datastore Target: {datastore_path}")
    print(f"Input Size: {input_size}x{input_size}")
    print(f"------------------------------------------")

    # --- 2. Load TFLite Model ---
    try:
        # Use TFLite runtime if available
        # import tflite_runtime.interpreter as tflite
        # interpreter = tflite.Interpreter(model_path=model_path)

        # Or use full TensorFlow
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading TFLite model from {model_path}: {e}")
        return

    # Get input and output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    input_dtype = input_details[0]['dtype']
    # Get expected output dimension
    expected_output_dim = output_details[0]['shape'][-1]
    print(f"Model expects embeddings of dimension: {expected_output_dim}")


    # --- 3. Load Face Detector ---
    try:
        if not os.path.exists(CASCADE_PATH):
             raise IOError(f"Haar Cascade file not found at {CASCADE_PATH}")
        face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if face_cascade.empty():
            raise IOError(f"Cannot load Haar Cascade classifier from {CASCADE_PATH}")
        print("Face detector loaded.")
    except Exception as e:
        print(f"Error loading face detector: {e}")
        return

    # --- 4. Initialize and Load Datastore ---
    datastore = {}

    # Function to save datastore (defined inside to access datastore_path)
    def save_datastore_local():
        # Convert numpy arrays to lists for JSON serialization
        serializable_datastore = {k: v.tolist() if isinstance(v, np.ndarray) else v
                                  for k, v in datastore.items()}
        try:
            with open(datastore_path, 'w') as f:
                json.dump(serializable_datastore, f, indent=4)
            print(f"\nDatastore saved successfully to {datastore_path}")
        except IOError as e:
            print(f"\nError saving datastore to {datastore_path}: {e}")
        except TypeError as e:
             print(f"\nError serializing datastore: {e}")

    # Load existing datastore if available
    try:
        if os.path.exists(datastore_path):
             with open(datastore_path, 'r') as f:
                 loaded_data = json.load(f)
                 # Convert lists back to numpy arrays after loading
                 datastore = {k: np.array(v, dtype=np.float32) for k, v in loaded_data.items()}
                 print(f"Loaded existing datastore with {len(datastore)} entries from {datastore_path}")
        else:
            print(f"Datastore file '{datastore_path}' not found. Creating a new one upon saving.")
            datastore = {}
    except json.JSONDecodeError:
        print(f"Error reading {datastore_path}. File might be corrupted. Starting with an empty datastore.")
        datastore = {}
    except Exception as e:
         print(f"An unexpected error occurred loading {datastore_path}: {e}. Starting empty.")
         datastore = {}

    # --- 5. Process Images ---
    print("\nProcessing images...")
    faces_added = 0

    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"Warning: Image file not found: {image_path}. Skipping.")
            continue

        print(f"\n--- Processing image: {image_path} ---")

        # Load image
        try:
            frame = cv2.imread(image_path)
            if frame is None:
                print(f"Warning: Could not read image file: {image_path}. Skipping.")
                continue
        except Exception as e:
            print(f"Warning: Error reading image {image_path}: {e}. Skipping.")
            continue

        # --- Face Detection ---
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Adjust scaleFactor and minNeighbors for potentially different image quality/sizes
        faces = face_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1, # Might need adjustment (e.g., 1.05 for smaller faces)
            minNeighbors=5,  # Might need adjustment (lower for harder detections)
            minSize=(40, 40) # Adjust minSize based on expected face size in static images
        )

        if len(faces) == 0:
            print("No faces detected in this image.")
            continue
        else:
            print(f"Detected {len(faces)} face(s) in this image.")

        # --- Process Each Detected Face ---
        for i, (x, y, w, h) in enumerate(faces):
            print(f"\nProcessing Face #{i+1} in {os.path.basename(image_path)}...")

            # Crop the face region
            padding = 10 # Adjust padding if needed
            face_roi = frame[max(0, y-padding):min(frame.shape[0], y+h+padding),
                             max(0, x-padding):min(frame.shape[1], x+w+padding)]

            if face_roi.size == 0:
                print("Warning: Could not crop face ROI properly for this face. Skipping.")
                continue

            # --- Show the specific face and get name ---
            name_input = "" # Reset name for each face
            try:
                face_window_name = f"Face #{i+1} from {os.path.basename(image_path)}"
                cv2.imshow(face_window_name, face_roi)
                print(f"-> Showing Face #{i+1}. Look at the window '{face_window_name}'.")
                name_input = input(f"Enter name for Face #{i+1} (leave blank to skip): ").strip()
                print("   Press any key in the WINDOW to continue...")
                cv2.waitKey(0) # Wait for key press in the window
                cv2.destroyWindow(face_window_name)
            except Exception as e:
                print(f"Warning: Could not display face window or get input: {e}")
                cv2.destroyAllWindows() # Close any open windows in case of error
                continue # Skip this face

            # --- Preprocessing ---
            try:
                # 1. Resize
                resized_face = cv2.resize(face_roi, (input_size, input_size))
                # 2. BGR to RGB
                rgb_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2RGB)
                # 3. Normalize
                normalized_face = (rgb_face.astype(np.float32) - image_mean) / image_std
                # 4. Add batch dimension
                input_data = np.expand_dims(normalized_face, axis=0)
                # 5. Ensure correct dtype
                if input_data.dtype != input_dtype:
                    input_data = input_data.astype(input_dtype)
            except Exception as e:
                print(f"Error during preprocessing for Face #{i+1}: {e}. Skipping this face.")
                continue

            # --- Inference ---
            try:
                interpreter.set_tensor(input_details[0]['index'], input_data)
                interpreter.invoke()
                embeddings = interpreter.get_tensor(output_details[0]['index'])
                embedding_vector = embeddings[0] # Get the 1D vector
            except Exception as e:
                print(f"Error during inference for Face #{i+1}: {e}. Skipping this face.")
                continue

            # --- Check Dimension and Save ---
            if embedding_vector.shape[0] != expected_output_dim:
                 print(f"Error: Generated embedding dim ({embedding_vector.shape[0]}) doesn't match model output dim ({expected_output_dim}). Not saving.")
                 continue

            # Use the name entered earlier
            name = name_input
            if not name:
                print("Skipping saving this face.")
            elif name in datastore:
                overwrite = input(f"Name '{name}' already exists in {datastore_path}. Overwrite? (y/n): ").strip().lower()
                if overwrite == 'y':
                    datastore[name] = embedding_vector
                    print(f"Embedding for '{name}' updated.")
                    faces_added += 1
                else:
                    print("Not overwriting. Face not saved.")
            else:
                datastore[name] = embedding_vector
                print(f"Embedding for '{name}' added.")
                faces_added += 1

    # --- End of loop for faces in one image ---
    # Optionally show the image with all detected faces marked (already done with rectangles earlier)
    # cv2.imshow(f"Detected Faces in {os.path.basename(image_path)}", display_frame)
    # cv2.waitKey(1000) # Show for 1 second
    # cv2.destroyWindow(f"Detected Faces in {os.path.basename(image_path)}")


    # --- End of loop for all images ---

    # --- Final Save ---
    if faces_added > 0:
        save_datastore_local() # Use the local save function
    else:
        print("\nNo new faces were added or updated in the datastore.")

    cv2.destroyAllWindows() # Ensure any remaining windows are closed
    print("\nProcessing complete.")


# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect faces in static images, generate embeddings using a specified model, and add to datastore.")

    parser.add_argument(
        "-m", "--model",
        type=str,
        default='facenet_lite', # Default to the model used in the original script
        choices=MODEL_CONFIGS.keys(),
        help=f"Name of the model configuration to use. Choices: {list(MODEL_CONFIGS.keys())}"
    )
    parser.add_argument('image_paths', metavar='IMAGE_PATH', type=str, nargs='+',
                        help='Paths to one or more image files (.jpg, .jpeg, .png)')

    args = parser.parse_args()

    # Make sure the default model choice exists if user doesn't specify
    if args.model not in MODEL_CONFIGS:
         print(f"Error: Default model '{args.model}' not found in configurations. Please specify a valid model.")
         exit()

    run_static_face_add(args.model, args.image_paths)