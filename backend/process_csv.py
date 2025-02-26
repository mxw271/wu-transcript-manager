import os
import json
import sqlite3
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import time
import traceback
from collections import defaultdict

from data_pipeline import validate_data, structure_data, save_to_database
from db_service import check_database_status
from utils import PASSING_GRADES, GRADE_RANKING, load_json_log, save_json_log, handle_csv_error


# Load environment variables from .env file
DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")  # Ensure correct path
load_dotenv(DOTENV_PATH)
DATABASE_FILE = os.getenv("DATABASE_FILE", "../database/database.db") # Load Database file from .env

CSV_FOLDER = '/Users/maxiw/Downloads/transcripts_in_csv'
LOG_FILE = os.path.join(CSV_FOLDER, "csv_processing_log.json")


# Function to convert a pandas DataFrame to a nested dictionary
def df_to_nested_dict(df: pd.DataFrame) -> dict:
    """
    Converts a pandas DataFrame into a nested dictionary.
    Args:
        df (pd.DataFrame): DataFrame containing student transcript data.
    Returns:
        dict: Nested dictionary with student details, degrees, and courses.
    """
    data_dict = {"student": {}, "degrees": [], "file_name": df["file_name"].iloc[0]}

    # Extract student details
    data_dict["student"] = {
        "first_name": df["first_name"].iloc[0],
        "middle_name": df["middle_name"].iloc[0] if pd.notna(df["middle_name"].iloc[0]) else "",
        "last_name": df["last_name"].iloc[0],
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

    for _, row in df.iterrows():
        # Normalize key values to prevent minor differences causing duplicate degrees
        institution = row["institution_name"].strip() if pd.notna(row["institution_name"]) else ""
        degree = row["degree"].strip() if pd.notna(row["degree"]) else ""
        major = row["major"].strip() if pd.notna(row["major"]) else ""
        minor = row["minor"].strip() if pd.notna(row["minor"]) else ""
        awarded_date = row["awarded_date"].strip() if pd.notna(row["awarded_date"]) else ""

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
                "overall_credits_earned": row["overall_credits_earned"] if pd.notna(row["overall_credits_earned"]) else None,
                "overall_gpa": row["overall_gpa"] if pd.notna(row["overall_gpa"]) else None,
            })

        # Add course information under the respective degree
        degrees[degree_key]["courses"].append({
            "course_name": row["course_name"].strip(),
            "credits_earned": row["credits_earned"],
            "grade": row["grade"].strip(),
            "is_passed": None  # Placeholder, can be computed based on grading rules
        })

     # Convert defaultdict to list of degrees
    data_dict["degrees"] = list(degrees.values())

    return data_dict


# Function to process a CSV file
def process_csv_file(csv_file, log_file, log_data):
    """Processes a single CSV file and inserts its data into the database."""
    print(f"📄 Processing file: {csv_file}...")

    # Load CSV into Pandas DataFrame
    try:
        df = pd.read_csv(os.path.join(CSV_FOLDER, csv_file))
    except Exception as e:
        handle_csv_error(csv_file, log_file, log_data, "Failed to read CSV", e)
        return

    extracted_dict = df_to_nested_dict(df)
    print("Extracted data:", json.dumps(extracted_dict, indent=4))

    # Renew file_name
    csv_base_name = os.path.splitext(os.path.basename(csv_file))[0]
    file_name_parts = extracted_dict["file_name"].split("_page")[0]

    if csv_base_name != file_name_parts:
        extracted_dict["file_name"] = f"{file_name_parts}.pdf"
    
    # Validate the data
    print("🔍 Validating extracted data...")
    try:
        validation_result = validate_data(extracted_dict)
        if validation_result["status"] == "error":
            handle_csv_error(csv_file, log_file, log_data, "Error during validation", validation_result.get("message", "Unknown error"))
            return

        validated_dict = validation_result.get("data", {})
        if not validated_dict:
            handle_csv_error(csv_file, log_file, log_data, "Validation returned empty data", "There might be issues with OCR text extraction or AI-based validation.")
            return
    except Exception as e:
        handle_csv_error(csv_file, log_file, log_data, "Unexpected error while validating data", e)
        return


    # Structure the data
    print("🔧 Structuring validated data...")
    try:
        structured_result = structure_data(validated_dict)
        if structured_result["status"] == "error":
            handle_csv_error(csv_file, log_file, log_data, "Error during structuring", structured_result.get("message", "Unknown error"))
            return

        structured_dict = structured_result.get("data", {})
        if not structured_dict:
            handle_csv_error(csv_file, log_file, log_data, "Structuring returned empty data", "Possible reasons: Data extraction issues or AI processing failure.")
            return
        
        warnings = structured_result.get("warnings", None)
    except Exception as e:
        handle_csv_error(csv_file, log_file, log_data, "Unexpected error while structuring data", e)
        return

    # Determine is_passed and adjusted_credits_earned
    for degree in structured_dict["degrees"]:
        degree_level = degree["degree_level"]  
        passing_grade = PASSING_GRADES.get(degree_level, PASSING_GRADES["Bachelor"])  # Default to Bachelor
        
        for course in degree["courses"]:
            grade = course.get("grade", "").strip()
            
            if not grade:  # Handle missing grades
                course["is_passed"] = False
                continue

            # Determine if grade is numeric
            try:
                numeric_grade = float(grade)
                course["is_passed"] = numeric_grade >= passing_grade["numeric"]
            except ValueError:
                # Grade is not a number, check letter grade
                letter_grade = grade.upper()
                course["is_passed"] = GRADE_RANKING.get(letter_grade, 0) >= GRADE_RANKING.get(passing_grade["letter"], 0)
            
            # Recalculate adjusted credits
            course["adjusted_credits_earned"] = course["credits_earned"] if course["is_passed"] else 0

    # Save the data to the database
    print("💾 Saving structured data to the database...")
    try:
        saved_result = save_to_database(structured_dict, DATABASE_FILE)
        if saved_result["status"] == "error":
            handle_csv_error(csv_file, log_file, log_data, "Error during saving data to the database", saved_result.get("message", "Unknown error"))
            return

        # Include warnings if present
        if warnings:
            saved_result["warnings"] = warnings
            print("⚠️ Warnings:", warnings)

        log_data[csv_file] = saved_result
        save_json_log(LOG_FILE, log_data)
        print(f"✅ Finished processing {csv_file}.")
    except Exception as e:
        handle_csv_error(csv_file, log_file, log_data, "Unexpected error while saving data to database", e)
        return

    print("✅ File processed successfully!")


# Main function to process all CSV files
def process_all_csv_files():
    """Processes all CSV files in the ./processed_csv directory."""
    check_database_status(DATABASE_FILE)

    log_data = load_json_log(LOG_FILE)
    files = [f for f in os.listdir(CSV_FOLDER) if f.endswith(".csv")]

    if not files:
        print("⚠️ No CSV files found in the directory.")
        return

    for file in files:
        if file in log_data:
            print(f"⏭️ Skipping {file}, already processed.")
        else:
            process_csv_file(file, LOG_FILE, log_data)


if __name__ == "__main__":
    process_all_csv_files()

