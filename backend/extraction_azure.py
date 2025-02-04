##
# Install the required Python libraries:
# pip3 install azure-cognitiveservices-vision-computervision
##

from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
import time


# Extract text from a file
def extract_text_from_file_using_azure(file_path, azure_client):
    """
    Extract text from a PDF file or image using Azure Computer Vision Read API.
    Args:
        file_path (str): Path to the local file (PDF or image).
    Returns:
        str: Extracted text.
    """
    # Open the file to read in binary mode
    with open(file_path, "rb") as file:
        # Call the Read API
        response = azure_client.read_in_stream(file, raw=True)
    
    # Get the operation location (URL with the operation ID)
    operation_location = response.headers["Operation-Location"]

    # Extract operation ID from the URL
    operation_id = operation_location.split("/")[-1]

    # Wait for the Read API to finish processing
    print("Processing...")
    while True:
        result = azure_client.get_read_result(operation_id)
        if result.status not in [OperationStatusCodes.not_started, OperationStatusCodes.running]:
            break
        time.sleep(1)

    # Extract text from the results
    extracted_text = ""
    if result.status == OperationStatusCodes.succeeded:
        for page in result.analyze_result.read_results:
            for line in page.lines:
                extracted_text += line.text + "\n"

    return extracted_text
