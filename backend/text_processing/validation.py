
import os
import re
import regex
import pandas as pd
import numpy as np
import json
from datetime import datetime
from dateutil import parser
from clients_service import get_openai_client
from utils import get_valid_value


# Set a randomness level for OpenAI
TEMPERATURE = 0.3 # Lower value for more deterministic, precise, and consistent


# Define validation regex patterns
PATTERNS = {
    "first_name": regex.compile(r"^[\p{L}\s\-\.\'’]+$", regex.UNICODE),
    "middle_name": regex.compile(r"^[\p{L}\s\-\.\'’]*$", regex.UNICODE),  # Can be empty
    "last_name": regex.compile(r"^[\p{L}\s\-\.\'’]+$", regex.UNICODE),
    "institution_name": regex.compile(r"^[\p{L}0-9\s\.\'’,&\-]+$", regex.UNICODE),
    "degree": re.compile(r"^[A-Za-z\s\-\&\.,\'’\/\(\)]*$"),  # Can be empty
    "major": re.compile(r"^[A-Za-z\s\-\&\.,\'’\/\(\):]*$"),  # Can be empty
    "minor": re.compile(r"^[A-Za-z\s\-\&\.,\'’\/\(\):]*$"),  # Can be empty
    "awarded_date": re.compile(r"^\d{4}-\d{2}-\d{2}$|^$"),  # Can be empty
    "overall_credits_earned": re.compile(r"^\d{1,3}(\.\d{1,4})?$|^$"),  # Must be a positive integer, can be empty
    "overall_gpa": re.compile(r"^\d{1,2}(\.\d{1,4})?$|^$"),  # Allows decimals, can be empty
    "course_name": re.compile(r"^[A-Za-z0-9\s\-\&\.,\'’\/\(\):]+$"),
    "credits_earned": re.compile(r"^\d{1,2}(\.\d{1,4})?$|^$"),  # Can be empty
    "grade": re.compile(r"^(A\+?|A\-?|B\+?|B\-?|C\+?|C\-?|D\+?|D\-?|F|[A-Z]{1,3}|[0-9]{1,3}(\.\d{1,4})?)$|^$"),  # Supports letter and numeric grades, can be empty
    "is_passed": re.compile(r"^(True|False|true|false)$")  # Boolean values
}


# Function to validate each field in the dictionary using regex patterns
def rule_based_validation(data_dict) -> list:
    """
    Applies rule-based validation to a dictionary containing academic transcript data.
    Args:
        data_dict (dict): The preprocessed transcript data.
    Returns:
        list: A list of validation error messages.
    """
    errors = []

    try:
        for key, values in data_dict.items():
            if key in PATTERNS:
                pattern = PATTERNS[key]
                
                for i, value in enumerate(values):
                    if value is None or value == "":
                        continue  # Skip empty values
                    
                    value_str = str(value).strip()  # Convert to string and remove spaces
                    
                    if not pattern.match(value_str):
                        errors.append(f"❌ Field '{key}', Item {i + 1}: Invalid format - '{value_str}'")
    
    except Exception as e:
        print(f"Error in rule-based validation: {e}")
        errors.append(f"Unexpected error during rule-based validation: {str(e)}")

    return errors


# Function to validate first_name, middle_name, and last_name using OpenAI
def validate_name_openai(first_name, middle_name, last_name, temperature: float = TEMPERATURE):
    openai_client = get_openai_client()

    prompt = f"""
    Validate the following name details:
    - First Name: {first_name}
    - Middle Name: {middle_name}
    - Last Name: {last_name}

    Check if each name is a valid human name. Ensure proper capitalization, detect OCR errors, and suggest corrections if necessary.
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - If a field is empty, leave it as an empty string.

    Return the corrections as a JSON object following this structure:
    ```json
    {{
        "first_name": "",
        "middle_name": "",
        "last_name": ""
    }}
    ```
    """
    try: 
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an OCR expert in validating human name details."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        result = response.choices[0].message.content.strip()

        if not result:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        result = result.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(result)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", result)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to validate intitution_name, degree, major, and minor using OpenAI
