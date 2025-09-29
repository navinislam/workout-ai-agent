// Chat application JavaScript
class ChatApp {
    constructor() {
        this.conversationHistory = [];
        this.isLoading = false;
        this.currentProfile = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSettings();
        this.checkHealth();
        this.autoResizeTextarea();
    }

    bindEvents() {
        // Send message
        const sendButton = document.getElementById('sendButton');
        const messageInput = document.getElementById('messageInput');
        
        sendButton.addEventListener('click', () => this.sendMessage());
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Clear chat
        document.getElementById('clearButton').addEventListener('click', () => this.clearChat());

        // Add document modal
        document.getElementById('addDocumentButton').addEventListener('click', () => this.showDocumentModal());
        document.getElementById('cancelDocumentButton').addEventListener('click', () => this.hideDocumentModal());
        document.getElementById('submitDocumentButton').addEventListener('click', () => this.addDocument());
        document.querySelector('.close').addEventListener('click', () => this.hideDocumentModal());

        // Save API key
        document.getElementById('saveKeyButton').addEventListener('click', () => this.saveApiKey());

        // Modal close on outside click
        window.addEventListener('click', (e) => {
            const modal = document.getElementById('documentModal');
            if (e.target === modal) {
                this.hideDocumentModal();
            }
        });
    }

    autoResizeTextarea() {
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value.trim();
        
        if (!message || this.isLoading) return;

        // Add user message to chat
        this.addMessageToChat('user', message);
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // Show typing indicator
        this.showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    profile: this.currentProfile,
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // Track merged profile from backend so follow-ups are stateful
                this.currentProfile = data.profile;

                // Render clarifying questions if any
                if (data.questions && data.questions.length) {
                    const qText = data.questions.map((q, i) => `Q${i+1}: ${q}`).join('\n');
                    this.addMessageToChat('assistant', qText);
                }

                // Always show a compact plan summary so user gets an answer
                if (data.plan) {
                    const planText = this.formatPlanSummary(data.plan);
                    this.addMessageToChat('assistant', planText);
                }
                // Update sources
                // this.updateSources(data.sources);
            } else {
                this.addMessageToChat('assistant', `Error: ${data.detail || 'Failed to get response'}`);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessageToChat('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            this.hideTypingIndicator();
        }
    }

    addMessageToChat(role, content) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        if (role === 'user') {
            messageContent.innerHTML = `<i class="fas fa-user"></i>${this.escapeHtml(content)}`;
        } else if (role === 'assistant') {
            messageContent.innerHTML = `<i class="fas fa-robot"></i>${this.escapeHtml(content)}`;
        } else {
            messageContent.innerHTML = content;
        }
        
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Add to conversation history
        this.conversationHistory.push({ role, content });
        
