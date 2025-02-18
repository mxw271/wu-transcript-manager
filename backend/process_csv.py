import os
import json
import sqlite3
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import traceback

from data_pipeline import structure_data, save_to_database
from db_service import check_database_status
from utils import load_json_log, save_json_log, handle_csv_error


# Load environment variables from .env file
DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")  # Ensure correct path
load_dotenv(DOTENV_PATH)
DATABASE_FILE = os.getenv("DATABASE_FILE", "../database/database.db") # Load Database file from .env

CSV_FOLDER = '/Users/maxiw/Downloads/transcripts_in_csv'
LOG_FILE = os.path.join(CSV_FOLDER, "csv_processing_log.json")


# Function to process a CSV file
def process_csv_file(csv_file, log_data):
    """Processes a single CSV file and inserts its data into the database."""
    print(f"📄 Processing file: {csv_file}...")

    # Load CSV into Pandas DataFrame
    try:
        df = pd.read_csv(os.path.join(CSV_FOLDER, csv_file))
    except Exception as e:
        handle_csv_error(csv_file, log_data, "Failed to read CSV", e)
        return

    # Structure the data
    try:
        structured_result = structure_data(df)
        if structured_result["status"] == "error":
            handle_csv_error(csv_file, log_data, "Error during structuring", structured_result.get("message", "Unknown error"))
            return
        structured_df = structured_result["data"]
        warnings = structured_result.get("warnings", None)
    except Exception as e:
        handle_csv_error(csv_file, log_data, "Unexpected error while structuring data", e)
        return

    # Show preview of the structured DataFrame
    print("\n🔍 Preview of CSV file:")
    print(structured_df.iloc[:,:8])
    print(structured_df.iloc[:,8:-5])
    print(structured_df.iloc[:,-5:])  
    print("\nFull DataFrame dimensions:", structured_df.shape)

    # Prompt user for confirmation
    user_input = input(f"\nContinue processing {csv_file}? (Y to proceed, N to skip): ").strip().upper()
    if user_input != "Y":
        print(f"⏭️ Skipped processing {csv_file}.")
        log_data[csv_file] = {"status": "skipped", "message": "User chose to skip processing."}
        save_json_log(LOG_FILE, log_data)
        return

    try:
        # Save the data to the database
        save_result = save_to_database(structured_df, DATABASE_FILE)

        # Include warnings if present
        if warnings:
            save_result["warnings"] = warnings
            print("⚠️ Warnings:", warnings)

        log_data[csv_file] = save_result
        save_json_log(LOG_FILE, log_data)
        print(f"✅ Finished processing {csv_file}.")
    except Exception as e:
        handle_csv_error(csv_file, log_data, "Error saving data to database", e)
        return


# Main function to process all CSV files
def process_all_csv_files():
    """Processes all CSV files in the ./processed_csv directory."""
    check_database_status(DATABASE_FILE)

    log_data = load_json_log(LOG_FILE)
    files = [f for f in os.listdir(CSV_FOLDER) if f.endswith(".csv")]

    if not files:
        print("⚠️ No CSV files found in the directory.")
        return

    for file in files:
        if file in log_data:
            print(f"⏭️ Skipping {file}, already processed.")
        else:
            process_csv_file(file, log_data)


if __name__ == "__main__":
    process_all_csv_files()

