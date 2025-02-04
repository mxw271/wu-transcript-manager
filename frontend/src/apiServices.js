import axios from 'axios';

// Set the base URL for API calls. FastAPI runs on port 8000 by default.
const API_URL = process.env.REACT_API_URL || 'http://localhost:8000';


export const fetchCourseCategories = async () => {
  try {
    const response = await axios.get(`${API_URL}/course-categories`);
    return response.data.course_categories;
  } catch (error) {
    console.error("Error fetching course categories:", error);
    return [];
  }
};


/**
 * Upload a file to the backend
 * @param {File} file - The file to be uploaded
 * @returns {Promise<Object>} - The processed file data
 */
export const uploadFile = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('files', file);

  try {
    return axios.post(`${API_URL}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (onProgress) {
          const percentCompleted = Math.round((event.loaded * 100) / event.total);
          onProgress(percentCompleted);
        }
      },
    });
  } catch (error) {
    console.error('Error uploading file:', error);
    throw error;
  }
};

/**
 * Search data in the backend
 * @param {Object} criteria - The search criteria
 * @returns {Promise<Array>} - The search results
 */
export const searchData = async (criteria) => {
  try {
    console.log(criteria);
    const response = await axios.post(`${API_URL}/search`, {
      educator_name: criteria.name,
      course_category: criteria.courseCategory,
      education_level: criteria.educationLevel,
    });
    return response.data;
  } catch (error) {
    console.error('Error searching data:', error);
    throw error;
  }
};

/**
 * Download data as a CSV file
 * @param {Object} criteria - The search criteria
 * @returns {Promise<void>} - Triggers a file download
 */
export const downloadData = async (criteria) => {
  try {
    const response = await axios.post(`${API_URL}/download`, criteria, { 
      responseType: 'blob',
      headers: { 
        Accept: 'text/csv', 
        'Content-Type': 'application/json'
      },
    });

    // Extract filename from Content-Disposition header
    const contentDisposition = response.headers['content-disposition'];
    let fileName = "Queried_Transcript.csv"; // Default filename

    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*=UTF-8''(.+)/);
      if (match) {
        fileName = decodeURIComponent(match[1]); 
      } else {
        const fallbackMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        if (fallbackMatch) {
          fileName = fallbackMatch[1];
        }
      }
    }

    // Create a blob and generate a URL
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));

    // Create and trigger a download link
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();

    // Clean up by removing the link
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url); // Free up memory
  } catch (error) {
    console.error('Error downloading data:', error);
    throw error;
  }
};

/**
 * Handle API errors gracefully by logging and displaying an alert to the user.
 * @param {Object} error - Axios error object.
 * @param {string} action - Description of the action that failed.
 */
export const handleApiError = (error, action) => {
  console.error(`Error with ${action}:`, error);
  const message = error.response?.data?.message || 'An unexpected error occurred.';
  alert(`Failed ${action}: ${message}`);
};