        // Keep only last 20 messages
        if (this.conversationHistory.length > 20) {
            this.conversationHistory = this.conversationHistory.slice(-20);
        }
    }

    formatPlanSummary(plan) {
        try {
            const days = plan.days || [];
            const header = `Planned Week: ${days.length} day(s)`;
            const lines = days.slice(0, 4).map((d, idx) => {
                const firstBlock = (d.blocks && d.blocks[0]) ? d.blocks[0] : null;
                const exNames = firstBlock && firstBlock.exercises ? firstBlock.exercises.map(e => e.name).slice(0, 2).join(', ') : '—';
                return `Day ${idx+1} - ${d.name}: ${exNames}`;
            });
            return [header, ...lines].join('\n');
        } catch (e) {
            return 'Generated a plan.';
        }
    }

    showTypingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant';
        typingDiv.id = 'typingIndicator';
        
        const typingContent = document.createElement('div');
        typingContent.className = 'typing-indicator';
        typingContent.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        
        typingDiv.appendChild(typingContent);
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        this.isLoading = true;
    }

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        this.isLoading = false;
    }

    updateSources(sources) {
        const sourcesList = document.getElementById('sourcesList');
        
        if (!sources || sources.length === 0) {
            sourcesList.innerHTML = '<p class="no-sources">No sources found for current query</p>';
            return;
        }

        sourcesList.innerHTML = '';
        sources.forEach((source, index) => {
            const sourceDiv = document.createElement('div');
            sourceDiv.className = 'source-item';
            sourceDiv.innerHTML = `
                <h4>Source ${index + 1}</h4>
                <p>${this.escapeHtml(source.text.substring(0, 200))}${source.text.length > 200 ? '...' : ''}</p>
                <p class="score">Relevance: ${(source.score * 100).toFixed(1)}%</p>
                ${source.metadata ? `<p><small>${this.escapeHtml(source.metadata)}</small></p>` : ''}
            `;
            sourcesList.appendChild(sourceDiv);
        });
    }

    clearChat() {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="message system-message">
                <div class="message-content">
                    <i class="fas fa-info-circle"></i>
                    Welcome! I'm your AI assistant powered by ChatGPT and enhanced with RAG (Retrieval-Augmented Generation). 
                    I can help you with questions and provide context-aware responses using the knowledge base.
                </div>
            </div>
        `;
        this.conversationHistory = [];
        this.updateSources([]);
    }

    showDocumentModal() {
        document.getElementById('documentModal').style.display = 'block';
        document.getElementById('documentText').focus();
    }

    hideDocumentModal() {
        document.getElementById('documentModal').style.display = 'none';
        document.getElementById('documentText').value = '';
        document.getElementById('documentMetadata').value = '';
    }

    async addDocument() {
        const text = document.getElementById('documentText').value.trim();
        const metadata = document.getElementById('documentMetadata').value.trim();
        
        if (!text) {
            alert('Please enter document text');
            return;
        }

        const submitButton = document.getElementById('submitDocumentButton');
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
        submitButton.disabled = true;

        try {
            const response = await fetch('/api/add-document', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    metadata: metadata
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                alert('Document added successfully!');
                this.hideDocumentModal();
            } else {
                alert(`Error: ${data.detail || 'Failed to add document'}`);
            }
        } catch (error) {
            console.error('Error adding document:', error);
            alert('Error adding document. Please try again.');
        } finally {
            submitButton.innerHTML = originalText;
            submitButton.disabled = false;
        }
    }

    saveApiKey() {
        const apiKey = document.getElementById('openaiKey').value.trim();
        if (apiKey) {
            localStorage.setItem('openai_api_key', apiKey);
            alert('API key saved!');
        } else {
            alert('Please enter an API key');
        }
    }

    loadSettings() {
        const savedApiKey = localStorage.getItem('openai_api_key');
        if (savedApiKey) {
            document.getElementById('openaiKey').value = savedApiKey;
        }
    }

    async checkHealth() {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();
            
            const apiStatus = document.getElementById('apiStatus');
            const milvusStatus = document.getElementById('milvusStatus');
            
            if (response.ok) {
                apiStatus.textContent = 'Healthy';
                apiStatus.className = 'status-value healthy';
                
                if (data.milvus_connected) {
                    milvusStatus.textContent = 'Connected';
                    milvusStatus.className = 'status-value healthy';
                } else {
                    milvusStatus.textContent = 'Disconnected';
                    milvusStatus.className = 'status-value error';
                }
            } else {
                apiStatus.textContent = 'Error';
                apiStatus.className = 'status-value error';
                milvusStatus.textContent = 'Unknown';
                milvusStatus.className = 'status-value error';
            }
        } catch (error) {
            console.error('Health check failed:', error);
            document.getElementById('apiStatus').textContent = 'Error';
            document.getElementById('apiStatus').className = 'status-value error';
            document.getElementById('milvusStatus').textContent = 'Unknown';
            document.getElementById('milvusStatus').className = 'status-value error';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the chat application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
}); 
