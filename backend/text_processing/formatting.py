import os
import csv
import json
import re
import regex
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import parser
from clients_service import get_openai_client


# Set a randomness level for OpenAI
TEMPERATURE = 0.3 # Lower value for more deterministic, precise, and consistent


# List of minor words that should remain lowercase (unless first word)
MINOR_WORDS = {"of", "the", "in", "and", "for", "at", "to", "with", "on", "as", "by"}


# Dictionary of special words that should always be formatted correctly
SPECIAL_WORDS = {"phd.": "PhD.", "esl": "ESL", "mba": "MBA", "bsc": "BSc", "msc": "MSc"}


# Function to process text using OpenAI API
def generate_data_dict_using_openai(text, temperature: float = TEMPERATURE):
    """
    Calls OpenAI API to extract and structure transcript data into JSON format.
    Args:
        text (str): Extracted text from the transcript.
        temperature (float): OpenAI model temperature for response variation.
    Returns:
        dict | None: Parsed JSON data or None if extraction fails.
    """
    openai_client = get_openai_client()

    prompt = f"""
    Extract and organize the following data into a **valid JSON object**.
    The JSON **must** follow this structure:
    ```json
    {{
        "degrees": [
            {{
                "degree": "",
                "major": "",
                "minor": "",
                "institution_name": "",
                "awarded_date": "",
                "overall_credits_earned": "",
                "overall_gpa": "",
                "courses": [
                    {{
                        "course_name": "",
                        "credits_earned": "",
                        "grade": "",
                        "is_passed": ""
                    }}
                ]
            }}
        ],
        "student": {{
            "first_name": "",
            "middle_name": "",
            "last_name": ""
        }}
    }}
    ```
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - The dictionary keys must match the exact structure specified.
    - All degree-related fields (degree, major, minor, institution_name, awarded_date, overall_credits_earned, overall_gpa) must be grouped under degrees.
    - Each degree must contain a list of its corresponding courses.
    - The student name must be stored separately under the "student" key.
    - If student name is missing, look for "record of" field instead.
    - If a student name has a suffix (e.g., Jr., III), put it with the first name.
    - If the degree awarded date is missing, look for the program graduation date instead.
    - Format "awarded_date" as "yyyy-mm-dd". If only the year is provided, format it as "yyyy-12-31".
    - Course names may contain abbreviations or special characters: expand abbreviations (e.g., "Mgmt" → "Management"); preserve special characters (e.g., "&" remains "&").
    - Course codes contain abbreviations and numbers. Discard course codes and extract only course names.
    - If credits earned is missing for a course, look for credits attempted or credits from the same course. Credits earned may be displayed as an abbreviation (e.g., CrE).
    - The grade is either a letter grade (e.g., A, B+) or a numeric grade. If numeric, convert it into a string.
    - Use the grading system from the transcript to determine "is_passed": if the grade is a passing grade for the program, "is_passed" = True; if not, "is_passed" = False.
    - The number of items in "course_name", "credits_earned", and "grade" lists must match. If not, redo extraction.
    - The sum of "credits_earned" for a degree must match "overall_credits_earned". If not, redo extraction.
    - Ensure numerical values are properly formatted (e.g., 3.0, 4.5 for credits; 3.33 for GPA).
    - Capitalize only important words. Keep minor words lowercase (e.g., "of", "in", "the") unless they start a sentence.
    - If a field is not found, use an empty string ("") for single values and an empty list ([]) for lists.

    **Input Data:**
    ```
    {text}
    ```
    **Output Format:** Return **ONLY** a valid JSON object. 
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Use GPT-4 for better accuracy
            messages=[
                {"role": "system", "content": "You are an OCR expert in extracting text from academic transcript images with high accuracy and returning structured JSON data."},
                {"role": "user", "content": prompt}
            ],
            #max_tokens=2000,
            temperature=temperature
        )
        
        structured_text = response.choices[0].message.content.strip()

        if not structured_text:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        structured_text = structured_text.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(structured_text)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", structured_text)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to format title case names while handling minor words
def format_title(text):
    if not isinstance(text, str) or not text.strip():
        return text  # Return as is if not a valid string
    
    words = text.lower().split()
    formatted_words = []
    
    for i, word in enumerate(words):
        if word in SPECIAL_WORDS:  # Special words should retain their specific case
            formatted_words.append(SPECIAL_WORDS[word])
        elif i == 0 or word not in MINOR_WORDS:  # First word and important words should be capitalized
            formatted_words.append(word.capitalize())
        else:
            formatted_words.append(word)  # Minor words stay lowercase

    return " ".join(formatted_words)


# Function to ensure awarded_date is in YYYY-MM-DD format
def format_date(date_str):
    if not isinstance(date_str, str) or not date_str.strip():
        return None

    try:
        # Auto-detect date format and convert to YYYY-MM-DD
        parsed_date = parser.parse(date_str)
        return parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return None 


# Function to convert numeric fields to float with up to 4 decimal places
def format_float(value):
    try:
        return round(float(value), 4)  # Convert to float with 4 decimal places
    except (ValueError, TypeError):
        return None 


# Function to convert values to boolean
def format_boolean(value):
    if isinstance(value, bool):
        return value  # Already boolean
    if isinstance(value, str):
        return value.lower() in ["true", "1", "yes", "y", "pass"]  # Convert truthy strings to True
    if isinstance(value, int):
        return value == 1  # Convert 1 to True, 0 to False
    return False  # Default to False


# Function to format and clean the DataFrame before validation
def preprocess_data_dict(data_dict: dict) -> dict: 
    """
    Preprocesses and formats extracted transcript data stored in a dictionary.
    Args:
        data_dict (dict): Dictionary containing extracted transcript data.
    Returns:
        dict: Dictionary with formatted values.
    """
    # Define a mapping of column names to their corresponding formatting functions
    format_map = {
        "first_name": format_title,
        "middle_name": format_title,
        "last_name": format_title,
        "institution_name": format_title,
        "degree": format_title,
        "major": format_title,
        "minor": format_title,
        "awarded_date": format_date,
        "overall_credits_earned": format_float,
        "overall_gpa": format_float,
        "course_name": format_title,
        "credits_earned": format_float,
        "is_passed": format_boolean
    }

    formatted_data = {"student": {}, "degrees": {}, "file_name": data_dict["file_name"]}

    # Process student-level fields
    formatted_data["student"] = {
        key: format_map[key](value) if key in format_map else value
        for key, value in data_dict.get("student", {}).items()
    }

    # Process degrees and their courses
    formatted_data["degrees"] = []

    for degree in data_dict.get("degrees", []):
        formatted_degree = {
            key: format_map[key](degree[key]) if key in format_map else degree[key]
            for key in degree if key != "courses"  # Skip courses for now
        }

        # Process courses within each degree
        formatted_degree["courses"] = [
            {
                course_key: format_map[course_key](course[course_key]) if course_key in format_map else course[course_key]
                for course_key in course
            }
            for course in degree.get("courses", [])
        ]

        formatted_data["degrees"].append(formatted_degree)

    return formatted_data


# Function to convert JSON data to a Pandas DataFrame
def json_data_to_dataframe(json_data):
    """
    Converts structured JSON data into a Pandas DataFrame.
    Args:
        json_data (dict): Extracted structured data.
    Returns:
        pd.DataFrame | None: Returns a formatted DataFrame or None if processing fails.
    """
    try:
        # Extract course-related fields (multi-value)
        course_names = json_data.get("course_name", [])
        credits_earned = json_data.get("credits_earned", [])
        grades = json_data.get("grade", [])

        # Ensure all course-related lists have the same length
        max_len = max(len(course_names), len(credits_earned), len(grades))
        course_names += [""] * (max_len - len(course_names))
        credits_earned += [""] * (max_len - len(credits_earned))
        grades += [""] * (max_len - len(grades))

        # Create a DataFrame with expanded course details
        df = pd.DataFrame({
            "first_name": [json_data.get("student_firstName", [""])[0]] * max_len,
            "middle_name": [json_data.get("student_middleName", [""])[0] if json_data.get("student_middleName") else ""] * max_len,
            "last_name": [json_data.get("student_lastName", [""])[0]] * max_len,
            "institution_name": [json_data.get("institution_name", [""])[0]] * max_len,
            "degree": [json_data.get("degree", [""])[0] if json_data.get("degree") else ""] * max_len,
            "major": [json_data.get("major", [""])[0] if json_data.get("major") else ""] * max_len,
            "minor": [json_data.get("minor", [""])[0] if json_data.get("minor") else ""] * max_len,
            "awarded_date": [json_data.get("awarded_date", [""])[0] if json_data.get("awarded_date") else ""] * max_len,
            "overall_credits_earned": [json_data.get("overall_credits_earned", [""])[0] if json_data.get("overall_credits_earned") else ""] * max_len,
            "overall_gpa": [json_data.get("overall_gpa", [""])[0] if json_data.get("overall_gpa") else ""] * max_len,
            "course_name": course_names,
            "credits_earned": credits_earned,
            "grade": grades,
            "is_passed": is_passed
        })

        return df

    except Exception as e:
        print(f"Error converting JSON to DataFrame: {e}")
        return None
