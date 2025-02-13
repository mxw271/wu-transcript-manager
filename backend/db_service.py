##
# Define helper functions for database operations
##

import sqlite3
from sqlite3 import Connection


# Function to validate data exists
def check_database_content(database_file):
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


# Function to insert an educator
def insert_educator(
    conn: Connection, 
    firstName: str,
    lastName: str, 
    middleName: str = None
) -> int:
    """
    Inserts a new educator into the educators table.
    Args:
        conn (Connection): Database connection object.
        firstName (str): The first name of the educator.
        lastName (str): The last name of the educator.
        middleName (str, optional): The middle name of the educator.
    Returns:
        int: The educator_id of the inserted educator.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO educators (firstName, lastName, middleName) 
           VALUES (?, ?, ?)''', 
        (firstName, lastName, middleName)
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
    credits_earned: float = None, 
    grade: str = None,
) -> int:
    """
    Inserts a new course into the courses table.
    Args:
        conn (Connection): Database connection object.
        transcript_id (int): The ID of the transcript (foreign key).
        course_name (str): Name of the course.
        should_be_category (str): Category the course belongs to.
        adjusted_credits_earned (float): Credits earned for the course if passed.
        credits_earned (float, optional): Credits earned for the course.
        grade (str, optional): Grade earned for the course.
    Returns:
        int: The course_id of the inserted course.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO courses (transcript_id, course_name, should_be_category, adjusted_credits_earned, credits_earned, grade)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (transcript_id, course_name, should_be_category, adjusted_credits_earned, credits_earned, grade)
    )
    conn.commit()

    # Return the last inserted ID (course_id)
    return cursor.lastrowid


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
            educators.firstName AS educator_firstName,
            educators.middleName AS educator_middleName,
            educators.lastName AS educator_lastName,
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
    if criteria.get("educator_firstName") and criteria.get("educator_lastName"):
        query += " AND educators.firstName = ? AND educators.lastName = ?"
        params.append(criteria["educator_firstName"])
        params.append(criteria["educator_lastName"])
    
    # Filtering by course category
    if criteria.get("course_category"):
        query += " AND courses.should_be_category = ?"
        params.append(criteria["course_category"])

    # Filtering by education level
    if criteria.get("education_level") and isinstance(criteria["education_level"], list):
        placeholders = ", ".join(["?" for _ in criteria["education_level"]])  # Create correct number of placeholders
        query += f" AND transcripts.degree_level IN ({placeholders})"
        params.extend(criteria["education_level"])

    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()

    return results
