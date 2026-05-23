const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Add User's message to the chat
    appendMessage('You', text, 'user-message');
    userInput.value = '';
    
    // 2. Show a loading indicator
    const loadingId = appendMessage('System', 'Engine is calculating... (This may take a minute based on CPU limits)', 'ai-message');
    sendBtn.disabled = true;

    try {
        // 3. Send the request to your Python Backend
        const response = await fetch('http://127.0.0.1:8000/api/ask-engineer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text })
        });

        if (!response.ok) throw new Error("Backend request failed");

        const data = await response.json();
        
        // 4. Remove loading text and add the real answer
        document.getElementById(loadingId).remove();
        appendMessage('Process Engineer', data.answer, 'ai-message');

    } catch (error) {
        console.error(error);
        document.getElementById(loadingId).innerText = "Error: Could not connect to the backend server.";
    } finally {
        sendBtn.disabled = false;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// Helper function to draw messages on the screen
function appendMessage(sender, text, className) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${className}`;
    
    // Create a unique ID for loading messages so we can delete them later
    const id = 'msg-' + Date.now();
    msgDiv.id = id;
    
    msgDiv.innerHTML = `<strong>${sender}:</strong><br/>${text}`;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to bottom
    
    return id;
}

// Allow pressing "Enter" to send the message
userInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});