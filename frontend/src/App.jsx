import { useState } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { MessageSquare } from 'lucide-react'
import './App.css'
import MedicaidChatbot from './components/MedicaidChatbot'
import IdahoALFChatbot from './components/IdahoALFChatbot'
import AdminDashboard from './components/AdminDashboard'

function App() {
  const location = useLocation()

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-wrapper">
          <div className="header-top-bar">
            <div className="header-logo">
              <MessageSquare size={28} />
              <h1>Senior Chatbots</h1>
            </div>
          </div>

          <nav className="header-nav">
            <Link
              to="/"
              className={`nav-tab ${location.pathname === '/' ? 'active' : ''}`}
            >
              Home
            </Link>
            <Link
              to="/medicaid"
              className={`nav-tab ${location.pathname === '/medicaid' ? 'active' : ''}`}
            >
              Medicaid Policies
            </Link>
            <Link
              to="/idaho-alf"
              className={`nav-tab ${location.pathname === '/idaho-alf' ? 'active' : ''}`}
            >
              Idaho ALF
            </Link>
          </nav>
        </div>
      </header>

      <Routes>
        <Route path="/" element={
          <main className="app-main">
            <div className="home-container">
              <h2>Welcome to Senior Chatbots</h2>
              <p>Choose a chatbot to get started:</p>
              <div className="chatbot-cards">
                <Link to="/medicaid" className="chatbot-card">
                  <h3>Medicaid Policies</h3>
                  <p>Ask questions about Medicaid SNF reimbursement policies for all 50 states</p>
                </Link>
                <Link to="/idaho-alf" className="chatbot-card">
                  <h3>Idaho ALF Regulations</h3>
                  <p>Get answers about Idaho assisted living facility regulations</p>
                </Link>
              </div>
            </div>
          </main>
        } />
        <Route path="/medicaid" element={<MedicaidChatbot />} />
        <Route path="/idaho-alf" element={<IdahoALFChatbot />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </div>
  )
}

export default App
