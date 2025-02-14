import React, { useCallback, useState } from 'react';
import { searchData } from '../apiServices'
import NotificationBar from '../components/NotificationBar';
import SearchCriteria from '../components/SearchCriteria';
import ResultTable from '../components/ResultTable';
import BackToHomeButton from '../components/BackToHomeButton';
import '../styles/QueryPage.css';

const QueryPage = () => {
  const [criteria, setCriteria] = useState({ 
    firstName: '',
    lastName: '',
    courseCategory: '',
    educationLevel: [],
  }); // State for search criteria
  const [results, setResults] = useState([]); // State to store search results
  const [notification, setNotification] = useState('');
  const [notificationType, setNotificationType] = useState(null);

  // Function to count the unique educators 
  const countTotalEducators = () => {
    if (!results.educator_name && results.queried_data && results.queried_data.length > 0) {
      const educatorSet = new Set();

      results.queried_data.forEach((row) => {
        const match = row["Course Details"].match(/- ([^-]+)$/); // Extract educator name 
        if (match) {
          educatorSet.add(match[1].trim()); // Add unique educator names
        }
      });
      return educatorSet.size;
    }
    return 0;
  };
  
  // Calculate before rendering ResultTable
  const totalEducators = countTotalEducators(); 
    
  // Handles the search request
  const handleSearch = useCallback(async () => {
    // Validate search criteria: if both firstName and lastName are provided or both are empty, prevent search
    if (criteria.firstName.trim() !== "" ^ criteria.lastName.trim() !== "") {
      setResults([]); 
      setNotification("Please enter both first and last name or leave them blank.");
      setNotificationType("warning");
      return;
    }

    try {
      const searchResults = await searchData(criteria); // Call API with criteria
      console.log(searchResults)
      setNotification(searchResults.message)

      // Handle different response statuses
      if (searchResults.status === "success") {
        setResults(searchResults); // Store the response data
        setNotificationType("success");
      } else {
        setResults([]);
        if (searchResults.status_code === 404 || searchResults.status === "not_found") {
          setNotificationType("warning");
        } else {
          setNotificationType("error");
        }
      }
    } catch (error) {
      console.error("SearchAPI Error:", error)
      setResults([]);

      if (error.response && error.response.status === 404) {
        setNotification("No transcripts found for the given search criteria.");
        setNotificationType("warning");
      } else {
        setNotification("Error during search.");
        setNotificationType("error");
      }
    }
  }, [criteria]);

  // Handles the download request
  const handleDownload = () => {
    // Validate if results exist
    if (!results || !results.queried_data || results.queried_data.length === 0) {
      setNotification("No data available to download.");
      setNotificationType("warning");
      return;
    }

    let fileName;
    let csvHeaders;

    // Determin filename and headers based on educator_name presence
    if (!results.educator_name) {
      fileName = "Qualifications_Worksheet.csv";
      csvHeaders = `"Total Faculty Count","${totalEducators}"\n`;
    } else {
      const name = results.educator_name.trim();
      if (!name) {
        setNotification("Educator name is empty or invalid. Using default filename.");
        setNotificationType("warning");
        fileName = "Unnamed_Educator_Qualifications_Worksheet.csv";
      } else {
        fileName = `${name.replace(/\s+/g, '_')}_Qualifications_Worksheet.csv`;
      }
      csvHeaders = `"Faculty's Name","${name || "Unknown"}"\n`;
    }

    // Convert search results to CSV
    let csvRows = [];
    results.queried_data.forEach(row => {
      if (!row || typeof row !== "object") {
        setNotification("Some data entries are invalid and were skipped.");
        setNotificationType("warning");
        return; // Skip invalid rows without stopping execution
      }
      csvRows.push(Object.values(row).map(value => `"${value}"`).join(","));
    });

    const csvContent = csvHeaders + csvRows.join("\n");

    if (!csvContent.trim()) {
      setNotification("CSV content is empty. No valid data to download.");
      setNotificationType("warning");
      return;
    }

    try {
      // Create a Blob and download the CSV
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);

      // Create and trigger a download link
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute("download", fileName);
      document.body.appendChild(link);
      link.click();

      // Clean up by removing the link
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url); // Free up memory

      setNotification("CSV downloaded successfully.");
      setNotificationType("success");
    } catch (error) {
      console.error("CSV Download Error:", error);
      setNotification(`Error generating CSV: $error.message`);
      setNotificationType("error");
    }
  };

  return (
    <div className="container">
      <h1>Query and Download Data</h1>
      {/* Notification Bar */}
      {notification && notificationType && (
        <NotificationBar message={notification} type={notificationType} />
      )}

      {/* Search Criteria Component */}
      <SearchCriteria 
        criteria={criteria} 
        setCriteria={setCriteria} 
        handleSearch={handleSearch} 
      />

      {/* Display ResultTable and export button only if results exist */}
      {results.queried_data && results.queried_data.length > 0 && (
        <>
          <ResultTable data={results} totalEducators={totalEducators} />
          <button className="export-btn" onClick={handleDownload}>
            Export as CSV
          </button>
        </>
      )}

      {/* Return back to home page button */}
      <BackToHomeButton />
    </div>
  );
}

export default QueryPage;
