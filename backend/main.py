##
# Contain the FastAPI app
# Define routes for uploading, searching, and downloading data
##

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from dotenv import load_dotenv
import json
import pandas as pd
import traceback
from typing import Dict, List, Optional

from data_pipeline import process_file
from db_service import check_database_status, query_transcripts
from utils import MAX_FILES, SearchCriteria, load_course_categories, is_allowed_file, generate_summary_df

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
DATABASE_FILE = os.getenv("DATABASE_FILE", "../database/database.db") # Load Database file from .env


UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Get database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)#, check_same_thread=False)  # Allow cross-thread access
    conn.row_factory = sqlite3.Row
    return conn


# Return a list of course categories
@app.get("/course-categories")
def get_course_categories():
    categories_dict = load_course_categories()
    categories_list = list(categories_dict.keys())
    return {"course_categories": categories_list}


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Handles file uploads, validates files, and processes them.
    Returns a JSON response with success and error details for each file.
    """
    check_database_status(DATABASE_FILE)
    
    # Validate file amounts
    if len(files) > MAX_FILES:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Too many files uploaded. Maximum allowed is {MAX_FILES}.",
                "data": []
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
            print(f"❌ Error processing {file.filename}: {str(e)}")  # Log error in backend
            file_result["status"] = "error"
            file_result["message"] = f"Unexpected error while processing {file.filename}: {str(e)}"
            file_result["details"] = error_details
        
        processed_results.append(file_result)

    # Return structured JSON response for all files
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "File processing completed.",
            "processed_files": processed_results
        }
    )


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

    try:
        results = query_transcripts(conn, criteria_dict)

        # Handling errors from query_transcripts()
        if results == "error":
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Database query failed. Please try again later.",
                    "data": []
                }
            )
        
        # If no results are found
        if results is None:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "not_found",
                    "message": "No transcripts found for the given search criteria.",
                    "data": []
                }
            )

        # Convert to Pandas DataFrame
        df = pd.DataFrame(results, columns=[
            "Educator First Name", "Educator Middle Name", "Educator Last Name", 
            "Degree", "Degree Level", "Course Name", "Course Category", "Adjusted Credits Earned"
        ])
    
        # Generate a summary DataFrame
        summary_df = generate_summary_df(criteria_dict, df)

    except Exception as e:
        print(f"❌ Search failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "An unexpected error occurred while searching transcripts.",
                "data": []
            }
        )

    finally:
        cursor.close()
        conn.close()  # Ensure the database connection is closed

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "queried_data": summary_df.to_dict(orient="records"),
            "educator_name": (
                f"{df['Educator First Name'].iloc[0]} {df['Educator Last Name'].iloc[0]}"
                if not df.empty and criteria_dict.get("educator_first_name") and criteria_dict.get("educator_last_name") 
                else ""
            ),
            "message": "Transcripts retrieved successfully.",
            "notes": """Note: A course with 0 credit may fall into one of the following cases: 
                        1. The course is not an actual academic course but is designed for administrative or tracking purposes. 
                        2. The educator did not pass the course.
                    """
        }
    )
