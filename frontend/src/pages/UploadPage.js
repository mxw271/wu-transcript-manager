import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Buffer } from 'buffer';
import { fetchCourseCategories, uploadFile, getFlaggedCourses, submitUserDecisions } from '../apiServices';
import FlaggedCourses from '../components/FlaggedCourses';
import BackToHomeButton from '../components/BackToHomeButton';
import '../styles/UploadPage.css';

// Set the base URL for WebSocket connections. It runs on port 8000 by default.
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

const UploadPage = () => {
  const [uploadStatus, setUploadStatus] = useState(''); // Track upload status messages
  const [progress, setProgress] = useState({}); // Track individual file upload progress
  const [processedFiles, setProcessedFiles] = useState([]); // Store processed file names & results
  const [courseCategories, setCourseCategories] = useState([]);
  const [flaggedCourses, setFlaggedCourses] = useState([]);
  const [userDecisions, setUserDecisions] = useState({});
  const [currentFile, setCurrentFile] = useState(null);
  const currentFileRef = useRef(null); // Reference to track the current file immediately
  const [pendingFiles, setPendingFiles] = useState([]); // Queue for files to be processed
  const pendingFilesRef = useRef(pendingFiles);
  const [invalidFiles, setInvalidFiles] = useState([]); // List for invalid files
  const [isProcessing, setIsProcessing] = useState(false);
  const isProcessingRef = useRef(isProcessing);
  const wsRef = useRef(null); // Reference to the WebSocket connection
  const activeWebSockets = useRef(new Map()); // Track active WebSocket connections
  const reconnectAttemptsRef = useRef({}); // Store reconnect attempts 
  const webSocketClosedByBackendRef = useRef(false); // Track backend-initiated closure
  let flaggedCoursesReceived = false; // Global variable to track whether flagged courses were received

  // File upload restrictions
  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB limit per file
  const MAX_FILE_COUNT = 100; // Maximum number of files allowed
  const ALLOWED_TYPES = ['application/pdf', 'image/jpg', 'image/jpeg', 'image/png', 'text/csv']; // Allowed file types

  // Fetch course categories only once and memoize them
  const memoizedCategories = useMemo(async () => {
    try {
      const categories = await fetchCourseCategories();
      return categories || [];
    } catch (error) {
      console.error("Failed to fetch course categories:", error);
      return [];
    }
  }, []); // Runs once on mount

  // Store the fetched categories in state once
  useEffect(() => {
    memoizedCategories.then(setCourseCategories);
  }, [memoizedCategories]);

  // Synchronize currentFileRef with currentFile state
  useEffect(() => {
    currentFileRef.current = currentFile;
  }, [currentFile]);

  // Synchronize pendingFilesRef with pendingFiles state
  useEffect(() => {
    pendingFilesRef.current = pendingFiles;
  }, [pendingFiles]);

  // Synchronize isProcessingRef with isProcessing state
  useEffect(() => {
    isProcessingRef.current = isProcessing; 
  }, [isProcessing]);

 // Process pending files if any exist
  useEffect(() => {
    if (pendingFiles.length > 0 && !isProcessing && !currentFileRef.current) {  // Prevent unintended WebSocket reconnections
      processNextFile(); 
    }
  }, [pendingFiles, isProcessing, currentFile]);

  // Mark the status for a file with given message
  const markFileStatus = (fileName, status, message) => {
    setProcessedFiles(prev => {
      const processedFileNames = new Set(prev.map(file => file.name));
      if (!processedFileNames.has(fileName)) {
        return [...prev, { name: fileName, result: { status, message } }];
      }
      return prev;
    });
  };

  // Move to the next file in the queue
  const moveToNextFile = () => {
    cleanupWebSocket(currentFileRef.current, () => {
      setPendingFiles(prev => {
        const updatedFiles = prev.slice(1); // Remove the first file
        if (updatedFiles.length === 0) {
          setUploadStatus("All files processed."); // All files completed
          setCurrentFile(null);
        } else {
          setCurrentFile(updatedFiles[0].name); // Set the next file as the current file
          setTimeout(() => processNextFile(), 500); // Allow state updates before processing next file
        }
        return updatedFiles;
      });
  
      setIsProcessing(false); // Mark processing as completed
    });
  };

  // Properly close the WebSocket connection and reset the weRef
  const cleanupWebSocket = (fileName, callback) => {
    if (wsRef.current && !webSocketClosedByBackendRef.current) {
      console.log(`Cleaning up WebSocket for ${fileName}`);

      // Only close the WebSocket if it's still open
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.onclose = null; // Prevent duplicate closures
        setTimeout(() => {
          wsRef.current.close();
          console.log(`WebSocket closed for ${fileName}`);
          
          // Reset the WebSocket reference and remove from activeWebSockets
          wsRef.current = null;
          activeWebSockets.current.delete(fileName);
          
          // Reset the flag after the WebSocket is fully closed
           webSocketClosedByBackendRef.current = false;

          if (callback) callback(); // Execute callback after WebSocket is closed
        }, 3000); // Delay closure slightly
      
      } else {
        // If the WebSocket is already closed, reset the flag and execute the callback
        wsRef.current = null;
        activeWebSockets.current.delete(fileName);
        webSocketClosedByBackendRef.current = false;
        if (callback) callback(); // Execute callback immediately if WebSocket is already closed
      }

    } else {
      // If no WebSocket is active, reset the flag and execute the callback
      webSocketClosedByBackendRef.current = false;
      if (callback) callback(); // Execute callback immediately if no WebSocket is active
    }
  };

  // Handles file selection and adds files to the processing queue
  const handleFileUpload = (event) => {
    // Reset states before handling new files
    cleanupWebSocket(currentFileRef.current, () => {
      setProcessedFiles([]);
      setCurrentFile(null);
      setPendingFiles([]);
      setInvalidFiles([]);
      setUploadStatus('');
      setFlaggedCourses([]);
      setUserDecisions({});
      setIsProcessing(false);
      
      setUploadStatus('Uploading...');

      const files = Array.from(event.target.files);
      
      // Enforce max file count
      if (files.length > MAX_FILE_COUNT) {
        setUploadStatus(`Error: You can upload up to ${MAX_FILE_COUNT} files at a time.`);
        return;
      }

      // Separate valid and invalid files
      const validFiles = [];
      const invalidFiles = [];

      files.forEach((file) => {
        if (!ALLOWED_TYPES.includes(file.type) || file.size > MAX_FILE_SIZE) {
          invalidFiles.push({
            name: file.name,
            reason: !ALLOWED_TYPES.includes(file.type) ? 'Unsupported format' : 'File size exceeds 5MB',
          });
        } else {
          validFiles.push(file);
        }
      });

      // Update states for valid and invalid files
      setInvalidFiles(invalidFiles);
      setPendingFiles(prev => [...prev, ...validFiles]);
    });
  };

  // Processes the next file in the queue sequentially
  const processNextFile = async () => {
    if (pendingFilesRef.current.length === 0 || isProcessingRef.current) return;

    setIsProcessing(true); // Mark processing as started
    const nextFile = pendingFilesRef.current[0]; // Get the first file in the queue
    setCurrentFile(nextFile.name);
    setUploadStatus(`Processing ${nextFile.name}...`);

    if (processedFiles.some(file => file.name === nextFile.name)) {
      console.log(`Skipping already processed file: ${nextFile.name}`);
      moveToNextFile();
      return;
    }

    try {
      // Open WebSocket connection for real-time updates only for unprocessed files
      await setupWebSocketConnection(nextFile.name);
    } catch (error) {
      setUploadStatus(`Error setting up WebSocket for ${nextFile.name}.`);
      cleanupWebSocket(nextFile.name, () => {
        markFileStatus(nextFile.name, "error", "WebSocket setup failed.");
        moveToNextFile();
      });
    }
  };

  // Sets up the WebSocket connection for a given file
  const setupWebSocketConnection = async (fileName) => {
    if (!fileName) return;

    // Ensure file is unprocessed before setting up a WebSocket connection
    if (isProcessingRef.current || processedFiles.some(file => file.name === fileName)) return;
    console.log(activeWebSockets.current);
    // Prevent multiple active WebSockets for the same file
    if (activeWebSockets.current.has(fileName)) {
      console.warn(`WebSocket already active for ${fileName}. Skipping duplicate connection.`);
      return;
    }

    reconnectAttemptsRef.current[fileName] = 0; // Reset reconnect attempts when starting a new file
    flaggedCoursesReceived = false; // Reset tracking when starting a new WebSocket
    
    console.log(`Opening WebSocket for ${fileName}`);
    const ws = setupWebSocket(fileName);
    if (ws) activeWebSockets.current.set(fileName, ws);
    console.log(activeWebSockets.current);
  };

  // Sets up the WebSocket connection for the file being processed
  const setupWebSocket = (fileName) => {
    console.log(`Setting up WebSocket for ${fileName}`);
    if (!fileName) return null;
  
    // Prevent reuse of closed WebSocket connections
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      console.warn(`WebSocket already exists for ${fileName}. Skipping duplicate connection.`);
      return wsRef.current;
    }
  
    const encodedFileName = Buffer.from(fileName).toString("base64");
    let ws = new WebSocket(`${WS_URL}/ws/flagged_courses/${encodedFileName}`);
    wsRef.current = ws; // Assign the WebSocket instance to wsRef.current

    const MAX_RECONNECT_ATTEMPTS = 3; // Limit retries to prevent infinite loops
    const RECONNECT_DELAY = 3000; // Wait 3 seconds before reconnecting
    let keepAliveInterval;
  
    // Funtion to attempt WebSocket Reconnection on timeout
    const reconnectWebSocket = () => {
      if (reconnectAttemptsRef.current[fileName] >= MAX_RECONNECT_ATTEMPTS) {
        console.error(`Max WebSocket reconnect attempts reached for ${fileName}. Marking file as failed.`);
        cleanupWebSocket(fileName, () => {
          markFileStatus(fileName, "error", "WebSocket reconnection failed.");
          moveToNextFile();
        });
        return;
      }

      console.log(`Reconnecting WebSocket for ${fileName}... Attempt ${reconnectAttemptsRef.current[fileName] + 1}`);
      reconnectAttemptsRef.current[fileName]++;

      // Ensure the WebSocket is fully closed before reconnecting
      cleanupWebSocket(fileName, () => {
        setTimeout(() => setupWebSocket(fileName), RECONNECT_DELAY); // Reconnect after delay
      });
    };
  
    ws.onopen = () => {
      // Start keepalive ping every 30 seconds
      keepAliveInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
          console.log("Keepalive ping sent.");
        }
      }, 30000);
    };
  
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
  
        if (data.status === "connected") {
          console.log(`WebSocket connection confirmed for ${data.file_name}`);
          // Start processing the file only after the WebSocket connection is confirmed
          processAfterWebSocketConfirmed(fileName);

        } else if (data.status === "ready" && fileName === currentFileRef.current) {
          console.log(`Flagged courses are ready for ${data.file_name}`);
          fetchFlaggedCourses(data.file_name);
          flaggedCoursesReceived = true; // Track flagged courses to prevent unnecessary reconnection attempts
        
        } else if (data.status === "intentional_closure") {
          console.log(`Backend intentionally closed WebSocket for ${fileName}. No further reconnection needed.`);
          webSocketClosedByBackendRef.current = true; 

          // Use cleanupWebSocket() to close the WebSocket and clean up
          cleanupWebSocket(fileName, () => {
            console.log(`WebSocket closed and cleaned up for ${fileName}`);
          });
  
        } else if (data.status === "no_flagged_courses" && fileName === currentFileRef.current) {
          console.log(`No flagged courses for ${data.file_name}. Backend closed WebSocket and no further reconnection needed.`);
          webSocketClosedByBackendRef.current = true; 

          // Use cleanupWebSocket() to close the WebSocket and clean up
          cleanupWebSocket(fileName, () => {
            markFileStatus(fileName, "success", "No flagged courses found. File processing completed.");
            moveToNextFile();
          }); 
        }
      } catch (error) {
        console.error("WebSocket JSON parse error:", error);
      }
    };
  
    ws.onerror = (error) => {
      console.error(`WebSocket error for ${fileName}:`, error);
      
      // If the backend intentionally closed the WebSocket, do not reconnection
      if (webSocketClosedByBackendRef.current) {
        console.log(`WebSocket error occured after intentional closure for ${fileName}. No need to reconnect.`);
        wsRef.current = null;
        activeWebSockets.current.delete(fileName);
        return;
      }
  
      // If flagged courses were already received, continue handling user decisions
      if (flaggedCoursesReceived) {
        console.log("WebSocket error, but flagged courses already received. Ignoring error.");
        wsRef.current = null;
        activeWebSockets.current.delete(fileName);
        return;
      }
  
      // If WebSocket disconnects before flagged courses are received, attempt reconnection
      reconnectWebSocket();
    };
  
    ws.onclose = (event) => {
      console.warn(`WebSocket closed for ${fileName}, reason: ${event.reason}`);
      
      clearInterval(keepAliveInterval); // Stop keepalive pings on close
  
      // If the backend intentionally closed the WebSocket, do not reconnection
      if (webSocketClosedByBackendRef.current) {
        console.log(`WebSocket closed intentionally by backend for ${fileName}. No need to reconnect.`);
        wsRef.current = null;
        activeWebSockets.current.delete(fileName);
        return;
      }
  
      // If flagged courses are already received, continue handling user decisions
      if (flaggedCoursesReceived) {
        console.log("WebSocket disconnected, but flagged courses already received. Continuing...");
        wsRef.current = null;
        activeWebSockets.current.delete(fileName);
        return;
      }

      // If WebSocket disconnects before flagged courses are received, attempt reconnection
      reconnectWebSocket();
    };
  
    return ws;
  };

  // Process the file after the WebSocket connection is established
  const processAfterWebSocketConfirmed = async (fileName) => {
    if (fileName !== currentFileRef.current) return;

    const nextFile = pendingFilesRef.current[0]; // Get the first file in the queue
    setUploadStatus(`Processing ${nextFile.name}...`);
    
    try {
      // Upload the file to the backend
      console.log(`Sending ${nextFile.name} to the backend...`);
      await uploadFile(nextFile, percent => setProgress(prev => ({ ...prev, [nextFile.name]: percent })));
    } catch (error) {
      const errorMessage = `Error processing ${nextFile.name}.`;
      setUploadStatus(`Error processing ${nextFile.name}.`);
      cleanupWebSocket(nextFile.name, () => {
        markFileStatus(nextFile.name, "error", errorMessage || "File processing failed.");
        moveToNextFile();
      });
    }
  };

  // Fetches flagged courses for the current file once they are ready
  const fetchFlaggedCourses = async (fileName, retryCount = 0) => {
    if (fileName !== currentFileRef.current || flaggedCoursesReceived) return;  // Only fetch for the current file
    setFlaggedCourses([]);
    setUserDecisions({});
    
    try {
      const response = await getFlaggedCourses(fileName);

      if (response.status === "success" && response.flagged_courses.length > 0) {
        setFlaggedCourses(response.flagged_courses);
        flaggedCoursesReceived = true;
        
        if (currentFileRef.current !== fileName) return; // Prevent reprocessing old file decisions

        // Initialize user decisions
        const initialDecisions = {};
        response.flagged_courses.forEach(degree => {
          degree.courses.forEach(course => {
            const decisionKey = `${degree.file_name}--${degree.degree}--${degree.major}--${course.course_name}`;
            initialDecisions[decisionKey] = {};
            if (course.should_be_category) { initialDecisions[decisionKey]["should_be_category"] = course.should_be_category };
            if (course.credits_earned) { initialDecisions[decisionKey]["credits_earned"] = String(course.credits_earned) };
            if (course.is_passed) { initialDecisions[decisionKey]["is_passed"] = course.is_passed };
          });
        });
        setUserDecisions(initialDecisions);
        setUploadStatus(`Please review flagged courses for ${fileName}.`);

      } else {
        console.log(`No flagged courses received for ${fileName}. Retrying (${retryCount + 1}/3)...`);

        if (retryCount < 3) {
          setTimeout(() => fetchFlaggedCourses(fileName, retryCount + 1), 1000);
        } else {
          console.error(`No flagged courses detected for ${fileName}. Marking file as failed.`);
          setUploadStatus(`No flagged courses detected for ${fileName}.`);
          cleanupWebSocket(fileName, () => {
            markFileStatus(fileName, "error", "No flagged courses received.");
            moveToNextFile();
          });
        }
      }

      retryCount++;
    } catch (error) {
      console.error("Error fetching flagged courses:", error);
      setUploadStatus(`Error: Unable to fetch flagged courses for ${fileName}`);
      cleanupWebSocket(fileName, () => {
        markFileStatus(fileName, "error", "Failed to fetch flagged courses.");
        moveToNextFile();
      });
    }
  };

  // Handle user decision input changes
  const handleDecisionChange = (fileName, degree, major, courseName, courseIndex, field, value) => {
    setUploadStatus('Waiting for user decisions...');
    setUserDecisions(prev => ({
      ...prev,
      [`${fileName}--${degree}--${major}--${courseName}--${courseIndex}`]: {
        ...prev[`${fileName}--${degree}--${major}--${courseName}--${courseIndex}`],
        [field]: field === "credits_earned" ? (value === "" ? "" : value) : value
      }
    }));
  };

  // Submits user clicks on the upload box or the "Back to Home" button
  const handleSubmitDecisions = async () => {
    setUploadStatus('Submitting user decisions and processing it...');

    if (!currentFileRef.current) {
      alert("Error: No file selected.");
      return;
    }

    const structuredDecisions = Object.keys(userDecisions).reduce((acc, key) => {
      const [fileName, degree, major, courseName] = key.split("--");

      if (fileName === currentFileRef.current) {
        const updatedCourse = {
          course_name: courseName,
          should_be_category: userDecisions[key].should_be_category,
          credits_earned: userDecisions[key].credits_earned,
          is_passed: userDecisions[key].is_passed
        };

        let degreeEntry = acc.find(entry => entry.degree === degree);
        if (!degreeEntry) {
          degreeEntry = { file_name: fileName, degree, major, courses: [] };
          acc.push(degreeEntry);
        }
        degreeEntry.courses.push(updatedCourse);
      }
      return acc;
    }, []);

    try {
      const response = await submitUserDecisions(currentFileRef.current, structuredDecisions);

      if (response.status === "success") {
        alert(response.message || "Decisions submitted successfully!");
        cleanupWebSocket(currentFileRef.current, () => {
          markFileStatus(currentFileRef.current, "success", `${response.message} File processing completed.`);
          moveToNextFile();
        });

      } else {
        alert(response.message || "Error submitting decisions. Please try again.");
        cleanupWebSocket(currentFileRef.current, () => {
          markFileStatus(currentFileRef.current, "error", "Failed to submit decisions.");
          moveToNextFile();
        });
      }

    } catch (error) {
      const errorMessage = `Error submitting decisions: ${error.message}`;
      alert(errorMessage);
      cleanupWebSocket(currentFileRef.current, () => {
        markFileStatus(currentFileRef.current, "error", "Error submitting decisions.");
        moveToNextFile();
      });
    }
  };
  
  return (
    <div className="container">
      <h1>Upload Transcripts</h1>
      <p>Allowed formats: <strong>PDF, JPG, JPEG, PNG, CSV</strong></p>
      <p>Maximum size: <strong>5MB</strong></p>
      <p>Max files: <strong>100</strong></p>
      
      {/* Upload box */}
      <input
        type="file"
        accept=".pdf, .jpg, .jpeg, .png, .csv"
        multiple
        onChange={handleFileUpload}
        disabled={isProcessing}
      />
      
      {/* Display upload status for any valid files */}
      {uploadStatus && (
        <div className="status">
          <p className={uploadStatus.startsWith('Error') ? 'error-text' : ''}>{uploadStatus}</p>
        </div>
      )}


      {/* Display files that are processing */}
      {pendingFiles.length > 0 && (
        <div>
          <p>Pending Files</p>
          <ul>
            {pendingFiles.map((file, index) => (
              <li key={index}>
                {file.name} ({(file.size / 1024).toFixed(2)} KB)

                {/* Progress Bar */}
                <div className="progress-bar-container">
                  <div
                    className="progress-bar"
                    style={{ width: `${progress[file.name] || 0}%` }}
                  >
                    {Math.round(progress[file.name] || 0)}%
                  </div>
                </div>

                {/* Flagged Courses for User Decision */}
                {flaggedCourses
                  .filter(degree => degree.file_name === file.name) // Only show flagged courses for this file
                  .length > 0 && (
                  <FlaggedCourses
                    flaggedCourses={flaggedCourses.filter(degree => degree.file_name === file.name)}
                    userDecisions={userDecisions}
                    handleDecisionChange={handleDecisionChange}
                    handleSubmitDecisions={handleSubmitDecisions}
                    courseCategories={courseCategories}
                  />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Display files that have been processed */}
      {processedFiles.length > 0 && (
        <div>
          <p>Processed Files</p>
          <ul>
            {processedFiles.map((file, index) => (
              <li key={index}>
                {file.name}
                {file.result.message && file.result.status === "success" && (
                  <p className="success-text">{file.result.message}</p>
                )}
                {file.result.message && file.result.status === "error" && (
                  <p className="error-text">{file.result.message}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Display errors for any invalid files */}
      {invalidFiles.length > 0 && (
        <div className="error-text">
          <p>Invalid Files:</p>
          <ul>
            {invalidFiles.map((file, index) => (
              <li key={index}>{file.name} - {file.reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Return back to home page button */}
      <BackToHomeButton disabled={isProcessing}/>      
    </div>
  );
}

export default UploadPage;
