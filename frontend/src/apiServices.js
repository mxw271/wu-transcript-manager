import axios from 'axios';
import { Buffer } from 'buffer';

// Set the base URL for API calls. FastAPI runs on port 8000 by default.
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';


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
 * Upload a single file to the backend
 * @param {File} file - The file to be uploaded
 * @param {Function} onProgress - Callback function for upload progress
 * @returns {Promise<Object>} - The processed file data
 */
export const uploadFile = async (file, onProgress) => {
  //if (activeUploads.has(file.name)) {
  //  console.warn(`Upload already in progress for ${file.name}`);
  //  return { status: "error", message: "Upload already in progress." };
  //}

  //activeUploads.add(file.name);
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await axios.post(`${API_URL}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (onProgress) {
          const percentCompleted = Math.round((event.loaded * 100) / event.total);
          onProgress(percentCompleted, file.name);
        }
      },
    });

    //activeUploads.delete(file.name); // Remove from active uploads after success
    if (response.data?.status === "success") {
      return response.data; 
    }
    return { status: "error", message: "Unexpected response format from server." };
  
  } catch (error) {
    console.error("Error uploading file:", error);
    //activeUploads.delete(file.name); // Remove from active uploads on failure
    return { status: "error", message: "File upload failed. Please try again." };
  }
};


/**
 * Fetch flagged courses from the backend
 * @param {string} fileName - The file name to retrieve flagged courses
 * @returns {Promise<Object>} - Flagged courses data
 */
export const getFlaggedCourses = async (fileName) => {
  try {
    const encodedFileName = Buffer.from(fileName).toString("base64"); // Encode spaces
    const response = await axios.get(`${API_URL}/get_flagged_courses`, { params: { file_name: encodedFileName } });

    if (response.data?.status === "success") {
      return { status: "success", flagged_courses: response.data.flagged_courses || [] }; 
    } 
    // If the response was not successful, return an empty flagged_courses list instead of an error
    return { status: "success", flagged_courses: [] };  
  
  } catch (error) {
    console.error("Error fetching flagged courses:", error);
    return { status: "error", message: "Failed to fetch flagged courses." };
  }
};


/**
 * Submit user decisions on flagged courses
 * @param {string} fileName - The file name for which decisions are being submitted
 * @param {Array} decisions - List of user decisions
 * @returns {Promise<Object>} - Response from backend
 */
export const submitUserDecisions = async (fileName, decisions) => {
  try {
    const encodedFileName = Buffer.from(fileName).toString("base64"); // Encode spaces

    const processedDecisions = decisions.map(degree => ({
      ...degree,
      courses: degree.courses.map(course => ({
        ...course,
        credits_earned: course.credits_earned && Number(course.credits_earned),
        is_passed: course.is_passed && course.is_passed === "True"
      }))
    }));

    // Ensure API call uses the trailing slash
    const response = await axios.post(`${API_URL}/submit_user_decisions`, {
      file_name: encodedFileName,
      decisions: processedDecisions
    });

    if (response.data?.status === "success") {
      return { status: "success", message: "Decisions submitted successfully." };
    }
    return { status: "error", message: response.data?.message || "Unexpected response format." };
 
  } catch (error) {
    console.error("Error submitting flagged decisions:", error);
    return { status: "error", message: "Failed to submit flagged course decisions." };
  }
};


/**
 * Search data in the backend
 * @param {Object} criteria - The search criteria
 * @returns {Promise<Array>} - The search results
 */
export const searchData = async (criteria) => {
  try {
    const response = await axios.post(`${API_URL}/search`, {
      educator_first_name: criteria.firstName,
      educator_last_name: criteria.lastName,
      course_category: criteria.courseCategory,
      education_level: criteria.educationLevel,
    });

    return response.data;
  } catch (error) {
    console.error('Error searching data:', error);
    throw error;
  }
};
