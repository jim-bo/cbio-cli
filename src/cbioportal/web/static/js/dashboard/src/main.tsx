import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

console.log('Study Dashboard script starting...');
const container = document.getElementById('study-dashboard');
console.log('Found dashboard container:', container);
if (container) {
  const studyId = container.getAttribute('data-study-id') || '';
  console.log('Mounting dashboard for study:', studyId);
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <App studyId={studyId} />
    </React.StrictMode>,
  )
} else {
  console.error('Study Dashboard container not found!');
}
