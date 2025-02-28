import pandas as pd
import numpy as np
import sqlite3
import os
import csv
import json
from pathlib import Path
from typing import Dict, Any, List
import time
import traceback
from collections import defaultdict
import asyncio
from asyncio import Lock

from text_processing.extraction import extract_text_from_file_using_opencv, extract_text_from_file_using_azure
from text_processing.formatting import generate_data_dict_using_openai, preprocess_data_dict, json_data_to_dataframe
from text_processing.validation import rule_based_validation, validate_coursework_openai, openai_based_validation
from text_processing.matching import match_courses_using_openai, match_courses_using_sbert
from db_service import insert_records_from_dict
from utils import (
    ALLOWED_EXTENSIONS, PASSING_GRADES, GRADE_RANKING, load_course_categories, get_valid_value, 
    categorize_degree, calculate_adjusted_credits, generate_row_hash
)


# Specify the output directory
OUTPUT_FOLDER = "./middle_products"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


global_lock = Lock()  # Global lock to synchronize file processing


# Step 1 option 1: Load data from csv file 
def load_data(file_path: str) -> dict:
    """
    Load data from a CSV and formats it into a nested dictionary.
    Args:
        file_path (str): Path to the CSV file.
    Returns:
        dict: Result containing status, message, and extracted JSON object.
    """
    try:
        # Load CSV into a DataFrame
        print("Loading data from CSV...")
        df = pd.read_csv(file_path)
        if df.empty:
            return {
                "status": "error",
                "message": "CSV file is empty.",
                "details": "Ensure the CSV contains readable data.",
                "file": file_path
            }

        # Initialize the data dictionary
        data_dict = {"student": {}, "degrees": [], "file_name": df["file_name"].iloc[0] if "file_name" in df else ""}

        # Extract student details
        data_dict["student"] = {
            "first_name": df["first_name"].iloc[0] if "first_name" in df else "",
            "middle_name": df["middle_name"].iloc[0] if "middle_name" in df and pd.notna(df["middle_name"].iloc[0]) else "",
            "last_name": df["last_name"].iloc[0] if "last_name" in df else "",
        }

        # Group courses by unique degree
        degrees = defaultdict(lambda: {
            "degree": "",
            "major": "",
            "minor": "",
            "institution_name": "",
            "awarded_date": "",
            "overall_credits_earned": None,
            "overall_gpa": None,
            "courses": []
        })

        print("Organizing courses by degree...")
        for _, row in df.iterrows():
            # Normalize key values to prevent minor differences causing duplicate degrees
            institution = row["institution_name"].strip() if "institution_name" in row and pd.notna(row["institution_name"]) else ""
            degree = row["degree"].strip() if "degree" in row and pd.notna(row["degree"]) else ""
            major = row["major"].strip() if "major" in row and pd.notna(row["major"]) else ""
            minor = row["minor"].strip() if "minor" in row and pd.notna(row["minor"]) else ""
            awarded_date = row["awarded_date"].strip() if "awarded_date" in row and pd.notna(row["awarded_date"]) else ""

            # Create a standardized key for degree grouping
            degree_key = (institution.lower(), degree.lower(), major.lower(), minor.lower(), awarded_date)

            # Populate degree details only once
            if not degrees[degree_key]["degree"]: 
                degrees[degree_key].update({
                    "degree": degree,
                    "major": major,
                    "minor": minor,
                    "institution_name": institution,
                    "awarded_date": awarded_date,
                    "overall_credits_earned": row["overall_credits_earned"] if "overall_credits_earned" in row and pd.notna(row["overall_credits_earned"]) else None,
                    "overall_gpa": row["overall_gpa"] if "overall_gpa" in row and pd.notna(row["overall_gpa"]) else None,
                })

            # Add course information under the respective degree
            degrees[degree_key]["courses"].append({
                "course_name": row["course_name"].strip() if "course_name" in row and pd.notna(row["course_name"]) else "",
                "credits_earned": row["credits_earned"] if "credits_earned" in row and pd.notna(row["credits_earned"]) else None,
                "grade": row["grade"].strip() if "grade" in row and pd.notna(row["grade"]) else "",
            })

        # Convert defaultdict to list of degrees
        data_dict["degrees"] = list(degrees.values())

        # Add the file name to the DataFrame
        data_dict["file_name"] = os.path.basename(file_path)

        print("Loaded data:", json.dumps(data_dict, indent=4))

        print("Data loaded successfully.")
        return {
            "status": "success",
            "message": "CSV file loaded successfully.",
            "file": file_path,
            "data": data_dict
        }
    
    except Exception as e:
        error_message = f"Error loading data from file: {str(e)}"
        print(error_message)
        print(traceback.format_exc())  # Print full traceback for debugging
        return {
            "status": "error",
            "message": error_message,
            "details": traceback.format_exc(),
            "file": file_path
        }


