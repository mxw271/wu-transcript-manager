import os
import csv
import json
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from models_service import get_openai_client, get_sbert_model

# Set a similarity threshold for SBERT
THRESHOLD = 0.7  # Matches below this threshold will be marked as "Uncategorized"


# Function to expand abbreviation in a course name
def expand_abbreviation_using_openai(text: str, text_type: str, openai_client) -> str:
    """
    Expands abbreviations in a given text using OpenAI's ChatGPT API.
    Args:
        text (str): Text with possible abbreviations.   
    Returns:v
        str: Expanded text.
    """
    prompt = f"Expand all abbreviations in the following '{text_type}': '{text}'. Keep it concise."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Use GPT-4 for better understanding
            messages=[
                {"role": "system", "content": f"Expand abbreviations in academic {text_type}."},
                {"role": "user", "content": f"Expand: {text}"}
            ],
            max_tokens=50
        )
        expanded_text = response.choices[0].message.content.strip()
        return expanded_text

    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        return text  # Return original text in case of failure


# Function to get the best match for a course name
def match_courses_using_sbert(
    course_names: list, 
    categories_list: list, 
    threshold: float = THRESHOLD
) -> list:
    """
    Uses SBERT to match course names with predefined categories based on cosine similarity after expanding abbreviations.
    Args:
        course_names (list): List of course names from the transcript data.
        categories_list (list): List of predefined course categories.
        threshold (float): Similarity threshold for classification.
    Returns:
        list: List of matched categories.
    """
    sbert_model = get_sbert_model()

    # Create a mapping dictionary to restore the original formatting of category names
    category_mapping = {category.lower(): category for category in categories_list}

    # Extract unique categories in lowercase
    unique_categories = sorted(category_mapping.keys())

    # Generate SBERT embeddings
    print("Generating SBERT embeddings for matching...")
    course_name_embeddings = sbert_model.encode(course_names, convert_to_numpy=True)
    category_embeddings = sbert_model.encode(unique_categories, convert_to_numpy=True)

    # Compute cosine similarity
    similarity_matrix = cosine_similarity(course_name_embeddings, category_embeddings)

    # Find the best match for each course name
    best_match_indices = np.argmax(similarity_matrix, axis=1)
    best_match_scores = np.max(similarity_matrix, axis=1)

    # Assign matched categories based on threshold
    matched_categories = [
        category_mapping[unique_categories[idx]] if score >= THRESHOLD else "Uncategorized"
        for idx, score in zip(best_match_indices, best_match_scores)
    ]

    return matched_categories
