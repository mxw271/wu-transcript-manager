import pandas as pd
import os
from typing import Dict, List, Optional, Any
import json
from pydantic import BaseModel
import base64
import hashlib
import traceback


# Constants for uploading file limits
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".csv"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
MAX_FILES = 100


# Constants for passing grades based on degree level
PASSING_GRADES = {
    "Doctorate": {"letter": "C", "numeric": 70.0},
    "Master": {"letter": "C", "numeric": 70.0},
    "Bachelor": {"letter": "D", "numeric": 60.0}
}


# Define a ranking system for letter grades, including modifiers
GRADE_RANKING = {
    "A+": 13, "A": 12, "A-": 11,
    "B+": 10, "B": 9, "B-": 8,
    "C+": 7, "C": 6, "C-": 5,
    "D+": 4, "D": 3, "D-": 2,
    "F": 1
}


# Define search request schema
class SearchCriteria(BaseModel):
    educator_first_name: Optional[str] = None
    educator_last_name: Optional[str] = None
    course_category: Optional[str] = None
    education_level: List[str] = []


# Define individual flagged course schema
class FlaggedCourse(BaseModel):
    course_name: str
    should_be_category: Optional[str] = None
    credits_earned: Optional[float] = None
    grade: Optional[str] = None
    is_passed: Optional[bool] = None


# Define the structure for flagged degrees
class FlaggedDegree(BaseModel):
    file_name: str
    degree: str
    major: str
    overall_credits_earned: Optional[float] = None
    courses: List[FlaggedCourse]


# Define the overall structure for flagged courses list
class FlaggedCoursesList(BaseModel):
    flagged_courses: List[FlaggedDegree]


# Define course decision schema
class UserDecision(BaseModel):
    file_name: str
    decisions: List[FlaggedDegree]


# Load course categories from JSON file
def load_course_categories(categories_file = "./course_categories.json"):
    # Check if the categories file exists
    if not os.path.exists(categories_file):
        print(f"Warning: {categories_file} not found! Using default empty category list.")
        return []
    
    # Load categories from JSON file
    with open(categories_file, "r", encoding="utf-8") as file:
        course_categories = json.load(file)
    
    return course_categories # Returns a dictionary of categories with descriptions


# Decode file name from the frontend
def decode_file_name(encoded_name: str) -> str:
    """
    Decode a base64 encoded file name safely, handling incorrect padding.
    """
    try:
        # Fix incorrect padding by adding '=' if necessary
        missing_padding = len(encoded_name) % 4
        if missing_padding:
            encoded_name += "=" * (4 - missing_padding)
        return base64.b64decode(encoded_name).decode("utf-8")
    except Exception as e:
        print(f"Error decoding file name: {e}")
        return None  # Return None if decoding fails


# Function to check if the file extension is allowed
def is_allowed_file(file):
    # Check if the file has an allowed extension
    if not ("." in file.filename and os.path.splitext(file.filename)[-1].lower() in ALLOWED_EXTENSIONS):
        return False

    # Check if the file size is within the limit
    if file.size > MAX_FILE_SIZE:
        return False

    return True


# Function to return a valid value or None/empty string based on type
def get_valid_value(value, default="", is_numeric=False):
    if value in [None, "", []]:  
        return None if is_numeric else default  # Return None for numeric fields, default for text fields
    if is_numeric:
        try:
            return float(value)  # Convert to float
        except ValueError:
            return None  # If conversion fails, return None
    return value  # Return as-is for string fields


# Function to categorize degree levels
def categorize_degree(degree: str) -> str:
    """
    Categorizes a degree into doctor, master, or bachelor level.
    Args:
        degree (str): The degree name.
    Returns:
        str: The categorized degree level.
    """
    if pd.isna(degree):
        return "Unknown"

    degree = degree.lower()
    if any(word in degree for word in ["phd", "doctor", "md", "dnp", "dr"]):
        return "Doctorate"
    elif any(word in degree for word in ["master", "ms", "ma", "mba", "m.ed", "mph"]):
        return "Master"
    elif any(word in degree for word in ["bachelor", "bs", "ba", "b.ed", "bba", "bsc"]):
        return "Bachelor"
    else:
        return "Unknown"