# Step 1 option 2: Extract data from pdf / jpg / jpeg / png file 
def extract_data(file_path: str) -> dict:
    """
    Extracts text from a PDF, processes it using OpenAI, and formats it into a nested dictionary.
    Args:
        file_path (str): Path to the PDF / JPG / JPEG / PNG file.
    Returns:
        dict: Result containing status, message, and extracted JSON object.
    """
    try:
        # Extract text from PDF
        print("Extracting text from PDF...")
        extracted_text = extract_text_from_file_using_opencv(file_path, OUTPUT_FOLDER)
        if not extracted_text:
            return {
                "status": "error",
                "message": "Extracted text is empty. PDF may not contain valid text.",
                "details": "Ensure the PDF contains readable text, not just images.",
                "file": file_path
            }

        # Save the text to a .csv file
        extracted_text_path = os.path.join(OUTPUT_FOLDER, f"{Path(file_path).stem}_extracted_text_opencv.csv")
        with open(extracted_text_path, "w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Line"])  # Add a header
            csv_writer.writerows([[line] for line in extracted_text.splitlines()])
        print(f"Extracted text saved to: {extracted_text_path}")

        # Process the text using OpenAI API
        print("Sending extracted text to OpenAI API for processing...")
        data_dict = generate_data_dict_using_openai(extracted_text)
        if not data_dict:
            return {
                "status": "error",
                "message": "OpenAI response is empty. Check API request and input text.",
                "details": "Possible issues: API timeout, invalid input text, or authentication failure.",
                "file": file_path
            }

        # Add the file name to the DataFrame
        data_dict["file_name"] = os.path.basename(file_path)

        print("Extracted data:", json.dumps(data_dict, indent=4))

        # Save the JSON obejct to a file
        json_path = os.path.join(OUTPUT_FOLDER, f"{Path(file_path).stem}_extracted_data_dict.json")
        with open(json_path, "w") as json_file:
            json.dump(data_dict, json_file, indent=4)
        print(f"JSON object saved to: {json_path}")

        return {
            "status": "success", 
            "message": "Data extracted successfully.", 
            "file": file_path, 
            "data": data_dict
        }
    
    except Exception as e:
        error_message = f"Error extracting data from file: {str(e)}"
        print(error_message)
        print(traceback.format_exc())  # Print full traceback for debugging
        return {
            "status": "error",
            "message": error_message,
            "details": traceback.format_exc(),
            "file": file_path
        }


# Step 2: Validate extracted data 
def validate_data(data_dict: dict) -> dict:
    """
    Reads the extracted transcript data and apply rule-based and OpenAI-based validation.
    Args:
        data_dict (dict): The raw extracted transcript data.
    Returns:
        dict: A dictionary with status, message, and validated data.
    """
    try:
        # Proprocess data before validation
        preprocessed_dict = preprocess_data_dict(data_dict)

        # Rule-based validation
        errors = rule_based_validation(preprocessed_dict)
        if errors:
            print("Rule-based validation errors detected:")
            print("\n".join(errors)) 

        # OpenAI-based validation
        corrected_dict = openai_based_validation(preprocessed_dict)
        if not corrected_dict:
            return {
                "status": "error",
                "message": "Validation failed. No valid data returned.",
                "details": "Ensure the extracted text is valid and properly formatted."
            }

        # Ensure validated data is structured correctly
        if not isinstance(corrected_dict, dict) or not corrected_dict:
            return {
                "status": "error",
                "message": "Validated data structure is invalid.",
                "details": "Check for issues in OpenAI validation output."
            }

        print("Validated data:", json.dumps(corrected_dict, indent=4))

        # Save the JSON obejct to a file
        json_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(corrected_dict["file_name"])[0]}_validated_data_dict.json")
        with open(json_path, "w") as json_file:
            json.dump(corrected_dict, json_file, indent=4)
        print(f"JSON object saved to: {json_path}")

        return {
            "status": "success",
            "message": "Validation completed successfully.",
            "data": corrected_dict
        }
    
    except Exception as e:
        print(f"Error in validate_data(): {e}")
        print(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Unexpected error during validation: {str(e)}",
            "details": traceback.format_exc()
        }


