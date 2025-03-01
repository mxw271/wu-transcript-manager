import React from "react";
import PropTypes from 'prop-types';
import '../styles/FlaggedCourses.css';

const FlaggedCourses = ({ flaggedCourses, userDecisions, handleDecisionChange, handleSubmitDecisions, courseCategories }) => {
  if (flaggedCourses.length === 0) {
    return null; // Don't render if there are no flagged courses
  }

  return (
    <div className="flagged-courses-container">
      <h3>Review Flagged Courses</h3>
      {flaggedCourses.map((degree, degreeIndex) => (
        <div key={degreeIndex}>
          <p>{degree.degree ? degree.degree : "Unknown Degree"}{' '}in{' '}{degree.major ? degree.major : "Unknown Major"}</p>
          {degree.overall_credits_earned && (<p>Overall Credits Earned: {degree.overall_credits_earned}</p>)}
          <table>
            <thead>
              <tr>
                <th>Course Name</th>
                {degree.courses.some(course => "should_be_category" in course) && (
                  <>
                    <th>Category</th>
                    <th>Corrected Category</th>
                  </>
                )}
                {degree.courses.some(course => "overall_credits_earned" in degree && "credits_earned" in course) && (
                  <>
                    <th>Credits Earned</th>
                    <th>Corrected Credits Earned</th>
                  </>
                )}
                {degree.courses.some(course => "grade" in course && "is_passed" in course) && (
                  <>
                    <th>Grade</th>
                    <th>Is Passed?</th>
                    <th>Corrected Is Passed?</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {degree.courses.map((course, index) => {
                const decisionKey = `${degree.file_name}--${degree.degree}--${degree.major}--${course.course_name}--${index}`;
                return (
                  <tr key={decisionKey}>
                    <td>{course.course_name}</td>

                    {/* Display Category Fields Only If should_be_category Exists */}
                    {"should_be_category" in course && (
                      <>
                        <td>{course.should_be_category}</td>
                        <td>
                          <select
                            className="select-category"
                            value={userDecisions[decisionKey]?.should_be_category ?? "Uncategorized"}
                            onChange={(e) => handleDecisionChange(
                                degree.file_name, degree.degree, degree.major, course.course_name, index,
                                "should_be_category", e.target.value
                            )}
                          >
                            <option value="Uncategorized">Uncategorized</option>
                            {courseCategories.map((category, idx) => (
                              <option key={idx} value={category}>
                                {category}
                              </option>
                            ))}
                          </select>
                        </td>
                      </>
                    )}

                    {/* Display Credits Earned Fields Only If They Exist */}
                    {"overall_credits_earned" in degree && "credits_earned" in course && (
                      <>
                        <td>{course.credits_earned}</td>
                        <td>
                          <input
                            type="text"
                            className="input-credit"
                            value={userDecisions[decisionKey]?.credits_earned === "" ? "" : userDecisions[decisionKey]?.credits_earned ?? ""}
                            onChange={(e) => handleDecisionChange(
                                degree.file_name, degree.degree, degree.major, course.course_name, index,
                                "credits_earned", e.target.value === "" ? "" : e.target.value
                            )}
                          />
                        </td>
                      </>
                    )}

                    {/* Display Grade & Is Passed Fields Only If They Exist */}
                    {"grade" in course && "is_passed" in course && (
                      <>
                        <td>{course.grade}</td>
                        <td>{course.is_passed?.toString()}</td>
                        <td>
                          <select
                            className="select-passed"
                            value={userDecisions[decisionKey]?.is_passed ?? "False"}
                            onChange={(e) => handleDecisionChange(
                                degree.file_name, degree.degree, degree.major, course.course_name, index,
                                "is_passed", e.target.value
                            )}
                          >
                            <option value="False">Fail</option>
                            <option value="True">Pass</option>
                          </select>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
      <button className="submit-decision" onClick={handleSubmitDecisions}>Submit Decisions</button>
    </div>
  );
};

// Define prop types for type safety
FlaggedCourses.propTypes = {
  flaggedCourses: PropTypes.arrayOf(
    PropTypes.shape({
      file_name: PropTypes.string.isRequired,
      degree: PropTypes.string.isRequired,
      courses: PropTypes.arrayOf(
        PropTypes.shape({
          course_name: PropTypes.string.isRequired,
          should_be_category: PropTypes.string,
          overall_credits_earned: PropTypes.number,
          credits_earned: PropTypes.number,
          grade: PropTypes.string,
          is_passed: PropTypes.string      
        })
      ).isRequired
    })
  ).isRequired,
  userDecisions: PropTypes.objectOf(
    PropTypes.shape({
      should_be_category: PropTypes.string,
      credits_earned: PropTypes.string,
      is_passed: PropTypes.string      
    })
  ).isRequired,
  handleDecisionChange: PropTypes.func.isRequired,
  handleSubmitDecisions: PropTypes.func.isRequired,
  courseCategories: PropTypes.arrayOf(PropTypes.string).isRequired
};

export default FlaggedCourses;
