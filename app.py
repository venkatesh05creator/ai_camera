from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import numpy as np
import json

from face_recognize_static import extract_embeddings_from_image, MODEL_CONFIGS

app = FastAPI(
    title="Face Embedding API",
    description="API for extracting face embeddings from images using different models",
    version="1.0.0"
)

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    face_locations: List[Dict[str, int]]
    model_name: str
    image_path: str

@app.get("/")
async def root():
    return {"message": "Face Embedding API is running"}

@app.get("/models")
async def get_available_models():
    """Returns a list of available model configurations"""
    return {"available_models": list(MODEL_CONFIGS.keys())}

@app.post("/extract-embeddings", response_model=EmbeddingResponse)
async def extract_embeddings(model_name: str, image_path: str):
    """
    Extract face embeddings from an image using the specified model.
    
    Args:
        model_name: Name of the model configuration to use
        image_path: Path to the image file
    
    Returns:
        EmbeddingResponse containing:
        - embeddings: List of face embeddings (each embedding is a list of floats)
        - face_locations: List of face locations (x, y, width, height)
        - model_name: The model used
        - image_path: The image processed
    """
    try:
        # Validate model name
        if model_name not in MODEL_CONFIGS:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_name}' not found. Available models: {list(MODEL_CONFIGS.keys())}"
            )

        # Extract embeddings
        results = extract_embeddings_from_image(model_name, image_path)
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail="No faces detected in the image or error processing the image"
            )

        # Convert numpy arrays to lists for JSON serialization
        embeddings = []
        face_locations = []
        
        for embedding, (x, y, w, h) in results:
            embeddings.append(embedding.tolist())
            face_locations.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h)
            })

        return EmbeddingResponse(
            embeddings=embeddings,
            face_locations=face_locations,
            model_name=model_name,
            image_path=image_path
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 