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
from typing import List, Optional

from models_service import get_openai_client
from process_categories import load_course_categories
from data_pipeline import process_file
from db_service import insert_educator, insert_transcript, insert_course, query_transcripts


app = FastAPI()


# Load environment variables from .env file
DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")  # Ensure correct path
load_dotenv(DOTENV_PATH)
DATABASE_FILE = os.getenv("DATABASE_FILE") # Load Database file from .env


# Allow CORS for all origins (for development purposes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)


UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILES = 300


# Check if the file extension is allowed
def is_allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Define search request schema
class SearchCriteria(BaseModel):
    educator_name: Optional[str] = None
    course_category: Optional[str] = None
    education_level: List[str] = []


# Get database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)#, check_same_thread=False)  # Allow cross-thread access
    conn.row_factory = sqlite3.Row
    return conn


# Generate a summary DataFrame
def generate_summary_df(df: pd.DataFrame, categories_file: str = "course_categories.json") -> pd.DataFrame:
    """
    Generates a summary DataFrame with unique course categories and corresponding course details.
    Args:
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
        formatted_course = f"{row['Course Name']} ({row['Degree']} - {row['Adjusted Credits Earned']} credits)"
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
        key=lambda col: col.str.lower() if col.name == "Category" else col,
        ascending=[True, True]
    ).reset_index(drop=True)

    return summary_df_sorted


# Return a list of course categories
@app.get("/course-categories")
def get_course_categories():
    return {"course_categories": load_course_categories()}


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    # Validate file amounts
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"Too many files uploaded. Maximum allowed is {MAX_FILES}."
        )

    # Validate file formats
    for file in files:
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400, detail=f"File format not allowed: {file.filename}"
            )

    processed_results = []

    # Process files one by one if no more than 100
    if len(files) <= 100:
        for file in files:
            if not is_allowed_file(file.filename):
                raise HTTPException(
                    status_code=400, detail=f"File format not allowed: {file.filename}"
                )
            file_location = os.path.join(UPLOAD_FOLDER, file.filename)
            with open(file_location, "wb") as f:
                f.write(await file.read())
            #processed_results.append(process_file(file_location, DATABASE_FILE))
            process_file(file_location, DATABASE_FILE)

    # Process files in batches of 10 if more than 100
    else:
        for i in range(0, len(files), 10):
            batch = files[i:i + 10]
            for file in batch:
                if not is_allowed_file(file.filename):
                    raise HTTPException(
                        status_code=400, detail=f"File format not allowed: {file.filename}"
                    )
                file_location = os.path.join(UPLOAD_FOLDER, file.filename)
                with open(file_location, "wb") as f:
                    f.write(await file.read())
                #processed_results.append(process_file(file_location, DATABASE_FILE))
                process_file(file_location, DATABASE_FILE)
    
    # Return the processed data to the frontend            
    return JSONResponse(content={"processed_files": processed_results})


@app.post("/search")
def search_transcripts(criteria: SearchCriteria, conn=Depends(get_db_connection)):
    """
    Searches transcripts based on educator name, course category, or both.
    Args:
        criteria (SearchCriteria): Search parameters.
        conn (Connection): Database connection object.
    Returns:
        JSONResponse: Queried results.
    """
    criteria_dict = criteria.model_dump()
    cursor = conn.cursor()
    print(criteria_dict.get("educator_name"), criteria_dict.get("course_category"), criteria_dict.get("education_level"))

    try:
        results = query_transcripts(conn, criteria_dict)
        if not results:
            raise HTTPException(status_code=404, detail="No transcripts found")

        # Convert to Pandas DataFrame
        df = pd.DataFrame(results, columns=["Educator Name", "Degree", "Degree Level", "Course Name", "Course Category", "Adjusted Credits Earned"])

        # Generate a summary DataFrame
        summary_df = generate_summary_df(df)
        print(summary_df)

    finally:
        cursor.close()
        conn.close()  # Ensure the database connection is closed

    return JSONResponse(content={
        "queried_data": summary_df.to_dict(orient="records"),
        "educator_name": df["Educator Name"].iloc[0] if not df.empty else "Unknown",
        "notes": "Note: A course with 0 credits may fall into one of the following cases: 1. The course is not an actual academic course but is designed for administrative or tracking purposes. 2. The educator did not pass the course."
    })


@app.post("/download")
def download_transcripts(criteria: SearchCriteria, conn=Depends(get_db_connection)):
    """
    Queries transcript data and generates a CSV file for download.
    """
    criteria_dict = criteria.model_dump()
    cursor = conn.cursor()
    
    try:
        results = query_transcripts(conn, criteria_dict)
        if not results:
            raise HTTPException(status_code=404, detail="No transcripts found")
    
        # Convert to Pandas DataFrame
        df = pd.DataFrame(results, columns=["Educator Name", "Degree", "Degree Level", "Course Name", "Course Category", "Adjusted Credits Earned"])

        # Generate a summary DataFrame
        summary_df = generate_summary_df(df)

        # Extract Educator Name for filename (default fallback if not available)
        educator_name = df["Educator Name"].iloc[0] if not df.empty else "Transcript"

        # Create filename
        filename = f"{educator_name} Qualification Worksheet.csv"

        # Convert DataFrame to CSV in-memory (instead of writing to disk)
        csv_stream = summary_df.to_csv(index=False)

        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv",
        }
        print("Sending headers:", headers)
        print(filename) 

    finally:
        conn.close()  # Ensure the database connection is closed

    print("sending csv stream")
    return StreamingResponse(
        iter([csv_stream]), 
        media_type="text/csv",
        headers=headers
    )
