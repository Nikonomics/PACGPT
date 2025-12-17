import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Search, MessageCircle, BookOpen, ChevronRight, ChevronDown, FileText, Send, Folder, File, MapPin } from 'lucide-react';
import './IdahoALFChatbot.css';

const ALF_API_URL = import.meta.env.VITE_ALF_API_URL || 'http://localhost:8000';

// Available states for the dropdown
const AVAILABLE_STATES = [
  { value: 'Idaho', label: 'Idaho', abbrev: 'ID' },
  { value: 'Washington', label: 'Washington', abbrev: 'WA' },
  { value: 'Oregon', label: 'Oregon', abbrev: 'OR' },
];

// Generate or retrieve session ID for analytics
const getSessionId = () => {
  let sessionId = sessionStorage.getItem('alf_session_id');
  if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
    sessionStorage.setItem('alf_session_id', sessionId);
  }
  return sessionId;
};

const IdahoALFChatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedState, setSelectedState] = useState('Idaho'); // Default to Idaho
  const [library, setLibrary] = useState([]);
  const [regulations, setRegulations] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedRegulation, setSelectedRegulation] = useState(null);
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(true);
  const [libraryError, setLibraryError] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [totalChunks, setTotalChunks] = useState(0);
  const [showLibraryMobile, setShowLibraryMobile] = useState(false);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const sessionId = useRef(getSessionId());

  const scrollToBottom = () => {
    // Scroll within the messages container, not the whole page
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  const exampleQuestions = [
    'What are the staffing requirements for a 20-bed facility?',
    'How much square footage is required per resident?',
    'What are the ADA door width requirements?',
    'Do I need a sprinkler system?',
    'What diseases must be reported?'
  ];

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadLibrary();
    loadRegulations();
    // Track page view
    trackPageView();
  }, []);

  const trackPageView = async () => {
    try {
      await fetch(`${ALF_API_URL}/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId.current,
          event: 'page_view',
          page: '/alf',
          user_agent: navigator.userAgent
        })
      });
    } catch (error) {
      // Silently fail - analytics shouldn't break the app
      console.debug('Analytics tracking failed:', error);
    }
  };

  const loadLibrary = async () => {
    try {
      setIsLoadingLibrary(true);
      setLibraryError(null);
      const response = await fetch(`${ALF_API_URL}/library`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setLibrary(data.library || []);
      setTotalChunks(data.total_chunks || 0);
    } catch (error) {
      console.error('Error loading library:', error);
      setLibraryError('Failed to load library.');
      setLibrary([]);
    } finally {
      setIsLoadingLibrary(false);
    }
  };

  const loadRegulations = async () => {
    try {
      const response = await fetch(`${ALF_API_URL}/chunks`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setRegulations(data.chunks || []);
    } catch (error) {
      console.error('Error loading regulations:', error);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const filtered = regulations.filter(regulation =>
      regulation.section_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      regulation.citation?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      regulation.content?.toLowerCase().includes(searchQuery.toLowerCase())
    );
    setSearchResults(filtered.slice(0, 50)); // Limit results
  };

  const handleQuestionClick = (question) => {
    setInput(question);
  };

  // Handle state change - clear conversation when state changes
  const handleStateChange = (newState) => {
    if (newState !== selectedState) {
      setSelectedState(newState);
      setMessages([]); // Clear conversation when state changes
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${ALF_API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage,
          conversation_history: messages.slice(-10),
          top_k: 5,
          temperature: 0.3,
          session_id: sessionId.current,
          state: selectedState  // Pass selected state to backend
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        citations: data.citations || [],
        state: selectedState  // Track which state the response was for
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

  const toggleNode = (nodeId) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  const findChunkByIdOrCitation = (chunkId, citation) => {
    return regulations.find(r =>
      r.chunk_id === chunkId || r.citation === citation
    );
  };

  // Format regulation text for better readability
  const formatRegulationContent = (content) => {
    if (!content) return '';

    return content
      // Convert URLs to clickable markdown links
      .replace(/(https?:\/\/[^\s\)]+)/g, '[$1]($1)')
      // Add line breaks before paragraph markers (A), (B), (C), etc.
      .replace(/\s*\(([A-Z])\)\s*/g, '\n\n**($1)** ')
      // Add line breaks before numbered subsections like (1), (2), (3)
      .replace(/\s*\((\d+)\)\s*/g, '\n\n*($1)* ')
      // Add line breaks before section numbers like "3-403.11" or "16.03.22.100"
      .replace(/(\d+-\d+\.\d+|\d+\.\d+\.\d+\.\d+)/g, '\n\n**$1**')
      // Add line breaks before common section headers
      .replace(/(Reheating|Preparation|Requirements|Definitions|Standards|Procedures|Equipment|Facilities)/g, '\n\n**$1**')
      // Clean up multiple newlines
      .replace(/\n{3,}/g, '\n\n')
      // Trim whitespace
      .trim();
  };

  // Render content with clickable inline citations
  const renderContentWithCitations = (content, citations) => {
    if (!citations || citations.length === 0) {
      return <ReactMarkdown>{content}</ReactMarkdown>;
    }

    // Split content by citation markers like [1], [2], etc.
    const parts = content.split(/(\[\d+\])/g);

    return (
      <div className="alf-content-with-citations">
        {parts.map((part, index) => {
          // Check if this part is a citation marker
          const citationMatch = part.match(/^\[(\d+)\]$/);
          if (citationMatch) {
            const citationIndex = parseInt(citationMatch[1], 10) - 1;
            const citation = citations[citationIndex];
            if (citation) {
              return (
                <button
                  key={index}
                  className="alf-inline-citation"
                  onClick={() => {
                    const reg = regulations.find(r => r.citation === citation.citation);
                    if (reg) setSelectedRegulation(reg);
                  }}
                  title={citation.citation}
                >
                  [{citationMatch[1]}]
                </button>
              );
            }
          }
          // Regular text - render as markdown
          if (part.trim()) {
            return <ReactMarkdown key={index}>{part}</ReactMarkdown>;
          }
          return null;
        })}
      </div>
    );
  };

  // Recursive tree node component
  const TreeNode = ({ node, level = 0 }) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const hasChunks = node.chunks && node.chunks.length > 0;
    const isLeaf = !hasChildren && hasChunks;

    return (
      <div className="tree-node" style={{ marginLeft: level > 0 ? '12px' : '0' }}>
        <button
          className={`tree-node-header ${isExpanded ? 'expanded' : ''} ${isLeaf ? 'leaf' : ''}`}
          onClick={() => {
            if (hasChildren || hasChunks) {
              toggleNode(node.id);
            }
          }}
        >
          <div className="tree-node-icon">
            {hasChildren ? (
              isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
            ) : hasChunks ? (
              isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
            ) : (
              <File size={14} />
            )}
          </div>
          <div className="tree-node-content">
            <span className="tree-node-name">{node.name}</span>
            <span className="tree-node-count">{node.count}</span>
          </div>
        </button>

        {isExpanded && hasChildren && (
          <div className="tree-node-children">
            {node.children.map((child, idx) => (
              <TreeNode key={child.id || idx} node={child} level={level + 1} />
            ))}
          </div>
        )}

        {isExpanded && hasChunks && !hasChildren && (
          <div className="tree-node-chunks">
            {node.chunks.map((chunk, idx) => (
              <button
                key={chunk.chunk_id || idx}
                className="tree-chunk-item"
                onClick={() => {
                  const fullChunk = findChunkByIdOrCitation(chunk.chunk_id, chunk.citation);
                  if (fullChunk) setSelectedRegulation(fullChunk);
                }}
              >
                <File size={12} />
                <span className="tree-chunk-title">{chunk.title || chunk.citation}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="alf-page">
      <main className="alf-container">
        {/* Page Header */}
        <div className="alf-page-header">
          <div className="alf-page-icon">
            <FileText />
          </div>
          <div className="alf-header-content">
            <h2 className="alf-page-title">ALF RegNavigator</h2>
            <p className="alf-page-subtitle">AI-powered assistant for Assisted Living Facility regulations</p>
          </div>
          <div className="alf-state-selector">
            <MapPin size={18} className="alf-state-icon" />
            <select
              value={selectedState}
              onChange={(e) => handleStateChange(e.target.value)}
              className="alf-state-dropdown"
            >
              {AVAILABLE_STATES.map((state) => (
                <option key={state.value} value={state.value}>
                  {state.label}
                </option>
              ))}
            </select>
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
                  <span>Ready to help with {selectedState} ALF regulations</span>
                </div>
              </div>
            </div>

            {/* Chat Messages Area */}
            <div className="alf-messages" ref={messagesContainerRef}>
              {messages.length === 0 ? (
                /* Welcome Message */
                <div className="alf-message assistant">
                  <div className="alf-message-avatar">
                    <MessageCircle />
                  </div>
                  <div className="alf-welcome">
                    <p className="alf-welcome-text">
                      Hello! I'm your {selectedState} Assisted Living Facility regulation expert. Ask me anything about {selectedState} ALF regulations, federal requirements, ADA guidelines, food safety codes, and more.
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
                            {renderContentWithCitations(msg.content, msg.citations)}
                          </div>
                        ) : (
                          msg.content
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
                  placeholder={`Ask about ${selectedState} ALF regulations...`}
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

          {/* Mobile Library Toggle Button */}
          <button
            className="alf-library-toggle-mobile"
            onClick={() => setShowLibraryMobile(!showLibraryMobile)}
          >
            <BookOpen size={18} />
            <span>{showLibraryMobile ? 'Hide' : 'Browse'} Regulation Library</span>
            <ChevronDown
              size={18}
              className={`toggle-chevron ${showLibraryMobile ? 'open' : ''}`}
            />
          </button>

          {/* Regulation Library Panel - Right Side (1/3 width) - STICKY */}
          <div className={`alf-library-panel ${showLibraryMobile ? 'show-mobile' : ''}`}>
            <div className="alf-card">
              {/* Library Header */}
              <div className="alf-library-header">
                <div className="alf-library-icon">
                  <BookOpen />
                </div>
                <div>
                  <h3 className="alf-library-title">Regulation Library</h3>
                  <p className="alf-library-subtitle">{totalChunks.toLocaleString()} indexed sections</p>
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

              {/* Library Tree or Search Results */}
              <div className="alf-library-content">
                {isLoadingLibrary ? (
                  <div className="alf-loading-regs">
                    <div className="alf-spinner"></div>
                    <p className="alf-loading-text">Loading library...</p>
                  </div>
                ) : libraryError ? (
                  <div className="alf-error">
                    <p className="alf-error-text">{libraryError}</p>
                    <button onClick={loadLibrary} className="alf-retry-btn">
                      Try again
                    </button>
                  </div>
                ) : searchResults.length > 0 ? (
                  /* Search Results */
                  <div className="alf-search-results">
                    <div className="alf-search-header">
                      <span>{searchResults.length} results</span>
                      <button
                        className="alf-clear-search"
                        onClick={() => {
                          setSearchQuery('');
                          setSearchResults([]);
                        }}
                      >
                        Clear
                      </button>
                    </div>
                    {searchResults.map((reg, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedRegulation(reg)}
                        className="alf-search-result-item"
                      >
                        <p className="alf-result-citation">{reg.citation}</p>
                        <p className="alf-result-title">{reg.section_title}</p>
                      </button>
                    ))}
                  </div>
                ) : (
                  /* Hierarchical Tree */
                  <div className="alf-library-tree">
                    {library.map((doc, idx) => (
                      <TreeNode key={doc.id || idx} node={doc} level={0} />
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Stats Footer */}
              <div className="alf-library-footer">
                <span>{library.length} document groups</span>
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
              <div className="alf-prose formatted-regulation">
                <ReactMarkdown
                  components={{
                    a: ({node, ...props}) => (
                      <a {...props} target="_blank" rel="noopener noreferrer" />
                    )
                  }}
                >{formatRegulationContent(selectedRegulation.content)}</ReactMarkdown>
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
