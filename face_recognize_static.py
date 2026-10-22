import cv2
import numpy as np
import argparse
from typing import Tuple, Dict, Any
import os

from config import MODEL_CONFIGS
from utils.face_utils import (
    load_face_cascade,
    detect_faces,
    extract_face_embedding,
    find_match,
    base64_to_image,
    image_to_base64
)
from models.model_manager import ModelManager

def process_image(base64_image: str, model_manager: ModelManager, 
                 face_cascade: cv2.CascadeClassifier) -> Tuple[list[Dict[str, Any]], Dict[str, str]]:
    """
    Processes a base64 encoded image and returns recognition results and images.
    
    Returns:
        Tuple containing:
        - List of recognition results (each containing name, confidence, and position)
        - Dictionary containing:
            - 'original': Base64 encoded string of the original image
            - 'annotated': Base64 encoded string of the annotated image
    """
    # Convert base64 to image
    image = base64_to_image(base64_image)
    if image is None:
        return [], {'original': '', 'annotated': ''}

    # Create a copy for display
    display_image = image.copy()

    # Detect faces
    faces = detect_faces(image, face_cascade)
    if not faces:
        return [], {
            'original': image_to_base64(image),
            'annotated': image_to_base64(display_image)
        }

    # Get model info
    input_details, output_details = model_manager.get_model_info()
    config = model_manager.get_config()

    # Process each face
    results = []
    for (x, y, w, h) in faces:
        # Extract face ROI
        face_roi = image[y:y+h, x:x+w]
        
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
        
        # Add result
        result = {
            'name': match_name or "Unknown",
            'confidence': float(confidence),
            'position': {
                'x': int(x),
                'y': int(y),
                'width': int(w),
                'height': int(h)
            }
        }
        results.append(result)

        # Draw results on display image
        color = (0, 255, 0) if match_name != "Unknown" else (0, 0, 255)
        cv2.rectangle(display_image, (x, y), (x + w, y + h), color, 2)
        
        # Draw label
        label = f"{result['name']} ({result['confidence']:.2f})"
        cv2.putText(display_image, label, (x, y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return results, {
        'original': image_to_base64(image),
        'annotated': image_to_base64(display_image)
    }

def recognize_face(model_name: str, base64_image: str) -> Tuple[list[Dict[str, Any]], Dict[str, str]]:
    """
    Recognizes faces in a single base64 encoded image.
    
    Args:
        model_name: Name of the model configuration to use
        base64_image: Base64 encoded image string
        
    Returns:
        Tuple containing:
        - Recognition results for each face
        - Dictionary with 'original' and 'annotated' base64 encoded images
    """
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Model configuration '{model_name}' not found. "
                        f"Available configurations: {list(MODEL_CONFIGS.keys())}")

    # Initialize components
    config = MODEL_CONFIGS[model_name]
    model_manager = ModelManager(config)
    face_cascade = load_face_cascade()

    # Process the image
    face_results, images = process_image(base64_image, model_manager, face_cascade)
    return face_results, images

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Face recognition on a static image')
    parser.add_argument('--model', type=str, default='facenet',
                      help='Model configuration name (default: facenet)')
    parser.add_argument('--image', type=str, default=None,
                      help='Path to image for face recognition')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    image_path = args.image
    if not image_path:
        image_path = input("Enter path to image: ").strip().strip('"')
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        exit(1)
    image = cv2.imread(image_path)
    b64_image = image_to_base64(image)
    results, images = recognize_face(model_name=args.model, base64_image=b64_image)
    print(f"Total faces found: {len(results)}")
    for result in results:
        print(f"Found {result['name']} with confidence {result['confidence']:.2f}")
