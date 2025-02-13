##
# Contain the FastAPI app
# Define routes for uploading, searching, and downloading data
##
# Install the required Python libraries:
# pip3 install sqlite fastapi uvicorn pandas
##

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
from dotenv import load_dotenv
import json
import pandas as pd
import traceback
from typing import Dict, List, Optional

from clients_service import get_openai_client
from process_categories import load_course_categories
from data_pipeline import process_file
from db_service import check_database_content, insert_educator, insert_transcript, insert_course, query_transcripts


app = FastAPI()

# Allow CORS for all origins (for development purposes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)


# Load environment variables from .env file
DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")  # Ensure correct path
load_dotenv(DOTENV_PATH)


# Load Database file from .env (fallback if .env is missing)
DATABASE_FILE = os.getenv("DATABASE_FILE" "../database/database.db") 
if not DATABASE_FILE or not os.path.exists(DATABASE_FILE):
    raise FileNotFoundError(f"❌ Database file not found: {DATABASE_FILE}")

# Verify database content
check_database_content(DATABASE_FILE)


UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
MAX_FILES = 300


# Function to check if the file extension is allowed
def is_allowed_file(file):
    # Check if the file has an allowed extension
    if not ("." in file.filename and file.filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS):
        return False

    # Check if the file size is within the limit
    if file.size > MAX_FILE_SIZE:
        return False

    return True


# Define search request schema
class SearchCriteria(BaseModel):
    educator_firstName: Optional[str] = None
    educator_lastName: Optional[str] = None
    course_category: Optional[str] = None
    education_level: List[str] = []


# Get database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)#, check_same_thread=False)  # Allow cross-thread access
    conn.row_factory = sqlite3.Row
    return conn


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
    unique_categories = load_course_categories(openai_client = get_openai_client())
    unique_categories.append("Uncategorized")

    # Initialize dictionary to store course details for each category
    category_mapping = {category: [] for category in unique_categories}

    # Populate category_mapping with course details
    for _, row in df.iterrows():
        # Determine formatted course string based on criteria_dict["educator_firstName"] & criteria_dict["educator_lastName"]
        """if criteria_dict.get("educator_firstName") and criteria_dict.get("educator_lastName"): 
            formatted_course = f"{row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits)"
        else:  # Include educator name
            formatted_course = f"{format_name(row['Educator FirstName'], row['Educator MiddleName'], row['Educator LastName'])}: {row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits)"
        """
        formatted_course = f"{row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits - {format_name(row['Educator FirstName'], row['Educator MiddleName'], row['Educator LastName'])})"
        
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


# Return a list of course categories
@app.get("/course-categories")
def get_course_categories():
    return {"course_categories": load_course_categories()}


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Handles file uploads, validates files, and processes them.
    Returns a JSON response with success and error details for each file.
    """
    # Validate file amounts
    if len(files) > MAX_FILES:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Too many files uploaded. Maximum allowed is {MAX_FILES}."
            } 
        )

    processed_results = []

    # Process files one by one if no more than 100
    for file in files:
        file_result = {"filename": file.filename}

        try:
            # Validate file formats
            if not is_allowed_file(file):
                file_result["status"] = "error"
                file_result["message"] = f"File format not allowed: {file.filename}"
                processed_results.append(file_result)
                continue 

            # Save file to server
            file_location = os.path.join(UPLOAD_FOLDER, file.filename)
            with open(file_location, "wb") as f:
                f.write(await file.read())
            print(f"✅ File saved successfully: {file_location}")

            # Process the file
            print(f"Processing file: {file.filename}...")
            process_result = process_file(file_location, DATABASE_FILE)

            if process_result["status"] == "error":
                file_result["status"] = "error"
                file_result["message"] = process_result["message"]
                file_result["details"] = process_result.get("details", "")
            else:
                file_result["status"] = "success"
                file_result["message"] = "File processed successfully."

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error processing {file.filename}: {e}")  # Log error in backend
            file_result["status"] = "error"
            file_result["message"] = f"Unexpected error while processing {file.filename}: {str(e)}"
            file_result["details"] = error_details
        
        processed_results.append(file_result)

    # Return structured JSON response for all files
    return JSONResponse(content={"processed_files": processed_results})


@app.post("/search")
def search_transcripts(criteria: SearchCriteria, conn=Depends(get_db_connection)):
    """
    Searches transcripts based on educator name, course category, degree level.
    Args:
        criteria (SearchCriteria): Search parameters.
        conn (Connection): Database connection object.
    Returns:
        JSONResponse: Queried results.
    """
    criteria_dict = criteria.model_dump()
    cursor = conn.cursor()
    print(criteria_dict.get("educator_firstName"), criteria_dict.get("educator_lastName"), criteria_dict.get("course_category"), criteria_dict.get("education_level"))

    try:
        results = query_transcripts(conn, criteria_dict)
        if not results:
            return {
                "status": "success",
                "message": "No transcripts found for the given criteria.",
                "data": []
            }

        # Convert to Pandas DataFrame
        df = pd.DataFrame(results, columns=["Educator FirstName", "Educator MiddleName", "Educator LastName", "Degree", "Degree Level", "Course Name", "Course Category", "Adjusted Credits Earned"])
    
        # Generate a summary DataFrame
        summary_df = generate_summary_df(criteria_dict, df)

    finally:
        cursor.close()
        conn.close()  # Ensure the database connection is closed

    return JSONResponse(content={
        "queried_data": summary_df.to_dict(orient="records") if results else [],
        "educator_name": (
            f"{df['Educator FirstName'].iloc[0]} {df['Educator LastName'].iloc[0]}"
            if not df.empty and criteria_dict.get("educator_firstName") and criteria_dict.get("educator_lastName") 
            else ""
        ) if results else "",
        "message": "Transcripts retrieved successfully." if results else "No transcripts found for the given search criteria.",
        "notes": """Note: A course with 0 credit may fall into one of the following cases: 
                    1. The course is not an actual academic course but is designed for administrative or tracking purposes. 
                    2. The educator did not pass the course.
                 """ if results else ""
    })
