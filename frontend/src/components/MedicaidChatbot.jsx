import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Send, FileText, ExternalLink, Loader, AlertCircle, Zap, ChevronDown, ChevronUp, DollarSign, TrendingUp, Calendar, Award, Shield, Activity } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { getMedicaidStates, askMedicaidQuestion, getRevenueLevers } from '../services/apiService';
import './MedicaidChatbot.css';

function MedicaidChatbot() {
  const [states, setStates] = useState([]);
  const [selectedState, setSelectedState] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deepAnalysis, setDeepAnalysis] = useState(false);
  const [expandedCitations, setExpandedCitations] = useState({});
  const [stateRevenueLevers, setStateRevenueLevers] = useState(null);
  const messagesEndRef = useRef(null);

  // Load states on mount
  useEffect(() => {
    loadStates();
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load revenue levers when state changes
  useEffect(() => {
    if (selectedState) {
      loadRevenueLevers(selectedState);
    } else {
      setStateRevenueLevers(null);
    }
  }, [selectedState]);

  const loadRevenueLevers = async (state) => {
    try {
      const data = await getRevenueLevers(state);
      setStateRevenueLevers(data);
    } catch (err) {
      console.error('Error loading revenue levers:', err);
      // Don't show error to user, just log it
    }
  };

  const loadStates = async () => {
    try {
      const data = await getMedicaidStates();
      setStates(data.states);
    } catch (err) {
      console.error('Error loading states:', err);
      setError('Failed to load states. Please refresh the page.');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleStateChange = (e) => {
    const newState = e.target.value;
    setSelectedState(newState);
    setMessages([]);
    setError(null);

    // Add welcome message for the selected state
    if (newState) {
      setMessages([{
        role: 'assistant',
        content: `Hello! I can help you with information about ${newState}'s Medicaid Fee-for-Service Nursing Facility Payment Policies. What would you like to know?`,
        citations: null
      }]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!inputValue.trim() || !selectedState) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setError(null);

    // Add user message to chat
    const newMessages = [
      ...messages,
      { role: 'user', content: userMessage }
    ];
    setMessages(newMessages);

    try {
      // Build conversation history for API (last 10 messages)
      const conversationHistory = newMessages
        .slice(-10)
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      // Get AI response
      const response = await askMedicaidQuestion(
        selectedState,
        userMessage,
        conversationHistory,
        deepAnalysis
      );

      // Add assistant message to chat
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: response.response,
          citations: response.citations,
          deepAnalysis: response.deepAnalysis,
          documentsFetched: response.documentsFetched
        }
      ]);
    } catch (err) {
      console.error('Error getting response:', err);
      setError('Failed to get response. Please try again.');
      // Remove the user message since we couldn't get a response
      setMessages(messages);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExampleQuestion = (question) => {
    if (!selectedState) {
      setError('Please select a state first');
      return;
    }
    setInputValue(question);
  };

  const toggleCitations = (messageIndex) => {
    setExpandedCitations(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  // Group citations by category
  const groupCitationsByCategory = (citations) => {
    const grouped = {};
    citations.forEach(citation => {
      const category = citation.category || 'Other';
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(citation);
    });
    return grouped;
  };

  // Extract URLs from source text and make them clickable
  const renderSourceWithLinks = (sourceText) => {
    if (!sourceText) return null;

    // Match URLs in the text
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = sourceText.split(urlRegex);

    return parts.map((part, idx) => {
      if (part.match(urlRegex)) {
        // Clean up URL (remove trailing punctuation)
        const cleanUrl = part.replace(/[.,;:)]$/, '');
        return (
          <a
            key={idx}
            href={cleanUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="source-link"
          >
            {cleanUrl}
          </a>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  };

  const exampleQuestions = [
    "What add-on services can increase my reimbursement?",
    "Are there quality incentive payments available?",
    "When do rates get rebased in this state?",
    "What's the bed-hold policy?",
    "Are there payments for ventilator or behavioral health units?",
    "How can I maximize revenue through cost reporting?"
  ];

  return (
    <div className="medicaid-chatbot">
      <div className="chatbot-container">
        {/* Chat Sidebar */}
        <aside className="state-selector-sidebar">
          {/* Compact State Selector */}
          <select
            value={selectedState}
            onChange={handleStateChange}
            className="state-select"
            style={{ marginBottom: '12px', fontSize: '0.9rem', padding: '8px' }}
          >
            <option value="">-- Choose a State --</option>
            {states.map(state => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>

          {!selectedState ? (
            <div className="empty-state">
              <MessageSquare size={48} />
              <h3 style={{ fontSize: '1.1rem', margin: '12px 0 8px 0' }}>Select a State</h3>
              <p style={{ fontSize: '0.85rem', margin: 0 }}>Choose a state to view revenue intelligence and ask policy questions.</p>
            </div>
          ) : (
            <>
              {/* Messages Container */}
              <div className="messages-container">
                {messages.map((message, idx) => (
                  <div key={idx} className={`message ${message.role}`}>
                    <div className="message-content">
                      {message.deepAnalysis && message.role === 'assistant' && (
                        <div className="deep-analysis-badge">
                          <Zap size={14} />
                          <span>Deep Analysis {message.documentsFetched > 0 && `(${message.documentsFetched} docs)`}</span>
                        </div>
                      )}
                      <div className="message-text">
                        {message.role === 'assistant' ? (
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        ) : (
                          message.content
                        )}
                      </div>

                      {message.citations && message.citations.length > 0 && (
                        <div className="citations-container">
                          <div className="citations-divider">
                            <hr />
                            <span>Sources & References</span>
                            <hr />
                          </div>

                          <button
                            className="citations-toggle-btn"
                            onClick={() => toggleCitations(idx)}
                          >
                            {expandedCitations[idx] ? (
                              <>
                                <ChevronUp size={18} />
                                <span>Hide {message.citations.length} Sources</span>
                              </>
                            ) : (
                              <>
                                <ChevronDown size={18} />
                                <span>Show {message.citations.length} Sources</span>
                              </>
                            )}
                          </button>

                          {expandedCitations[idx] && (
                            <div className="citations-content">
                              {Object.entries(groupCitationsByCategory(message.citations)).map(([category, citations]) => (
                                <div key={category} className="citation-category">
                                  <h4 className="citation-category-header">
                                    <FileText size={16} />
                                    {category}
                                  </h4>
                                  {citations.map((citation, cidx) => (
                                    <div key={cidx} className="citation-item">
                                      <div className="citation-policy-name">
                                        {citation.policyName}
                                      </div>
                                      {citation.sources && (
                                        <div className="citation-source">
                                          <ExternalLink size={14} />
                                          <div className="citation-source-text">
                                            {renderSourceWithLinks(citation.sources)}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="message assistant loading">
                    <div className="message-content">
                      <Loader size={20} className="spinner" />
                      <span>Analyzing {selectedState} policies...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Form */}
              <form onSubmit={handleSubmit} className="chat-input-form">
                {error && (
                  <div className="error-banner">
                    <AlertCircle size={16} />
                    <span>{error}</span>
                  </div>
                )}

                <div className="input-wrapper">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder={`Ask about ${selectedState}'s Medicaid policies...`}
                    disabled={isLoading}
                    className="chat-input"
                  />
                  <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading}
                    className="send-btn"
                  >
                    <Send size={20} />
                  </button>
                </div>

                {/* Deep Analysis Toggle - Compact */}
                <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.75rem', color: '#4a5568' }}>
                    <input
                      type="checkbox"
                      checked={deepAnalysis}
                      onChange={(e) => setDeepAnalysis(e.target.checked)}
                      style={{ width: '14px', height: '14px' }}
                    />
                    <Zap size={12} style={{ color: '#f59e0b' }} />
                    <span>Deep Analysis</span>
                  </label>
                </div>
              </form>
            </>
          )}
        </aside>

        {/* Revenue Dashboard Area */}
        <div className="chat-main">
          {!selectedState ? (
            <div className="empty-state">
              <DollarSign size={64} />
              <h2>Revenue Intelligence Dashboard</h2>
              <p>Select a state to view detailed revenue optimization opportunities.</p>
            </div>
          ) : (
            <>
              {/* Revenue Levers Dashboard - Scrollable */}
              {stateRevenueLevers && (
                <div style={{ overflowY: 'auto', padding: '24px', borderBottom: '1px solid #e2e8f0' }}>
                  <h2 style={{ fontSize: '1.3em', fontWeight: '700', color: '#111827', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <DollarSign size={22} />
                    Revenue Optimization Intelligence: {selectedState}
                  </h2>

                  {/* Summary Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '24px' }}>
                    {/* Add-Ons Card */}
                    <div style={{ backgroundColor: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <TrendingUp size={16} style={{ color: '#16a34a' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#166534', margin: 0 }}>Service Add-Ons</h3>
                      </div>
                      <div style={{ fontSize: '1.8em', fontWeight: '700', color: '#15803d', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.totalAddOns}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#166534', margin: 0 }}>
                        {stateRevenueLevers.summary.totalAddOns > 0 ? 'specialized services' : 'none found'}
                      </p>
                    </div>

                    {/* Quality Incentives Card */}
                    <div style={{ backgroundColor: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <Award size={16} style={{ color: '#2563eb' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#1e40af', margin: 0 }}>Quality Programs</h3>
                      </div>
                      <div style={{ fontSize: '1.8em', fontWeight: '700', color: '#1d4ed8', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.totalIncentives}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#1e40af', margin: 0 }}>
                        {stateRevenueLevers.summary.totalIncentives > 0 ? 'incentive programs' : 'none found'}
                      </p>
                    </div>

                    {/* Supplemental Payments Card */}
                    <div style={{ backgroundColor: '#fef3f2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <DollarSign size={16} style={{ color: '#dc2626' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#991b1b', margin: 0 }}>Supplemental Payments</h3>
                      </div>
                      <div style={{ fontSize: '1.8em', fontWeight: '700', color: '#dc2626', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.totalSupplementalPayments || 0}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#991b1b', margin: 0 }}>
                        {stateRevenueLevers.summary.totalSupplementalPayments > 0 ? 'additional payments' : 'none found'}
                      </p>
                    </div>

                    {/* Rebasing Timeline Card */}
                    <div style={{ backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <Calendar size={16} style={{ color: '#d97706' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#92400e', margin: 0 }}>Rate Rebasing</h3>
                      </div>
                      <div style={{ fontSize: '1.4em', fontWeight: '700', color: '#b45309', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.hasRebasingInfo ? '✓' : '—'}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#92400e', margin: 0 }}>
                        {stateRevenueLevers.summary.hasRebasingInfo ? 'timing available' : 'no info'}
                      </p>
                    </div>

                    {/* Acuity System Card */}
                    <div style={{ backgroundColor: '#faf5ff', border: '1px solid #d8b4fe', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <Activity size={16} style={{ color: '#9333ea' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#6b21a8', margin: 0 }}>Acuity System</h3>
                      </div>
                      <div style={{ fontSize: '1.4em', fontWeight: '700', color: '#7e22ce', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.hasAcuitySystem ? '✓' : '—'}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#6b21a8', margin: 0 }}>
                        {stateRevenueLevers.summary.hasAcuitySystem ? 'case-mix adjusted' : 'no system'}
                      </p>
                    </div>

                    {/* Bed Hold Policy Card */}
                    <div style={{ backgroundColor: '#f3e8ff', border: '1px solid #c084fc', borderRadius: '8px', padding: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <Shield size={16} style={{ color: '#a855f7' }} />
                        <h3 style={{ fontSize: '0.85em', fontWeight: '600', color: '#7c3aed', margin: 0 }}>Bed-Hold Policy</h3>
                      </div>
                      <div style={{ fontSize: '1.4em', fontWeight: '700', color: '#9333ea', marginBottom: '2px' }}>
                        {stateRevenueLevers.summary.hasBedHoldPolicy ? '✓' : '—'}
                      </div>
                      <p style={{ fontSize: '0.75em', color: '#7c3aed', margin: 0 }}>
                        {stateRevenueLevers.summary.hasBedHoldPolicy ? 'protection exists' : 'none available'}
                      </p>
                    </div>
                  </div>

                  {/* Detailed Revenue Levers */}
                  {stateRevenueLevers.addOns.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Activity size={18} style={{ color: '#16a34a' }} />
                        Available Add-On Services
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.addOns.filter(addon => addon.available).map((addon, idx) => (
                          <div key={idx} style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #16a34a', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>{addon.name}</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{addon.summary}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {stateRevenueLevers.incentives.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Award size={18} style={{ color: '#2563eb' }} />
                        Quality Incentive Programs
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.incentives.filter(inc => inc.available).map((incentive, idx) => (
                          <div key={idx} style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #2563eb', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>{incentive.name}</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{incentive.summary}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {stateRevenueLevers.supplementalPayments && stateRevenueLevers.supplementalPayments.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <DollarSign size={18} style={{ color: '#dc2626' }} />
                        Supplemental Payment Opportunities
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.supplementalPayments.filter(sup => sup.available).map((supplement, idx) => (
                          <div key={idx} style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #dc2626', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>{supplement.name}</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{supplement.summary}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Key Timing Factors */}
                  {(stateRevenueLevers.keyTimingFactors.rebasing || stateRevenueLevers.keyTimingFactors.costReport || stateRevenueLevers.keyTimingFactors.paymentApproach || stateRevenueLevers.keyTimingFactors.inflationFactor) && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Calendar size={18} style={{ color: '#d97706' }} />
                        Critical Timing & Rate Information
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.keyTimingFactors.rebasing && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #d97706', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Rebasing Frequency</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.keyTimingFactors.rebasing.frequency}</div>
                          </div>
                        )}
                        {stateRevenueLevers.keyTimingFactors.costReport && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #d97706', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Cost Report Requirements</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.keyTimingFactors.costReport.type}</div>
                          </div>
                        )}
                        {stateRevenueLevers.keyTimingFactors.paymentApproach && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #d97706', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Payment Methodology</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.keyTimingFactors.paymentApproach.method}</div>
                          </div>
                        )}
                        {stateRevenueLevers.keyTimingFactors.inflationFactor && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #d97706', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Inflation Adjustment</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.keyTimingFactors.inflationFactor.adjustment}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Revenue Protection Policies */}
                  {(stateRevenueLevers.revenueProtection.bedHold || stateRevenueLevers.revenueProtection.occupancyMinimum) && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Shield size={18} style={{ color: '#9333ea' }} />
                        Revenue Protection Policies
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.revenueProtection.bedHold && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #9333ea', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Bed-Hold Policy</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.revenueProtection.bedHold.policy}</div>
                          </div>
                        )}
                        {stateRevenueLevers.revenueProtection.occupancyMinimum && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #9333ea', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Occupancy Rate Minimum</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.revenueProtection.occupancyMinimum.requirement}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Rate Determinants */}
                  {(stateRevenueLevers.rateDeterminants?.acuitySystem || stateRevenueLevers.rateDeterminants?.peerGrouping || stateRevenueLevers.rateDeterminants?.geographicAdjustment || stateRevenueLevers.rateDeterminants?.basisForRates) && (
                    <div>
                      <h3 style={{ fontSize: '1.1em', fontWeight: '700', color: '#111827', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Activity size={18} style={{ color: '#7c3aed' }} />
                        Rate Determinants & Competitive Factors
                      </h3>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {stateRevenueLevers.rateDeterminants.acuitySystem && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #7c3aed', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Acuity/Case-Mix System</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.rateDeterminants.acuitySystem.system}</div>
                          </div>
                        )}
                        {stateRevenueLevers.rateDeterminants.peerGrouping && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #7c3aed', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Peer Grouping Methodology</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.rateDeterminants.peerGrouping.methodology}</div>
                          </div>
                        )}
                        {stateRevenueLevers.rateDeterminants.geographicAdjustment && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #7c3aed', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Geographic Rate Adjustment</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.rateDeterminants.geographicAdjustment.adjustment}</div>
                          </div>
                        )}
                        {stateRevenueLevers.rateDeterminants.basisForRates && (
                          <div style={{ backgroundColor: '#f9fafb', borderLeft: '3px solid #7c3aed', padding: '12px', borderRadius: '6px' }}>
                            <div style={{ fontWeight: '600', color: '#111827', marginBottom: '4px' }}>Underlying Basis for Rates</div>
                            <div style={{ fontSize: '0.9em', color: '#4b5563' }}>{stateRevenueLevers.rateDeterminants.basisForRates.basis}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default MedicaidChatbot;
