import pandas as pd
import numpy as np
import sqlite3
import os
import csv
import json
from typing import Dict, Any, List
import time
import traceback

from clients_service import get_openai_client
from process_categories import load_course_categories
from extraction_opencv import extract_text_from_pdf_using_opencv
from extraction_azure import extract_text_from_file_using_azure
from formatting_openai import generate_json_data_using_openai, json_data_to_dataframe
from text_matching import match_courses_using_sbert
from db_service import insert_educator, insert_transcript, insert_course


# Specify the output directory
OUTPUT_FOLDER = "./middle_products"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Constants for passing grades based on degree level
PASSING_GRADES = {
    "Doctorate": "C",
    "Master": "C",
    "Bachelor": "D"
}


# Define a ranking system for letter grades, including modifiers
GRADE_RANKING = {
    "A+": 13, "A": 12, "A-": 11,
    "B+": 10, "B": 9, "B-": 8,
    "C+": 7, "C": 6, "C-": 5,
    "D+": 4, "D": 3, "D-": 2,
    "F": 1
}

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


# Step 1: Extract data from the file 
def extract_data(file_path: str) -> pd.DataFrame:
    try:
        # Extract text from PDF
        print("Extracting text from PDF...")
        extracted_text = extract_text_from_pdf_using_opencv(file_path, OUTPUT_FOLDER)
        if not extracted_text:
            return {
                "status": "error",
                "message": "Extracted text is empty. PDF may not contain valid text.",
                "details": "Ensure the PDF contains readable text, not just images.",
                "file": file_path
            }

        # Save the text to a .csv file
        extracted_text_path = os.path.join(OUTPUT_FOLDER, "extracted_text_opencv.csv")
        with open(extracted_text_path, "w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Line"])  # Add a header
            for line in extracted_text.splitlines():
                csv_writer.writerow([line])
        print(f"✅ Extracted text saved to: {extracted_text_path}")

        # Process the text using OpenAI API
        print("Sending extracted text to OpenAI API for processing...")
        openai_client = get_openai_client()
        json_data = generate_json_data_using_openai(extracted_text, openai_client)
        if not json_data:
            return {
                "status": "error",
                "message": "OpenAI response is empty. Check API request and input text.",
                "details": "Possible issues: API timeout, invalid input text, or authentication failure.",
                "file": file_path
            }
        print("OpenAI API response received:", json.dumps(json_data, indent=4))

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
        print(f"✅ Formatted transcript saved to: {formatted_table_path}")
       
        return {"status": "success", "message": "Data extracted successfully.", "data": formatted_df}
    
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
def validate_data(data: Dict[str, Any]) -> bool:
    # Simulate validation logic
    return "content" in data


