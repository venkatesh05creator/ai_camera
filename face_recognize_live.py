import cv2
import numpy as np
import tensorflow as tf # Or import tflite_runtime.interpreter as tflite
import time
import json
import os # Added for path joining
import argparse # Added for command-line arguments

from config import MODEL_CONFIGS

CASCADE_PATH = 'models/haarcascade_frontalface_default.xml' # Keep cascade path common for now
RECOGNITION_THRESHOLD = 0.9 # Adjust this threshold (might need tuning per model)

def run_face_recognition(model_name: str):
    """
    Runs live face recognition using the specified model.

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
    # output_size = config['output_size'] # Needed if used later, e.g., for checks
    image_mean = config['image_mean']
    image_std = config['image_std']

    print(f"--- Using Model: {model_name} ---")
    print(f"Model Path: {model_path}")
    print(f"Datastore: {datastore_path}")
    print(f"Input Size: {input_size}x{input_size}")
    print(f"-----------------------------")


    # --- 2. Load TFLite Model ---
    try:
        # Use TFLite runtime if available (preferred for inference)
        # import tflite_runtime.interpreter as tflite
        # interpreter = tflite.Interpreter(model_path=model_path)

        # Or use full TensorFlow
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading TFLite model from {model_path}: {e}")
        return # Exit the function if model loading fails

    # Get input and output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Check input details (optional but good practice)
    print("Input details:", input_details)
    print("Output details:", output_details)
    # Ensure input tensor is float32
    input_dtype = input_details[0]['dtype']
    # Get expected output dimension
    expected_output_dim = output_details[0]['shape'][-1] # Last element of the shape tuple
    print(f"Expected embedding dimension: {expected_output_dim}")
    if input_dtype != np.float32:
        print(f"Warning: Expected input dtype float32, but got {input_dtype}. Adjusting preprocessing.")

    # --- 3. Load Datastore ---
    try:
        with open(datastore_path, 'r') as f:
            datastore = json.load(f)
            # Convert lists back to numpy arrays **immediately** after loading
            datastore = {k: np.array(v, dtype=np.float32) for k, v in datastore.items()}
        print(f"Loaded datastore from {datastore_path} with {len(datastore)} entries.")
    except FileNotFoundError:
        print(f"Warning: Datastore file '{datastore_path}' not found. Starting with empty datastore.")
        datastore = {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {datastore_path}. Starting with empty datastore.")
        datastore = {}
    except Exception as e: # Catch other potential errors during loading/conversion
        print(f"Error loading or processing datastore {datastore_path}: {e}. Starting with empty datastore.")
        datastore = {}


    # --- 4. Load Face Detector ---
    try:
        if not os.path.exists(CASCADE_PATH):
             raise IOError(f"Haar Cascade file not found at {CASCADE_PATH}")
        face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if face_cascade.empty():
            raise IOError(f"Cannot load Haar Cascade classifier from {CASCADE_PATH}")
        print("Face detector loaded.")
    except Exception as e:
        print(f"Error loading face detector: {e}")
        return # Exit the function if detector loading fails

    # --- 5. Start Video Capture ---
    cap = cv2.VideoCapture(0) # 0 for default laptop camera
    if not cap.isOpened():
        print("Error: Could not open video capture device.")
        return # Exit the function if camera fails
    print("\nStarting video stream...")
    print("Press 'q' in the window to quit.\n")

    # --- 6. Recognition Loop ---
    last_logged_name = None
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to grab frame.")
            time.sleep(0.5)
            continue

        display_frame = frame.copy() # Work on a copy for display/drawing
        recognized_name_in_frame = None # Track recognition within this frame

        # --- Face Detection ---
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60) # Keep minimum detection size reasonable
        )

        # --- Process Detected Faces ---
        for (x, y, w, h) in faces:
            # Draw rectangle around the face
            cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2) # Thinner rectangle

            # Crop the face region (use original frame for accurate data)
            padding = 10 # Consider making padding relative to face size?
            face_roi = frame[max(0, y-padding):min(frame.shape[0], y+h+padding),
                             max(0, x-padding):min(frame.shape[1], x+w+padding)]

            if face_roi.size == 0:
                continue

            # --- Preprocessing ---
            try:
                # 1. Resize using the model's specific input size
                resized_face = cv2.resize(face_roi, (input_size, input_size))
                # 2. BGR to RGB
                rgb_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2RGB)
                # 3. Normalize using model's specific mean/std
                normalized_face = (rgb_face.astype(np.float32) - image_mean) / image_std
                # 4. Add batch dimension
                input_data = np.expand_dims(normalized_face, axis=0)
                # 5. Ensure correct dtype (if necessary)
                if input_data.dtype != input_dtype:
                    input_data = input_data.astype(input_dtype)

            except Exception as e:
                print(f"Error during preprocessing: {e}")
                continue

            # --- Inference & Comparison ---
            try:
                # Inference
                interpreter.set_tensor(input_details[0]['index'], input_data)
                interpreter.invoke()
                current_embedding = interpreter.get_tensor(output_details[0]['index'])[0]

                # Compare with datastore
                min_distance = float('inf')
                recognized_name = None

                if not datastore:
                    # Display "Unknown" if datastore is empty
                    recognized_name = "Unknown (No faces stored)"
                else:
                    for name, stored_embedding in datastore.items(): # Directly use numpy array now
                        # Ensure stored_embedding is a NumPy array (already done at load)
                        # Handle potential loading issues (if not saved correctly)
                        # try:
                        #      stored_embedding = np.array(stored_embedding_list, dtype=np.float32)
                        # except ValueError:
                        #      print(f"Warning: Skipping invalid embedding format for {name}")
                        #      continue

                        # --- ADD DIMENSION CHECK ---
                        if stored_embedding.shape[0] != expected_output_dim:
                           print(f"Warning: Skipping '{name}' due to mismatched embedding size (Stored: {stored_embedding.shape[0]}, Expected: {expected_output_dim})")
                           continue
                        # --- END DIMENSION CHECK ---


                        distance = np.linalg.norm(current_embedding - stored_embedding)

                        if distance < min_distance:
                            min_distance = distance
                            if distance < RECOGNITION_THRESHOLD:
                                recognized_name = name

                    if recognized_name is None and min_distance != float('inf'):
                        recognized_name = "Unknown" # Label faces not matching threshold as Unknown
                    elif min_distance == float('inf'): # Handles empty or skipped datastore entries
                         recognized_name = "Unknown (DB issue?)"


                recognized_name_in_frame = recognized_name # Store the result for this frame

                # Calculate confidence percentage (adjust denominator if threshold is not 1.0 based)
                # This calculation assumes lower distance is better, capping at the threshold
                confidence = max(0.0, 100.0 * (1.0 - min_distance / RECOGNITION_THRESHOLD))
                if min_distance > RECOGNITION_THRESHOLD:
                    confidence = max(0.0, 100.0 * (1.0 - min_distance)) # Show distance-based 'unconfidence' for unknowns

                # Prepare display text
                display_text = f"{recognized_name_in_frame}"
                if recognized_name_in_frame not in ["Unknown", "Unknown (No faces stored)", "Unknown (DB issue?)"]:
                    display_text += f" ({confidence:.1f}%)"
                # Optionally show distance for unknowns
                # else:
                #     display_text += f" (Dist: {min_distance:.2f})"


                # Display recognized name and confidence above the box
                cv2.putText(display_frame, display_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2) # Smaller font

                # Only process the first detected face for simplicity in logging
                # If you want to log all recognized faces, remove this break
                # and adjust the debounced logging logic
                break

            except Exception as e:
                print(f"Error during inference or comparison: {e}")
                # Optional: Print details for debugging
                # print(f"Input data shape: {input_data.shape}, dtype: {input_data.dtype}")

        # --- Debounced Logging ---
        if recognized_name_in_frame != last_logged_name:
            if recognized_name_in_frame and recognized_name_in_frame not in ["Unknown", "Unknown (No faces stored)", "Unknown (DB issue?)"]:
                print(f"--- Recognized: {recognized_name_in_frame} ---")
            # Update last logged name regardless
            last_logged_name = recognized_name_in_frame


        # --- Display the resulting frame ---
        cv2.imshow('Face Recognition Stream - Press Q to Quit', display_frame)

        # --- Exit condition ---
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Exiting...")
            break

    # --- Release resources ---
    cap.release()
    cv2.destroyAllWindows()
    print("Resources released.")


# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Face Recognition")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default='facenet', # Default model
        choices=MODEL_CONFIGS.keys(), # Allow only configured models
        help=f"Name of the face recognition model configuration to use. Choices: {list(MODEL_CONFIGS.keys())}"
    )
    args = parser.parse_args()

    run_face_recognition(args.model)