import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { fetchCourseCategories, uploadFile, getFlaggedCourses, submitFlaggedDecisions, setupWebSocket } from '../apiServices';
import FlaggedCourses from '../components/FlaggedCourses';
import BackToHomeButton from '../components/BackToHomeButton';
import '../styles/UploadPage.css';

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
  const [invalidFiles, setInvalidFiles] = useState([]); // List for invalid files
  const wsRef = useRef(null); // Reference to the WebSocket connection
  const [isProcessing, setIsProcessing] = useState(false);
  let flaggedCoursesReceived = false; // Global variable to track whether flagged courses were received
  const activeWebSockets = new Map(); // Track active WebSocket connections

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

  // Process pending files if any exist
  useEffect(() => {
    if (pendingFiles.length > 0 && !currentFileRef.current) {  // Prevent unintended WebSocket reconnections
      setUploadStatus('Starting file processing...');
      processNextFile();
    }
  }, [pendingFiles]);

  // Synchronize currentFileRef with currentFile state
  useEffect(() => {
    currentFileRef.current = currentFile;
  }, [currentFile]);

  // Function to properly close the WebSocket connection and reset the weRef
  const cleanupWebSocket = () => {
    if (wsRef.current) {
      console.log(`Cleaning up WebSocket for ${wsRef.current.fileName}`);
      try {
        wsRef.current.onclose = null; // Remove the onclose handler to prevent reconnection
        wsRef.current.close(); // Close the WebSocket connection
      } catch (error) {
        console.warn("Error while closing WebSocket:", error);
      }
      wsRef.current = null; // Reset the WebSocket reference
    }
  };

  // Handles file selection and adds files to the processing queue
  const handleFileUpload = (event) => {
    setProcessedFiles([]);
    setCurrentFile(null);
    setPendingFiles([]);
    setInvalidFiles([]);
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
  };

  // Processes the next file in the queue sequentially
  const processNextFile = async () => {
    if (pendingFiles.length === 0 || isProcessing) return;

    setIsProcessing(true); // Mark processing as started
    const nextFile = pendingFiles[0]; // Get the first file in the queue
    setCurrentFile(nextFile.name);
    setUploadStatus(`Processing ${nextFile.name}...`);

    if (processedFiles.some(file => file.name === nextFile.name)) {
      console.log(`Skipping already processed file: ${nextFile.name}`);
      return moveToNextFile();
    }

    // Open WebSocket connection for real-time updates only for unprocessed files
    setupWebSocketConnection(nextFile.name);
      
    // Upload the file to the backend
    const response = await uploadFile(nextFile, percent => setProgress(prev => ({ ...prev, [nextFile.name]: percent})));
      
    // Store processed file result
    setProcessedFiles(prev => {
      if (!prev.some(file => file.name === nextFile.name)) {
          return [...prev, { name: nextFile.name, result: response }];
      }
      return prev;
    });
    setIsProcessing(false);
  };

  // Sets up the WebSocket connection for a given file
  const setupWebSocketConnection = (fileName) => {
    flaggedCoursesReceived = false; // Reset tracking when starting a new WebSocket

    // Ensure file is unprocessed before setting up a WebSocket connection
    if (processedFiles.some(file => file.name === fileName)) return;

    // Close any existing WebSockets for files that are not currently being processed
    activeWebSockets.forEach((ws, key) => {
      if (key !== fileName) {
        console.log(`Closing extra WebSocket connection for ${key}`);
        ws.close();
        activeWebSockets.delete(key);
      }
    });
    
    console.log(`Opening WebSocket for ${fileName}`);
    const ws = setupWebSocket(fileName, wsRef, currentFileRef, flaggedCoursesReceived, fetchFlaggedCourses, moveToNextFile, setProcessedFiles, handleWebSocketError, setIsProcessing);
    activeWebSockets.set(fileName, ws);
  };

  // Handles WebSocket errors and reconnection logic
  const handleWebSocketError = (fileName, event) => {
    console.warn(`WebSocket error or disconnection for ${fileName}: ${event.reason}`);

    // If flagged courses are already received, continue handling user decisions
    if (flaggedCourses.length > 0) return;

    // If WebSocket disconnects before flagged courses are received, attempt to reconnect
    if (event.reason === "keepalive ping timeout" || event.code === 1006) {
      return setupWebSocketConnection(fileName);
    }

    setProcessedFiles(prev => prev.some(file => file.name === fileName) ? prev : [...prev, { name: fileName, result: { status: "error", message: "WebSocket error. File processing failed." } }]);
    moveToNextFile();
  };

  // Fetches flagged courses for the current file once they are ready
  const fetchFlaggedCourses = async (fileName) => {
    if (fileName !== currentFileRef.current) return; // Only fetch for the current file
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
        console.log(`No flagged courses detected for ${fileName}. Marking as successfully processed.`);
        setUploadStatus(`No flagged courses detected for ${fileName}.`);
        setProcessedFiles(prev => {
          if (!prev.some(file => file.name === fileName)) {
            return [...prev, { name: fileName, result: { status: "error", message: "no flagged courses" } }];
          }
          return prev;
        });
        setIsProcessing(false);
        moveToNextFile();
      }
    } catch (error) {
      console.error("Error fetching flagged courses:", error);
      setUploadStatus("Error: Unable to fetch flagged courses.");
    
      // Mark the file as processed unsuccessfully
      setProcessedFiles(prev => {
        if (!prev.some(file => file.name === fileName)) {
          return [...prev, { name: fileName, result: { status: "error", message: "Failed to fetch flagged courses." } }];
        }
        return prev;
      });
      setIsProcessing(false);
      moveToNextFile();
    }
  };

  // Handle user decision input changes
  const handleDecisionChange = (fileName, degree, major, courseName, field, value) => {
    setUploadStatus('Waiting for user decisions...');
    setUserDecisions(prev => ({
      ...prev,
      [`${fileName}--${degree}--${major}--${courseName}`]: {
        ...prev[`${fileName}--${degree}--${major}--${courseName}`],
        [field]: field === "credits_earned" ? (value === "" ? "" : value) : value
      }
    }));
  };

  // Submits user decisions and moves to the next file
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

    const response = await submitFlaggedDecisions(currentFileRef.current, structuredDecisions);

    // Close the WebSocket for the current file
    if (wsRef.current) wsRef.current.close(); 

    if (response.status === "success") {
      alert("Decisions submitted successfully!");

      // Ensure backend has completed processing before moving to next file
      setTimeout(() => {
        if (wsRef.current) {
          wsRef.current.close();
        }
        moveToNextFile();
      }, 2000); // Small delay to ensure processing completion
    } else {
      alert("Error submitting decisions. Please try again.");
    }
  };

  // Moves to the next file in the queue
  const moveToNextFile = () => {
    cleanupWebSocket(); // Clean up the WebSocket connection
    setPendingFiles(prev => prev.slice(1));
    setCurrentFile(null);
    currentFileRef.current = null;

    // Check if all files are processed
    if (pendingFiles.length <= 1) {
      setUploadStatus("All files processed."); // Update status when all files are done
    } else {
      setTimeout(() => {
        processNextFile(); // Allow pendingFiles state to update before calling next process
      }, 500); // Small delay ensures proper state update
    }
  };
  
  return (
    <div className="container">
      <h1>Upload Transcripts</h1>
      <p>Allowed formats: <strong>PDF, JPG, JPEG, PNG, CSV</strong></p>
      <p>Maximum size: <strong>5MB</strong></p>
      <p>Max files: <strong>100</strong></p>
      
      <input
        type="file"
        accept=".pdf, .jpg, .jpeg, .png, .csv"
        multiple
        onChange={handleFileUpload}
      />
      
      {/* Display upload status for any valid files */}
      {uploadStatus && (
        <div className="status">
          <p className={uploadStatus.startsWith('Error') ? 'error-text' : ''}>{uploadStatus}</p>
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

      {/* Display files that have been processed */}
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

      {/* Return back to home page button */}
      <BackToHomeButton />
    </div>
  );
}

export default UploadPage;