def validate_academic_info_openai(institution_name, degree, major, minor, temperature: float = TEMPERATURE):
    openai_client = get_openai_client()

    prompt = f"""
    Validate the following academic information:
    - Institution: {institution_name}
    - Degree: {degree}
    - Major: {major}
    - Minor: {minor}

    Check if the institution exists and whether the degree, major, and minor are commonly offered.
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - If a field is empty, leave it as an empty string.
    
    Return the corrections as a JSON object following this structure:
    ```json
    {{
        "institution_name": "",
        "degree": "",
        "major": "",
        "minor": ""
    }}
    ```
    """
    try: 
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an OCR expert in validating academic information."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        result = response.choices[0].message.content.strip()

        if not result:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        result = result.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(result)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", result)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to validate awarded_date using OpenAI
def validate_awarded_date_openai(awarded_date, temperature: float = TEMPERATURE):
    openai_client = get_openai_client()

    prompt = f"""
    Check if the awarded date is correctly formatted in YYYY-MM-DD format:
    - Awarded Date: {awarded_date}

    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - If a field is empty, leave it as an empty string.
    
    Return the corrections as a JSON object following this structure:
    ```json
    {{
        "awarded_date": ""
    }}
    ```
    """
    try: 
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an OCR expert in validating academic degree awarded date format."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        result = response.choices[0].message.content.strip()

        if not result:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        result = result.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(result)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", result)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to validate overall_credits_earned and overall_gpa using OpenAI
def validate_academic_performance_openai(overall_credits_earned, overall_gpa, temperature: float = TEMPERATURE):
    openai_client = get_openai_client()

    prompt = f"""
    Validate the following academic performance indicators:
    - Overall Credits Earned: {overall_credits_earned}
    - Overall GPA: {overall_gpa}

    Check if the credits and GPA are within a reasonable range for a degree.
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - If a field is empty, return `None` instead of `0.0`.
    
    Return the corrections as a JSON object following this structure:
    ```json
    {{
        "overall_credits_earned": 0.0,
        "overall_gpa": 0.0
    }}
    ```
    """
    try: 
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an OCR expert in validating academic performance indicators."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        result = response.choices[0].message.content.strip()

        if not result:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        result = result.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(result)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", result)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to validate course_name, credits_earned, and grade using OpenAI
def validate_coursework_openai(course_name, credits_earned, grade, temperature: float = TEMPERATURE):
    openai_client = get_openai_client()

    prompt = f"""
    Validate the following course details:
    - Course Name: {course_name}
    - Credits Earned: {credits_earned}
    - Grade: {grade}

    Check if the course is commonly offered, if the credits make sense, and whether the grade is a valid academic grade.
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - If a field is empty, leave it as an empty value.
    - Check statistical anomalies for credits earned. 
    - If a grade is a numeric grade, do not convert it to a letter grade, and vice versa. The grade should be returned as a string.
    - If you cannot decide, convert the original value of the field into the correct format and return it.
    
    Return the corrections as a JSON object following this structure:
    ```json
    {{
        "course_name": "",
        "credits_earned": 0.0,
        "grade": ""
    }}
    ```
    """
    try: 
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an OCR expert in validating academic course details."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        result = response.choices[0].message.content.strip()

        if not result:
            print("OpenAI returned an empty response.")
            return None

        # Remove code block formatting if present
        result = result.replace("```json", "").replace("```", "").strip()

        # Ensure the response is valid JSON
        return json.loads(result)  # Parse JSON

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", result)
        return None
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


