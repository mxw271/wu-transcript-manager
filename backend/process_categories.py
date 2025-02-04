import os
import json
from text_matching import expand_abbreviation_using_openai


# Load course categories from JSON file
def load_course_categories(categories_file = "course_categories.json", openai_client=None):
    
    # Check if the categories file exists
    if not os.path.exists(categories_file):
        print(f"Warning: {categories_file} not found! Using default empty category list.")
        return []
    
    # Load original categories from categories_file
    with open(categories_file, "r") as file:
        data = json.load(file)
    course_categories = data.get("course_categories", [])
    
    '''
    # If no openai_client is provided, return the original categories
    if not openai_client:
        return course_categories

    # If the processed file already exists,load and return processed categories
    if os.path.exists(processed_file):
        with open(processed_file, "r") as file:
            processed_data = json.load(file)
        if "processed_categories" in processed_data:
            return processed_data["processed_categories"]

    # Expand abbreviations using OpenAI
    expanded_categories = [expand_abbreviation_using_openai(category, "course category", openai_client) for category in course_categories]

    # Sort the list in a case-insensitive manner and remove duplicates
    processed_categories = sorted(set(expanded_categories), key=lambda x: x.lower())

    # Save the processed categories in a separate JSON file
    processed_data = {"processed_categories": processed_categories}
    with open(processed_file, "w") as file:
        json.dump(processed_data, file, indent=4)

    return processed_categories
    '''
    return course_categories