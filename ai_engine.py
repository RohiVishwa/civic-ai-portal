import os

def analyze_damage(image_path="", text=""):
    """
    Civic AI damage triage engine.
    Analyzes uploaded evidence and description to assign priority: HIGH, MEDIUM, or LOW.
    """
    text_lower = (text or "").lower()
    
    # High Priority Keywords (Hazards, Deep Potholes, Flooding, Electrical Sparks)
    high_keywords = [
        "danger", "accident", "deep", "major", "severe", "spark", "electric", 
        "fire", "flood", "broken pipe", "live wire", "open drain", "collapse", 
        "urgent", "overflow", "death", "injury"
    ]
    
    # Medium Priority Keywords
    medium_keywords = [
        "pothole", "leakage", "garbage", "waste", "dark", "street light", 
        "damage", "broken", "blocked", "smell", "dump", "road"
    ]

    for kw in high_keywords:
        if kw in text_lower:
            return "HIGH"
            
    for kw in medium_keywords:
        if kw in text_lower:
            return "MEDIUM"

    # Agar image attach hui hai aur file exist karti hai
    if image_path and os.path.exists(image_path):
        return "MEDIUM"

    return "LOW"


def assign_department(text=""):
    """
    Auto-detects and routes complaint to the correct municipal authority.
    """
    text_lower = (text or "").lower()

    # Roads & Highway Authority
    if any(word in text_lower for word in ["road", "pothole", "footpath", "highway", "divider", "traffic", "crack"]):
        return "Roads & Highway Authority"

    # Water & Sewage Board
    if any(word in text_lower for word in ["water", "pipe", "leak", "tap", "drain", "sewage", "gutter", "overflow", "drinking"]):
        return "Water & Sewage Board"

    # Municipal Corporation (Sanitation Dept)
    if any(word in text_lower for word in ["garbage", "trash", "waste", "dump", "clean", "smell", "dustbin", "dead animal"]):
        return "Municipal Corporation (Sanitation Dept)"

    # Electricity & Lighting Board
    if any(word in text_lower for word in ["light", "dark", "wire", "pole", "electric", "power", "transformer", "spark"]):
        return "Electricity & Lighting Board"

    # Default Catch-all
    return "Central Grievance Cell (Municipal Authority)"