import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

const container = document.getElementById('study-dashboard');
if (container) {
  const studyId = container.getAttribute('data-study-id') || '';
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <App studyId={studyId} />
    </React.StrictMode>,
  )
}