# Step 3: Structure validated data
async def structure_data(data_dict: dict, processing_lock: dict) -> dict:
    """
    Reads the extracted transcript data, 
        matches course names to predefined categories using OpenAI, 
        processes degree levels and adjusted credits, generate row hash,
        and handles flagged courses.
    Args:
        data_dict (dict): The raw extracted transcript data.
    Returns:
        dict: A dictionary with status, message, and structured data.
    """    
    # Load course categories
    categories_dict = load_course_categories()

    # Initialize the list for flagged courses
    flagged_courses_list = []

    # Iterate through each degree and process its courses, check whether user decisions are needed
    for degree in data_dict.get("degrees", []):
        # Assign degree level
        degree["degree_level"] = categorize_degree(degree.get("degree", ""))

        # Initialize flag for uncategorized course
        course_uncategorized_flag = False
        course_names = [course["course_name"] for course in degree["courses"]]

        # Perform text matching using OpenAI
        print("Matching courses using OpenAI...")
        categorized_courses = match_courses_using_openai(course_names, categories_dict)

        # If OpenAI fails, fallback to SBERT
        if not categorized_courses or all(category == "Uncategorized" for category in categorized_courses):
            print("OpenAI classification failed or returned all 'Uncategorized'. Falling back to SBERT...")
            course_uncategorized_flag = True
            categories_list = list(categories_dict.keys())
            categorized_courses = match_courses_using_sbert(course_names, categories_list)

        # If SBERT also fails, default to Uncategorized
        if not categorized_courses or all(category == "Uncategorized" for category in categorized_courses):
            print("SBERT classification also failed, defaulting all categories to 'Uncategorized'.")
            course_uncategorized_flag = True

        for i, course in enumerate(degree["courses"]):
            course["should_be_category"] = categorized_courses[i] if categorized_courses else "Uncategorized"
        
        # Initialize flag for credit mismatch
        credit_mismatch_flag = False

        # Calculate sum of credits earned for this degree
        total_credits_earned = sum(
            float(course["credits_earned"]) if isinstance(course["credits_earned"], float) and course["credits_earned"] else 0
            for course in degree["courses"]
        )

        # Check if total credits earned matches the overall credits earned
        if degree.get("overall_credits_earned"):
            try:
                overall_credits = float(degree["overall_credits_earned"])
                if abs(total_credits_earned - overall_credits) > 0.01:  # Allow minor floating-point precision errors
                    credit_mismatch_flag = True
            except ValueError:
                credit_mismatch_flag = True
        else:
            credit_mismatch_flag = True

        passing_grade = PASSING_GRADES.get(degree["degree_level"], PASSING_GRADES["Bachelor"])  # Default to Bachelor
           
        # Determine is_passed
        for course in degree["courses"]:
            grade = course.get("grade", "").strip()
            if not grade: 
                course["is_passed"] = "Unknown"
            else:
                try: # Determine if grade is numeric
                    numeric_grade = float(grade)
                    course["is_passed"] = numeric_grade >= passing_grade["numeric"]
                except ValueError: # Grade is not a number, check letter grade
                    letter_grade = grade.upper()
                    if letter_grade in GRADE_RANKING:
                        course["is_passed"] = GRADE_RANKING[letter_grade] >= GRADE_RANKING[passing_grade["letter"]]
                    else:
                        course["is_passed"] = "Unknown"

        # Construct the flagged courses nested dictionary
        flagged_courses = []
        for course in degree["courses"]:
            flagged_course = { "course_name": course["course_name"] }
            
            if course_uncategorized_flag:
                flagged_course["should_be_category"] = course["should_be_category"]

            if credit_mismatch_flag:
                flagged_course["credits_earned"] = course.get("credits_earned", "")

            if course["is_passed"] == "Unknown": 
                flagged_course["grade"] = course.get("grade", "")
                flagged_course["is_passed"] = course["is_passed"]

            # Only append if at least one condition is met
            if len(flagged_course) > 1:
                flagged_courses.append(flagged_course)

        # Add to the final list only if there are flagged courses
        if flagged_courses:
            flagged_degree = {
                "file_name": data_dict.get("file_name", ""),
                "degree": degree.get("degree", ""),
                "major": degree.get("major"),
                "courses": flagged_courses
            }

            if credit_mismatch_flag:
                flagged_degree["overall_credits_earned"] = degree.get("overall_credits_earned", "")

            flagged_courses_list.append(flagged_degree)

    file_name = data_dict.get("file_name", "")

    # Call frontend for user decision if flagged courses exist
    if flagged_courses_list:
        print(flagged_courses_list)
        print(f"⚠️ User input required: Pausing processing for {file_name}. Waiting for user decisions...")

        # Store flagged courses and create lock for processing
        from main import flagged_courses_store, user_decisions_store, notify_status
        flagged_courses_store[file_name] = flagged_courses_list

        # Notify frontend via WebSocket
        asyncio.create_task(notify_status(file_name, "ready"))

        # wait until frontend submits decisions
        await processing_lock[file_name].wait() 

        # Apply user decisions
        user_decisions = user_decisions_store.get(file_name, [])
        if user_decisions:
            # Map decisions for quick lookup
            decision_map = {
                (d.file_name, d.degree, d.major, course.course_name): {
                    "should_be_category": course.should_be_category,
                    "credits_earned": course.credits_earned,
                    "is_passed": course.is_passed
                }
                for d in user_decisions for course in d.courses
            }
            print(decision_map)

            for degree in data_dict["degrees"]:
                for course in degree["courses"]:
                    decision_key = (file_name, degree["degree"], degree["major"], course["course_name"])
                    if decision_key in decision_map:
                        user_decision = decision_map[decision_key]
                        if user_decision["should_be_category"] is not None:
                            course["should_be_category"] = user_decision["should_be_category"]
                        if user_decision["credits_earned"] is not None:
                            course["credits_earned"] = user_decision["credits_earned"]
                        if user_decision["is_passed"] is not None:
                            course["is_passed"] = user_decision["is_passed"]
            
            print(f"User decisions applied successfully for {file_name}. Continue processing...")

    else: # If no flagged courses, notify frontend and close WebSocket
        print(f"⚠️ No flagged courses for {file_name}. Notifying frontend and closing WebSocket...")
        
        from main import notify_status
        asyncio.create_task(notify_status(file_name, "no_flagged_courses")) 

    # Iterate through each degree and process its courses with user decisions if available
    for degree in data_dict.get("degrees", []):
        # Process courses inside the degree
        for course in degree["courses"]:        
            # Calculate adjusted credits (if is_passed is True, keep credits; otherwise, set to 0)
            course["adjusted_credits_earned"] = course["credits_earned"] if course["is_passed"] else 0

            # Generate row hash for each course
            course["row_hash"] = generate_row_hash(
                get_valid_value(data_dict.get("student", {}).get("first_name")),
                get_valid_value(data_dict.get("student", {}).get("last_name")),
                get_valid_value(degree.get("institution_name")),
                get_valid_value(degree.get("degree")),
                get_valid_value(degree.get("major")),
                get_valid_value(degree.get("minor")),
                get_valid_value(degree.get("awarded_date")),
                get_valid_value(degree.get("overall_credits_earned"), None),
                get_valid_value(degree.get("overall_gpa"), None),
                course.get("course_name"),
                course.get("credits_earned"),
                course.get("grade")
            )

    print("Structured data:", json.dumps(data_dict, indent=4))

    # Save the JSON obejct to a file
    json_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(data_dict["file_name"])[0]}_structured_data_dict.json")
    with open(json_path, "w") as json_file:
        json.dump(data_dict, json_file, indent=4)
    print(f"JSON object saved to: {json_path}")

    print("Data structured successfully.")
    return {
        "status": "success",
        "message": "Data structured successfully.",
        "data": data_dict,
    }