# Step 3: Structure validated data
def structure_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reads the extracted transcript data, expands abbreviations using OpenAI,
        matches course names to predefined categories using SBERT, 
        and processes degree levels, passing grades, and adjusted credits.
    Args:
        file_path (str): Path to the transcript data CSV file.
    Returns:
        pd.DataFrame: Processed DataFrame with additional calculated fields.    
    """
    # Load course categories
    categories_list = load_course_categories(openai_client = get_openai_client())

    # Perform SBERT-based matching after abbreviation expansion
    print("Expanding abbreviations and matching courses...")
    df["course_name_lowercase"] = df["course_name"].astype(str).str.lower()
    df["should_be_category"] = match_courses_using_sbert(df["course_name_lowercase"].tolist(), categories_list)  

    # Determine the degree level
    df["degree_level"] = df["degree"].apply(categorize_degree)

    # Calculate adjusted credits
    df["adjusted_credits_earned"] = df.apply(
        lambda row: calculate_adjusted_credits(
            row["grade"], row["credits_earned"], row["degree_level"]
        ),
        axis=1
    )

    print(df.iloc[:, 9:])
    # Drop temporary columns
    df.drop(columns=["course_name_lowercase"], inplace=True)

    # Save the structured data to a new CSV file    
    structured_data_path = os.path.join(OUTPUT_FOLDER, "structured_data.csv")
    df.to_csv(structured_data_path, index=False, encoding="utf-8")

    return df


# Step 4: Save structured data to SQLite
def save_to_db(df: pd.DataFrame, database_file: str) -> pd.DataFrame:
    """
    Saves the pandas DataFrame into the database.
    Args:
        df (pd.DataFrame): The pandas DataFrame containing the data to be saved.
    Returns:
        pd.DataFrame: The DataFrame.
    """
    conn = sqlite3.connect(database_file)
    cursor = conn.cursor()

    transcript_map = {}  # Stores mapping of file_name -> transcript_id

    # Iterate over each row in the DataFrame
    for _, row in df.iterrows():
        # Check for existing educator
        cursor.execute(
            """SELECT educator_id FROM educators 
            WHERE firstName = ? AND lastName = ? AND COALESCE(middleName, '') = COALESCE(?, '')
            """, 
            (
                row.get("firstName"),
                row.get("lastName"),
                row.get("middleName") if row.get("middleName") else None
            )
        )
        educator = cursor.fetchone()

        if educator:
            educator_id = educator[0]
        else:
            # Insert educator and get educator_id
            educator_id = insert_educator(conn, row.get("firstName"), row.get("lastName"), row.get("middleName"))

        # Check for existing transcript
        file_name = row.get("file_name")
        if file_name in transcript_map:
            transcript_id = transcript_map[file_name]  # Use cached transcript_id
        else:
            cursor.execute(
                """
                SELECT transcript_id FROM transcripts WHERE 
                educator_id = ? AND institution_name = ? AND file_name = ?
                """,
                (educator_id, row.get("institution_name"), row.get("file_name"))
            )
            transcript = cursor.fetchone()

            if transcript:
                transcript_id = transcript[0]
            else:
                # Insert transcript and get transcript_id
                transcript_id = insert_transcript(
                    conn,
                    educator_id,
                    row.get("institution_name"),
                    row.get("degree_level"),
                    file_name,
                    row.get("degree"),
                    row.get("major"),
                    row.get("minor"),
                    row.get("awarded_date"),
                    row.get("overall_credits_earned"),
                    row.get("overall_gpa")
                )

            # Store transcript_id in map
            transcript_map[file_name] = transcript_id  

        # Insert course
        course_id = insert_course(
            conn,
            transcript_id,
            row.get("course_name"),
            row.get("should_be_category"),
            row.get("adjusted_credits_earned"),
            row.get("credits_earned"),
            row.get("grade"),
        )
    
    # Commit changes and close connection
    conn.commit()
    conn.close()

    print("✅ Data successfully saved to the database.")
    return df  # Return the DataFrame for further use


# Full data pipeline
def process_file(file_path: str, database_file: str):
    '''
    # Step 1: Extract data
    extracted_data = extract_data(file_path)

    # Step 2: Validate data
    is_valid = validate_data(extracted_data)

    if is_valid:
        # Step 3: Structure data
        structured_data = structure_data(extracted_data)

        # Step 4: Save structured data to SQLite
        save_to_db(structured_data)

        # Return processed data
        return {"filename": os.path.basename(file_path), "status": "Valid", "content": extracted_data.get("content", "")}
    else:
        # Return invalid data
        return {"filename": os.path.basename(file_path), "status": "Invalid", "content": ""}
    '''
    try:
        # Extract data 
        print(f"📄 Extracting data from: {file_path}...")
        extract_result = extract_data(file_path)
        # If extraction fails, return the error message
        if extract_result["status"] == "error":
            return extract_result  # Pass error response directly to `upload_files()`
        
        extracted_df = extract_result["data"]
        if extracted_df is None or extracted_df.empty:
            return {
                "status": "error",
                "message": "Extracted data is empty. Please check the input file.",
                "details": "Possible reasons: File contains no readable text or OCR failed.",
                "file": file_path
            }
        
        # Structure the data
        print("🔍 Structuring extracted data...")
        structured_df = structure_data(extracted_df)
        if structured_df is None or structured_df.empty:
            return {
                "status": "error",
                "message": "Structured data is empty after processing.",
                "details": "Possible reasons: Data extraction issues or AI processing failure.",
                "file": file_path
            }
        
        # Save the data to the database
        print("💾 Saving structured data to the database...")
        save_to_db(structured_df, database_file)

        print("✅ File processed successfully!")
        return {
            "status": "success", 
            "message": "File processed and saved to the database successfully.", 
            "file": file_path
        }

    except Exception as e:
        error_message = f"Error processing file: {str(e)}"
        print(error_message)
        print(traceback.format_exc())  # Print full error traceback for debugging
        return {
            "status": "error",
            "message": error_message,
            "details": traceback.format_exc(),
            "file": file_path
        }
