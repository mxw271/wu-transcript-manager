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
    if (criteria.firstName.trim() !== "" ^ criteria.lastName.trim() !== "") {
      setResults([]); // Clear previous results if both firstName and lastName are provided or both are empty
      setNotification('');
      setNotificationType(null);
      return;
    }

    try {
      const searchResults = await searchData(criteria); // Call API with criteria
      console.log(searchResults)

      if (!searchResults.queried_data || searchResults.queried_data.length === 0) {
        setResults([]);
        setNotification(searchResults.message)
        setNotificationType('error');
      } else {
        setResults(searchResults); // Store the response data
        setNotification(searchResults.message);
        setNotificationType('success');
      }
    } catch (error) {
      setResults([]);
      setNotification('Error during search.');
      setNotificationType('error');
    }
  }, [criteria]);

  // Handles the download request
  const handleDownload = () => {
    if (!results.queried_data || results.queried_data.length === 0) {
      setNotification('No data available to download.');
      setNotificationType('error');
      return;
    }

    let fileName;
    let csvHeaders;

    if (!results.educator_name) {
      // If educator_name is empty, use totalEducators
      fileName = "Qualifications_Worksheet.csv";
      csvHeaders = `"Total Faculty Count","${totalEducators}"\n`;
    } else {
      // If educator_name exists, format filename and headers
      const name = results.educator_name;
      fileName = `${name.replace(/\s+/g, '_')}_Qualifications_Worksheet.csv`;
      csvHeaders = `"Faculty's Name","${results.educator_name}"\n`;
    }

    // Convert search results to CSV
    const csvRows = results.queried_data
      .map(row => Object.values(row).map((value) => `"${value}"`).join(",")) // Ensure CSV-safe formatting
      .join("\n");

    const csvContent = csvHeaders + csvRows;

    // Create a Blob and download the CSV
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);

    // Create and trigger a download link
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();

    // Clean up by removing the link
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url); // Free up memory

    setNotification('CSV downloaded successfully.');
    setNotificationType('success');
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
