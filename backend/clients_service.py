import os
from dotenv import load_dotenv
from functools import lru_cache
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials


# Load environment variables from .env file
DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")  # Ensure correct path
load_dotenv(DOTENV_PATH)


# Lazy-load OpenAI client
@lru_cache()
def get_openai_client():
    """
    Lazily initializes and caches the OpenAI API client.
    """
    # Load API key from .env
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Check your .env file.")

    return OpenAI(api_key=OPENAI_API_KEY)


# Lazy-load SBERT model
@lru_cache()
def get_sbert_model():
    """
    Lazily initializes and caches the SBERT model.
    """
    return SentenceTransformer("all-MiniLM-L6-v2")


# Lazy-load Azure client
@lru_cache()
def get_azure_client():
    """
    Lazily initializes and caches the Azure Computer Vision API client.
    """
    # Load API key and endpoint from .env
    AZURE_CV_API_KEY = os.getenv("AZURE_CV_API_KEY")  
    AZURE_CV_ENDPOINT = os.getenv("AZURE_CV_ENDPOINT")
    if not AZURE_CV_API_KEY  or not AZURE_CV_ENDPOINT:
        raise ValueError("AZURE_CV_API_KEY or AZURE_CV_ENDPOINT is not set. Check your .env file.")

    return ComputerVisionClient(AZURE_CV_ENDPOINT, CognitiveServicesCredentials(AZURE_CV_API_KEY))

