import cv2
import numpy as np
import json
import os
import argparse
from typing import List, Tuple

from config import MODEL_CONFIGS
from utils.face_utils import (
    load_face_cascade,
    detect_faces,
    extract_face_embedding
)
from models.model_manager import ModelManager

def process_frame_for_addition(frame: np.ndarray, model_manager: ModelManager, 
                             face_cascade: cv2.CascadeClassifier) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
    """Processes a single frame and returns face embeddings with their locations."""
    # Detect faces
    faces = detect_faces(frame, face_cascade)
    if not faces:
        return []

    # Get model info
    input_details, output_details = model_manager.get_model_info()
    config = model_manager.get_config()

    # Process each face
    embeddings = []
    for (x, y, w, h) in faces:
        # Extract face ROI
        face_roi = frame[y:y+h, x:x+w]
        
        # Extract embedding
        embedding, status = extract_face_embedding(
            face_roi,
            model_manager.interpreter,
            input_details,
            output_details,
            config
        )
        
        if embedding is None:
            print(f"Failed to extract embedding: {status}")
            continue
            
        embeddings.append((embedding, (x, y, w, h)))

    return embeddings

def add_faces_live(model_name: str):
    """Runs live face capture and addition to the datastore."""
    if model_name not in MODEL_CONFIGS:
        print(f"Error: Model configuration '{model_name}' not found.")
        print(f"Available configurations: {list(MODEL_CONFIGS.keys())}")
        return

    # Initialize components
    config = MODEL_CONFIGS[model_name]
    model_manager = ModelManager(config)
    face_cascade = load_face_cascade()

    # Load existing datastore
    datastore = ModelManager.load_datastore(config['datastore_path'])

    # Initialize video capture
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video capture device")
        return

    print(f"Starting live face capture with model: {model_name}")
    print("Press 'c' to capture a face, 'q' to quit")

    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break

            # Process frame
            embeddings = process_frame_for_addition(frame, model_manager, face_cascade)

            # Draw face rectangles
            for _, (x, y, w, h) in embeddings:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Display frame
            cv2.imshow('Face Capture - Press C to Capture, Q to Quit', frame)

            # Check for capture or quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c') and embeddings:
                # Get name for the face
                name = input("Enter name for the captured face (leave blank to skip): ").strip()
                if not name:
                    continue

                # Add each face to datastore
                for embedding, (x, y, w, h) in embeddings:
                    # Create unique name if multiple faces in same frame
                    unique_name = name
                    counter = 1
                    while unique_name in datastore:
                        unique_name = f"{name}_{counter}"
                        counter += 1
                        
                    datastore[unique_name] = embedding.tolist()
                    print(f"Added face at ({x}, {y}, {w}, {h}) as {unique_name}")

                # Save updated datastore
                try:
                    with open(config['datastore_path'], 'w') as f:
                        json.dump(datastore, f)
                    print(f"Successfully saved {len(datastore)} faces to {config['datastore_path']}")
                except Exception as e:
                    print(f"Error saving datastore: {e}")

    finally:
        cap.release()
        cv2.destroyAllWindows()

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Add faces to the recognition datastore using live camera')
    parser.add_argument('--model', type=str, required=True,
                      help='Model configuration name (e.g., facenet, facenet_lite)')
    return parser.parse_args()

if __name__ == "__main__":
    # args = parse_arguments()
    add_faces_live("facenet")