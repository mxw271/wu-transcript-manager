
import pypdfium2 as pdfium
from PIL import Image
import cv2
import pytesseract
import os
import csv
import time
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes


# Convert PDF pages to images
def pdf_to_images(pdf_path, image_output_dir):
    """
    Converts PDF pages to images and saves them with a name combining the PDF name and page number.
    Args:
        pdf_path (str): Path to the PDF file.
        image_output_dir (str): Directory to save the images.
    """
    try: 
        # Load the PDF file
        pdf = pdfium.PdfDocument(pdf_path)

        # Extract the base name of the PDF (without path or extension)
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

        # Ensure output directory exists
        os.makedirs(image_output_dir, exist_ok=True)  

        # Iterate over each page
        for i in range(len(pdf)):
            # Get page
            page = pdf[i]

            # Render the page to an image
            pdf_bitmap = page.render(scale=4.0)  # Adjust scale for higher resolution

            # Convert PdfBitmap to a Pillow Image
            pil_image = Image.frombytes("RGB", (pdf_bitmap.width, pdf_bitmap.height), pdf_bitmap.buffer)

            # Save the image with a name combining PDF name and page number
            image_path = os.path.join(image_output_dir, f"{pdf_name}_page_{i + 1}.jpg")
            pil_image.save(image_path)
            print(f"Saved: {image_path}")

    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {str(e)}")


# Extract text from a file using opencv
def extract_text_from_file_using_opencv(file_path, image_output_dir):
    """
    Extract text from a PDF file or image using OpenCV and Tesseract.
    Args:
        file_path (str): Path to the local file (PDF or image).
        image_output_dir (str): Path to the image output directory.
    Returns:
        str: Extracted text.
    """
    try:
        # Determine the file type
        file_extension = os.path.splitext(file_path)[-1].lower()

        if file_extension == ".pdf":
            # Convert PDF to images
            pdf_to_images(file_path, image_output_dir)

            # Extract the base name of the PDF (without path or extension)
            pdf_name = os.path.splitext(os.path.basename(file_path))[0]

            # Find all images associated with the PDF file
            images = [f for f in os.listdir(image_output_dir) if f.startswith(pdf_name) and f.endswith(".jpg")]

        elif file_extension in [".jpg", ".jpeg", ".png"]:
            # If the file is already an image, use it directly
            images = [file_path]

        else:
            print(f"Unsupported file format: {file_extension}")
            images = []

        extracted_text = []
        for image_name in sorted(images):  # Sort to process in page order
            image_path = os.path.join(image_output_dir, image_name) if file_extension == ".pdf" else image_name

            # Read the image using OpenCV
            image = cv2.imread(image_path)
            if image is None:
                print(f"Skipping unreadable image: {image_path}")
                continue

            # Convert the image to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Preprocess the image (optional: denoising, thresholding)
            gray = cv2.medianBlur(gray, 3)
            _, binary_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Perform OCR using Tesseract
            extracted_text.append(pytesseract.image_to_string(binary_image))
        extracted_text = "\n".join(extracted_text)

        # Delete images after processing
        if file_extension == ".pdf":
            print("Deleting images...")
            for image_name in images:
                os.remove(os.path.join(image_output_dir, image_name))
            
        return extracted_text.strip()

    except Exception as e:
        print(f"Error extracting text from file: {str(e)}")
        return ""


# Extract text from a file using azure
def extract_text_from_file_using_azure(file_path, azure_client):
    """
    Extract text from a PDF file or image using Azure Computer Vision Read API.
    Args:
        file_path (str): Path to the local file (PDF or image).
        azure_client: Azure Computer Vision client instance.
    Returns:
        str: Extracted text.
    """
    try:
        # Open the file to read in binary mode
        with open(file_path, "rb") as file:
            # Call the Read API
            response = azure_client.read_in_stream(file, raw=True)
        
        # Validate response
        if "Operation-Location" not in response.headers:
            print(f"Azure API response missing 'Operation-Location' for {file_path}.")
            return ""

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
            extracted_text = "\n".join(line.text for page in result.analyze_result.read_results for line in page.lines)
            return extracted_text.strip() if extracted_text else None

        print(f"Azure OCR processing failed for {file_path}. Status: {result.status}")
        return ""

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return ""
    except Exception as e:
        print(f"Error in extract_text_from_file_using_azure(): {e}")
        return ""
