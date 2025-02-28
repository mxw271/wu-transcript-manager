import { useNavigate } from "react-router-dom";
import '../styles/BackToHomeButton.css';

const BackToHomeButton = ({ className = "back-btn", label = "Return to Home", disabled }) => {
  const navigate = useNavigate();

  return (
    <button className={className} onClick={() => navigate("/")} disabled={disabled}>
      {label}
    </button>
  );
};

export default BackToHomeButton;
