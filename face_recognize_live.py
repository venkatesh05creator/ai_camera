import cv2
import numpy as np
import time
import argparse
from typing import List, Tuple

from config import MODEL_CONFIGS
from utils.face_utils import (
    load_face_cascade,
    detect_faces,
    extract_face_embedding,
    find_match
)
from models.model_manager import ModelManager

def process_frame(frame: np.ndarray, model_manager: ModelManager, 
                 face_cascade: cv2.CascadeClassifier) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
    """Processes a single frame and returns detected faces with their matches."""
    # Detect faces
    faces = detect_faces(frame, face_cascade)
    if not faces:
        return []

    # Get model info
    input_details, output_details = model_manager.get_model_info()
    config = model_manager.get_config()

    # Process each face
    results = []
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

        # Load datastore
        datastore = ModelManager.load_datastore(config['datastore_path'])
        
        # Find match
        match_name, confidence = find_match(
            embedding,
            datastore,
            config['recognition_threshold'],
            config['output_size']
        )
        
        results.append((match_name or "Unknown", confidence, (x, y, w, h)))

    return results

def run_face_recognition(model_name: str):
    """Runs live face recognition using the specified model."""
    if model_name not in MODEL_CONFIGS:
        print(f"Error: Model configuration '{model_name}' not found.")
        print(f"Available configurations: {list(MODEL_CONFIGS.keys())}")
        return

    # Initialize components
    config = MODEL_CONFIGS[model_name]
    model_manager = ModelManager(config)
    face_cascade = load_face_cascade()

    # Initialize video capture
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video capture device")
        return

    print(f"Starting live face recognition with model: {model_name}")
    print("Press 'q' to quit")

    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break

            # Process frame
            results = process_frame(frame, model_manager, face_cascade)

            # Draw results
            for name, confidence, (x, y, w, h) in results:
                # Draw rectangle
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

                # Draw label
                label = f"{name} ({confidence:.2f})"
                cv2.putText(frame, label, (x, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Display frame
            cv2.imshow('Face Recognition', frame)

            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Live face recognition')
    parser.add_argument('--model', type=str, required=True,
                      help='Model configuration name (e.g., facenet, facenet_lite)')
    return parser.parse_args()

if __name__ == "__main__":
    # args = parse_arguments()
    run_face_recognition("facenet")