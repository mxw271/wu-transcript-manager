##
# Create the database tables using raw SQL with sqlite3
##

import sqlite3


# Table 1: wu_educators
CREATE_TABLE_EDUCATORS = '''
CREATE TABLE IF NOT EXISTS wu_educators (
    educator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL
);
'''

# Table 2: transcripts
CREATE_TABLE_TRANSCRIPTS = '''
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
    wu_educator_id INTEGER NOT NULL,
    institution_name VARCHAR(255) NOT NULL,
    degree VARCHAR(255) DEFAULT NULL,
    major VARCHAR(255) DEFAULT NULL,
    minor VARCHAR(255) DEFAULT NULL,
    awarded_date DATE DEFAULT NULL,
    overall_credits_earned FLOAT DEFAULT NULL,
    overall_gpa FLOAT DEFAULY NULL,
    degree_level VARCHAR(255) DEFAULT NULL,
    file_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transcripts_educator_id FOREIGN KEY (wu_educator_id) REFERENCES wu_educators (educator_id)
    --INDEX idx_transcripts_educator_id (educator_id)
);
'''

# Table 3: courses
CREATE_TABLE_COURSES = '''
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    credits_earned FLOAT DEFAULT NULL,
    grade VARCHAR(5) DEFAULT NULL,
    should_be_category VARCHAR(255) NOT NULL,
    adjusted_credits_earned FLOAT NOT NULL DEFAULT 0,
    CONSTRAINT fk_courses_transcript_id FOREIGN KEY (transcript_id) REFERENCES transcripts (transcript_id)
    --INDEX idx_courses_transcript_id (transcript_id),
    --INDEX idx_courses_course_name (course_name),
);
'''

# Table 4: wu_categorized_courses
CREATE_TABLE_CATEGORIZED_COURSES = '''
CREATE TABLE IF NOT EXISTS wu_categorized_courses (
    course_id INTEGER NOT NULL,
    transcript_id INTEGER NOT NULL,
    should_be_category VARCHAR(255) NOT NULL,
    adjusted_credits_earned FLOAT NOT NULL DEFAULT 0,
    PRIMARY KEY (course_id, transcript_id),
    CONSTRAINT fk_categorized_courses_course_id FOREIGN KEY (course_id) REFERENCES courses (course_id),
    CONSTRAINT fk_categorized_courses_transcript_id FOREIGN KEY (transcript_id) REFERENCES transcripts (transcript_id)
    --INDEX idx_categorized_courses_should_be_category (should_be_category)
);
'''

# Table 5: wu_categorized_transcripts
CREATE_TABLE_CATEGORIZED_TRANSCRIPTS = '''
CREATE TABLE IF NOT EXISTS wu_categorized_transcripts (
    transcript_id INTEGER NOT NULL,
    category_name VARCHAR(255) NOT NULL,
    category_credits_earned FLOAT NOT NULL DEFAULT 0,
    PRIMARY KEY (transcript_id, category_name),
    CONSTRAINT fk_categorized_transcript_id FOREIGN KEY (transcript_id) REFERENCES transcripts (transcript_id),
    CONSTRAINT fk_categorized_category_name FOREIGN KEY (category_name) REFERENCES wu_categorized_courses (should_be)
    --INDEX idx_categorized_transcripts_transcript_id (transcript_id),
    --INDEX idx_categorized_transcripts_category_name (category_name)
);
'''

# Index creation statements
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_transcripts_educator_id ON transcripts (wu_educator_id);",
    "CREATE INDEX IF NOT EXISTS idx_courses_transcript_id ON courses (transcript_id);",
    "CREATE INDEX IF NOT EXISTS idx_courses_course_name ON courses (course_name);",
    #"CREATE INDEX IF NOT EXISTS idx_categorized_courses_should_be_category ON wu_categorized_courses (should_be_category);",
    #"CREATE INDEX IF NOT EXISTS idx_categorized_transcripts_transcript_id ON wu_categorized_transcripts(transcript_id);",
    #"CREATE INDEX IF NOT EXISTS idx_categorized_transcripts_category_name ON wu_categorized_transcripts (category_name);"
]

def create_tables(database_file):
    connection = sqlite3.connect(database_file)
    cursor = connection.cursor()
    
    # Execute table creation statements
    cursor.execute(CREATE_TABLE_EDUCATORS)
    cursor.execute(CREATE_TABLE_TRANSCRIPTS)
    cursor.execute(CREATE_TABLE_COURSES)
    #cursor.execute(CREATE_TABLE_CATEGORIZED_COURSES)
    #cursor.execute(CREATE_TABLE_CATEGORIZED_TRANSCRIPTS)
    
    # Execute index creation statements
    for index_sql in CREATE_INDEXES:
        cursor.execute(index_sql)

    connection.commit()
    connection.close()
    #print("Tables and indexes created successfully!")

