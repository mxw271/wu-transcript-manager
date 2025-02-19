import os
import json
import sqlite3
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import time
import traceback
from collections import defaultdict

from clients_service import get_openai_client
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
        "overall_credits_earned": "",
        "overall_gpa": "",
        "courses": []
    })

    for _, row in df.iterrows():
        degree_key = (row["institution_name"], row["degree"], row["major"], row["minor"], row["awarded_date"])

        if not degrees[degree_key]["degree"]:  # Only set these once per degree
            degrees[degree_key].update({
                "degree": row["degree"] if pd.notna(row["degree"]) else "",
                "major": row["major"] if pd.notna(row["major"]) else "",
                "minor": row["minor"] if pd.notna(row["minor"]) else "",
                "institution_name": row["institution_name"],
                "awarded_date": row["awarded_date"] if pd.notna(row["awarded_date"]) else "",
                "overall_credits_earned": row["overall_credits_earned"] if pd.notna(row["overall_credits_earned"]) else None,
                "overall_gpa": row["overall_gpa"] if pd.notna(row["overall_gpa"]) else None,
            })

        # Add course information under the respective degree
        degrees[degree_key]["courses"].append({
            "course_name": row["course_name"],
            "credits_earned": row["credits_earned"],
            "grade": row["grade"],
            "is_passed": None  # Placeholder, can be computed based on grading rules
        })

     # Convert defaultdict to list of degrees
    data_dict["degrees"] = list(degrees.values())

    return data_dict


# Function to generate is_pased based on the degree and grade
def generate_is_passed_using_openai(data_dict, temperature: float = 0):
    """
    Uses OpenAI to determine if a course is passed based on the degree and grade.
    Args:
        data_dict (dict): The structured transcript data containing degrees and courses.
        temperature (float): The randomness level in GPT response.
    Returns:
        dict: Updated data_dict with "is_passed" field added to each course.
    """
    openai_client = get_openai_client()  
    retry_attempts = 3

    for degree in data_dict["degrees"]:
        degree_name = degree.get("degree", "")
        courses = degree.get("courses", [])
        print(degree_name)

        # Prepare input for OpenAI
        course_names = [course["course_name"] for course in courses]
        grades = [course["grade"] for course in courses]

        # Generate OpenAI prompt
        prompt = f"""
        You are an expert in academic evaluation. Your task is to determine whether a student has passed or failed each course based on the grade and degree type.

        **Rules:**
        - If the grade meets the passing criteria, return **True**; otherwise, return **False**.
        - If a grade is empty or unrecognized, return **null**.
        - The **output list MUST contain the EXACT same number of elements as the input course list**.
        - Do **NOT** add extra items or remove any courses. The index order must be preserved.

        **Degree:** {degree_name}
        **Courses & Grades:**
        {json.dumps(list(zip(course_names, grades)), indent=2)}

        **Output Format:** Return **ONLY** a JSON list of Boolean values (`true` or `false`), in the same order as the course list.
        """
        print(len(course_names), len(grades))

        for attempt in range(retry_attempts):
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert in evaluating academic course grades."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature
                )

                result_text = response.choices[0].message.content.strip()
                if not result_text:
                    print("OpenAI returned an empty response.")
                    continue

                # Remove potential JSON code block formatting
                result_text = result_text.replace("```json", "").replace("```", "").strip()

                # Parse the response into a Python list
                is_passed_list = json.loads(result_text)
                print(len(is_passed_list))
                print(is_passed_list)

                # Validate output format
                if isinstance(is_passed_list, list) and len(is_passed_list) == len(courses):
                    # Assign is_passed values to each course
                    for i, course in enumerate(courses):
                        course["is_passed"] = is_passed_list[i] if is_passed_list[i] is not None else False
                    break  # Exit retry loop if successful

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON (Attempt {attempt+1}/{retry_attempts}): {e}")
                print("OpenAI Response:", structured_text)
            except Exception as e:
                print(f"API error (Attempt {attempt+1}/{retry_attempts}): {e}")
                time.sleep(2)

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

        structured_dict = structured_result["data"]
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

