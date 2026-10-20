from face_add_static import extract_face_embeddings_from_image,add_embeddings_to_datastore, image_to_base64

import numpy as np
import cv2

def add_average_face_embedding_to_datastore(model_name: str, image_paths: list, name: str) -> str:
    """
    Extracts face embeddings from a list of image paths, calculates the average embedding, 
    and adds it to the datastore.
    
    Args:
        model_name: Name of the model configuration to use
        image_paths: List of image paths to extract embeddings from
        name: Name to associate with the detected face
        
    Returns:
        String "OK" if successful, error message otherwise
    """
    all_embeddings = []
    
    # Loop through each image path and extract embeddings
    for image_path in image_paths:
        # Load the image using OpenCV
        image = cv2.imread(image_path)
        if image is None:
            return f"Error: Unable to load image from {image_path}"
        
        # Convert the loaded image to base64
        base64_image = image_to_base64(image)
        if not base64_image:
            return f"Error converting image to base64 from {image_path}"
        
        # Extract embeddings from the base64-encoded image
        embedding, status = extract_face_embeddings_from_image(model_name, base64_image)
        if embedding is None:
            return f"Error extracting embedding from {image_path}: {status}"
        
        all_embeddings.append(embedding)

    # If embeddings were extracted successfully
    if all_embeddings:
        # Calculate the average embedding
        average_embedding = np.mean(all_embeddings, axis=0).tolist()  # Convert to list if needed

        # Add the average embedding to the datastore
        result = add_embeddings_to_datastore(model_name, average_embedding, name)
        return result
    else:
        return "No valid embeddings extracted"


image_paths=[

    '/Users/chaitanyakartik/Downloads/Faces/person-1/image3.jpeg'
]

res = add_average_face_embedding_to_datastore("facenet", image_paths, "person-1_v4")
print(res)  # Will print "OK" if successful, otherwise an error message
