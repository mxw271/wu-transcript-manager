import os
import csv
import json
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from clients_service import get_openai_client, get_sbert_model


# Set a similarity threshold for SBERT
THRESHOLD = 0.7  # Matches below this threshold will be marked as "Uncategorized"

# Set a randomness level for OpenAI
TEMPERATURE = 0.3 # Lower value for more deterministic, precise, and consistent


# Function to get the best match for a course name using OpenAI
def match_courses_using_openai(course_names: list, categories_dict: dict, temperature: float = TEMPERATURE) -> list:
    """
    Uses OpenAI API to call ChatGPT 4o-mini to match course names with predefined categories.
    Args:
        course_names (list): List of course names from the transcript data.
        categories_dict (dict): Dictionary of course categories with names as keys and descriptions as values.
        temperature (float): Randomness level in model's response.
    Returns:
        list: List of matched categories.
    """
    openai_client = get_openai_client()
    retry_attempts = 3
    
    # Convert dictionary to a formatted list for better clarity in the prompt
    categories_prompt = "\n".join([f"- **{name}**: {desc}" for name, desc in categories_dict.items()])

    prompt = f"""
    You are an expert in academic course classification. Your task is to accurately match each course name to the closest category from a predefined list.

    **Instructions:**
    - Each course name must be classified into one of the provided categories.
    - If multiple categories are relevant, choose the **most specific** category.
    - Return the classification as a **valid JSON list** where each course matches the respective category.
    
    **Courses:** {course_names}
    
    **Categories (with Descriptions):**
    {categories_prompt}

    **Output Format:** Return **ONLY** a JSON list of categories, where each index corresponds to the respective course name.
    """

    for attempt in range(retry_attempts):
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use GPT-4 for better accuracy
                messages=[
                    {"role": "system", "content": "You are an expert in categorizing academic courses into predefined categories and returning a structured list."},
                    {"role": "user", "content": prompt}
                ],
                #max_tokens=700,
                temperature=temperature
            )
            
            structured_text = response.choices[0].message.content.strip()
            
            if not structured_text:
                print("OpenAI returned an empty response.")
                return []  
            
            # Remove code block formatting (if present)
            structured_text = structured_text.replace("```json", "").replace("```", "").strip()
            
            # Ensure the response is valid JSON
            category_matches = json.loads(structured_text)  # Parse JSON

            # Validate output format
            if isinstance(category_matches, list) and len(category_matches) == len(course_names):
                return category_matches

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON (Attempt {attempt+1}/{retry_attempts}): {e}")
            print("OpenAI Response:", structured_text)
        except Exception as e:
            print(f"API error (Attempt {attempt+1}/{retry_attempts}): {e}")
            time.sleep(2)

    print("All retry attempts failed. Returning 'Uncategorized' for all courses.")
    return ["Uncategorized"] * len(course_names) # Default to Uncategorized


# Function to get the best match for a course name using SBERT
def match_courses_using_sbert(course_names: list, categories_list: list, threshold: float = THRESHOLD) -> list:
    """
    Uses SBERT to match course names with predefined categories based on cosine similarity.
    Args:
        course_names (list): List of course names from the transcript data.
        categories_list (list): List of predefined course categories.
        threshold (float): Similarity threshold for classification.
    Returns:
        list: List of matched categories.
    """
    try:
        sbert_model = get_sbert_model()
        if not sbert_model:
            print("SBERT model loading failed.")
            return []

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
            category_mapping[unique_categories[idx]] if score >= threshold else "Uncategorized"
            for idx, score in zip(best_match_indices, best_match_scores)
        ]

        return matched_categories

    except ValueError as ve:
        print(f"Value error in SBERT matching: {ve}")
        return []
    except Exception as e:
        print(f"Error in SBERT matching: {e}")
        return []
