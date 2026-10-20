import tensorflow as tf
import json
import os
from typing import Dict, Any, Tuple
import numpy as np

class ModelManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads the TFLite model and initializes the interpreter."""
        try:
            model_path = self.config['model_path']
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at {model_path}")
            
            self.interpreter = tf.lite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
        except Exception as e:
            print(f"Error loading model: {e}")
            raise

    def get_model_info(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns input and output details of the loaded model."""
        return self.input_details, self.output_details

    def get_config(self) -> Dict[str, Any]:
        """Returns the model configuration."""
        return self.config

    @staticmethod
    def load_datastore(datastore_path: str) -> Dict[str, np.ndarray]:
        """Loads the face embeddings datastore."""
        try:
            if not os.path.exists(datastore_path):
                return {}
            
            with open(datastore_path, 'r') as f:
                datastore = json.load(f)
            
            # Convert string keys to numpy arrays
            return {name: np.array(embedding) for name, embedding in datastore.items()}
        except Exception as e:
            print(f"Error loading datastore: {e}")
            return {} 