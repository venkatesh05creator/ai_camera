MODEL_CONFIGS = {
    'facenet': {
        'model_path': 'models/facenet-2.tflite',
        'datastore_path': 'datastore/datastore_512_Dim.json',
        'input_size': 160,
        'output_size': 512, # Output size for original facenet model used here
        'image_mean': 128.0,
        'image_std': 128.0,
        'recognition_threshold': 0.1  # Add this line
    },
    'mobile_facenet': {
        'model_path': 'models/mobile_face_net.tflite', # Assumed path
        'datastore_path': 'datastore/datastore_128_Dim.json', # Assumed path
        'input_size': 112,       # Assumed input size
        'output_size': 192,      # Verified against models/mobile_face_net.tflite
        'image_mean': 127.5,     # Common normalization for lite models
        'image_std': 127.5,      # Common normalization for lite models
        'recognition_threshold': 0.9  # Add this line
    }
    # Add more model configurations here if needed
}