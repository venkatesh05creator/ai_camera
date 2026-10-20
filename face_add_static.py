import cv2
import numpy as np
import json
import argparse
from typing import Tuple
import os

from config import MODEL_CONFIGS
from utils.face_utils import (
    load_face_cascade,
    detect_faces,
    extract_face_embedding,
    base64_to_image,
    image_to_base64
)
from models.model_manager import ModelManager

import cv2
import numpy as np
import json
from typing import Tuple

from config import MODEL_CONFIGS
from utils.face_utils import (
    load_face_cascade,
    detect_faces,
    extract_face_embedding,
    base64_to_image
)
from models.model_manager import ModelManager
def extract_face_embeddings_from_image(model_name: str, base64_image: str) -> tuple:
    """
    Extracts face embeddings from a base64 encoded image.
    
    Args:
        model_name: Name of the model configuration to use
        base64_image: Base64 encoded image string
        
    Returns:
        A tuple containing:
            - Embedding (list) if successful
            - Error message (str) if failed
    """
    if model_name not in MODEL_CONFIGS:
        return None, f"Error: Model configuration '{model_name}' not found"

    # Initialize components
    config = MODEL_CONFIGS[model_name]
    model_manager = ModelManager(config)
    face_cascade = load_face_cascade()

    # Convert base64 to image
    image = base64_to_image(base64_image)
    if image is None:
        return None, "Error: Could not decode base64 image"

    # Detect faces
    faces = detect_faces(image, face_cascade)
    if not faces:
        return None, "No faces detected in the image"

    # Get model info
    input_details, output_details = model_manager.get_model_info()

    # Process the first face (assuming single face per image)
    x, y, w, h = faces[0]
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
        return None, f"Failed to extract embedding: {status}"
    
    return embedding, "OK"

def add_embeddings_to_datastore(model_name: str, embedding: list, name: str) -> str:
    """
    Adds the provided face embeddings to the datastore.
    
    Args:
        model_name: Name of the model configuration to use
        embedding: Face embedding (list) to store
        name: Name to associate with the detected face
        
    Returns:
        String "OK" if successful, error message otherwise
    """
    if model_name not in MODEL_CONFIGS:
        return f"Error: Model configuration '{model_name}' not found"

    # Initialize components
    config = MODEL_CONFIGS[model_name]
    model_manager = ModelManager(config)

    # Load existing datastore safely
    datastore = {}
    if os.path.exists(config['datastore_path']):
        try:
            with open(config['datastore_path'], 'r') as f:
                content = f.read().strip()
                if content:  # only try to parse if not empty
                    datastore = json.loads(content)
        except Exception as e:
            return f"Error loading datastore: {e}"

    # Create unique name if needed
    unique_name = name
    counter = 1
    while unique_name in datastore:
        unique_name = f"{name}_{counter}"
        counter += 1
    
    # Add to datastore - convert ndarray to list explicitly
    datastore[unique_name] = embedding.tolist() 

    # Save updated datastore
    try:
        with open(config['datastore_path'], 'w') as f:
            json.dump(datastore, f)
        return "OK"
    except Exception as e:
        return f"Error saving datastore: {e}"

def add_face_from_base64(model_name: str, base64_image: str, name: str) -> str:
    # Step 1: Extract face embedding from the image
    embedding, status = extract_face_embeddings_from_image(model_name, base64_image)
    if embedding is None:
        return f"Error extracting embedding: {status}"

    # Step 2: Add embedding to the datastore
    result = add_embeddings_to_datastore(model_name, embedding, name)

    return result

if __name__ == "__main__":
    image_path = '/Users/chaitanyakartik/Downloads/WhatsApp Image 2025-04-22 at 17.52.48.jpeg'
    image = cv2.imread(image_path)
    b64_image = image_to_base64(image)
    res = add_face_from_base64("facenet", b64_image, "Pranav")
    print(res)

    