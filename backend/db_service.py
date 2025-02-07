##
# Define helper functions for database operations
##

from sqlite3 import Connection

# Function to insert an educator
def insert_educator(conn: Connection, name: str) -> int:
    """
    Inserts a new educator into the wu_educators table.
    Args:
        conn (Connection): Database connection object.
        name (str): The name of the educator.
    Returns:
        int: The educator_id of the inserted educator.
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO wu_educators (name) VALUES (?)", (name,))
    conn.commit()

    # Return the last inserted ID (educator_id)
    return cursor.lastrowid


# Function to insert a transcript
def insert_transcript(
    conn: Connection, 
    wu_educator_id: int, 
    institution_name: str, 
    degree: str = None, 
    major: str = None, 
    minor: str = None, 
    awarded_date: str = None, 
    overall_credits_earned: float = None, 
    overall_gpa: float = None, 
    degree_level: str = None, 
    file_name: str = None
) -> int:
    """
    Inserts a new transcript into the transcripts table.
    Args:
        conn (Connection): Database connection object.
        wu_educator_id (int): ID of the educator (foreign key).
        institution_name (str): Name of the institution.
        degree (str, optional): Degree earned (e.g., BS, MS).
        major (str, optional): Major field of study.
        minor (str, optional): Minor field of study.
        awarded_date (str, optional): Awarded date in YYYY-MM-DD format.
        overall_credits_earned (float, optional): Total credits earned.
        overall_gpa (float, optional): Overall GPA.
        degree_level (str, optional): Rank of the degree earned.
        file_name (str, optional): Name of the transcript file.
    Returns:
        int: The transcript_id of the inserted transcript.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO transcripts (wu_educator_id, institution_name, degree, major, minor, awarded_date,
                                    overall_credits_earned, overall_gpa, degree_level, file_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (wu_educator_id, institution_name, degree, major, minor, awarded_date, overall_credits_earned, overall_gpa, degree_level, file_name)
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
        credits_earned (float, optional): Credits earned for the course.
        grade (str, optional): Grade earned for the course.
        should_be_category (str): Category the course belongs to.
        adjusted_credits_earned (float): Credits earned for the course if passed.
    Returns:
        int: The course_id of the inserted course.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO courses (transcript_id, course_name, credits_earned, grade, should_be_category, adjusted_credits_earned)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (transcript_id, course_name, credits_earned, grade, should_be_category, adjusted_credits_earned)
    )
    conn.commit()

    # Return the last inserted ID (course_id)
    return cursor.lastrowid


# Function to insert a categorized_course
def insert_cateogrized_course(
    conn: Connection, 
    course_id: int,
    transcript_id: int, 
    should_be_category: str,
    adjusted_credits_earned: float
):
    """
    Inserts a new categorized course into the wu_categorized_courses table.
    Args:
        conn (Connection): Database connection object.
        course_id (int): The ID of the course (foreign key).
        transcript_id (int): The ID of the transcript (foreign key).
        should_be_category (str): Category the course belongs to.
        adjusted_credits_earned (float): Credits earned for the course if passed.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO wu_categorized_courses (course_id, transcript_id, should_be_category, adjusted_credits_earned)
           VALUES (?, ?, ?, ?)''',
        (course_id, transcript_id, should_be_category, adjusted_credits_earned)
    )
    conn.commit()


# Function to insert a categorized_transcript
def insert_categorized_transcript(
    conn: Connection, 
    transcript_id: int, 
    category_name: str,
    category_credits_earned: float,
):
    """
    Inserts a new categorized transcript into the wu_categorized_transcripts table.
    Args:
        conn (Connection): Database connection object.
        transcript_id (int): The ID of the transcript (foreign key).
        category_name (str): Category the transcript has.
        category_credits_earned (float): Total credits earned for the category.
    """
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO wu_categorized_transcripts (transcript_id, category_name, category_credits_earned)
           VALUES (?, ?, ?)''',
        (transcript_id, category_name, category_credits_earned)
    )
    conn.commit()


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
            wu_educators.name AS educator_name,
            transcripts.degree,
            transcripts.degree_level,
            courses.course_name,
            courses.should_be_category,
            courses.adjusted_credits_earned
        FROM wu_educators
        INNER JOIN transcripts ON transcripts.wu_educator_id = wu_educators.educator_id
        INNER JOIN courses ON courses.transcript_id = transcripts.transcript_id
        WHERE 1=1 
    ''' 

    params = []

    # Filtering by educator name
    if criteria.get("educator_name"):
        query += " AND wu_educators.name = ?"
        params.append(criteria["educator_name"])

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
