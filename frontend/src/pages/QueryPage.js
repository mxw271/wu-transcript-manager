import React, { useCallback, useState} from 'react';
import { searchData, downloadData } from '../apiServices'
import NotificationBar from '../components/NotificationBar';
import SearchCriteria from '../components/SearchCriteria';
import ResultTable from '../components/ResultTable';
import '../styles/QueryPage.css';

const QueryPage = () => {
  const [criteria, setCriteria] = useState({ 
    name: '',
    courseCategory: '',
    educationLevel: [],
  }); // State for search criteria
  const [results, setResults] = useState([]); // State to store search results
  const [notification, setNotification] = useState('');
  const [notificationType, setNotificationType] = useState(null);

  // Handles the search request
  const handleSearch = useCallback(async () => {
    if (!criteria.name.trim() && !criteria.courseCategory && criteria.educationLevel.length === 0) {
      setResults([]); // Clear previous results if no criteria is entered
      return;
    }

    try {
      const searchResults = await searchData(criteria); // Call API with criteria
      setResults(searchResults); // Store the response data
      setNotification('Search completed successfully.');
      setNotificationType('success');
    } catch (error) {
      setNotification('Error during search.');
      setNotificationType('error');
    }
  }, [criteria]);

  // Handles the download request
  const handleDownload = async () => {
    try {
      await downloadData(criteria); // Call API to download results as CSV
    } catch (error) {
      console.error('Error downloading data:', error);
      setNotification('Error downloading data.');
      setNotificationType('error');
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
          <ResultTable data={results} />
          <button className="export-btn" onClick={handleDownload}>
            Export as CSV
          </button>
        </>
      )}
    </div>
  );
}

export default QueryPage;
