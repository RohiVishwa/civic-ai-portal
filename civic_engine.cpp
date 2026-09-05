#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <cctype>

using namespace std;

enum Severity { LOW = 1, MEDIUM = 2, HIGH = 3, CRITICAL = 4 };
enum Category { ROAD, DRAINAGE, STREET_LIGHT, GARBAGE, OTHER };

struct Complaint {
    int id;
    string title;
    string description;
    string location;
    Severity severity;
    Category category;
    int priorityScore;
    string assignedDepartment;
    bool isDuplicate;
    double confidence;
};

class CivicEngine {
private:
    vector<Complaint> complaints;
    int nextId;
    map<string, Category> keywordMap;
    
public:
    CivicEngine() {
        nextId = 1;
        keywordMap["pothole"] = ROAD;
        keywordMap["crack"] = ROAD;
        keywordMap["road"] = ROAD;
        keywordMap["drain"] = DRAINAGE;
        keywordMap["sewage"] = DRAINAGE;
        keywordMap["water"] = DRAINAGE;
        keywordMap["light"] = STREET_LIGHT;
        keywordMap["street"] = STREET_LIGHT;
        keywordMap["garbage"] = GARBAGE;
        keywordMap["waste"] = GARBAGE;
        keywordMap["trash"] = GARBAGE;
    }
    
    Severity calculateSeverity(const string& description, const string& location) {
        string descLower = description;
        transform(descLower.begin(), descLower.end(), descLower.begin(), ::tolower);
        
        if (descLower.find("accident") != string::npos || 
            descLower.find("emergency") != string::npos ||
            descLower.find("electrocution") != string::npos ||
            descLower.find("life") != string::npos) {
            return CRITICAL;
        }
        
        if (descLower.find("deep") != string::npos || 
            descLower.find("large") != string::npos ||
            descLower.find("major") != string::npos ||
            descLower.find("dangerous") != string::npos) {
            return HIGH;
        }
        
        if (descLower.find("small") != string::npos || 
            descLower.find("minor") != string::npos) {
            return MEDIUM;
        }
        
        return LOW;
    }
    
    bool isMainRoad(const string& location) {
        string locLower = location;
        transform(locLower.begin(), locLower.end(), locLower.begin(), ::tolower);
        
        if (locLower.find("main") != string::npos ||
            locLower.find("highway") != string::npos ||
            locLower.find("national") != string::npos ||
            locLower.find("state") != string::npos) {
            return true;
        }
        return false;
    }
    
    int calculatePriority(Severity sev, bool isMainRoad, bool isDuplicate) {
        int baseScore = (int)sev * 25;
        if (isMainRoad) baseScore += 20;
        if (isDuplicate) baseScore -= 10;
        if (baseScore > 100) baseScore = 100;
        if (baseScore < 0) baseScore = 0;
        return baseScore;
    }
    
    Category detectCategory(const string& description) {
        string descLower = description;
        transform(descLower.begin(), descLower.end(), descLower.begin(), ::tolower);
        
        int maxMatches = 0;
        Category bestCategory = OTHER;
        
        for (auto& pair : keywordMap) {
            if (descLower.find(pair.first) != string::npos) {
                int count = 0;
                size_t pos = 0;
                while ((pos = descLower.find(pair.first, pos)) != string::npos) {
                    count++;
                    pos += pair.first.length();
                }
                if (count > maxMatches) {
                    maxMatches = count;
                    bestCategory = pair.second;
                }
            }
        }
        return bestCategory;
    }
    
    string assignDepartment(Category cat) {
        switch(cat) {
            case ROAD: return "Road Maintenance Department";
            case DRAINAGE: return "Water & Drainage Department";
            case STREET_LIGHT: return "Electricity Department";
            case GARBAGE: return "Sanitation Department";
            default: return "General Services Department";
        }
    }
    
    bool checkDuplicate(const string& title, const string& location) {
        string titleLower = title;
        transform(titleLower.begin(), titleLower.end(), titleLower.begin(), ::tolower);
        string locLower = location;
        transform(locLower.begin(), locLower.end(), locLower.begin(), ::tolower);
        
        for (auto& c : complaints) {
            string cTitle = c.title;
            transform(cTitle.begin(), cTitle.end(), cTitle.begin(), ::tolower);
            string cLoc = c.location;
            transform(cLoc.begin(), cLoc.end(), cLoc.begin(), ::tolower);
            
            if (cTitle.find(titleLower) != string::npos || titleLower.find(cTitle) != string::npos) {
                if (cLoc.find(locLower) != string::npos || locLower.find(cLoc) != string::npos) {
                    return true;
                }
            }
        }
        return false;
    }
    
    Complaint processComplaint(const string& title, const string& desc, 
                                const string& location, double aiConfidence) {
        Complaint c;
        c.id = nextId++;
        c.title = title;
        c.description = desc;
        c.location = location;
        c.confidence = aiConfidence;
        c.isDuplicate = checkDuplicate(title, location);
        c.category = detectCategory(desc);
        c.severity = calculateSeverity(desc, location);
        bool isMain = isMainRoad(location);
        c.priorityScore = calculatePriority(c.severity, isMain, c.isDuplicate);
        c.assignedDepartment = assignDepartment(c.category);
        complaints.push_back(c);
        return c;
    }
    
    string severityToString(Severity s) {
        switch(s) {
            case LOW: return "LOW";
            case MEDIUM: return "MEDIUM";
            case HIGH: return "HIGH";
            case CRITICAL: return "CRITICAL";
            default: return "UNKNOWN";
        }
    }
    
    string categoryToString(Category c) {
        switch(c) {
            case ROAD: return "Road";
            case DRAINAGE: return "Drainage";
            case STREET_LIGHT: return "Street Light";
            case GARBAGE: return "Garbage";
            default: return "Other";
        }
    }
    
    void printComplaint(const Complaint& c) {
        cout << "\n========================================";
        cout << "\n📋 Complaint ID: #" << c.id;
        cout << "\n📌 Title: " << c.title;
        cout << "\n📍 Location: " << c.location;
        cout << "\n🏷️  Category: " << categoryToString(c.category);
        cout << "\n⚡ Severity: " << severityToString(c.severity);
        cout << "\n🎯 Priority Score: " << c.priorityScore << "/100";
        cout << "\n🏢 Department: " << c.assignedDepartment;
        cout << "\n🤖 AI Confidence: " << (c.confidence * 100) << "%";
        cout << "\n🔄 Duplicate: " << (c.isDuplicate ? "YES ⚠️" : "NO");
        cout << "\n========================================\n";
    }
};

// Main test function
int main() {
    CivicEngine engine;
    
    cout << "🏗️ CIVIC ENGINE TEST\n";
    cout << "====================\n";
    
    Complaint c = engine.processComplaint(
        "Deep pothole on main road",
        "Large pothole causing traffic issues on main road",
        "Main Road, Sector 5",
        0.94
    );
    
    engine.printComplaint(c);
    
    return 0;
}