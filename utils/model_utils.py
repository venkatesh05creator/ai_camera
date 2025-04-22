import tensorflow as tf
import numpy as np
from typing import Dict, Any, Tuple, Optional

def load_model(model_path: str) -> Tuple[tf.lite.Interpreter, Dict, Dict]:
    """
    Load a TFLite model and get its details.
    
    Args:
        model_path: Path to the TFLite model file
        
    Returns:
        Tuple of (interpreter, input_details, output_details)
    """
    pass

def get_embedding(interpreter: tf.lite.Interpreter, 
                 input_details: Dict, 
                 output_details: Dict, 
                 preprocessed_face: np.ndarray) -> Optional[np.ndarray]:
    """
    Get embedding from a preprocessed face image.
    
    Args:
        interpreter: Loaded TFLite interpreter
        input_details: Model input details
        output_details: Model output details
        preprocessed_face: Preprocessed face image
        
    Returns:
        Face embedding as numpy array or None if error
    """
    pass 