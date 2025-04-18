import cv2
import numpy as np
import tensorflow as tf # Or import tflite_runtime.interpreter as tflite
import json
import time
import os # Added for path checking
import argparse # Added for command-line arguments

from config import MODEL_CONFIGS

CASCADE_PATH = 'models/haarcascade_frontalface_default.xml' # Common cascade path

def run_face_saving(model_name: str):
    """
    Captures video, detects faces, and saves embeddings for a specified model.

    Args:
        model_name (str): The name of the model configuration to use
                          (e.g., 'facenet', 'facenet_lite').
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

    print(f"--- Using Model for Saving: {model_name} ---")
    print(f"Model Path: {model_path}")
    print(f"Datastore Target: {datastore_path}")
    print(f"Input Size: {input_size}x{input_size}")
    print(f"--------------------------------------")

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
    # Get expected output dimension (for potential future checks)
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
                json.dump(serializable_datastore, f, indent=4) # Use indent for readability
            print(f"Datastore saved to {datastore_path}")
        except IOError as e:
            print(f"Error saving datastore to {datastore_path}: {e}")
        except TypeError as e:
             print(f"Error serializing datastore (maybe non-list/array data?): {e}")


    # Load existing datastore if available
    try:
        # Check if file exists before trying to open
        if os.path.exists(datastore_path):
            with open(datastore_path, 'r') as f:
                loaded_data = json.load(f)
                # Convert lists back to numpy arrays after loading
                datastore = {k: np.array(v, dtype=np.float32) for k, v in loaded_data.items()}
                print(f"Loaded existing datastore from {datastore_path} with {len(datastore)} entries.")
        else:
             print(f"Datastore file '{datastore_path}' not found. Creating a new one upon saving.")
             datastore = {} # Start empty
    except json.JSONDecodeError:
        print(f"Error reading {datastore_path}. File might be corrupted. Starting with an empty datastore.")
        datastore = {}
    except Exception as e: # Catch other potential loading errors
         print(f"An unexpected error occurred loading {datastore_path}: {e}. Starting empty.")
         datastore = {}


    # --- 5. Start Video Capture ---
    cap = cv2.VideoCapture(0) # 0 for default laptop camera
    if not cap.isOpened():
        print("Error: Could not open video capture device.")
        return

    print("\nStarting video stream...")
    print("Center face in rectangle.")
    print("Press 's' in the window to save the current face.")
    print("Press 'q' in the window to quit.\n")

    face_detected_in_frame = False
    current_frame_for_save = None
    face_coords = None
    window_name = 'Save Face - Press S to Save, Q to Quit'

    # --- 6. Saving Loop ---
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to grab frame.")
            time.sleep(0.5)
            continue

        display_frame = frame.copy() # Work on a copy for display

        # --- Face Detection ---
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60) # Adjust if needed
        )

        if len(faces) > 0:
            face_detected_in_frame = True
            # Use the first detected face
            (x, y, w, h) = faces[0]
            face_coords = (x, y, w, h) # Store coordinates

            # Draw rectangle on the display frame
            cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # Keep a reference to the original frame for saving if 's' is pressed
            current_frame_for_save = frame.copy()
        else:
            face_detected_in_frame = False
            current_frame_for_save = None
            face_coords = None

        # --- Display the resulting frame ---
        cv2.imshow(window_name, display_frame)

        # --- Check for Key Press ---
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("Exiting...")
            break
        elif key == ord('s'):
            if face_detected_in_frame and current_frame_for_save is not None and face_coords is not None:
                print("Face detected! Proceeding to save...")

                # --- Crop and Preprocess the face from the saved frame ---
                (x, y, w, h) = face_coords
                padding = 10 # Consider making padding relative
                face_roi = current_frame_for_save[max(0, y-padding):min(current_frame_for_save.shape[0], y+h+padding),
                                                  max(0, x-padding):min(current_frame_for_save.shape[1], x+w+padding)]

                if face_roi.size == 0:
                    print("Error: Could not crop face ROI properly. Try again.")
                    continue

                try:
                    # 1. Resize using model's input size
                    resized_face = cv2.resize(face_roi, (input_size, input_size))
                    # 2. BGR to RGB
                    rgb_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2RGB)
                    # 3. Normalize using model's mean/std
                    normalized_face = (rgb_face.astype(np.float32) - image_mean) / image_std
                    # 4. Add batch dimension
                    input_data = np.expand_dims(normalized_face, axis=0)
                    # 5. Ensure correct dtype
                    if input_data.dtype != input_dtype:
                        input_data = input_data.astype(input_dtype)

                    # --- Inference ---
                    interpreter.set_tensor(input_details[0]['index'], input_data)
                    interpreter.invoke()
                    embeddings = interpreter.get_tensor(output_details[0]['index'])
                    embedding_vector = embeddings[0] # Get the 1D vector

                    # --- Get Name and Save ---
                    # Temporarily hide the OpenCV window to prevent input focus issues
                    cv2.destroyWindow(window_name)
                    print("\nWindow closed temporarily for input.")
                    print(f"(Saving to: {datastore_path})") # Remind user which file is being updated

                    name = input("Enter name for this face (leave blank to cancel): ").strip()

                    if name:
                        if name in datastore:
                            overwrite = input(f"'{name}' already exists. Overwrite? (y/n): ").lower()
                            if overwrite != 'y':
                                print("Save cancelled.")
                                continue # Go back to capturing

                        # Check if embedding dim matches model output dim (sanity check)
                        if embedding_vector.shape[0] != expected_output_dim:
                             print(f"Error: Generated embedding dim ({embedding_vector.shape[0]}) doesn't match model output dim ({expected_output_dim}). Not saving.")
                             continue

                        datastore[name] = embedding_vector # Store as numpy array
                        save_datastore_local() # Use the local save function
                        print(f"Face embedding saved/updated for '{name}'.")
                        # Optionally break after successful save
                        # break
                    else:
                        print("No name entered. Face not saved.")
                    # Need to re-show window if we didn't break
                    # (Recreated implicitly at start of next loop iteration if we don't break)


                except Exception as e:
                    print(f"Error during processing, inference, or saving: {e}")
                    print("Please try capturing again.")
                    # Ensure window is eventually closed if error happens before destroyWindow
                    cv2.destroyAllWindows()


            else:
                print("No face detected in the frame when 's' was pressed. Please position face and try again.")


    # --- Release resources ---
    cap.release()
    cv2.destroyAllWindows() # Ensure all windows are closed
    print("Resources released.")


# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Face Saving Tool")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default='facenet', # Default model
        choices=MODEL_CONFIGS.keys(), # Allow only configured models
        help=f"Name of the face recognition model configuration to use for generating embeddings. Choices: {list(MODEL_CONFIGS.keys())}"
    )
    args = parser.parse_args()

    run_face_saving(args.model)