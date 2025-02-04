import pandas as pd
import numpy as np
import sqlite3
import os
import csv
import json
from typing import Dict, Any, List
import time

from models_service import get_openai_client
from process_categories import load_course_categories
from extraction_opencv import extract_text_from_pdf_using_opencv
from extraction_azure import extract_text_from_file_using_azure
from formatting_openai import generate_json_data_using_openai, json_data_to_dataframe
from text_matching import match_courses_using_sbert
from db_create_tables import create_tables 
from db_service import insert_educator, insert_transcript, insert_course, insert_cateogrized_course, insert_categorized_transcript


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


# Function to drop tables
def drop_tables(database_file):
    connection = sqlite3.connect(database_file)
    cursor = connection.cursor()

    # Drop tables if they exist
    tables = ["wu_educators", "transcripts", "courses", "wu_categorized_courses", "wu_categorized_transcripts"]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        #print(f"Table {table} dropped successfully.")

    connection.commit()
    connection.close()


# Function to format names from "lastname, firstname" to "firstname lastname"
def format_name(name):
    if "," in name:
        parts = name.split(",", 1)  
        return parts[1].strip() + " " + parts[0].strip()  
    return name.strip()


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
        return "unknown"

    degree = degree.lower()
    if any(word in degree for word in ["phd", "doctor", "md", "dnp", "dr"]):
        return "Doctorate"
    elif any(word in degree for word in ["master", "ms", "ma", "mba", "m.ed", "mph"]):
        return "Master"
    elif any(word in degree for word in ["bachelor", "bs", "ba", "b.ed", "bba", "bsc"]):
        return "Bachelor"
    else:
        return "unknown"


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
    extracted_text = extract_text_from_pdf_using_opencv(file_path, OUTPUT_FOLDER)
    
    # Save the text to a .csv file
    extracted_text_path = os.path.join(OUTPUT_FOLDER, "extracted_text_opencv.csv")
    with open(extracted_text_path, "w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Line"])  # Add a header
        for line in extracted_text.splitlines():
            csv_writer.writerow([line])

    # Process the text using OpenAI API
    json_data = generate_json_data_using_openai(extracted_text, get_openai_client())

    # Format the data to a DataFrame
    formatted_df = json_data_to_dataframe(json_data)

    # Add the file name to the DataFrame
    formatted_df["file_name"] = os.path.basename(file_path)

    # Save the formatted data to a new CSV file
    formatted_table_path = os.path.join(OUTPUT_FOLDER, "formatted_table_openai.csv")
    if not formatted_df.empty:
        formatted_df.to_csv(formatted_table_path, index=False, encoding="utf-8")
        print(f"Formatted transcript saved to: {formatted_table_path}")
    else:
        print("No valid data to save. Check OpenAI response.")

    return formatted_df


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

    print(df["name"].unique())
    # Format names
    df["name"] = df["name"].apply(format_name)
    print(df["name"].unique())

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
        cursor.execute("SELECT educator_id FROM wu_educators WHERE name = ?", (row.get("name"),))
        educator = cursor.fetchone()

        if educator:
            educator_id = educator[0]
        else:
            # Insert educator and get educator_id
            educator_id = insert_educator(conn, row.get("name"))

        # Check for existing transcript
        file_name = row.get("file_name")
        if file_name in transcript_map:
            transcript_id = transcript_map[file_name]  # Use cached transcript_id
        else:
            cursor.execute(
                """
                SELECT transcript_id FROM transcripts WHERE 
                wu_educator_id = ? AND institution_name = ? AND file_name = ?
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
                    row.get("degree"),
                    row.get("major"),
                    row.get("minor"),
                    row.get("awarded_date"),
                    row.get("overall_credits_earned"),
                    row.get("overall_gpa"),
                    row.get("degree_level"),
                    file_name
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

        # Check and insert rows only if category is valid
        '''
        if row.get("should_be_category") and row.get("should_be_category") != "Uncategorized":
            insert_cateogrized_course(
                conn,
                course_id,
                transcript_id,
                row.get("should_be_category")
            )
        '''
    
    # Commit changes and close connection
    conn.commit()
    conn.close()

    print("Data successfully saved to the database.")
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
    #drop_tables(database_file)
    create_tables(database_file)

    # Extract data 
    extracted_df = extract_data(file_path)

    # Structure the data
    structured_df = structure_data(extracted_df)

    # Save the data to the database
    save_to_db(structured_df, database_file)

