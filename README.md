# 🚀 Advanced Face Recognition System

A high-performance, real-time face recognition and management system leveraging **TFLite models**, **OpenCV**, and **FastAPI**. This project provides a robust framework for detecting, embedding, and identifying individuals from both static images and live video streams.

## ✨ Key Features

*   **🔍 Real-time Face Recognition:** Identify known individuals in live camera feeds with low latency.
*   **📸 Static Image Processing:** Batch process images for face detection and identification.
*   **📥 Dynamic Face Enrollment:** Add new faces to the system via live capture or static files.
*   **🛠️ Model Flexibility:** Switch between different TFLite architectures (e.g., FaceNet, MobileFaceNet) via simple configuration.
*   **🌐 REST API Ready:** Integrated with FastAPI for seamless integration into web and mobile applications.
*   **📦 Persistent Datastore:** Efficiently store and manage face embeddings in a JSON-based vector database.

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **Computer Vision:** OpenCV
- **Inference Engine:** TensorFlow Lite (TFLite)
- **Web Framework:** FastAPI / Uvicorn
- **Data Handling:** NumPy, Pydantic

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python installed. It's recommended to use a virtual environment.

### 2. Installation
```powershell
# Clone the repository
git clone <your-repo-url>
cd face_recognition_test

# Install dependencies
pip install -r requirements.txt
```

### 3. Model Setup
- Place your `.tflite` model files in the `models/` directory.
- Ensure the Haar Cascade XML file is present in `models/` for initial face detection.

### 4. Configuration
Update `config.py` to match your model's specifications (input size, normalization parameters, etc.).

## 📖 Usage Guide

### Live Face Recognition
```bash
python face_recognize_live.py -m <model_name>
```

### Add New Face (Live)
```bash
python face_add_live.py -m <model_name>
```
*Press 'c' to capture, then enter the name in the terminal.*

### Static Image Recognition
```bash
python face_recognize_static.py -m <model_name> path/to/image.jpg
```

### API Server
```bash
uvicorn app:app --reload
```

## 📂 Project Structure

- `app.py`: FastAPI server implementation.
- `face_add_*.py`: Scripts for adding faces to the database.
- `face_recognize_*.py`: Inference scripts for recognition.
- `config.py`: Centralized model and path configuration.
- `datastore/`: Contains JSON files storing face embeddings.
- `models/`: Storage for TFLite and Haar Cascade models.

## 📝 License
This project is open-source. See the LICENSE file for details.

---
*Developed with ❤️ by Venkatesh*