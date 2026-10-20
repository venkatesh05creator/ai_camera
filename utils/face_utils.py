import cv2
import numpy as np
import tensorflow as tf
import base64
from typing import List, Tuple, Optional, Dict, Any

# Common constants
CASCADE_PATH = 'models/haarcascade_frontalface_default.xml'

def load_face_cascade() -> cv2.CascadeClassifier:
    """Loads and returns the face detection cascade classifier."""
    return cv2.CascadeClassifier(CASCADE_PATH)

def base64_to_image(base64_string: str) -> Optional[np.ndarray]:
    """Converts a base64 encoded string to an OpenCV image."""
    try:
        # Remove the data URL prefix if present
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
            
        # Decode base64 string
        image_data = base64.b64decode(base64_string)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        
        # Decode image
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        print(f"Error converting base64 to image: {e}")
        return None

def image_to_base64(image: np.ndarray) -> str:
    """Converts an OpenCV image to a base64 encoded string."""
    try:
        # Encode image
        _, buffer = cv2.imencode('.jpg', image)
        
        # Convert to base64
        base64_string = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_string}"
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return ""

def detect_faces(image: np.ndarray, cascade: cv2.CascadeClassifier) -> List[Tuple[int, int, int, int]]:
    """Detects faces in an image and returns their coordinates."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    # Convert numpy array to list of tuples
    return [tuple(face) for face in faces]

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

def extract_face_embedding(face_roi: np.ndarray, interpreter: tf.lite.Interpreter, 
                         input_details: list, output_details: list, 
                         config: dict) -> Tuple[Optional[np.ndarray], str]:
    """Extracts face embedding from a face ROI using the provided model."""
    try:
        # Preprocess face
        input_data = preprocess_face(face_roi, config, input_details[0]['dtype'])
        if input_data is None:
            return None, "Preprocessing failed"

        # Set input tensor
        interpreter.set_tensor(input_details[0]['index'], input_data)
        
        # Run inference
        interpreter.invoke()
        
        # Get output tensor
        embedding = interpreter.get_tensor(output_details[0]['index'])
        
        # Normalize embedding
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding, "Success"
    except Exception as e:
        print(f"Error during embedding extraction: {e}")
        return None, str(e)

def find_match(current_embedding: np.ndarray, datastore: Dict[str, np.ndarray], 
              threshold: float, expected_output_dim: int) -> Tuple[Optional[str], float]:
    """Compares the current embedding against the datastore to find the best match."""
    if not datastore:
        return None, 0.0
    
    if current_embedding.shape[-1] != expected_output_dim:
        print(f"Warning: Embedding dimension mismatch. Expected {expected_output_dim}, got {current_embedding.shape[-1]}")
        return None, 0.0
    
    best_match = None
    best_score = 0.0
    
    for name, stored_embedding in datastore.items():
        if stored_embedding.shape[-1] != expected_output_dim:
            continue
            
        # Calculate cosine similarity
        similarity = np.dot(current_embedding, stored_embedding.T)
        # Convert similarity to scalar float
        similarity = float(similarity)
        if similarity > best_score:
            best_score = similarity
            best_match = name
    
    if best_score >= threshold:
        return best_match, best_score
    return None, best_score
