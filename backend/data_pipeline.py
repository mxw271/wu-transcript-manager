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

from text_processing.extraction import extract_text_from_file_using_opencv, extract_text_from_file_using_azure
from text_processing.formatting import generate_data_dict_using_openai, preprocess_data_dict, json_data_to_dataframe
from text_processing.validation import rule_based_validation, validate_coursework_openai, openai_based_validation
from text_processing.matching import match_courses_using_openai, match_courses_using_sbert
from db_service import insert_records_from_dict
from utils import PASSING_GRADES, GRADE_RANKING, load_course_categories, get_valid_value, categorize_degree, calculate_adjusted_credits, generate_row_hash


# Specify the output directory
OUTPUT_FOLDER = "./middle_products"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Step 1: Extract data from the file 
def extract_data(file_path: str) -> dict:
    """
    Extracts text from a PDF, processes it using OpenAI, and formats it into a DataFrame.
    Args:
        file_path (str): Path to the PDF file.
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

        #print("Extracted data:", json.dumps(data_dict, indent=4))

        # Save the JSON obejct to a file
        json_path = os.path.join(OUTPUT_FOLDER, f"{Path(file_path).stem}_extracted_data_dict.json")
        with open(json_path, "w") as json_file:
            json.dump(data_dict, json_file, indent=4)
        print(f"JSON object saved to: {json_path}")

        '''
        # Format the data to a DataFrame
        print("Formatting data into a DataFrame...")
        formatted_df = json_data_to_dataframe(json_data)
        if formatted_df is None or formatted_df.empty:
            return {
                "status": "error",
                "message": "Formatted DataFrame is empty. OpenAI response might be incorrect.",
                "details": "Check if the extracted text is properly structured before sending to OpenAI.",
                "file": file_path
            }

        # Add the file name to the DataFrame
        formatted_df["file_name"] = os.path.basename(file_path)

        # Save the formatted data to a new CSV file
        formatted_table_path = os.path.join(OUTPUT_FOLDER, "formatted_table_openai.csv")
        formatted_df.to_csv(formatted_table_path, index=False, encoding="utf-8")
        print(f"Formatted transcript saved to: {formatted_table_path}")
        '''

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

       # print("Validated data:", json.dumps(corrected_dict, indent=4))

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
def structure_data(data_dict: dict) -> dict:
    """
    Reads the extracted transcript data, 
        matches course names to predefined categories using OpenAI, 
        processes degree levels and adjusted credits,
        and generate row hash.
    Args:
        data_dict (dict): The raw extracted transcript data.
    Returns:
        dict: A dictionary with status, message, and structured data.
    """
    warnings = []

    # Load course categories
    categories_dict = load_course_categories()

    # Iterate through each degree and process its courses
    for degree in data_dict.get("degrees", []):
        course_names = [course["course_name"] for course in degree["courses"]]

        # Perform text matching using OpenAI
        print("Matching courses using OpenAI...")
        categorized_courses = match_courses_using_openai(course_names, categories_dict)

        # If OpenAI fails, fallback to SBERT
        if not categorized_courses or all(category == "Uncategorized" for category in categorized_courses):
            warnings.append(f"OpenAI classification failed for degree: {degree.get('degree', '')}.")
            print("OpenAI classification failed or returned all 'Uncategorized'. Falling back to SBERT...")
            categories_list = list(categories_dict.keys())
            categorized_courses = match_courses_using_sbert(course_names, categories_list)

        # If SBERT also fails, default to Uncategorized
        if not categorized_courses or all(category == "Uncategorized" for category in categorized_courses):
            warnings.append(f"SBERT classification also failed for degree: {degree.get('degree', '')}. Defaulting to 'Uncategorized'.")
            print("SBERT classification also failed, defaulting all categories to 'Uncategorized'.")

        # Assign categories to courses
        for i, course in enumerate(degree["courses"]):
            course["should_be_category"] = categorized_courses[i] if categorized_courses else "Uncategorized"

        # Assign degree level
        degree["degree_level"] = categorize_degree(degree.get("degree", ""))

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

    # Preserve warnings in the final data_dict if needed
    data_dict["categorization_warnings"] = warnings if warnings else None

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
        "warnings": warnings if warnings else None
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
def process_file(file_path: str, database_file: str) -> dict:
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
    try:
        # Extract data 
        print(f"📄 Extracting data from: {file_path}...")
        extraction_result = extract_data(file_path)
        if extraction_result["status"] == "error":
            return extraction_result  # Pass error response directly to `upload_files()`
        
        extracted_dict = extraction_result["data"]
        if not extracted_dict:
            return {
                "status": "error",
                "message": "Extracted data is empty. Please check the input file.",
                "details": "Possible reasons: File contains no readable text or OCR failed.",
                "file": file_path
            }
        
        # Validate the data
        print("🔍 Validating extracted data...")
        validation_result = validate_data(extracted_dict)
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
        structured_result = structure_data(validated_dict)
        if structured_result["status"] == "error":
            return structured_result

        structured_dict = structured_result["data"]
        if not structured_dict:
            return {
                "status": "error",
                "message": "Structured data is empty after processing.",
                "details": "Possible reasons: Data extraction issues or AI processing failure.",
                "file": file_path
            }

        # Save the data to the database
        print("💾 Saving structured data to the database...")
        saved_result = save_to_database(structured_dict, database_file)
        if saved_result["status"] == "error":
            return saved_result

        print("✅ File processed successfully! Deleting files...")

        # Delete files after processing
        file_prefix = Path(file_path).stem
        output_folder = Path(OUTPUT_FOLDER)
        for file in output_folder.iterdir():
            if file.is_file() and file.name.startswith(file_prefix):
                file.unlink()  # Deletes the file

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
