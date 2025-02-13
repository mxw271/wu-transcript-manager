##
# Create the database tables using raw SQL with sqlite3
##

import sqlite3


# Table 1: educators
CREATE_TABLE_EDUCATORS = '''
CREATE TABLE IF NOT EXISTS educators (
    educator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    firstName VARCHAR(50) NOT NULL,
    middleName VARCHAR(50) DEFAULT NULL,
    lastName VARCHAR(50) NOT NULL
);
'''

# Table 2: transcripts
CREATE_TABLE_TRANSCRIPTS = '''
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
    educator_id INTEGER NOT NULL,
    institution_name VARCHAR(255) NOT NULL,
    degree VARCHAR(255) DEFAULT NULL,
    major VARCHAR(255) DEFAULT NULL,
    minor VARCHAR(255) DEFAULT NULL,
    awarded_date VARCHAR(10) DEFAULT NULL,
    overall_credits_earned FLOAT DEFAULT NULL,
    overall_gpa FLOAT DEFAULT NULL,
    degree_level VARCHAR(10) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transcripts_educator_id FOREIGN KEY (educator_id) REFERENCES educators (educator_id)
);
'''

# Table 3: courses
CREATE_TABLE_COURSES = '''
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    credits_earned FLOAT DEFAULT NULL,
    grade VARCHAR(8) DEFAULT NULL,
    should_be_category VARCHAR(255) NOT NULL,
    adjusted_credits_earned FLOAT NOT NULL DEFAULT 0,
    CONSTRAINT fk_courses_transcript_id FOREIGN KEY (transcript_id) REFERENCES transcripts (transcript_id)
);
'''


# Index creation statements
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_educators_firstName ON educators (firstName);",
    "CREATE INDEX IF NOT EXISTS idx_educators_lastName ON educators (lastName);",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_educator_id ON transcripts (educator_id);",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_degree_level ON transcripts (degree_level);",
    "CREATE INDEX IF NOT EXISTS idx_courses_transcript_id ON courses (transcript_id);",
    "CREATE INDEX IF NOT EXISTS idx_courses_course_name ON courses (course_name);",
    "CREATE INDEX IF NOT EXISTS idx_courses_category ON courses (should_be_category);",
]

def initialize_database(database_file):
    if not database_file:
        raise ValueError("❌ Database file path is missing!")

    connection = sqlite3.connect(database_file)
    cursor = connection.cursor()
    
    # Ensure foreign keys are enforced
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Execute table creation statements
    cursor.execute(CREATE_TABLE_EDUCATORS)
    cursor.execute(CREATE_TABLE_TRANSCRIPTS)
    cursor.execute(CREATE_TABLE_COURSES)
    
    # Execute index creation statements
    for index_sql in CREATE_INDEXES:
        cursor.execute(index_sql)

    connection.commit()
    connection.close()
