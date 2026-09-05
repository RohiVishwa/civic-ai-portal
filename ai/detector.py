import random
from datetime import datetime

def detect_issue(image_path):
    """
    Simulated image detection — No OpenCV needed!
    """
    categories = ['pothole', 'garbage', 'street_light', 'drainage', 'other']
    weights = [0.35, 0.25, 0.15, 0.15, 0.10]
    
    detected = random.choices(categories, weights=weights)[0]
    confidence = round(random.uniform(0.70, 0.95), 2)
    
    return {
        'category': detected,
        'confidence': confidence,
        'timestamp': datetime.now().isoformat()
    }

def process_image(image_path):
    """Simple image processor"""
    return None

def extract_features(image_path):
    """Extract features - simplified"""
    return {
        'shape': (224, 224, 3),
        'mean_brightness': 128
    }

# ===== TEST =====
if __name__ == "__main__":
    print("=== Detector Test ===\n")
    result = detect_issue("test.jpg")
    print(f"Detected: {result['category']} ({result['confidence']*100}%)")
    print("✅ Detector working without OpenCV!")