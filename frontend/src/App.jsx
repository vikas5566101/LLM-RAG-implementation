import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

function App() {
  // --- STATE ---
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
  // Load sessions when the app starts
  useEffect(() => {
    fetchSessions();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- DATABASE FUNCTIONS ---
  const fetchSessions = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/sessions');
      const data = await response.json();
      setSessions(data);
      
      // If we have sessions, load the most recent one. Otherwise, create a new one.
      if (data.length > 0) {
        loadSession(data[0].session_id);
      } else {
        startNewSession();
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  };

  const startNewSession = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/sessions', { method: 'POST' });
      const data = await response.json();
      setCurrentSessionId(data.session_id);
      setMessages([{ role: 'ai', content: 'New persistent session started. How can I assist you today?' }]);
      setLogs([]); // Clear logs for new chat
      fetchSessions(); // Refresh the sidebar
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  const loadSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    setLogs([{ type: 'system', text: `> Loaded session: ${sessionId}` }]);
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/sessions/${sessionId}/messages`);
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

  // --- CHAT & UPLOAD FUNCTIONS ---
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

    // Add empty AI message bubble for streaming
    setMessages((prev) => [...prev, { role: 'ai', content: '' }]);

    try {
      const response = await fetch('http://127.0.0.1:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: userMessage.content,
          session_id: currentSessionId // NEW: Only sending the ID now!
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
          // Stream normal text to the chat bubble
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
                  💬 {session.title}
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
        <header className="chat-header">
          <span>⚙️ Senior Process Engineer (Session: {currentSessionId?.substring(0,6)}...)</span>
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