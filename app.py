"""
Simple Face Recognition Test App
A lightweight Flask app for testing basic face recognition functionality
without the heavy dlib dependency.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import cv2
import os
import numpy as np
from PIL import Image
import base64
import io
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'test_secret_key'

# Face data storage
FACE_DATA_FILE = 'face_data.json'

class SimpleFaceRecognizer:
    """Simple face recognition using OpenCV's built-in face detection and basic image comparison"""
    
    def __init__(self):
        # Load OpenCV's pre-trained face detection model
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.known_faces = self.load_known_faces()
    
    def load_known_faces(self):
        """Load known faces from file"""
        if os.path.exists(FACE_DATA_FILE):
            try:
                with open(FACE_DATA_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_known_faces(self):
        """Save known faces to file"""
        with open(FACE_DATA_FILE, 'w') as f:
            json.dump(self.known_faces, f)
    
    def detect_faces(self, image):
        """Detect faces in an image using OpenCV"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        return faces
    
    def extract_face_features(self, image, face_coords):
        """Extract simple features from a face region"""
        x, y, w, h = face_coords
        face_region = image[y:y+h, x:x+w]
        
        # Resize to standard size
        face_resized = cv2.resize(face_region, (100, 100))
        
        # Convert to grayscale and flatten
        gray_face = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        features = gray_face.flatten()
        
        # Safe conversion to list
        if hasattr(features, 'tolist'):
            return features.tolist()
        else:
            return list(features)
    
    def compare_faces(self, features1, features2, threshold=0.6):
        """Compare two face feature sets using simple correlation"""
        features1 = np.array(features1)
        features2 = np.array(features2)
        
        # Normalize features
        features1 = features1 / np.linalg.norm(features1)
        features2 = features2 / np.linalg.norm(features2)
        
        # Calculate similarity (dot product)
        similarity = np.dot(features1, features2)
        
        return similarity > threshold, similarity
    
    def check_face_similarity(self, features, similarity_threshold=0.85):
        """Check if a face with similar features is already registered"""
        for registered_name, face_data in self.known_faces.items():
            # Compare with primary averaged features
            registered_features = np.array(face_data['features'])
            is_similar, similarity = self.compare_faces(features, registered_features, similarity_threshold)
            
            if is_similar:
                return registered_name
            
            # Also check against individual features if available for more thorough checking
            if 'all_features' in face_data:
                for individual_features in face_data['all_features']:
                    individual_features = np.array(individual_features)
                    is_similar, similarity = self.compare_faces(features, individual_features, similarity_threshold)
                    if is_similar:
                        return registered_name
        
        return None  # No similar face found

    
    def register_face(self, images, name):
        """Register a face using exactly 3 images for optimal accuracy"""
        if len(images) != 3:
            return False, "Exactly 3 images are required"
        
        # Check if name already exists
        if name in self.known_faces:
            return False, f"Person with name '{name}' is already registered. Please use a different name or delete the existing registration first."
        
        all_features = []
        
        # Extract features from all images and check for duplicate faces
        for i, image in enumerate(images):
            faces = self.detect_faces(image)
            
            if len(faces) == 0:
                return False, f"No face detected in image {i+1}"
            
            if len(faces) > 1:
                return False, f"Multiple faces detected in image {i+1}. Please ensure only one face per image"
            
            # Extract features from the detected face
            face_coords = faces[0]
            features = self.extract_face_features(image, face_coords)
            
            # Check if this face is already registered (face similarity check)
            duplicate_name = self.check_face_similarity(features)
            if duplicate_name:
                return False, f"This face appears to be already registered under the name '{duplicate_name}'. Each person can only be registered once."
            
            all_features.append(features)
        
        # Calculate average features for better recognition accuracy
        avg_features = np.mean(all_features, axis=0)
        
        # Safe conversion to lists
        if hasattr(avg_features, 'tolist'):
            avg_features_list = avg_features.tolist()
        else:
            avg_features_list = list(avg_features)
        
        safe_all_features = []
        for f in all_features:
            if hasattr(f, 'tolist'):
                safe_all_features.append(f.tolist())
            else:
                safe_all_features.append(list(f))
        
        # Save the face data with multiple feature sets for robust matching
        self.known_faces[name] = {
            'features': avg_features_list,  # Primary averaged features
            'all_features': safe_all_features,  # All individual features
            'registered_at': datetime.now().isoformat(),
            'image_count': len(images)
        }
        
        self.save_known_faces()
        
        return True, f"Face registered successfully with {len(images)} high-quality photos!"
    
    def recognize_face(self, image):
        """Recognize a face from the image"""
        faces = self.detect_faces(image)
        
        if len(faces) == 0:
            return [], "No face detected"
        
        results = []
        
        for face_coords in faces:
            features = self.extract_face_features(image, face_coords)
            
            best_match = None
            best_similarity = 0
            
            # Compare with all known faces
            for name, face_data in self.known_faces.items():
                # Use primary averaged features
                known_features = np.array(face_data['features'])
                is_match, similarity = self.compare_faces(features, known_features)
                
                # If multiple features available, also check against individual features for better accuracy
                if 'all_features' in face_data and similarity < 0.8:  # If primary match isn't strong enough
                    best_individual_similarity = similarity
                    for individual_features in face_data['all_features']:
                        individual_features = np.array(individual_features)
                        _, individual_similarity = self.compare_faces(features, individual_features)
                        best_individual_similarity = max(best_individual_similarity, individual_similarity)
                    
                    similarity = best_individual_similarity
                    is_match = similarity > 0.75  # Slightly lower threshold for individual comparisons
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    if is_match:
                        best_match = name
            
            # Convert to list if it's a numpy array, otherwise keep as is
            if hasattr(face_coords, 'tolist'):
                coordinates = face_coords.tolist()
            else:
                coordinates = list(face_coords)
                
            results.append({
                'name': best_match or 'Unknown',
                'confidence': round(best_similarity * 100, 2),
                'coordinates': coordinates
            })
        
        return results, "Recognition completed"

# Initialize face recognizer
recognizer = SimpleFaceRecognizer()

@app.route('/')
def index():
    """Main page"""
    known_faces = list(recognizer.known_faces.keys())
    return render_template('index.html', known_faces=known_faces)

@app.route('/register_old', methods=['POST'])
def register_face_old():
    """Register a face using 3 images for better accuracy (old method)"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        images_data = data.get('images', [])
        
        if not name:
            return jsonify({'success': False, 'message': 'Name is required'})
        
        if len(images_data) != 3:
            return jsonify({'success': False, 'message': 'Exactly 3 images are required'})
        
        # Process and validate all images
        processed_images = []
        for i, image_data in enumerate(images_data):
            try:
                # Decode base64 image
                image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
                image_bytes = base64.b64decode(image_data)
                
                # Convert to OpenCV image
                nparr = np.frombuffer(image_bytes, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    return jsonify({'success': False, 'message': f'Invalid image format in photo {i+1}'})
                
                # Verify face exists
                faces = recognizer.detect_faces(image)
                if len(faces) != 1:
                    return jsonify({'success': False, 'message': f'Photo {i+1} must contain exactly one face'})
                
                processed_images.append(image)
                
            except Exception as e:
                return jsonify({'success': False, 'message': f'Error processing photo {i+1}: {str(e)}'})
        
        # Register using 3 images
        success, message = recognizer.register_face(processed_images, name)
        
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/detect_faces', methods=['POST'])
def detect_faces_endpoint():
    """Detect faces in uploaded image and check for duplicates during live preview"""
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'success': False, 'message': 'No image data provided', 'faces': []})
        
        # Decode base64 image
        image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
        image_bytes = base64.b64decode(image_data)
        
        # Convert to OpenCV image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return jsonify({'success': False, 'message': 'Invalid image format', 'faces': []})
        
        # Detect faces
        faces = recognizer.detect_faces(image)
        
        face_results = []
        for face_coords in faces:
            # Convert to list if it's a numpy array, otherwise keep as is
            if hasattr(face_coords, 'tolist'):
                coordinates = face_coords.tolist()
            else:
                coordinates = list(face_coords)
            
            # Extract features and check if this face is already registered
            features = recognizer.extract_face_features(image, face_coords)
            duplicate_name = recognizer.check_face_similarity(features, similarity_threshold=0.80)
            
            face_result = {
                'coordinates': coordinates,
                'is_duplicate': duplicate_name is not None,
                'duplicate_name': duplicate_name
            }
            
            face_results.append(face_result)
        
        # Check if any face is a duplicate
        has_duplicate = any(face.get('is_duplicate', False) for face in face_results)
        
        if has_duplicate:
            duplicate_names = [face.get('duplicate_name') for face in face_results if face.get('is_duplicate')]
            return jsonify({
                'success': False,
                'message': f'This face is already registered as: {", ".join(duplicate_names)}',
                'faces': face_results,
                'duplicate_detected': True
            })
        
        return jsonify({
            'success': True,
            'message': f'Detected {len(faces)} face(s) - ready for registration',
            'faces': face_results,
            'duplicate_detected': False
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}', 'faces': []})

@app.route('/recognize', methods=['POST'])
def recognize_face():
    """Recognize faces in uploaded image"""
    try:
        # Get image data from POST request
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'success': False, 'message': 'No image data provided', 'faces': []})
        
        # Decode base64 image
        image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
        image_bytes = base64.b64decode(image_data)
        
        # Convert to OpenCV image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return jsonify({'success': False, 'message': 'Invalid image format', 'faces': []})
        
        # Recognize faces
        results, message = recognizer.recognize_face(image)
        
        # Ensure results is always a list
        if results is None:
            results = []
        
        return jsonify({
            'success': True,
            'message': message,
            'faces': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}', 'faces': []})

@app.route('/register_page')
@app.route('/register', methods=['GET'])
def register_page():
    """Registration page"""
    return render_template('register.html')

@app.route('/register_multiple', methods=['POST'])
def register_multiple():
    """Register a face using multiple images for better accuracy"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        images_data = data.get('images', [])
        
        if not name:
            return jsonify({'success': False, 'message': 'Name is required'})
        
        if len(images_data) != 3:
            return jsonify({'success': False, 'message': 'Exactly 3 images are required'})
        
        # Process and validate all images
        processed_images = []
        for i, image_data in enumerate(images_data):
            try:
                # Decode base64 image
                image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
                image_bytes = base64.b64decode(image_data)
                
                # Convert to OpenCV image
                nparr = np.frombuffer(image_bytes, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    return jsonify({'success': False, 'message': f'Invalid image format in photo {i+1}'})
                
                # Verify face exists
                faces = recognizer.detect_faces(image)
                if len(faces) != 1:
                    return jsonify({'success': False, 'message': f'Photo {i+1} must contain exactly one face'})
                
                processed_images.append(image)
                
            except Exception as e:
                return jsonify({'success': False, 'message': f'Error processing photo {i+1}: {str(e)}'})
        
        # Register using 3 images
        success, message = recognizer.register_face(processed_images, name)
        
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/camera')
def camera_test():
    """Camera test page"""
    return render_template('camera.html')

@app.route('/delete_face/<name>', methods=['POST'])
def delete_face(name):
    """Delete a registered face"""
    try:
        if name in recognizer.known_faces:
            del recognizer.known_faces[name]
            recognizer.save_known_faces()
            
            return jsonify({'success': True, 'message': f'Face for {name} deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Face not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    print("🚀 Starting Simple Face Recognition Test App")
    print("📋 Features:")
    print("  - Register faces with names")
    print("  - Live camera recognition")
    print("  - Simple OpenCV-based detection")
    print("  - No heavy dependencies (no dlib)")
    print("\n🌐 Open your browser to http://localhost:5001")
    
    app.run(debug=True, port=5001)
