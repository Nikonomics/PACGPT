import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Search, MessageCircle, BookOpen, ChevronRight, FileText, Send } from 'lucide-react';
import './IdahoALFChatbot.css';

const IdahoALFChatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [regulations, setRegulations] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedRegulation, setSelectedRegulation] = useState(null);
  const [isLoadingRegulations, setIsLoadingRegulations] = useState(true);
  const [regulationsError, setRegulationsError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [expandedRegulations, setExpandedRegulations] = useState(new Set());
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Regulation categories
  const categories = [
    { id: 'all', name: 'All' },
    { id: 'administrative', name: 'Administrative' },
    { id: 'licensing', name: 'Licensing' },
    { id: 'staffing', name: 'Staffing' },
    { id: 'physical_plant', name: 'Physical Plant' },
    { id: 'fire_safety', name: 'Fire Safety' },
    { id: 'medications', name: 'Medications' },
    { id: 'resident_care', name: 'Resident Care' }
  ];

  const exampleQuestions = [
    'What are the staffing requirements for a 20-bed facility?',
    'How much square footage is required per resident?',
    'What are the bathroom requirements?',
    'Do I need a sprinkler system?',
    'Can staff assist with insulin?'
  ];

  // Group regulations by parent
  const groupRegulationsByParent = (regs) => {
    const grouped = {};
    regs.forEach(reg => {
      if (reg.citation.includes('US Food Code')) {
        const parent = 'US Food Code';
        if (!grouped[parent]) grouped[parent] = [];
        grouped[parent].push(reg);
        return;
      }
      const match = reg.citation.match(/^([A-Z0-9\s]+\d+\.\d+)/);
      const parent = match ? match[1] : reg.citation;
      if (!grouped[parent]) grouped[parent] = [];
      grouped[parent].push(reg);
    });
    Object.keys(grouped).forEach(parent => {
      grouped[parent].sort((a, b) => {
        const aParts = a.citation.match(/(\d+)/g) || [];
        const bParts = b.citation.match(/(\d+)/g) || [];
        for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
          const aNum = parseInt(aParts[i]) || 0;
          const bNum = parseInt(bParts[i]) || 0;
          if (aNum !== bNum) return aNum - bNum;
        }
        return 0;
      });
    });
    return grouped;
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadRegulations();
  }, []);

  const loadRegulations = async () => {
    try {
      setIsLoadingRegulations(true);
      setRegulationsError(null);
      const response = await fetch('http://localhost:8000/chunks');
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setRegulations(data.chunks || []);
    } catch (error) {
      console.error('Error loading regulations:', error);
      setRegulationsError('Failed to load regulations.');
      setRegulations([]);
    } finally {
      setIsLoadingRegulations(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const filtered = regulations.filter(regulation =>
      regulation.section_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      regulation.citation.toLowerCase().includes(searchQuery.toLowerCase()) ||
      regulation.content.toLowerCase().includes(searchQuery.toLowerCase())
    );
    setSearchResults(filtered);
  };

  const handleQuestionClick = (question) => {
    setInput(question);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage,
          conversation_history: messages.slice(-10),
          top_k: 5,
          temperature: 0.3
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        citations: data.citations || []
      }]);
    } catch (error) {
      console.error('Error calling chatbot API:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Unable to connect to the chatbot backend. Please ensure the ALF backend is running on port 8000.`,
        error: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const regsToDisplay = searchResults.length > 0 ? searchResults : regulations;
  const filteredRegs = regsToDisplay.filter(reg => selectedCategory === 'all' || reg.category === selectedCategory);
  const groupedRegs = groupRegulationsByParent(filteredRegs);
  const parentKeys = Object.keys(groupedRegs).sort();

  return (
    <div className="alf-page">
      <main className="alf-container">
        {/* Page Header */}
        <div className="alf-page-header">
          <div className="alf-page-icon">
            <FileText />
          </div>
          <div>
            <h2 className="alf-page-title">Idaho ALF RegNavigator</h2>
            <p className="alf-page-subtitle">AI-powered assistant for Idaho Assisted Living Facility regulations</p>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="alf-layout">

          {/* Chat Panel - Left Side (2/3 width) */}
          <div className="alf-chat-panel alf-card">
            {/* Chat Header */}
            <div className="alf-chat-header">
              <div className="alf-chat-avatar">
                <MessageCircle />
              </div>
              <div>
                <h3 className="alf-chat-title">RegNavigator</h3>
                <div className="alf-chat-status">
                  <span className="alf-status-dot"></span>
                  <span>Ready to help with IDAPA 16.03.22</span>
                </div>
              </div>
            </div>

            {/* Chat Messages Area */}
            <div className="alf-messages">
              {messages.length === 0 ? (
                /* Welcome Message */
                <div className="alf-message assistant">
                  <div className="alf-message-avatar">
                    <MessageCircle />
                  </div>
                  <div className="alf-welcome">
                    <p className="alf-welcome-text">
                      Hello! I'm your Idaho Assisted Living Facility regulation expert. Ask me anything about IDAPA 16.03.22 regulations.
                    </p>
                    <div className="alf-welcome-divider">
                      <p className="alf-welcome-label">Try asking:</p>
                      <div className="alf-example-questions">
                        {exampleQuestions.map((q, i) => (
                          <button
                            key={i}
                            onClick={() => handleQuestionClick(q)}
                            className="alf-example-btn"
                          >
                            <span className="alf-example-icon">?</span>
                            <span>{q}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* Messages */
                <div className="alf-messages-list">
                  {messages.map((msg, i) => (
                    <div key={i} className={`alf-message ${msg.role}${msg.error ? ' error' : ''}`}>
                      {msg.role === 'assistant' && (
                        <div className="alf-message-avatar">
                          <MessageCircle />
                        </div>
                      )}
                      <div className="alf-message-bubble">
                        {msg.role === 'assistant' ? (
                          <div className="alf-prose">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                          </div>
                        ) : (
                          msg.content
                        )}

                        {msg.citations && msg.citations.length > 0 && (
                          <div className="alf-citations">
                            <p className="alf-citations-label">Sources:</p>
                            <div className="alf-citations-list">
                              {msg.citations.map((citation, idx) => (
                                <button
                                  key={idx}
                                  onClick={() => {
                                    const reg = regulations.find(r => r.citation === citation.citation);
                                    if (reg) setSelectedRegulation(reg);
                                  }}
                                  className="alf-citation-btn"
                                >
                                  [{idx + 1}] {citation.citation}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {isLoading && (
                    <div className="alf-message assistant">
                      <div className="alf-message-avatar">
                        <MessageCircle />
                      </div>
                      <div className="alf-loading">
                        <div className="alf-loading-dots">
                          <div className="alf-loading-dot"></div>
                          <div className="alf-loading-dot"></div>
                          <div className="alf-loading-dot"></div>
                        </div>
                        <span className="alf-loading-text">Analyzing regulations...</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="alf-input-area">
              <form onSubmit={handleSubmit} className="alf-input-form">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about Idaho ALF regulations..."
                  className="alf-input"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="alf-send-btn"
                >
                  <span>Send</span>
                  <Send />
                </button>
              </form>
            </div>
          </div>

          {/* Regulation Library Panel - Right Side (1/3 width) - STICKY */}
          <div className="alf-library-panel">
            <div className="alf-card">
              {/* Library Header */}
              <div className="alf-library-header">
                <div className="alf-library-icon">
                  <BookOpen />
                </div>
                <div>
                  <h3 className="alf-library-title">Regulation Library</h3>
                  <p className="alf-library-subtitle">Browse source documents</p>
                </div>
              </div>

              {/* Search */}
              <div className="alf-search">
                <form onSubmit={handleSearch} className="alf-search-wrapper">
                  <Search className="alf-search-icon" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search regulations..."
                    className="alf-search-input"
                  />
                </form>
              </div>

              {/* Filter Tags */}
              <div className="alf-filters">
                <div className="alf-filter-tags">
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => {
                        setSelectedCategory(cat.id);
                        setSearchResults([]);
                      }}
                      className={`alf-filter-tag ${selectedCategory === cat.id ? 'active' : ''}`}
                    >
                      {cat.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Regulation List */}
              <div className="alf-reg-list">
                {isLoadingRegulations ? (
                  <div className="alf-loading-regs">
                    <div className="alf-spinner"></div>
                    <p className="alf-loading-text">Loading regulations...</p>
                  </div>
                ) : regulationsError ? (
                  <div className="alf-error">
                    <p className="alf-error-text">{regulationsError}</p>
                    <button onClick={loadRegulations} className="alf-retry-btn">
                      Try again
                    </button>
                  </div>
                ) : (
                  parentKeys.map((parent, idx) => {
                    const sections = groupedRegs[parent];
                    const isExpanded = expandedRegulations.has(parent);

                    return (
                      <div key={idx} className="alf-reg-group">
                        <button
                          onClick={() => {
                            const newExpanded = new Set(expandedRegulations);
                            if (isExpanded) newExpanded.delete(parent);
                            else newExpanded.add(parent);
                            setExpandedRegulations(newExpanded);
                          }}
                          className="alf-reg-header"
                        >
                          <div>
                            <p className="alf-reg-name">{parent}</p>
                            <p className="alf-reg-count">{sections.length} sections</p>
                          </div>
                          <ChevronRight className={`alf-reg-chevron ${isExpanded ? 'expanded' : ''}`} />
                        </button>

                        {isExpanded && (
                          <div className="alf-reg-sections">
                            {sections.slice(0, 10).map((reg, sectionIdx) => (
                              <button
                                key={sectionIdx}
                                onClick={() => setSelectedRegulation(reg)}
                                className="alf-reg-section"
                              >
                                <p className="alf-reg-section-id">{reg.citation.replace(parent + '.', '')}</p>
                                <p className="alf-reg-section-title">{reg.section_title}</p>
                              </button>
                            ))}
                            {sections.length > 10 && (
                              <div className="alf-reg-more">
                                +{sections.length - 10} more sections
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Quick Stats Footer */}
              <div className="alf-library-footer">
                <span>{regulations.length} documents indexed</span>
                <span className="alf-footer-status">
                  <span className="alf-footer-dot"></span>
                  Ready
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Regulation Detail Modal */}
      {selectedRegulation && (
        <div
          className="alf-modal-overlay"
          onClick={() => setSelectedRegulation(null)}
        >
          <div
            className="alf-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="alf-modal-header">
              <h3 className="alf-modal-title">{selectedRegulation.citation}</h3>
              <p className="alf-modal-subtitle">{selectedRegulation.section_title}</p>
            </div>

            <div className="alf-modal-content">
              <div className="alf-prose">
                <ReactMarkdown>{selectedRegulation.content}</ReactMarkdown>
              </div>
            </div>

            <div className="alf-modal-footer">
              <button
                onClick={() => {
                  setInput(`What are the requirements for ${selectedRegulation.citation}?`);
                  setSelectedRegulation(null);
                }}
                className="alf-modal-btn primary"
              >
                Ask about this
              </button>
              <button
                onClick={() => setSelectedRegulation(null)}
                className="alf-modal-btn secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IdahoALFChatbot;
