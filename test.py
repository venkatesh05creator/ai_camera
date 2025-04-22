import requests

img_path=r"/Users/chaitanyakartik/Downloads/Faces/1a6b41480b9316ef/image9.jpeg"
response = requests.post(
    "http://localhost:8000/extract-embeddings",
    params={
        "model_name": "facenet",
        "image_path": img_path
    }
)

print(response.json())