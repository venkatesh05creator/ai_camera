import cv2
import numpy as np
import tensorflow as tf
import json
import os
import argparse
from typing import Dict, Any, Tuple, Optional, List

# ==================================
# 1. Model Configurations
# ==================================

from config import MODEL_CONFIGS

# Common constant
CASCADE_PATH = 'models/haarcascade_frontalface_default.xml'

# ==================================
# 2. Helper Functions (Minimal)
# ==================================

def preprocess_face(face_roi: np.ndarray, config: Dict[str, Any], input_dtype: np.dtype) -> Optional[np.ndarray]:
    """Preprocesses the face ROI for model inference based on config."""
    if face_roi.size == 0:
        print("Warning: Received empty face ROI for preprocessing.")
        return None
    try:
        input_size = config['input_size']
        image_mean = config['image_mean']
        image_std = config['image_std']

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
        return input_data
    except Exception as e:
        print(f"Error during preprocessing: {e}")
        return None

def find_match(current_embedding: np.ndarray, datastore: Dict[str, np.ndarray], threshold: float, expected_output_dim: int) -> Tuple[Optional[str], float]:
    """Compares the current embedding against the datastore to find the best match."""
    if not datastore:
        return "Unknown (No faces stored)", float('inf') # No datastore to compare against

    # Check current embedding dimension consistency
    if current_embedding.shape[0] != expected_output_dim:
        print(f"Error: Current embedding dimension ({current_embedding.shape[0]}) "
              f"doesn't match model's expected output dimension ({expected_output_dim}). Cannot compare.")
        return "Error (Emb Dim Mismatch)", float('inf')

    min_distance = float('inf')
    best_match_name = None

    for name, stored_embedding in datastore.items():
        # Ensure stored embedding is valid and has the correct dimension
        if not isinstance(stored_embedding, np.ndarray) or stored_embedding.size == 0:
             print(f"Warning: Skipping invalid datastore entry for '{name}'.")
             continue
        if stored_embedding.shape[0] != expected_output_dim:
            print(f"Warning: Skipping '{name}'. Stored embedding dimension ({stored_embedding.shape[0]}) "
                  f"doesn't match model's expected output dimension ({expected_output_dim}).")
            continue

        # Calculate L2 distance (Euclidean distance)
        distance = np.linalg.norm(current_embedding - stored_embedding)

        if distance < min_distance:
            min_distance = distance
            best_match_name = name

    # Determine final recognized name based on threshold
    if min_distance < threshold:
        recognized_name = best_match_name
    elif best_match_name is not None: # A closest match was found, but above threshold
        recognized_name = "Unknown"
    else: # No valid matches found at all (e.g., all skipped due to errors)
        recognized_name = "Unknown (DB issue?)"


    return recognized_name, min_distance

# ==================================
# 3. Main Recognition Function
# ==================================

