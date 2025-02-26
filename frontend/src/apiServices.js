import axios from 'axios';
import { Buffer } from 'buffer';

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
 * Establish WebSocket connection for the file being processed
 * @param {string} fileName - File name to establish WebSocket for
 * @param {Object} wsRef - WebSocket reference
 * @param {Object} currentFileRef - Reference to current file
 * @param {Function} onFlaggedCoursesReady - Callback when flagged courses are ready
 * @param {Function} moveToNextFile - Callback to move to the next file
 * @returns {WebSocket} - The WebSocket connection instance
 */
export const setupWebSocket = (fileName, wsRef, currentFileRef, flaggedCoursesReceived, onFlaggedCoursesReady, moveToNextFile, setProcessedFiles, handleWebSocketError, setIsProcessing) => {
  if (!fileName) return null;

  // Prevent multiple WebSocket connections for the same file
  if (wsRef?.current && wsRef.current.readyState !== WebSocket.CLOSED) {
    console.warn(`WebSocket already active for ${fileName}. Skipping duplicate connection.`);
    return wsRef.current;
  }

  const encodedFileName = Buffer.from(fileName).toString("base64");
  let ws = new WebSocket(`ws://localhost:8000/ws/flagged_courses/${encodedFileName}`);

  // Assign the WebSocket instance to wsRef.current
  wsRef.current = ws;

  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 3; // Limit retries to prevent infinite loops
  const RECONNECT_DELAY = 3000; // Wait 3 seconds before reconnecting
  let keepAliveInterval;

  // Funtion to attempt WebSocket Reconnection on timeout
  const reconnectWebSocket = () => {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error(`Max WebSocket reconnect attempts reached for ${fileName}. Marking file as failed.`);
      markFileAsFailed(fileName);
      moveToNextFile();
      return;
    }
    console.warn(`Reconnecting WebSocket for ${fileName}... Attempt ${++reconnectAttempts}`);
    wsRef.current = setupWebSocket(fileName, wsRef, currentFileRef, flaggedCoursesReceived, onFlaggedCoursesReady, moveToNextFile, setProcessedFiles, handleWebSocketError, setIsProcessing); 
  };

  // Function to mark file as failed if WebSocket issues persist
  const markFileAsFailed = (fileName) => {
    setProcessedFiles(prev => {
      if (!prev.some(file => file.name === fileName)) {
        return [...prev, { name: fileName, result: { status: "error", message: "WebSocket reconnection failed." } }];
      }
      return prev;
    });
  };

  ws.onopen = () => {
    console.log(`WebSocket connected for ${fileName}`);
    reconnectAttempts = 0; // Reset attempts on successful connection

    // Start keepalive ping every 30 seconds
    keepAliveInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
        console.log("Keepalive ping sent.");
      }
    }, 30000);
  };

  ws.onmessage = (event) => {
    console.log("WebSocket message received:", event.data);
    try {
      const data = JSON.parse(event.data);

      if (data.status === "connected") {
        console.log(`WebSocket connection confirmed for ${data.file_name}`);
      } else if (data.status === "ready" && fileName === currentFileRef.current) {
        console.log(`Flagged courses are ready for ${data.file_name}`);
        onFlaggedCoursesReady(data.file_name);

        // Ensure flagged courses are tracked to prevent unnecessary reconnection attempts
        flaggedCoursesReceived = true;
      } else if (data.status === "no_flagged_courses" && fileName === currentFileRef.current) {
        console.log(`No flagged courses for ${data.file_name}, closing WebSocket.`);
        
        // Mark the file as processed successfully
        setProcessedFiles(prev => {
          if (!prev.some(file => file.name === fileName)) {
            return [...prev, { name: fileName, result: { status: "success", message: "No flagged courses found." } }];
          }
          return prev;
        });
        
        cleanupWebSocket(wsRef);
        setIsProcessing(false); // Set isProcessing to false to allow the next file to be processed
        moveToNextFile(); // Move to the next file
      }
    } catch (error) {
      console.error("WebSocket JSON parse error:", error);
    }
  };

  ws.onerror = (error) => {
    console.error(`WebSocket error for ${fileName}:`, error);
    
    // If WebSocket disconnects before flagged courses are received, attempt reconnection
    if (!flaggedCoursesReceived && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      console.log(`Attempting WebSocket reconnection for ${fileName}...`);
      reconnectAttempts++;
      setTimeout(reconnectWebSocket, RECONNECT_DELAY);
    } else {
      console.error(`Max WebSocket reconnect attempts reached for ${fileName}. Marking file as failed.`);

      // Mark the file as failed
      setProcessedFiles(prev => {
          if (!prev.some(file => file.name === fileName)) {
              return [...prev, { name: fileName, result: { status: "error", message: "WebSocket error. File processing failed." } }];
          }
          return prev;
      });

      moveToNextFile();
    }
  };

  ws.onclose = (event) => {
    console.warn(`WebSocket closed for ${fileName}, reason: ${event.reason}`);
    
    clearInterval(keepAliveInterval); // Stop keepalive pings on close

    // If flagged courses are already received, continue handling user decisions
    if (flaggedCoursesReceived) {
      console.log("WebSocket disconnected, but flagged courses already received. Continuing...");
      wsRef.current = null;
      return;
    }

    // If WebSocket disconnects before flagged courses are received, attempt reconnection
    if (!event.wasClean || event.reason === "keepalive ping timeout") {
      console.log(`Attempting WebSocket reconnection for ${fileName}...`);
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        setTimeout(reconnectWebSocket, RECONNECT_DELAY);
      } else {
        // If reconnection fails after retries, mark the file as failed
        console.error(`Max WebSocket reconnect attempts reached for ${fileName}. Marking file as failed.`);
        setProcessedFiles(prev => {
          if (!prev.some(file => file.name === fileName)) {
            return [...prev, { name: fileName, result: { status: "error", message: "WebSocket reconnection failed." } }];
          }
          return prev;
        });
        moveToNextFile();
      }
    } else {
      wsRef.current = null;
    }
  };

  return ws;
};


// Function to cleanup WebSocket
const cleanupWebSocket = (wsRef) => {
  if (wsRef.current) {
    wsRef.current.onclose = null;
    wsRef.current.close();
    wsRef.current = null;
  }
};


/**
 * Upload a single file to the backend
 * @param {File} file - The file to be uploaded
 * @param {Function} onProgress - Callback function for upload progress
 * @returns {Promise<Object>} - The processed file data
 */
export const uploadFile = async (file, onProgress) => {
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

    return response.data?.status === "success" ? response.data : Promise.reject("Unexpected response format.");
  } catch (error) {
    console.error("Error uploading file:", error);
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

    return response.data?.status === "success" && response.data.flagged_courses.length > 0 
      ? response.data : { status: "error", message: "No flagged courses detected." };
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
export const submitFlaggedDecisions = async (fileName, decisions) => {
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
    const response = await axios.post(`${API_URL}/submit_flagged_decisions`, {
      file_name: encodedFileName,
      decisions: processedDecisions
    });

    return response.data;
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
