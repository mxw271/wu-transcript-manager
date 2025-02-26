##
# Contain the FastAPI app
# Define routes for uploading, searching, and downloading data
##

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from dotenv import load_dotenv
import json
import pandas as pd
import traceback
from typing import Dict, List, Optional
import base64
import asyncio

from data_pipeline import process_file
from db_service import check_database_status, query_transcripts
from utils import (
    MAX_FILES, SearchCriteria, UserDecision, load_course_categories, 
    decode_file_name, is_allowed_file, generate_summary_df
)


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


# Global storage for WebSocket connections & flagged courses
websocket_connections: Dict[str, WebSocket] = {}
flagged_courses_store: Dict[str, List[Dict]] = {}
user_decisions_store: Dict[str, List[Dict]] = {}
processing_lock: Dict[str, asyncio.Event] = {} # Lock to pause/resume processing


# Return a list of course categories
@app.get("/course-categories")
def get_course_categories():
    categories_dict = load_course_categories()
    categories_list = list(categories_dict.keys())
    return {"course_categories": categories_list}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Handles single file uploads, validates the file, and processes it.
    Returns a JSON response with success and error details.
    This function is called sequentially for each file.
    """
    if not file:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No file uploaded"})

    check_database_status(DATABASE_FILE)
    
    file_name = file.filename
    print(f"File uploaded: {file_name}")

    file_result = {"filename": file_name}
    try:
        # Validate file formats
        if not is_allowed_file(file):
            return JSONResponse(
                status_code=400, 
                content={"status": "error", "message": f"File format not allowed: {file_name}"}
            )
        
        # Save file to server
        file_location = os.path.join(UPLOAD_FOLDER, file_name)
        with open(file_location, "wb") as f:
            f.write(await file.read())
        print(f"✅ File saved successfully: {file_location}")

        # Process the file
        print(f"Processing file: {file_name}...")
        process_result = await process_file(file_location, DATABASE_FILE)

        if process_result["status"] == "error":
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": process_result["message"],
                    "details": process_result.get("details", "")
                }
            )

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error processing {file_name}: {str(e)}")  # Log error in backend
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Unexpected error while processing {file_name}: {str(e)}",
                "details": error_details
            }
        )
    
    # Return structured JSON response
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "File processing completed.",
            "processed_files": file_result
        }
    )


# Manage WebSocket connections for flagged courses
@app.websocket("/ws/flagged_courses/{file_name}")
async def websocket_flagged_courses(websocket: WebSocket, file_name: str):
    """
    WebSocket connection for flagged courses. 
    This opens before file processing starts and sends flagged courses when ready.
    """
    await websocket.accept()

    file_name = decode_file_name(file_name)  # Decode spaces in filename
    print(f"🌐 WebSocket connection established for {file_name}")

    # Store WebSocket connection
    websocket_connections[file_name] = websocket

    try:
        # Send initial connection confirmation
        await websocket.send_json({"status": "connected", "file_name": file_name})

        while True:
            await asyncio.sleep(5)  # Keep connection alive with periodic sleep
    except WebSocketDisconnect:
        websocket_connections.pop(file_name, None)
        print(f"🌐 WebSocket disconnected for {file_name}")


# Send WebSocket notifications to frontend when flagged courses are ready
async def notify_flagged_courses_ready(file_name: str):
    """
    Notify the frontend when flagged courses are ready.
    """
    ws = websocket_connections.get(file_name) # Get the WebSocket for this file
    if not ws:
        print(f"No WebSocket connection found for {file_name}.")
        return

    # Ensure the notification is for the correct file
    if file_name not in processing_lock:
        print(f"Ignoring notification for {file_name} as processing has completed.")
        return

    try:
        await ws.send_json({"status": "ready", "file_name": file_name})
        print(f"🌐 WebSocket notification sent for {file_name}")
    except Exception as e:
        print(f"🌐 Error sending WebSocket message for {file_name}: {e}")


# Send WebSocket notifications to frontend when there are no flagged courses
async def notify_no_flagged_courses(file_name: str):
    """
    Notify the frontend that no flagged courses were found.
    The frontend should close the WebSocket and continue processing.
    """
    ws = websocket_connections.get(file_name)  # Get the WebSocket for this file
    if not ws:
        print(f"No WebSocket connection found for {file_name}.")
        return

    try:
        await ws.send_json({"status": "no_flagged_courses", "file_name": file_name})
        print(f"🌐 WebSocket notification sent: No flagged courses for {file_name}")

        # Close the WebSocket connection
        await ws.close()
        websocket_connections.pop(file_name, None)
    except Exception as e:
        print(f"🌐 Error sending 'no flagged courses' WebSocket message for {file_name}: {e}")


# Handle frontend requests for flagged courses
@app.get("/get_flagged_courses")
async def get_flagged_courses(file_name: str):
    """
    Retrieve flagged courses for a file and send via WebSocket.
    """
    file_name = decode_file_name(file_name) # Decode spaces in filename
    print(f"Fetching flagged courses for {file_name}")
    '''
    max_retries = 10  # Limit retries
    retries = 0

    while retries < max_retries:
        print(f"Retry {retries + 1} for flagged courses: {file_name}")
        flagged_courses = flagged_courses_store.get(file_name, [])
        if flagged_courses:
            # Send flagged courses through WebSocket
            await notify_flagged_courses_ready(file_name)
            return {"status": "success", "flagged_courses": flagged_courses}

        await asyncio.sleep(1)
        retries += 1
    '''
    flagged_courses = flagged_courses_store.get(file_name, [])
    if flagged_courses:
        return JSONResponse(
            status_code=200,
            content={"status": "success", "flagged_courses": flagged_courses}
        )
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": f"No flagged courses found for {file_name}."}
    )


# Receives user decisions and resumes processing
@app.post("/submit_flagged_decisions")
async def submit_flagged_decisions(request: UserDecision):
    """
    Receive user decisions and resume processing.
    """
    file_name = decode_file_name(request.file_name) # Decode spaces in filename
    print(f"Processing file: {file_name}")
    print(f"Current processing_lock state: {processing_lock}")
    print(f"Current flagged_courses_store state: {flagged_courses_store}")
    
    decisions = request.decisions
    print(f"Receiving user decisions for {file_name}")

    if not file_name or file_name not in processing_lock:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No active processing found for this file."}
        )

    if not decisions:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No decisions received from frontend."}
        )

    # Store user decisions
    user_decisions_store[file_name] = decisions

    # Unlock processing and clean up state
    if file_name in processing_lock:
        processing_lock[file_name].set()  # Resume processing
        del processing_lock[file_name]  # Ensure the lock is removed
    if file_name in flagged_courses_store:
        del flagged_courses_store[file_name]  # Clean up flagged courses

    # Close WebSocket for the processed file
    if file_name in websocket_connections:
        ws = websocket_connections.pop(file_name, None)
        if ws:
            await ws.close()
            print(f"🌐 WebSocket closed for {file_name}")

    return JSONResponse(
        status_code=200,
        content={"status": "success", "message": "Decisions received. Processing will resume."}
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