def recognize_faces_in_images(model_name: str, image_paths: List[str]):
    """
    Loads a specified face recognition model and processes a list of static images.

    Args:
        model_name (str): The name of the model configuration to use (must be a key in MODEL_CONFIGS).
        image_paths (List[str]): A list of paths to the image files to process.
    """
    # --- 1. Load Configuration ---
    if model_name not in MODEL_CONFIGS:
        print(f"Error: Model configuration '{model_name}' not found.")
        print(f"Available configurations: {list(MODEL_CONFIGS.keys())}")
        return

    config = MODEL_CONFIGS[model_name]
    model_path = config['model_path']
    datastore_path = config['datastore_path']
    recognition_threshold = config['recognition_threshold']
    # Other config values (input_size, mean, std) used in helper or later

    print(f"--- Using Model: {model_name} ---")
    print(f"Model Path: {model_path}")
    print(f"Datastore: {datastore_path}")
    print(f"Input Size: {config['input_size']}x{config['input_size']}")
    print(f"Threshold: {recognition_threshold}")
    print(f"-----------------------------")

    # --- 2. Load TFLite Model ---
    try:
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        print("Model loaded successfully.")
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        input_dtype = input_details[0]['dtype']
        # Determine expected output dimension FOR THE LOADED MODEL
        expected_output_dim = output_details[0]['shape'][-1]
        print(f"Model expects input dtype: {input_dtype}, output dimension: {expected_output_dim}")
    except Exception as e:
        print(f"Error loading TFLite model from {model_path}: {e}")
        return # Exit if model loading fails

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
        return # Exit if detector loading fails

    # --- 4. Load Datastore ---
    datastore = {}
    try:
        with open(datastore_path, 'r') as f:
            loaded_data = json.load(f)
            # Convert lists back to numpy arrays, ensuring float32 type
            datastore = {
                k: np.array(v, dtype=np.float32)
                for k, v in loaded_data.items()
            }
        print(f"Loaded datastore with {len(datastore)} entries from {datastore_path}")
        # Optional: Check first entry dimension against model output dim
        if datastore:
            first_key = next(iter(datastore))
            first_emb_dim = datastore[first_key].shape[0]
            if first_emb_dim != expected_output_dim:
                 print(f"\nWarning: Datastore embedding dimension ({first_emb_dim}) "
                       f"might not match model's expected output dimension ({expected_output_dim}). "
                       f"Ensure datastore was created with the correct model.\n")

    except FileNotFoundError:
        print(f"Warning: Datastore file '{datastore_path}' not found. Recognition will default to 'Unknown'.")
    except json.JSONDecodeError:
        print(f"Warning: Error decoding JSON from '{datastore_path}'. Recognition will default to 'Unknown'.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred loading datastore '{datastore_path}': {e}")

    # --- 5. Process Images ---
    print("\nStarting image processing...")
    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"Warning: Image file not found: {image_path}. Skipping.")
            continue

        print(f"\n--- Processing image: {image_path} ---")

        # Load image
        try:
            frame = cv2.imread(image_path)
            if frame is None:
                print(f"Warning: Could not read image file (frame is None): {image_path}. Skipping.")
                continue
        except Exception as e:
            print(f"Warning: Error reading image {image_path}: {e}. Skipping.")
            continue

        display_frame = frame.copy() # Work on a copy

        # --- Face Detection ---
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60) # Make this configurable? For now, fixed.
        )

        if not faces:
            print("No faces detected in this image.")
        else:
            print(f"Detected {len(faces)} face(s). Recognizing...")

        # --- Process Each Detected Face ---
        for (x, y, w, h) in faces:
            # Crop the face region
            padding = 10 # Fixed padding
            face_roi = frame[max(0, y - padding):min(frame.shape[0], y + h + padding),
                             max(0, x - padding):min(frame.shape[1], x + w + padding)]

            if face_roi.size == 0:
                print("Warning: Could not crop face ROI properly for a face. Skipping recognition.")
                # Draw error on frame
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(display_frame, "Crop Error", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                continue

            # --- Preprocessing ---
            input_data = preprocess_face(face_roi, config, input_dtype)
            if input_data is None:
                print("Warning: Preprocessing failed for a face. Skipping recognition.")
                # Draw error on frame
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(display_frame, "Preproc Error", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                continue

            # --- Inference ---
            try:
                interpreter.set_tensor(input_details[0]['index'], input_data)
                interpreter.invoke()
                current_embedding = interpreter.get_tensor(output_details[0]['index'])[0]
                current_embedding = current_embedding.astype(np.float32) # Ensure correct type
            except Exception as e:
                print(f"Error during inference for a face: {e}")
                # Draw error on frame
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(display_frame, "Inference Error", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                continue

            # --- Comparison & Matching ---
            try:
                recognized_name, min_distance = find_match(current_embedding, datastore, recognition_threshold, expected_output_dim)

                # Prepare display text
                display_text = f"{recognized_name}"
                if recognized_name not in ["Unknown", "Unknown (No faces stored)", "Unknown (DB issue?)", "Error (Emb Dim Mismatch)"]:
                    # Calculate confidence only for successful recognitions below threshold
                    confidence = max(0.0, 100.0 * (1.0 - min_distance / recognition_threshold))
                    display_text += f" ({confidence:.1f}%)"
                # Optionally add distance for Unknown matches
                # elif recognized_name == "Unknown":
                #     display_text += f" (Dist: {min_distance:.2f})"

                # Display results on frame
                box_color = (0, 255, 0) if not display_text.startswith("Error") else (0, 0, 255)
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), box_color, 2) # Thinner box
                # Adjust text position slightly
                text_y = y - 10 if y > 20 else y + h + 15
                cv2.putText(display_frame, display_text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2) # Smaller font
                print(f"  - Face at ({x},{y}) recognized as: {display_text}")

            except Exception as e:
                print(f"Error during comparison/matching for a face: {e}")
                # Draw error on frame
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(display_frame, "Match Error", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                continue # Continue to next face

        # --- Display the processed image ---
        window_name = f"Recognition Result [{model_name}] - {os.path.basename(image_path)}"
        cv2.imshow(window_name, display_frame)
        print(f"-> Displaying results for {os.path.basename(image_path)}. Press any key in the window to continue...")
        cv2.waitKey(0) # Wait indefinitely for key press
        cv2.destroyWindow(window_name) # Close the specific window

    # --- End of Image Loop ---
    print("\nFinished processing all images.")


# ==================================
# 4. Argument Parsing & Execution
# ==================================

def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for model name and image paths."""
    parser = argparse.ArgumentParser(description="Detect and recognize faces in images using a specified model.")
    parser.add_argument(
        "-m", "--model",
        type=str,
        required=True, # Make model selection mandatory
        choices=MODEL_CONFIGS.keys(),
        help=f"Name of the face recognition model configuration to use. Choices: {list(MODEL_CONFIGS.keys())}"
    )
    parser.add_argument('image_paths', metavar='IMAGE_PATH', type=str, nargs='+',
                        help='Paths to one or more image files (.jpg, .jpeg, .png)')
    # Example: Add threshold override
    # parser.add_argument("--threshold", type=float, default=None, help="Override recognition distance threshold")
    args = parser.parse_args()
    return args

# --- Entry Point ---
if __name__ == "__main__":
    args = parse_arguments()

    # # Optional: Override threshold from args if provided
    # if args.threshold is not None:
    #     if args.model in MODEL_CONFIGS:
    #         print(f"Overriding threshold for {args.model} to {args.threshold}")
    #         MODEL_CONFIGS[args.model]['recognition_threshold'] = args.threshold
    #     else:
    #         # This case should ideally not happen due to 'choices' in argparse
    #         print(f"Warning: Cannot override threshold for unknown model '{args.model}'")

    recognize_faces_in_images(args.model, args.image_paths)

    cv2.destroyAllWindows() # Final cleanup just in case
    print("\nProcessing complete.")