import os
from face_recognize_static import recognize_face
from utils.face_utils import image_to_base64, base64_to_image
import cv2
import matplotlib.pyplot as plt
from face_add_static import add_face_from_base64
from face_recognize_static import recognize_face

def add_face(image_path,name):
    # Example usage
    image = cv2.imread(image_path)
    b64_image = image_to_base64(image)

    # Call the recognize_face function directly
    res = add_face_from_base64("facenet", b64_image,name)
    print(res)

def recognize(image_path,name):
    missing_persons = ["person-43", "person-27", "person-16", "person-45", "person-15"]

    if name not in missing_persons:
        # Example usage
        image = cv2.imread(image_path)
        b64_image = image_to_base64(image)

        # Call the recognize_face function directly
        face_results, images = recognize_face("facenet", b64_image)

        best_match = max(face_results, key=lambda x: x['confidence'])
        # print(best_match)            

        return best_match
        
            

# Path to your main folder
root_dir = "/Users/Venkatesh/Downloads/face_recognition_test copy/face_recognition_test copy/data/Faces"

# Extract subfolder names
subfolders = [name for name in os.listdir(root_dir) 
              if os.path.isdir(os.path.join(root_dir, name))]

# Print subfolder names
for name in subfolders:
    img_path = os.path.join(root_dir, name, "image1.jpeg")
    add_face(img_path,name)

# #----------------------
# # img_path = os.path.join(root_dir, "person-1", "image5.jpeg")

# # res = recognize(image_path=img_path,name="person-1")

# # print(f"Found {res['name']} with confidence {res['confidence']:.2f}")

# from collections import Counter

# def recognize_images_in_folder(root_dir, folder, recognize):
#     folder_path = os.path.join(root_dir, folder)
    
#     recognized_names = []

#     # Supported image extensions
#     image_extensions = {'.jpg', '.jpeg', '.png'}

#     # Loop over all images in the folder
#     for file in os.listdir(folder_path):
#         ext = os.path.splitext(file)[1].lower()
#         if ext in image_extensions:
#             img_path = os.path.join(folder_path, file)
#             try:
#                 res = recognize(image_path=img_path, name=folder)
#                 recognized_names.append(res['name'])
#                 # print(f"{file}: Recognized {res['name']} with confidence {res['confidence']:.2f}")
#             except Exception as e:
#                 print(f"{file}: Error during recognition - {e}")
    
#     # Count how many times each name was recognized
#     name_counts = Counter(recognized_names)

#     # Return the results
#     return name_counts

# # Example usage
# root_dir = "/Users/chaitanyakartik/Downloads/Faces"
# folder = "person-1"

# name_counts = recognize_images_in_folder(root_dir, folder, recognize)

# # Print summary
# print("\nRecognition Summary:")
# for name, count in name_counts.items():
#     print(f"{name}: {count} times")