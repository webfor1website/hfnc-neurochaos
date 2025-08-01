import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import UploadPage from './UploadPage';
import VisualizePage from './VisualizePage';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div>
        <nav>
          <Link to="/">Home</Link> | <Link to="/upload">Upload</Link> | <Link to="/visualize">Visualize</Link>
        </nav>
        <Routes>
          <Route path="/" element={<h1>Welcome to HNFC NeuroChaos</h1>} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/visualize" element={<VisualizePage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App; 