# Step 4: Save structured data to SQLite
def save_to_database(data_dict: dict, database_file: str) -> dict:
    """
    Saves the pandas DataFrame into the database.
    Args:
        data_dict (dict): The dictionary containing the data to be saved.
        database_file (str): Path to the SQLite database file.
    Returns:
        dict: Summary with counts of inserted and duplicate rows.
    """
    try:
        conn = sqlite3.connect(database_file)
        
        # Insert records using optimized function
        transcript_map = {}  # Caches transcript_id to reduce redundant queries
        result = insert_records_from_dict(conn, data_dict, transcript_map)

        # Commit changes if successful
        conn.commit()
        conn.close()

        print(f"Data successfully saved to database: {result['inserted_count']} rows inserted, {len(result['duplicate_rows'])} duplicates skipped.")
        return {
            "status": "success",
            "message": f"Data saved successfully: {result['inserted_count']} rows inserted, {len(result['duplicate_rows'])} duplicates skipped.",
        }

    except Exception as e:
        conn.rollback()  # Rollback any changes in case of an error
        print(f"Error saving data: {str(e)}")
        return {
            "status": "error",
            "message": "Error saving data to database.",
            "details": traceback.format_exc()
        }


# Full data pipeline
async def process_file(file_path: str, database_file: str) -> dict:
    """
    Handles the full processing of a file:
    - Extracts data
    - Validates data
    - Structures data
    - Saves structured data to a database
    Args:
        file_path (str): The path to the file to be processed.
        database_file (str): The path to the database file.
    Returns:
        dict: A response containing the status, message, and any error details.
    """
    async with global_lock:
        # Create processing_lock for the file
        from main import flagged_courses_store, user_decisions_store, processing_lock
        file_name = os.path.basename(file_path)
        processing_lock[file_name] = asyncio.Event()
        
        # Determine the file type
        file_extension = os.path.splitext(file_path)[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            return {
                "status": "error",
                "message": f"Unsupported file format: {file_extension}",
                "details": "Only PDF, JPG, JPEG, PNG, and CSV files are supported.",
                "file": file_path
            }

        extracted_dict = None # Initialize extracted data dictionary

        try:
            # Extract data 
            print(f"📄 Extracting data from: {file_path}...")
            extraction_function = load_data if file_extension == ".csv" else extract_data

            extraction_result = await asyncio.to_thread(extraction_function, file_path)
            if extraction_result["status"] == "error":
                return extraction_result  # Pass error response directly

            extracted_dict = extraction_result.get("data", {})
            if not extracted_dict:
                return {
                    "status": "error",
                    "message": "Extracted data is empty. Please check the input file.",
                    "details": "Possible reasons: File contains no readable text or OCR failed.",
                    "file": file_path
                }
            
            # Validate the data
            print("🔍 Validating extracted data...")
            validation_result = await asyncio.to_thread(validate_data, extracted_dict)
            if validation_result["status"] == "error":
                return validation_result  # Return validation error directly

            validated_dict = validation_result.get("data", {})
            if not validated_dict:
                return {
                    "status": "error",
                    "message": "Validation returned empty data.",
                    "details": "There might be issues with OCR text extraction or AI-based validation.",
                    "file": file_path
                }

            # Structure the data
            print("🔧 Structuring validated data...")
            structured_result = await structure_data(validated_dict, processing_lock)
            if structured_result["status"] == "error":
                return structured_result

            structured_dict = structured_result.get("data", {})
            if not structured_dict:
                return {
                    "status": "error",
                    "message": "Structured data is empty after processing.",
                    "details": "Possible reasons: Data extraction issues or AI processing failure.",
                    "file": file_path
                }

            # Save the data to the database
            print("💾 Saving structured data to the database...")
            saved_result = await asyncio.to_thread(save_to_database, structured_dict, database_file)
            if saved_result["status"] == "error":
                return saved_result

            print("✅ File processed successfully! Deleting files...")

            # Delete files after processing
            file_prefix = Path(file_path).stem
            output_folder = Path(OUTPUT_FOLDER)
            for file in output_folder.iterdir():
                if file.is_file() and file.name.startswith(file_prefix):
                    await asyncio.to_thread(file.unlink)  # Deletes the file

            return {
                "status": "success", 
                "message": "File processed and saved to the database successfully.", 
                "file": file_path
            }

        except Exception as e:
            error_message = f"Unexpected error processing file: {file_path}: {str(e)}"
            print(error_message)
            print(traceback.format_exc())  # Print full error traceback for debugging
            return {
                "status": "error",
                "message": error_message,
                "details": traceback.format_exc(),
                "file": file_path
            }

        finally:
            # Clean up state after processing is complete
            if file_name in processing_lock:
                del processing_lock[file_name]
            if file_name in flagged_courses_store:
                del flagged_courses_store[file_name]
            if file_name in user_decisions_store: 
                del user_decisions_store[file_name]