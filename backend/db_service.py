##
# Define helper functions for database operations
##

import os
import pandas as pd
import sqlite3
from sqlite3 import Connection
from db_create_tables import initialize_database


# Function to validate data exists
def check_database_content(database_file: str):
    conn = None
    try:
        conn = sqlite3.connect(database_file)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM educators")
        educators_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transcripts")
        transcripts_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM courses")
        courses_count = cursor.fetchone()[0]

        print(f"Educators: {educators_count}, Transcripts: {transcripts_count}, Courses: {courses_count}")

    except Exception as e:
        print(f"❌ Database check failed: {str(e)}")
    
    finally:
        if conn:
            conn.close()


# Function to check if database status
def check_database_status(database_file: str):
    if not database_file or not os.path.exists(database_file):
        print(f"❌ Database file not found: {database_file}. Creating a new one...")
        initialize_database(database_file)
    
    # Verify database content
    check_database_content(database_file)


# Function to insert an educator
def insert_educator(
    conn: Connection, 
    first_name: str,
    last_name: str, 
    middle_name: str = None
) -> int:
    """
    Inserts a new educator into the educators table.
    Args:
        conn (Connection): Database connection object.
        first_name (str): The first name of the educator.
        last_name (str): The last name of the educator.
        middle_name (str, optional): The middle name of the educator.
    Returns:
        int: The educator_id of the inserted educator.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO educators (first_name, last_name, middle_name) 
           VALUES (?, ?, ?)''', 
        (first_name, last_name, middle_name)
    )
    conn.commit()

    # Return the last inserted ID (educator_id)
    return cursor.lastrowid


# Function to insert a transcript
def insert_transcript(
    conn: Connection, 
    educator_id: int, 
    institution_name: str, 
    degree_level: str, 
    file_name: str,
    degree: str = None, 
    major: str = None, 
    minor: str = None, 
    awarded_date: str = None, 
    overall_credits_earned: float = None, 
    overall_gpa: float = None, 
) -> int:
    """
    Inserts a new transcript into the transcripts table.
    Args:
        conn (Connection): Database connection object.
        educator_id (int): ID of the educator (foreign key).
        institution_name (str): Name of the institution.
        degree_level (str): Rank of the degree earned.
        file_name (str): Name of the transcript file.
        degree (str, optional): Degree earned (e.g., BS, MS).
        major (str, optional): Major field of study.
        minor (str, optional): Minor field of study.
        awarded_date (str, optional): Awarded date in YYYY-MM-DD format.
        overall_credits_earned (float, optional): Total credits earned.
        overall_gpa (float, optional): Overall GPA.
        
    Returns:
        int: The transcript_id of the inserted transcript.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO transcripts (educator_id, institution_name, degree_level, file_name, degree,
                                    major, minor, awarded_date, overall_credits_earned, overall_gpa)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (educator_id, institution_name, degree_level, file_name, degree, 
         major, minor, awarded_date, overall_credits_earned, overall_gpa)
    )
    conn.commit()

    # Return the last inserted ID (transcript_id)
    return cursor.lastrowid


