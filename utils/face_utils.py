import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

def load_face_detector(cascade_path: str) -> cv2.CascadeClassifier:
    """
    Load the face detector cascade classifier.
    
    Args:
        cascade_path: Path to the Haar Cascade XML file
        
    Returns:
        Loaded CascadeClassifier
    """
    pass

def detect_faces(image: np.ndarray, 
                face_detector: cv2.CascadeClassifier,
                scale_factor: float = 1.1,
                min_neighbors: int = 5,
                min_size: Tuple[int, int] = (60, 60)) -> List[Tuple[int, int, int, int]]:
    """
    Detect faces in an image.
    
    Args:
        image: Input image
        face_detector: Loaded face detector
        scale_factor: Scale factor for detection
        min_neighbors: Minimum neighbors for detection
        min_size: Minimum face size
        
    Returns:
        List of (x, y, w, h) face rectangles
    """
    pass

def preprocess_face(face_roi: np.ndarray, 
                   config: Dict[str, Any]) -> Optional[np.ndarray]:
    """
    Preprocess a face ROI for model input.
    
    Args:
        face_roi: Face region of interest
        config: Model configuration dictionary
        
    Returns:
        Preprocessed face or None if error
    """
    pass

def crop_face_roi(frame: np.ndarray, 
                 face_rect: Tuple[int, int, int, int],
                 padding: int = 10) -> Optional[np.ndarray]:
    """
    Crop face region from frame with padding.
    
    Args:
        frame: Input frame
        face_rect: (x, y, w, h) face rectangle
        padding: Padding around face
        
    Returns:
        Cropped face ROI or None if error
    """
    pass 