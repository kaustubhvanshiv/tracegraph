import React from 'react';
import ReactDOM from 'react-dom/client';
import cytoscape from 'cytoscape';
// @ts-expect-error — no types bundle shipped by fcose
import fcose from 'cytoscape-fcose';
import App from './App';
import './index.css';

// Register fCoSE layout once
cytoscape.use(fcose);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
