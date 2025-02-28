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
websocket_closed_flags: Dict[str, bool] = {}  # Track whether WebSocket has been closed


# Return a list of course categories
@app.get("/course-categories")
def get_course_categories():
    categories_dict = load_course_categories()
    categories_list = list(categories_dict.keys())
    return {"course_categories": categories_list}


# Send WebSocket notifications to frontend with stauts
async def notify_status(file_name: str, status: str):
    """
    Notify the frontend with a specific status message.
    Closes the WebSocket connection if needed.
    """
    print(f"🔍 Debug: Attempting to send WebSocket message for {file_name}: {status}")

    ws = websocket_connections.get(file_name) # Get the WebSocket for this file
    if not ws:
        print(f"No WebSocket connection found for {file_name}.")
        return

    try:
        # Check if the WebSocket is still open
        if ws.client_state.name != "CONNECTED":
            print(f"Skipping WebSocket message for {file_name} as the connection is closed.")
            return

        # Send the status message
        await ws.send_json({"status": status, "file_name": file_name})
        print(f"🌐 WebSocket notification sent: {status} for {file_name}")
        
        # Close the WebSocket if the status indicates it's no longer needed
        if status in {"no_flagged_courses", "intentional_closure"}:
            await asyncio.sleep(1)  # Give the frontend time to handle closure
            await ws.close()
            websocket_connections.pop(file_name, None)
            websocket_closed_flags[file_name] = True
            print(f"🌐 WebSocket connection closed for {file_name}")

    except Exception as e:
        print(f"🌐 Error sending WebSocket message for {file_name}: {e}")
        websocket_connections.pop(file_name, None)


# Manage WebSocket connections for flagged courses
@app.websocket("/ws/flagged_courses/{file_name}")
async def websocket_flagged_courses(websocket: WebSocket, file_name: str):
    """
    WebSocket connection for flagged courses. 
    Opens before file processing and sends flagged courses when ready.
    """
    file_name = decode_file_name(file_name)  # Decode spaces in filename
    print(f"🌐 WebSocket connection established for {file_name}")
    
    await websocket.accept()

    # Store WebSocket connection
    websocket_connections[file_name] = websocket

    try:
        # Send initial connection confirmation
        await websocket.send_json({"status": "connected", "file_name": file_name})
        
        # Wait for processing_lock to be created
        max_retries = 10 
        retry_delay = 1  # Delay between retries (in seconds)
        for attempt in range(max_retries):
            if file_name in processing_lock:
                break  
            await asyncio.sleep(retry_delay)  # Wait before retrying

        if file_name not in processing_lock:
            print(f"🌐 Processing lock not created for {file_name} after {max_retries} attempts. Closing WebSocket.")
            await websocket.close()
            return

        # Main WebSocket loop
        while file_name in processing_lock:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=20)  # Keep WebSocket alive
                print(f"🌐 WebSocket received message: {data}")
            except asyncio.TimeoutError:
                await websocket.send_json({"status": "ping"})  # Keep alive every 20s

    except WebSocketDisconnect:
        print(f"🌐 WebSocket disconnected unexpectedly for {file_name}")
    except Exception as e:
        print(f"🌐 WebSocket error for {file_name}: {e}")
    finally:
        print(f"🌐 WebSocket cleanup triggered for {file_name}")
        websocket_connections.pop(file_name, None)

        # Only close the WebSocket if it hasn't already been closed
        if not websocket_closed_flags.get(file_name, False):
            await websocket.close()
        else:
            print(f"WebSocket for {file_name} already closed. Skipping duplicate closure.")

        # Clean up the closed flag
        websocket_closed_flags.pop(file_name, None)


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
        }
    )


# Handle frontend requests for flagged courses
@app.get("/get_flagged_courses")
async def get_flagged_courses(file_name: str):
    """
    Retrieve flagged courses for a file and send via WebSocket. 
    Retries if flagged courses are not yet available.
    """
    file_name = decode_file_name(file_name) # Decode spaces in filename
    print(f"Fetching flagged courses for {file_name}")

    max_retries = 3  # Maximum number of retries
    retry_delay = 1  # Delay between retries (in seconds)

    for attempt in range(max_retries):
        flagged_courses = flagged_courses_store.get(file_name, [])

        if flagged_courses:
            return JSONResponse(
                status_code=200,
                content={"status": "success", "flagged_courses": flagged_courses}
            )

        await asyncio.sleep(retry_delay)  # Wait before retrying

    print(f"❌ No flagged courses found after {max_retries} attempts for {file_name}.")
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": f"No flagged courses found for {file_name}."}
    )


# Receives user decisions and resumes processing
@app.post("/submit_user_decisions")
async def submit_user_decisions(request: UserDecision):
    """
    Receive user decisions and resume processing.
    """
    file_name = decode_file_name(request.file_name) # Decode spaces in filename
    decisions = request.decisions
    print(f"Receiving user decisions for {file_name}")

    if not file_name or file_name not in processing_lock:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No active processing found."}
        )

    if not decisions:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No decisions received from frontend."}
        )

    # Store user decisions
    user_decisions_store[file_name] = decisions

    # Resume processing in data_pipeline.py
    processing_lock[file_name].set() 
    
    #Notify frontend that processing is completed before closing WebSocket
    await notify_status(file_name, "intentional_closure") 

    return JSONResponse(
        status_code=200,
        content={"status": "success", "message": "Decisions received. Processing will resume."}
    )


@app.post("/search")
def search_transcripts(criteria: SearchCriteria):
    """
    Searches transcripts based on educator name, course category, degree level.
    Args:
        criteria (SearchCriteria): Search parameters.
        conn (Connection): Database connection object.
    Returns:
        JSONResponse: Queried results.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        results = query_transcripts(conn, criteria.model_dump())
            
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
