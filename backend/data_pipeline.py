import pandas as pd
import numpy as np
import sqlite3
import os
import csv
import json
from typing import Dict, Any, List
import time
import traceback

from text_processing.extraction import extract_text_from_file_using_opencv, extract_text_from_file_using_azure
from text_processing.formatting import generate_json_data_using_openai, json_data_to_dataframe
from text_processing.matching import match_courses_using_openai, match_courses_using_sbert
from db_service import insert_records_from_df
from utils import PASSING_GRADES, GRADE_RANKING, load_course_categories, categorize_degree, calculate_adjusted_credits, generate_row_hash


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
        dict: Result containing status, message, and extracted DataFrame.
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
        extracted_text_path = os.path.join(OUTPUT_FOLDER, "extracted_text_opencv.csv")
        with open(extracted_text_path, "w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Line"])  # Add a header
            csv_writer.writerows([[line] for line in extracted_text.splitlines()])
        print(f"✅ Extracted text saved to: {extracted_text_path}")

        # Process the text using OpenAI API
        print("Sending extracted text to OpenAI API for processing...")
        json_data = generate_json_data_using_openai(extracted_text)
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
       
        return {
            "status": "success", 
            "message": "Data extracted successfully.", 
            "file": file_path, 
            "data": formatted_df
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
def validate_data(data: Dict[str, Any]) -> bool:
    # Simulate validation logic
    return "content" in data


# Step 3: Structure validated data
def structure_data(df: pd.DataFrame) -> dict:
    """
    Reads the extracted transcript data, 
        matches course names to predefined categories using OpenAI, 
        processes degree levels and adjusted credits,
        and generate row hash.
    Args:
        df (pd.DataFrame): The raw extracted transcript data.
    Returns:
        dict: A dictionary with `status`, `message`, and `data` (processed DataFrame).
    """
    # Load course categories
    categories_list = load_course_categories()

    # Perform text matching
    print("🔍 Matching courses using OpenAI...")
    categorized_courses = match_courses_using_openai(df["course_name"].tolist(), categories_list)

    if not categorized_courses or all(category == "Uncategorized" for category in categorized_courses):
        print("OpenAI classification failed or returned all 'Uncategorized'. Falling back to SBERT...")
        categorized_courses = match_courses_using_sbert(df["course_name"].tolist(), categories_list)

    df["should_be_category"] = ["Uncategorized"] * len(df["course_names"]) if not categorized_courses else categorized_courses

    # Determine the degree level
    df["degree_level"] = df["degree"].apply(categorize_degree)

    # Calculate adjusted credits
    df["adjusted_credits_earned"] = df.apply(
        lambda row: calculate_adjusted_credits(
            row["grade"], row["credits_earned"], row["degree_level"]
        ),
        axis=1
    )

    # Generate row hash
    df['row_hash'] = df.apply(
        lambda row: generate_row_hash(
            row["first_name"], row["last_name"], row["institution_name"], row["degree"], row["major"], 
            row["minor"], row["awarded_date"], row["overall_credits_earned"], row["overall_gpa"],
            row["course_name"], row["credits_earned"], row["grade"]
        ),
        axis=1
    )

    # Save the structured data to a new CSV file    
    structured_data_path = os.path.join(OUTPUT_FOLDER, "structured_data.csv")
    df.to_csv(structured_data_path, index=False, encoding="utf-8")

    print(df.iloc[:,-4:])
    print("Data structured successfully.")
    return {
        "status": "success",
        "message": "Data structured successfully.",
        "data": df
    }


# Step 4: Save structured data to SQLite
def save_to_database(df: pd.DataFrame, database_file: str) -> dict:
    """
    Saves the pandas DataFrame into the database.
    Args:
        df (pd.DataFrame): The pandas DataFrame containing the data to be saved.
        database_file (str): Path to the SQLite database file.
    Returns:
        dict: Summary with counts of inserted and duplicate rows.
    """
    try:
        conn = sqlite3.connect(database_file)
        
        # Insert records using optimized function
        transcript_map = {}  # Caches transcript_id to reduce redundant queries
        result = insert_records_from_df(conn, df, transcript_map)

        # Commit changes if successful
        conn.commit()
        conn.close()

        print(f"✅ Data successfully saved to database: {result['inserted_count']} rows inserted, {len(result['duplicate_rows'])} duplicates skipped.")
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
        save_to_database(structured_data)

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
        structured_result = structure_data(extracted_df)
        if structured_result["status"] == "error":
            return structured_result

        structured_df = structured_result["data"]
        if structured_df is None or structured_df.empty:
            return {
                "status": "error",
                "message": "Structured data is empty after processing.",
                "details": "Possible reasons: Data extraction issues or AI processing failure.",
                "file": file_path
            }

        # Save the data to the database
        print("💾 Saving structured data to the database...")
        saved_result = save_to_database(structured_df, database_file)
        if saved_result["status"] == "error":
            return saved_result

        print("✅ File processed successfully!")
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
