import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

function App() {
  // --- AUTHENTICATION STATE ---
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoginMode, setIsLoginMode] = useState(true);

  // --- CHAT STATE ---
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [logs, setLogs] = useState([]); 
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // --- INITIALIZATION ---
  // Only try to fetch sessions IF the user has a token (is logged in)
  useEffect(() => {
    if (token) {
      fetchSessions();
    }
  }, [token]);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- SECURITY LOGIC ---
  const handleAuth = async (e) => {
    e.preventDefault();
    const endpoint = isLoginMode ? "/login" : "/register";
    
    let body;
    let headers = {};
    
    if (isLoginMode) {
      body = new URLSearchParams();
      body.append("username", username);
      body.append("password", password);
      headers = { "Content-Type": "application/x-www-form-urlencoded" };
    } else {
      body = JSON.stringify({ username, password });
      headers = { "Content-Type": "application/json" };
    }

    try {
      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        headers: headers,
        body: body
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Authentication failed");

      if (isLoginMode) {
        localStorage.setItem("token", data.access_token);
        setToken(data.access_token);
      } else {
        alert("Registration successful! Please log in.");
        setIsLoginMode(true);
      }
    } catch (error) {
      alert(error.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setSessions([]);
    setCurrentSessionId(null);
    setMessages([]);
  };

  // --- DATABASE FUNCTIONS (SECURED) ---
  const fetchSessions = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/sessions', {
        headers: { 'Authorization': `Bearer ${token}` } // <-- SECURED
      });
      if (!response.ok) throw new Error("Failed to authenticate token");
      
      const data = await response.json();
      setSessions(data);
      
      if (data.length > 0) {
        loadSession(data[0].session_id);
      } else {
        startNewSession();
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
      if (error.message.includes("authenticate")) handleLogout(); // Force logout if token expires
    }
  };

  const startNewSession = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/sessions', { 
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      
      // --- THE FIX ---
      // We manually add the new session to the top of the list instead of triggering an infinite fetch loop
      setSessions(prev => [{ session_id: data.session_id, title: "New Chat" }, ...prev]);
      
      setCurrentSessionId(data.session_id);
      setMessages([{ role: 'ai', content: 'New persistent session started. How can I assist you today?' }]);
      setLogs([]); 
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  const loadSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    setLogs([{ type: 'system', text: `> Loaded session: ${sessionId}` }]);
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/sessions/${sessionId}/messages`, {
        headers: { 'Authorization': `Bearer ${token}` } // <-- SECURED
      });
      const data = await response.json();
      
      if (data.length === 0) {
        setMessages([{ role: 'ai', content: 'Empty session loaded. How can I assist you?' }]);
      } else {
        setMessages(data);
      }
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  };

  const deleteSession = async (sessionId, e) => {
    e.stopPropagation(); 
    if (!window.confirm("Are you sure you want to delete this chat?")) return;

    try {
      await fetch(`http://127.0.0.1:8000/sessions/${sessionId}`, { 
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` } // <-- SECURED
      });
      
      const updatedSessions = sessions.filter(s => s.session_id !== sessionId);
      setSessions(updatedSessions);
      
      if (currentSessionId === sessionId) {
        if (updatedSessions.length > 0) {
          loadSession(updatedSessions[0].session_id);
        } else {
          startNewSession(); 
        }
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  // --- CHAT & UPLOAD FUNCTIONS (SECURED) ---
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      alert("Please upload a valid PDF file.");
      return;
    }

    setIsUploading(true);
    setLogs((prev) => [...prev, { type: 'system', text: `> Uploading ${file.name}...` }]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }, // <-- SECURED
        body: formData, 
      });

      const data = await response.json();
      
      if (data.status === "success") {
        setLogs((prev) => [...prev, { type: 'result', text: `> Success: ${data.message}` }]);
        setMessages((prev) => [...prev, { 
          role: 'ai', 
          content: `✅ **Database Updated:** I have successfully read and memorized **${file.name}**. (${data.message})` 
        }]);
      } else {
        throw new Error(data.message);
      }
    } catch (error) {
      console.error("Upload Error:", error);
      setLogs((prev) => [...prev, { type: 'error', text: `> Upload Error: ${error.message}` }]);
      alert("Failed to upload the manual. Check the logs.");
    } finally {
      setIsUploading(false);
      e.target.value = null; 
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;

    const userMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setLogs((prev) => [...prev, { type: 'system', text: 'Initiating AI thought process...' }]);

    setMessages((prev) => [...prev, { role: 'ai', content: '' }]);

    try {
      const response = await fetch('http://127.0.0.1:8000/ask', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` // <-- SECURED
        },
        body: JSON.stringify({ 
          question: userMessage.content,
          session_id: currentSessionId
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        if (buffer.includes(':::')) {
          const parts = buffer.split(':::');
          buffer = parts.pop(); 
          
          parts.forEach(part => {
            if (part.startsWith('__TOOL_USE__:')) {
               const cleanLog = part.replace('__TOOL_USE__:', '');
               setLogs((prev) => [...prev, { type: 'active', text: `> Executing Tool: ${cleanLog}` }]);
            } 
            else if (part.startsWith('__TOOL_RESULT__:')) {
               const cleanLog = part.replace('__TOOL_RESULT__:', '');
               setLogs((prev) => [...prev, { type: 'result', text: `> Result: ${cleanLog}` }]);
            }
          });
        } else {
          const currentText = buffer;
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: newMessages[lastIndex].content + currentText
            };
            return newMessages;
          });
          buffer = ""; 
        }
      }
    } catch (error) {
      console.error("Error:", error);
      setLogs((prev) => [...prev, { type: 'error', text: `> Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
      setLogs((prev) => [...prev, { type: 'system', text: 'Agent execution complete.' }]);
    }
  };

  // --- THE GATEKEEPER ---
  if (!token) {
    return (
      <div style={{ 
        display: 'flex', justifyContent: 'center', alignItems: 'center', 
        width: '100vw', height: '100vh', minHeight: '100vh',
        background: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)', 
        color: 'white', fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif" 
      }}>
        <form onSubmit={handleAuth} style={{ 
          display: 'flex', flexDirection: 'column', gap: '24px', 
          padding: '60px 50px', /* Increased padding */
          background: 'rgba(30, 30, 30, 0.65)', backdropFilter: 'blur(12px)', 
          borderRadius: '20px', /* Slightly rounder corners */
          width: '440px', /* Increased width from 380px */
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.5)', border: '1px solid rgba(255, 255, 255, 0.08)' 
        }}>
          
          <div style={{ textAlign: 'center', marginBottom: '15px' }}>
            <h2 style={{ margin: '0 0 10px 0', fontSize: '32px', fontWeight: '600', letterSpacing: '0.5px' }}>i-HEMS Workspace</h2>
            <p style={{ margin: 0, color: '#9ca3af', fontSize: '15px' }}>
              {isLoginMode ? "Sign in to your enterprise session" : "Register a secure account"}
            </p>
          </div>

          <input 
            type="text" 
            placeholder="Username" 
            value={username} 
            onChange={e => setUsername(e.target.value)} 
            required 
            style={{ 
              padding: '16px', borderRadius: '10px', border: '1px solid #444', 
              background: 'rgba(0,0,0,0.2)', color: 'white', fontSize: '16px', outline: 'none',
              transition: 'border 0.3s'
            }}
            onFocus={(e) => e.target.style.border = '1px solid #3b82f6'}
            onBlur={(e) => e.target.style.border = '1px solid #444'}
          />
          <input 
            type="password" 
            placeholder="Password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
            style={{ 
              padding: '16px', borderRadius: '10px', border: '1px solid #444', 
              background: 'rgba(0,0,0,0.2)', color: 'white', fontSize: '16px', outline: 'none',
              transition: 'border 0.3s'
            }}
            onFocus={(e) => e.target.style.border = '1px solid #3b82f6'}
            onBlur={(e) => e.target.style.border = '1px solid #444'}
          />
          
          <button type="submit" style={{ 
            padding: '16px', background: '#3b82f6', color: 'white', border: 'none', 
            borderRadius: '10px', cursor: 'pointer', fontSize: '18px', fontWeight: '600', 
            marginTop: '15px', transition: 'background 0.3s ease, transform 0.1s ease' 
          }}
          onMouseOver={(e) => e.target.style.background = '#2563eb'}
          onMouseOut={(e) => e.target.style.background = '#3b82f6'}
          onMouseDown={(e) => e.target.style.transform = 'scale(0.98)'}
          onMouseUp={(e) => e.target.style.transform = 'scale(1)'}
          >
            {isLoginMode ? "Secure Login" : "Create Account"}
          </button>

          <div style={{ textAlign: 'center', marginTop: '15px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '25px' }}>
            <button 
              type="button" 
              onClick={() => setIsLoginMode(!isLoginMode)} 
              style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '15px', transition: 'color 0.3s ease' }}
              onMouseOver={(e) => e.target.style.color = '#ffffff'}
              onMouseOut={(e) => e.target.style.color = '#9ca3af'}
            >
              {isLoginMode ? "Need an account? Register here" : "Already have an account? Sign in"}
            </button>
          </div>
        </form>
      </div>
    );
  }

  // --- THE SECURE WORKSPACE UI ---
  return (
    <div className="workspace-container">
      
      {/* LEFT SIDEBAR: Chat History & Status */}
      <aside className="sidebar left-sidebar">
        <div className="sidebar-header">
          <h2>i-HEMS Workspace</h2>
          <button className="new-chat-btn" onClick={startNewSession}>+ New Chat</button>
        </div>
        
        <div className="sidebar-content">
          <div className="status-card history-card">
            <h3>Recent Sessions</h3>
            <ul className="session-list">
              {sessions.map((session) => (
                <li 
                  key={session.session_id} 
                  className={currentSessionId === session.session_id ? 'active-session' : ''}
                  onClick={() => loadSession(session.session_id)}
                >
                  <span className="session-title" title={session.title}>💬 {session.title}</span>
                  <button 
                    className="delete-session-btn" 
                    onClick={(e) => deleteSession(session.session_id, e)}
                    title="Delete Chat"
                  >
                    🗑️
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="status-card">
            <h3>System Vitals</h3>
            <ul>
              <li>🟢 <span>Engine:</span> Llama 3.2 (3B)</li>
              <li>🟢 <span>Vector DB:</span> Chroma Active</li>
              <li>🟢 <span>Memory:</span> SQLite Connected</li>
            </ul>
          </div>
        </div>
      </aside>

      {/* CENTER COLUMN: The Chat Interface */}
      <main className="main-chat-area">
        <header className="chat-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚙️ Senior Process Engineer (Session: {currentSessionId?.substring(0,6)}...)</span>
          <button onClick={handleLogout} style={{ background: '#ff4d4d', color: 'white', border: 'none', padding: '5px 15px', borderRadius: '4px', cursor: 'pointer' }}>
            Logout
          </button>
        </header>
        
        <div className="chat-box">
          {messages.map((msg, index) => (
            <div key={index} className={`message-wrapper ${msg.role === 'user' ? 'user-wrapper' : 'ai-wrapper'}`}>
              {msg.role === 'ai' && <div className="avatar ai-avatar">⚙️</div>}
              
              <div className={`message ${msg.role === 'user' ? 'user-message' : 'ai-message'}`}>
                {msg.role === 'ai' ? <ReactMarkdown>{msg.content}</ReactMarkdown> : msg.content}
              </div>
              
              {msg.role === 'user' && <div className="avatar user-avatar">👤</div>}
            </div>
          ))}
          
          {isLoading && (
            <div className="message-wrapper ai-wrapper">
              <div className="avatar ai-avatar">⚙️</div>
              <div className="message ai-message">
                  <div className="typing-indicator">
                      <div className="dot"></div>
                      <div className="dot"></div>
                      <div className="dot"></div>
                  </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <form className="input-area" onSubmit={sendMessage}>
          <input 
            type="file" 
            accept=".pdf" 
            style={{ display: 'none' }} 
            ref={fileInputRef}
            onChange={handleFileUpload}
          />
          <button 
            type="button" 
            className="attach-btn" 
            title="Upload Document"
            onClick={() => fileInputRef.current.click()}
            disabled={isLoading || isUploading}
          >
            {isUploading ? '⏳' : '📎'}
          </button>
          
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            placeholder={isUploading ? "Uploading manual..." : "Ask an engineering question..."} 
            disabled={isLoading || isUploading || !currentSessionId}
          />
          <button type="submit" className="send-btn" disabled={isLoading || isUploading || !input.trim() || !currentSessionId}>
            Send
          </button>
        </form>
      </main>

      {/* RIGHT SIDEBAR: Agent Context */}
      <aside className="sidebar right-sidebar">
        <div className="sidebar-header">
          <h2>Agent Execution Logs</h2>
        </div>
        <div className="sidebar-content context-logs">
          {logs.length === 0 && <p className="log-entry system-log">Waiting for agent execution...</p>}
          {logs.map((log, index) => (
            <p key={index} className={`log-entry ${log.type}-log`}>
              {log.text}
            </p>
          ))}
          {isLoading && <p className="log-entry active-log">Agent is thinking...</p>}
        </div>
      </aside>

    </div>
  );
}

export default App;