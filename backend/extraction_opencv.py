##
# Install the required Python libraries:
# pip3 install pypdfium2 opencv-python pytesseract
##

import pypdfium2 as pdfium
from PIL import Image
import cv2
import pytesseract
import os
import csv


# Convert PDF pages to images
def pdf_to_images(pdf_path, image_output_dir):
    """
    Converts PDF pages to images and saves them with a name combining the PDF name and page number.
    Args:
        pdf_path (str): Path to the PDF file.
        image_output_dir (str): Directory to save the images.
    """
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

        # PdfBitmap format defaults to RGB
        mode = "RGB"

        # Convert PdfBitmap to a Pillow Image
        pil_image = Image.frombytes(mode, (pdf_bitmap.width, pdf_bitmap.height), pdf_bitmap.buffer)

        # Save the image with a name combining PDF name and page number
        image_path = os.path.join(image_output_dir, f"{pdf_name}_page_{i + 1}.jpg")
        pil_image.save(image_path)
        print(f"Saved: {image_path}")


# Extract text from images generated from a PDF
def extract_text_from_pdf_using_opencv(pdf_path, image_output_dir):
    """
    Extract text from images generated from a PDF using OpenCV and Tesseract.
    Args:
        pdf_path (str): Path to the local PDF file.
        image_output_dir (str): Path to the image output directory.
    Returns:
        str: Extracted text.
    """

    # Convert PDF to images
    pdf_to_images(pdf_path, image_output_dir)

    # Extract the base name of the PDF (without path or extension)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    # Find all images associated with the PDF file
    images = [f for f in os.listdir(image_output_dir) if f.startswith(pdf_name) and f.endswith(".jpg")]

    extracted_text = ""

    for image_name in sorted(images):  # Sort to process in page order
        image_path = os.path.join(image_output_dir, image_name)

        # Read the image using OpenCV
        image = cv2.imread(image_path)

        # Convert the image to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Preprocess the image (optional: denoising, thresholding)
        gray = cv2.medianBlur(gray, 3)
        _, binary_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Perform OCR using Tesseract
        text = pytesseract.image_to_string(binary_image)
        extracted_text += text + "\n"

    # Delete images after processing
    print("Deleting images...")
    for image_name in images:
        image_path = os.path.join(image_output_dir, image_name)
        os.remove(image_path)
       
    return extracted_text
