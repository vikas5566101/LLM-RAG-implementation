import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Engine initialized. What process scale-up questions can I help you with today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // State to hold our agent execution logs
  const [logs, setLogs] = useState([]); 
  
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const clearChat = () => {
    setMessages([{ role: 'ai', content: 'Memory cleared. New session started.' }]);
    setLogs([]);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setLogs((prev) => [...prev, { type: 'system', text: 'Initiating AI thought process...' }]);

    setMessages((prev) => [...prev, { role: 'ai', content: '' }]);

    try {
      const response = await fetch('http://127.0.0.1:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: userMessage.content,
          chat_history: messages.filter(m => m.content !== '') 
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Check if the buffer contains our special tool markers
        if (buffer.includes(':::')) {
          const parts = buffer.split(':::');
          buffer = parts.pop(); // Keep the unfinished part in the buffer
          
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
          // If it's normal text, stream it to the chat bubble
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
          buffer = ""; // Clear buffer after updating chat
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
      
      {/* LEFT SIDEBAR: System Status */}
      <aside className="sidebar left-sidebar">
        <div className="sidebar-header">
          <h2>i-HEMS Workspace</h2>
        </div>
        <div className="sidebar-content">
          <div className="status-card">
            <h3>System Vitals</h3>
            <ul>
              <li>🟢 <span>Engine:</span> Llama 3.2 (3B)</li>
              <li>🟢 <span>Vector DB:</span> Chroma Active</li>
              <li>🟢 <span>Memory:</span> Stateful</li>
            </ul>
          </div>
          <div className="status-card">
            <h3>Loaded Manuals</h3>
            <ul className="doc-list">
              <li>📄 OISD_Standard_118.pdf</li>
              <li>📄 Perry_Chem_Eng.pdf</li>
            </ul>
          </div>
        </div>
      </aside>

      {/* CENTER COLUMN: The Chat Interface */}
      <main className="main-chat-area">
        <header className="chat-header">
          <span>⚙️ Senior Process Engineer</span>
          <button className="clear-btn" onClick={clearChat} title="Clear Memory">🗑️ Clear</button>
        </header>
        
        <div className="chat-box">
          {messages.map((msg, index) => (
            <div key={index} className={`message-wrapper ${msg.role === 'user' ? 'user-wrapper' : 'ai-wrapper'}`}>
              {/* Added Avatar Placeholders */}
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
          <button type="button" className="attach-btn" title="Upload Document">📎</button>
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            placeholder="Ask an engineering question..." 
            disabled={isLoading}
          />
          <button type="submit" className="send-btn" disabled={isLoading || !input.trim()}>Send</button>
        </form>
      </main>

      {/* RIGHT SIDEBAR: Agent Context */}
      <aside className="sidebar right-sidebar">
        <div className="sidebar-header">
          <h2>Agent Execution Logs</h2>
        </div>
        <div className="sidebar-content context-logs">
          
          {/* Default message if there are no logs yet */}
          {logs.length === 0 && <p className="log-entry system-log">Waiting for agent execution...</p>}
          
          {/* Dynamically render all logs as they stream in */}
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