# Function to determine adjusted credits
def calculate_adjusted_credits(
    grade: str, 
    credits_earned: float, 
    degree_level: str,
    #should_be_category: str
) -> float:
    """
    Determines adjusted credits earned based on grade, passing grade for the degree level, and course category.
    Args:
        grade (str): The grade received.
        credits_earned (float): The number of credits earned for the course.
        degree_level (str): The categorized degree level.
        should_be_category (str): The course category.
    Returns:
        float: Adjusted credits earned (0 if the grade is below passing, else credits_earned).
    """
    if pd.isna(grade) or pd.isna(credits_earned): 
        return 0  # If grade or credits_earned is missing, assume no credits earned

    # Convert grade to uppercase for consistency
    grade = grade.upper()

    # Get the passing grade for the degree level (default to "D" if unknown)
    passing_grade = PASSING_GRADES.get(degree_level, "D")

     # Compare grades using the ranking system
    if GRADE_RANKING.get(grade, 0) >= GRADE_RANKING.get(passing_grade, 0):
        return credits_earned

    return 0


# Function to generate a hash for a row (excluding file_name)
def generate_row_hash(first_name, last_name, institution_name, degree, major, minor, awarded_date, overall_credits_earned, overall_gpa, course_name, grade):
    """Generates a hash for a row excluding file_name."""
    hash_input = f"{first_name}|{last_name}|{institution_name}|{degree}|{major}|{minor}|{awarded_date}|{overall_credits_earned}|{overall_gpa}|{course_name}|{grade}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


# Function to load or initialize JSON log file
def load_json_log(log_file):
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read().strip()  
                if not content: 
                    return {}  # Return an empty dictionary instead of throwing an error
                return json.loads(content) 
        except (json.JSONDecodeError, ValueError) as e:  
            print(f"⚠️ Warning: JSON log file is corrupted. Resetting log. Error: {str(e)}")
            return {}  # If JSON is invalid, return an empty dictionary
    return {}  # If file does not exist, return an empty dictionary


# Function to save JSON log file
def save_json_log(log_file, log_data):
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=4)


# Function for error handling
def handle_csv_error(csv_file, log_file, log_data, message, exception):
    """Handles and logs errors during CSV processing."""
    error_details = traceback.format_exc() if isinstance(exception, Exception) else str(exception)
    print(f"{message}: {error_details}")
    
    log_data[csv_file] = {"status": "error", "message": message, "details": error_details}
    save_json_log(log_file, log_data)


# Function to format educator's full name
def format_name(first, middle, last):
    return f"{first} {middle + ' ' if pd.notna(middle) and middle.strip() else ''}{last}"


# Function to generate a summary DataFrame
def generate_summary_df(
    criteria_dict: Dict, 
    df: pd.DataFrame, 
    categories_file: str = "course_categories.json"
) -> pd.DataFrame:
    """
    Generates a summary DataFrame with unique course categories and corresponding course details.
    Args:
        criteria_dict (dict): Dictionary containing search criteria.
        df (pd.DataFrame): Input DataFrame containing course data.
        categories_file (str): Path to the JSON file containing course categories.
    Returns:
        pd.DataFrame: Processed summary DataFrame with categories and course details.
    """
    # Load categorized courses data from JSON
    categories_dict = load_course_categories()
    unique_categories = list(categories_dict.keys())
    unique_categories.append("Uncategorized")

    # Initialize dictionary to store course details for each category
    category_mapping = {category: [] for category in unique_categories}

    # Populate category_mapping with course details
    for _, row in df.iterrows():
        # Determine formatted course string based on criteria_dict["educator_first_name"] & criteria_dict["educator_last_name"]
        """if criteria_dict.get("educator_first_name") and criteria_dict.get("educator_last_name"): 
            formatted_course = f"{row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits)"
        else:  # Include educator name
            formatted_course = f"{format_name(row['Educator First Name'], row['Educator Middle Name'], row['Educator Last Name'])}: {row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits)"
        """
        formatted_course = f"{row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits - {format_name(row['Educator First Name'], row['Educator Middle Name'], row['Educator Last Name'])})"
        
        # Assign course to correct category or "Uncategorized"
        category = row["Course Category"] if row["Course Category"] in unique_categories else "Uncategorized"
        category_mapping[category].append(formatted_course)

    # Convert category_mapping to a list of tuples, ensuring every category exists
    expanded_rows = []
    for category in unique_categories:
        if category_mapping[category]:  # If there are courses in this category
            for course_detail in sorted(set(category_mapping[category])):  # Sort and remove duplicates
                expanded_rows.append((category, course_detail))
        else:
            expanded_rows.append((category, "N/A"))  # If no courses found, assign "N/A"

    # Convert to DataFrame and drop duplicates
    summary_df = pd.DataFrame(expanded_rows, columns=["Category", "Course Details"]).drop_duplicates()

    # Sort the DataFrame
    summary_df_sorted = summary_df.sort_values(
        by=["Category", "Course Details"],
        key=lambda col: col.str.lower() if col.name in ["Category", "Course Details"] else col,
        ascending=[True, True]
    ).reset_index(drop=True)


    return summary_df_sorted


