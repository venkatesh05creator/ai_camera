# Face Recognition Project

This project implements basic face recognition and management using TFLite models and OpenCV.

## Features

*   **Face Adding (Static Images):** Detect faces in images, generate embeddings, and add them to a datastore with names.
*   **Face Adding (Live Video):** Detect faces in a live camera feed, capture embeddings, and add them to a datastore with names.
*   **Face Recognition (Static Images):** Detect faces in images and compare their embeddings against a datastore to identify known individuals.
*   **Face Recognition (Live Video):** Detect faces in a live camera feed and compare their embeddings in real-time against a datastore.
*   **Face Removal:** Remove specific faces (by name) from the datastore.
*   **Face Viewing:** List the names of faces currently stored in the datastore.
*   **Model Flexibility:** Supports different TFLite models via a configuration file (`config.py`).

## Setup

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: Ensure `requirements.txt` includes `opencv-python`, `tensorflow` (or `tflite-runtime`), and `numpy`.* You may need to install specific versions depending on your system and TFLite model compatibility.

4.  **Download Models:**
    *   Place your TFLite model files (e.g., `mobile_face_net.tflite`, `facenet.tflite`) inside the `models/` directory.
    *   Ensure the Haar Cascade file (`haarcascade_frontalface_default.xml`) is also in the `models/` directory. You can usually find this within your OpenCV installation or download it separately.

5.  **Configure Models (`config.py`):**
    *   Create or update `config.py` to define your model configurations. Example:
        ```python
        # config.py
        MODEL_CONFIGS = {
            'facenet_lite': {
                'model_path': 'models/mobile_face_net.tflite',
                'datastore_path': 'datastore_128_Dim.json', # Or derive based on model
                'input_size': 112,
                'image_mean': 128.0,
                'image_std': 128.0,
                # Add output_size if needed for checks
            },
            'facenet': {
                'model_path': 'models/facenet.tflite',
                'datastore_path': 'datastore_512_Dim.json', # Or derive based on model
                'input_size': 160, # Example size for FaceNet
                'image_mean': 127.5,
                'image_std': 127.5,
                # Add output_size if needed for checks
            },
            # Add more model configurations as needed
        }
        ```

## Usage

Replace `'<model_name>'` with the key you defined in `config.py` (e.g., `'facenet_lite'`, `'facenet'`).

*   **Add faces from static images:**
    ```bash
    python face_add_static.py -m <model_name> path/to/image1.jpg path/to/image2.png ...
    ```

*   **Add faces from live video:**
    ```bash
    python face_add_live.py -m <model_name>
    ```
    *   Follow the on-screen prompts. Press 'c' to capture a face, then enter the name in the terminal.

*   **Recognize faces in static images:**
    ```bash
    python face_recognize_static.py -m <model_name> path/to/image1.jpg path/to/image2.png ...
    ```

*   **Recognize faces in live video:**
    ```bash
    python face_recognize_live.py -m <model_name>
    ```
    *   Press 'q' in the OpenCV window to quit.

*   **View stored faces:**
    ```bash
    python face_remove.py -m <model_name> --view
    ```

*   **Remove a face:**
    ```bash
    python face_remove.py -m <model_name> --name "Person Name"
    ```

## Notes

*   The quality of face detection and recognition depends heavily on the chosen model, lighting conditions, face angles, and the quality of the images/video feed.
*   Recognition thresholds (`RECOGNITION_THRESHOLD` in recognition scripts) might need tuning based on the model and desired accuracy.
*   Datastore files (`.json`) store the embeddings and names. Ensure you use the correct datastore corresponding to the model you are using. 