# Function to validate each value of a dictionary using OpenAI-based validation functions
def openai_based_validation(data_dict):
    """
    Iterates through a dictionary and validates each value using OpenAI-based validation functions.
    Updates invalid values with corrected suggestions where applicable.
    Args:
        data_dict (dict): The extracted transcript data.
    Returns:
        dict: A dictionary with validated/corrected data.
    """
    corrected_data = {}
    
    try:
        # Validate Name Fields
        corrected_names = validate_name_openai(
            get_valid_value(data_dict.get("student_firstName")),
            get_valid_value(data_dict.get("student_middleName")),
            get_valid_value(data_dict.get("student_lastName"))
        ) or {}

        # Validate Academic Information (Institution, Degree, Major, Minor)
        corrected_academic_info = validate_academic_info_openai(
            get_valid_value(data_dict.get("institution_name")),
            get_valid_value(data_dict.get("degree")),
            get_valid_value(data_dict.get("major")),
            get_valid_value(data_dict.get("minor"))
        ) or {}

        # Validate Awarded Date
        corrected_awarded_date = validate_awarded_date_openai(
            get_valid_value(data_dict.get("awarded_date"))
        ) or {}

        # Validate Overall Credits Earned & Overall GPA
        corrected_performance = validate_academic_performance_openai(
            get_valid_value(data_dict.get("overall_credits_earned"), None),
            get_valid_value(data_dict.get("overall_gpa"), None)
        ) or {}

        # Validate Coursework (Course Name, Credits Earned, Grade)
        corrected_coursework = [
            validate_coursework_openai(course, credits, grade) or 
            {"course_name": course, "credits_earned": credits, "grade": grade}
            for course, credits, grade in zip(
                data_dict.get("course_name", []),
                data_dict.get("credits_earned", []),
                data_dict.get("grade", [])
            )
        ]

        # Corrected Data Assignment
        corrected_data["first_name"] = [corrected_names.get("first_name", get_valid_value(data_dict.get("student_firstName")))]
        corrected_data["middle_name"] = (
            [] if not data_dict.get("middle_name") else 
            [corrected_names.get("middle_name", get_valid_value(data_dict.get("student_middleName")))]
        )
        corrected_data["last_name"] = [corrected_names.get("last_name", get_valid_value(data_dict.get("student_lastName")))]
        corrected_data["institution_name"] = [corrected_academic_info.get("institution_name", get_valid_value(data_dict.get("institution_name")))]
        corrected_data["degree"] = (
            [] if not data_dict.get("degree") else 
            [corrected_academic_info.get("degree", get_valid_value(data_dict.get("degree")))]
        )
        corrected_data["major"] = (
            [] if not data_dict.get("major") else 
            [corrected_academic_info.get("major", get_valid_value(data_dict.get("major")))]
        )
        corrected_data["minor"] = (
            [] if not data_dict.get("minor") else 
            [corrected_academic_info.get("minor", get_valid_value(data_dict.get("minor")))]
        )
        corrected_data["awarded_date"] = (
            [] if not data_dict.get("awarded_date") else 
            [corrected_awarded_date.get("awarded_date", get_valid_value(data_dict.get("awarded_date")))]
        )
        corrected_data["overall_credits_earned"] = (
            [] if not data_dict.get("overall_credits_earned") else 
            [corrected_performance.get("overall_credits_earned", get_valid_value(data_dict.get("overall_credits_earned"), None))]
        )
        corrected_data["overall_gpa"] = (
            [] if not data_dict.get("overall_gpa") else 
            [corrected_performance.get("overall_gpa", get_valid_value(data_dict.get("overall_gpa"), None))]
        )

        # Processing corrected coursework
        corrected_data["course_name"] = [entry.get("course_name", "") for entry in corrected_coursework]
        corrected_data["credits_earned"] = [entry.get("credits_earned", "") for entry in corrected_coursework]
        corrected_data["grade"] = [entry.get("grade", "") for entry in corrected_coursework]

        # Handle Boolean `is_passed`
        corrected_data["is_passed"] = data_dict.get("is_passed", [])
        corrected_data["file_name"] = data_dict.get("file_name", [])

        return corrected_data

    except Exception as e:
        print(f"Error in OpenAI-based validation: {e}")
        print(traceback.format_exc())
        return None  
