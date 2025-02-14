import os
import csv
import json
import pandas as pd


# Function to process text using OpenAI API
def generate_json_data_using_openai(text, openai_client):

    prompt = f"""
    Extract and organize the following data into a **valid JSON object**.
    The JSON **must** follow this structure:
    ```json
    {{
        "student_firstName": [],
        "student_middleName": [],
        "student_lastName": [],
        "institution_name": [],
        "degree": [],
        "major": [],
        "minor": [],
        "awarded_date": [],
        "overall_credits_earned": [],
        "overall_gpa": [],
        "course_name": [],
        "credits_earned": [],
        "grade": []
    }}
    ```
    **Rules:**
    - Return only valid JSON, with no extra text, comments, or markdown formatting.
    - No explanations, just the JSON output.
    - The dictionary keys must match the column names specified.
    - The dictionary values must be lists of strings or numbers.
    - If student name is missing, look for "record of" field instead.
    - If a student name as a prefix, put it with the first name.
    - If degree awarded date is missing, look for program graduation date instead.
    - Format awarded_date as "yyyy-mm-dd". If only the year is provided, format it as "yyyy-12-31".
    - Course names, course codes, credits earned, and grade are in the same line, but may be in different orders.
    - Course names may contain abbreviations or special characters. If present, expand abbreviations, but don't expand special characters (e.g., &).
    - Course codes contain abbreviations and numbers. Discard course codes and extract only course names. 
    - If credits earned is missing for a course, look for the credits attempted or the credits of that course.
    - Find letter grade first. If grade is a numeric number, turn it into a string.
    - The number of items in course_name, credits_earned, and grade lists should match.
    - Credits are in numerical format (e.g., 3.0, 4.5). GPA is in numerical format (e.g., 3.33). Ensure numerical values are properly formatted.
    - Capitalize only important words. Keep minor words (e.g., of, in, the, and) in lowercase, unless they start a sentence. Apply to student name, institution name, degree, major, minor, and course name.
    - If a field is not found, leave it as an empty list.
    **Input Data:**
    ```
    {text}
    ```
    **Output Format:** Return **ONLY** a valid JSON object. 
    """
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",  # Use GPT-4 for better accuracy
        messages=[
            {"role": "system", "content": "You are an expert in processing academic transcripts and returning structured JSON data."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000
    )
    
    structured_text = response.choices[0].message.content.strip()

    if not structured_text:
        print("OpenAI returned an empty response.")
        return pd.DataFrame()  # Return an empty DataFrame

    try:
        # Remove code block formatting (if present)
        if structured_text.startswith("```json"):
            structured_text = structured_text.strip("```json").strip("```")

        # Ensure the response is valid JSON
        json_data = json.loads(structured_text)  # Parse JSON
        return json_data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("OpenAI Response:", structured_text)
        return {}


# Function to convert JSON data to a Pandas DataFrame
def json_data_to_dataframe(json_data):
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
        "firstName": [json_data.get("student_firstName", [""])[0]] * max_len,
        "middleName": [json_data.get("student_middleName", [""])[0] if json_data.get("student_middleName") else ""] * max_len,
        "lastName": [json_data.get("student_lastName", [""])[0]] * max_len,
        "institution_name": [json_data.get("institution_name", [""])[0]] * max_len,
        "degree": [json_data.get("degree", [""])[0] if json_data.get("degree") else ""] * max_len,
        "major": [json_data.get("major", [""])[0] if json_data.get("major") else ""] * max_len,
        "minor": [json_data.get("minor", [""])[0] if json_data.get("minor") else ""] * max_len,
        "awarded_date": [json_data.get("awarded_date", [""])[0] if json_data.get("awarded_date") else ""] * max_len,
        "overall_credits_earned": [json_data.get("overall_credits_earned", [""])[0] if json_data.get("overall_credits_earned") else ""] * max_len,
        "overall_gpa": [json_data.get("overall_gpa", [""])[0] if json_data.get("overall_gpa") else ""] * max_len,
        "course_name": course_names,
        "credits_earned": credits_earned,
        "grade": grades
    })

    return df