# Function to insert a course
def insert_course(
    conn: Connection, 
    transcript_id: int, 
    course_name: str, 
    should_be_category: str,
    adjusted_credits_earned: float,
    row_hash: str,
    credits_earned: float = None, 
    grade: str = None,
    is_passed: bool = None,
) -> int:
    """
    Inserts a new course into the courses table.
    Args:
        conn (Connection): Database connection object.
        transcript_id (int): The ID of the transcript (foreign key).
        course_name (str): Name of the course.
        should_be_category (str): Category the course belongs to.
        adjusted_credits_earned (float): Credits earned for the course if passed.
        row_hash (str): Unique hash for deduplication.
        credits_earned (float, optional): Credits earned for the course.
        grade (str, optional): Grade earned for the course.
        is_passed (bool, optional): Whether the course was passed
    Returns:
        int: The course_id of the inserted course.
    """
    cursor = conn.cursor()

    # Convert `is_passed` to an integer for SQLite (1 = True, 0 = False, NULL if None)
    is_passed_value = None if is_passed is None else int(is_passed)

    # Check if a course with the same hash already exists
    cursor.execute("SELECT course_id FROM courses WHERE row_hash = ?", (row_hash,))
    existing_course = cursor.fetchone()
    if existing_course:
        print(f"⚠️ Duplicate course detected: {course_name}. Skipping insertion.")
        return existing_course[0]  # Return the existing course_id

    # Insert new course
    cursor.execute(
        '''INSERT INTO courses (transcript_id, course_name, should_be_category, adjusted_credits_earned, row_hash, credits_earned, grade, is_passed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (transcript_id, course_name, should_be_category, adjusted_credits_earned, row_hash, credits_earned, grade, is_passed_value)
    )
    conn.commit()

    # Return the last inserted ID (course_id)
    return cursor.lastrowid


# Function to insert records from dict into database
def insert_records_from_dict(conn, data_dict: dict, transcript_map: dict) -> dict:
    """
    Inserts records from a structured dictionary into the database while handling duplicates.
    Args:
        conn (sqlite3.Connection): Active database connection.
        data_dict (dict): Structured dictionary containing transcript data.
        transcript_map (dict): Cached mapping of file names to transcript IDs.
    Returns:
        dict: A summary with counts of inserted and duplicate rows.
    """
    cursor = conn.cursor()

    # Get existing hashes from the database
    existing_hashes = set(row[0] for row in cursor.execute("SELECT row_hash FROM courses"))

    duplicate_rows = []
    inserted_count = 0
    batch_size = 10  # Commit after every 10 insertions for performance

    try:
        # Extract student-level information
        student = data_dict.get("student", {})
        first_name = student.get("first_name", "")
        middle_name = student.get("middle_name", None)  # Can be None
        last_name = student.get("last_name", "")

        # Check if educator exists
        cursor.execute(
            """SELECT educator_id FROM educators 
            WHERE first_name = ? AND last_name = ? AND COALESCE(middle_name, '') = COALESCE(?, '')""",
            (first_name, last_name, middle_name)
        )
        educator = cursor.fetchone()

        if educator:
            educator_id = educator[0]
        else: # Insert educator and get educator_id
            educator_id = insert_educator(conn, first_name, last_name, middle_name)

        # Iterate over degrees
        for degree in data_dict.get("degrees", []):
            institution_name = degree.get("institution_name", "")
            degree_name = degree.get("degree", None)  # Can be None
            major = degree.get("major", None)  # Can be None
            minor = degree.get("minor", None)  # Can be None
            awarded_date = degree.get("awarded_date", None)  # Can be None
            overall_credits_earned = degree.get("overall_credits_earned", None)  # Can be None
            overall_gpa = degree.get("overall_gpa", None)  # Can be None
            degree_level = degree.get("degree_level", "")

            # Check if transcript exists
            file_name = data_dict.get("file_name", "")
            if file_name in transcript_map:
                transcript_id = transcript_map[file_name]  # Use cached transcript_id
            else:
                cursor.execute(
                    """SELECT transcript_id FROM transcripts WHERE 
                    educator_id = ? AND institution_name = ? AND file_name = ?""",
                    (educator_id, institution_name, file_name)
                )
                transcript = cursor.fetchone()

                if transcript:
                    transcript_id = transcript[0]
                else: # Insert transcript and get transcript_id
                    transcript_id = insert_transcript(
                        conn, educator_id, institution_name, degree_level,
                        file_name, degree_name, major, minor, awarded_date, 
                        overall_credits_earned, overall_gpa
                    )

                # Store transcript_id in map
                transcript_map[file_name] = transcript_id  

            # Iterate over courses in the degree
            for course in degree.get("courses", []):
                row_hash = course["row_hash"]

                # Skip duplicates
                if row_hash in existing_hashes:
                    duplicate_rows.append(row_hash)
                    print(f"Skipping duplicate course: {course['course_name']}")
                    continue

                # Insert course record
                course_id = insert_course(
                    conn, transcript_id, 
                    course["course_name"], 
                    course["should_be_category"], 
                    course["adjusted_credits_earned"], 
                    course["row_hash"], 
                    course["credits_earned"], 
                    course["grade"],
                    course["is_passed"]
                )

                inserted_count += 1
                if inserted_count % batch_size == 0:
                    conn.commit()  # Commit periodically for performance
        
        conn.commit()  # Final commit for remaining transactions

    except Exception as e:
        conn.rollback()  # Rollback changes if any error occurs
        print(f"Error inserting records: {str(e)}")
        print(traceback.format_exc())

    return {
        "inserted_count": inserted_count,
        "duplicate_rows": duplicate_rows
    }


# Function to insert records from dataframe into database
def insert_records_from_df(conn, df: pd.DataFrame, transcript_map: dict) -> dict:
    """
    Inserts records from a DataFrame into the database while handling duplicates.
    Args:
        conn (sqlite3.Connection): Active database connection.
        df (pd.DataFrame): Structured DataFrame containing transcript data.
        transcript_map (dict): Cached mapping of file names to transcript IDs.
    Returns:
        dict: A summary with counts of inserted and duplicate rows.
    """
    cursor = conn.cursor()

    # Get existing hashes from the database
    existing_hashes = set(row[0] for row in cursor.execute("SELECT row_hash FROM courses"))

    duplicate_rows = []
    inserted_count = 0
    batch_size = 10  # Commit after every 10 insertions for performance

    try:
        # Iterate over rows
        for index, row in df.iterrows():
            row_hash = row.get("row_hash")

            # Skip duplicates
            if row_hash in existing_hashes:
                duplicate_rows.append(index)
                print(f"Skipping duplicate row {index}.")
                continue

            # Check if educator exists
            cursor.execute(
                """SELECT educator_id FROM educators 
                WHERE first_name = ? AND last_name = ? AND COALESCE(middle_name, '') = COALESCE(?, '')""",
                (row.get("first_name", ""), row.get("last_name", ""), row.get("middle_name", None))
            )
            educator = cursor.fetchone()

            if educator:
                educator_id = educator[0]
            else:
                # Insert educator and get educator_id
                educator_id = insert_educator(conn, row.get("first_name", ""), row.get("last_name", ""), row.get("middle_name", None))
            
        
            # Check if transcript exists
            file_name = row.get("file_name", "")
            if file_name in transcript_map:
                transcript_id = transcript_map[file_name]  # Use cached transcript_id
            else:
                cursor.execute(
                    """SELECT transcript_id FROM transcripts WHERE 
                    educator_id = ? AND institution_name = ? AND file_name = ?""",
                    (educator_id, row.get("institution_name", ""), file_name)
                )
                transcript = cursor.fetchone()

                if transcript:
                    transcript_id = transcript[0]
                else:
                    # Insert transcript and get transcript_id
                    transcript_id = insert_transcript(
                        conn, educator_id, row.get("institution_name", ""), row.get("degree_level", ""),
                        file_name, row.get("degree", ""), row.get("major", ""), row.get("minor", ""),
                        row.get("awarded_date", ""), row.get("overall_credits_earned", None), row.get("overall_gpa", None)
                    )

                # Store transcript_id in map
                transcript_map[file_name] = transcript_id  
         
            # Insert course
            course_id = insert_course(
                conn, transcript_id, row.get("course_name", ""), row.get("should_be_category", "Uncategorized"),
                row.get("adjusted_credits_earned", 0), row.get("row_hash", ""), 
                row.get("credits_earned", None), row.get("grade", None), row.get("is_passed", None)
            )

            inserted_count += 1
            if inserted_count % batch_size == 0:
                conn.commit()  # Commit periodically to improve performance
        
        conn.commit()  # Final commit for remaining transactions
    
    except Exception as e:
        conn.rollback()  # Rollback changes if any error occurs
        print(f"Error inserting records: {str(e)}")
        print(traceback.format_exc())
    
    return {
        "inserted_count": inserted_count,
        "duplicate_rows": duplicate_rows
    }


# Function to query transcript data based on search criteria
def query_transcripts(conn: Connection, criteria: dict) -> list:
    """
    Query transcript data based on search criteria.
    Args:
        conn (Connection): Database connection object.
        criteria (dict): Search parameters containing educator_name and/or course_category and/or education_level.
    Returns:
        list: Queried results.
    """
    query = '''
        SELECT 
            educators.first_name AS educator_first_name,
            educators.middle_name AS educator_middle_name,
            educators.last_name AS educator_last_name,
            transcripts.degree,
            transcripts.degree_level,
            courses.course_name,
            courses.should_be_category,
            courses.adjusted_credits_earned
        FROM educators
        INNER JOIN transcripts ON transcripts.educator_id = educators.educator_id
        INNER JOIN courses ON courses.transcript_id = transcripts.transcript_id
        WHERE 1=1 
    ''' 

    params = []

    # Filtering by educator's name
    if criteria.get("educator_first_name") and criteria.get("educator_last_name"):
        query += " AND LOWER(educators.first_name) = LOWER(?) AND LOWER(educators.last_name) = LOWER(?)"
        params.append(criteria["educator_first_name"].lower())
        params.append(criteria["educator_last_name"].lower())
    
    # Filtering by course category
    if criteria.get("course_category"):
        query += " AND LOWER(courses.should_be_category) = LOWER(?)"
        params.append(criteria["course_category"].lower())

    # Filtering by education level
    if criteria.get("education_level") and isinstance(criteria["education_level"], list):
        placeholders = ", ".join(["?" for _ in criteria["education_level"]])  # Create correct number of placeholders
        query += f" AND transcripts.degree_level IN ({placeholders})"
        params.extend(criteria["education_level"])

    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()

        return None if not results else results
    except Exception as e:
        print(f"❌ Database Query Failed: {str(e)}")
        return "error" 
