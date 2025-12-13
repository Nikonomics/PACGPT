import React, { useState, useEffect } from 'react';
import { BarChart3, Users, MessageSquare, Clock, TrendingUp, RefreshCw, Lock } from 'lucide-react';
import './AdminDashboard.css';

const ALF_API_URL = import.meta.env.VITE_ALF_API_URL || 'http://localhost:8000';

// Simple password protection - change this!
const ADMIN_PASSWORD = 'alfadmin2024';

const AdminDashboard = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const [stats, setStats] = useState(null);
  const [queries, setQueries] = useState([]);
  const [popular, setPopular] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [days, setDays] = useState(30);

  const handleLogin = (e) => {
    e.preventDefault();
    if (password === ADMIN_PASSWORD) {
      setIsAuthenticated(true);
      setPasswordError('');
      sessionStorage.setItem('admin_auth', 'true');
    } else {
      setPasswordError('Incorrect password');
    }
  };

  useEffect(() => {
    // Check if already authenticated this session
    if (sessionStorage.getItem('admin_auth') === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated, days]);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [statsRes, queriesRes, popularRes] = await Promise.all([
        fetch(`${ALF_API_URL}/admin/stats?days=${days}`),
        fetch(`${ALF_API_URL}/admin/queries?limit=50&days=${days}`),
        fetch(`${ALF_API_URL}/admin/popular?limit=10&days=${days}`)
      ]);

      if (!statsRes.ok || !queriesRes.ok || !popularRes.ok) {
        throw new Error('Failed to fetch analytics data');
      }

      const [statsData, queriesData, popularData] = await Promise.all([
        statsRes.json(),
        queriesRes.json(),
        popularRes.json()
      ]);

      setStats(statsData);
      setQueries(queriesData.queries || []);
      setPopular(popularData.queries || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="admin-login">
        <div className="admin-login-card">
          <Lock size={48} className="admin-login-icon" />
          <h2>Admin Dashboard</h2>
          <p>Enter password to access analytics</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="admin-password-input"
            />
            {passwordError && <p className="admin-error">{passwordError}</p>}
            <button type="submit" className="admin-login-btn">
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <div className="admin-header-content">
          <h1><BarChart3 size={28} /> ALF Analytics Dashboard</h1>
          <div className="admin-controls">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="admin-select"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <button onClick={loadData} className="admin-refresh-btn" disabled={isLoading}>
              <RefreshCw size={16} className={isLoading ? 'spinning' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="admin-error-banner">
          Error loading data: {error}
        </div>
      )}

      {stats && (
        <>
          {/* Stats Cards */}
          <div className="admin-stats-grid">
            <div className="admin-stat-card">
              <MessageSquare size={24} />
              <div className="admin-stat-content">
                <span className="admin-stat-value">{stats.total_queries}</span>
                <span className="admin-stat-label">Total Questions</span>
              </div>
            </div>
            <div className="admin-stat-card">
              <Users size={24} />
              <div className="admin-stat-content">
                <span className="admin-stat-value">{stats.unique_sessions}</span>
                <span className="admin-stat-label">Unique Sessions</span>
              </div>
            </div>
            <div className="admin-stat-card">
              <Clock size={24} />
              <div className="admin-stat-content">
                <span className="admin-stat-value">
                  {stats.avg_response_time_ms ? `${(stats.avg_response_time_ms / 1000).toFixed(1)}s` : '-'}
                </span>
                <span className="admin-stat-label">Avg Response Time</span>
              </div>
            </div>
            <div className="admin-stat-card">
              <TrendingUp size={24} />
              <div className="admin-stat-content">
                <span className="admin-stat-value">{stats.total_page_views}</span>
                <span className="admin-stat-label">Page Views</span>
              </div>
            </div>
          </div>

          {/* Two Column Layout */}
          <div className="admin-content-grid">
            {/* Recent Queries */}
            <div className="admin-panel">
              <h2>Recent Questions</h2>
              <div className="admin-queries-list">
                {queries.length === 0 ? (
                  <p className="admin-empty">No queries yet</p>
                ) : (
                  queries.map((q, i) => (
                    <div key={i} className="admin-query-item">
                      <div className="admin-query-text">{q.question}</div>
                      <div className="admin-query-meta">
                        <span>{new Date(q.timestamp).toLocaleString()}</span>
                        <span>{q.response_time_ms}ms</span>
                        {q.top_citation && <span className="admin-citation">{q.top_citation}</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Popular Queries */}
            <div className="admin-panel">
              <h2>Popular Questions</h2>
              <div className="admin-popular-list">
                {popular.length === 0 ? (
                  <p className="admin-empty">No data yet</p>
                ) : (
                  popular.map((q, i) => (
                    <div key={i} className="admin-popular-item">
                      <span className="admin-popular-rank">#{i + 1}</span>
                      <span className="admin-popular-text">{q.query}</span>
                      <span className="admin-popular-count">{q.count}x</span>
                    </div>
                  ))
                )}
              </div>

              <h2 style={{ marginTop: '24px' }}>Top Cited Regulations</h2>
              <div className="admin-citations-list">
                {stats.top_citations?.length === 0 ? (
                  <p className="admin-empty">No data yet</p>
                ) : (
                  stats.top_citations?.map((c, i) => (
                    <div key={i} className="admin-citation-item">
                      <span className="admin-citation-text">{c.citation}</span>
                      <span className="admin-citation-count">{c.count}x</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Queries by Day Chart (simple text version) */}
          <div className="admin-panel admin-panel-full">
            <h2>Queries by Day</h2>
            <div className="admin-chart">
              {stats.queries_by_day?.length === 0 ? (
                <p className="admin-empty">No data yet</p>
              ) : (
                <div className="admin-bar-chart">
                  {stats.queries_by_day?.slice(0, 14).reverse().map((d, i) => (
                    <div key={i} className="admin-bar-item">
                      <div
                        className="admin-bar"
                        style={{
                          height: `${Math.max(20, (d.count / Math.max(...stats.queries_by_day.map(x => x.count))) * 100)}%`
                        }}
                      >
                        <span className="admin-bar-value">{d.count}</span>
                      </div>
                      <span className="admin-bar-label">{d.date.slice(5)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AdminDashboard;
