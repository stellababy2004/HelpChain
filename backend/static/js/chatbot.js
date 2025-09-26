/**
 * HelpChain Chatbot Widget JavaScript
 * Модерна интерактивност за чатбот
 */

class HelpChainChatbot {
    constructor() {
        this.isOpen = false;
        this.isInitialized = false;
        this.sessionId = null;
        this.messages = [];
        
        this.init();
    }

    init() {
        this.createWidget();
        this.bindEvents();
        this.initializeChatbot();
    }

    createWidget() {
        const widget = document.createElement('div');
        widget.className = 'chatbot-widget';
        widget.innerHTML = `
            <!-- Toggle бутон -->
            <button class="chatbot-toggle" id="chatbot-toggle">
                <i class="fas fa-comments"></i>
            </button>

            <!-- Чат прозорец -->
            <div class="chatbot-window" id="chatbot-window">
                <!-- Header -->
                <div class="chatbot-header">
                    <div class="chatbot-title">
                        <i class="fas fa-robot"></i>
                        HelpChain Асистент
                    </div>
                    <button class="chatbot-close" id="chatbot-close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>

                <!-- Съдържание -->
                <div class="chatbot-content">
                    <!-- Съобщения -->
                    <div class="chatbot-messages" id="chatbot-messages">
                        <!-- Съобщенията ще се добавят тук -->
                    </div>

                    <!-- Typing indicator -->
                    <div class="typing-indicator" id="typing-indicator">
                        HelpChain асистента пише<span class="typing-dots"></span>
                    </div>

                    <!-- Бързи въпроси -->
                    <div class="quick-questions" id="quick-questions">
                        <!-- Бързите въпроси ще се добавят тук -->
                    </div>

                    <!-- Input област -->
                    <div class="chatbot-input-area">
                        <div class="chatbot-input-container">
                            <textarea 
                                class="chatbot-input" 
                                id="chatbot-input" 
                                placeholder="Напишете съобщение..."
                                rows="1"
                            ></textarea>
                            <button class="chatbot-send" id="chatbot-send">
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(widget);

        // Съхраняваме референции към елементите
        this.toggleBtn = document.getElementById('chatbot-toggle');
        this.window = document.getElementById('chatbot-window');
        this.closeBtn = document.getElementById('chatbot-close');
        this.messagesContainer = document.getElementById('chatbot-messages');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.quickQuestions = document.getElementById('quick-questions');
        this.input = document.getElementById('chatbot-input');
        this.sendBtn = document.getElementById('chatbot-send');
    }

    bindEvents() {
        // Toggle чат
        this.toggleBtn.addEventListener('click', () => this.toggleChat());
        this.closeBtn.addEventListener('click', () => this.closeChat());

        // Изпращане на съобщение
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize на textarea
        this.input.addEventListener('input', () => this.autoResizeTextarea());

        // Затваряне при клик извън чата
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.chatbot-widget') && this.isOpen) {
                this.closeChat();
            }
        });
    }

    async initializeChatbot() {
        try {
            const response = await fetch('/chatbot/init');
            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                this.addMessage(data.welcome_message, 'bot');
                this.showQuickQuestions(data.quick_questions);
                this.isInitialized = true;
            } else {
                console.error('Chatbot initialization failed:', data.message);
            }
        } catch (error) {
            console.error('Error initializing chatbot:', error);
        }
    }

    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }

    openChat() {
        this.isOpen = true;
        this.window.classList.add('open');
        this.toggleBtn.classList.add('active');
        this.input.focus();
        this.scrollToBottom();
    }

    closeChat() {
        this.isOpen = false;
        this.window.classList.remove('open');
        this.toggleBtn.classList.remove('active');
    }

    async sendMessage() {
        const message = this.input.value.trim();
        if (!message || !this.isInitialized) return;

        // Добавяме съобщението на потребителя
        this.addMessage(message, 'user');
        this.input.value = '';
        this.autoResizeTextarea();

        // Показваме typing indicator
        this.showTyping();

        // Скриваме бързите въпроси
        this.hideQuickQuestions();

        try {
            const response = await fetch('/chatbot/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId
                })
            });

            const data = await response.json();
            
            // Скриваме typing indicator
            this.hideTyping();

            if (data.success) {
                this.addMessage(data.message, 'bot');
                
                // Ако има предложения, показваме ги
                if (data.suggestions) {
                    setTimeout(() => {
                        this.showQuickQuestions(data.suggestions);
                    }, 500);
                }
            } else {
                this.addMessage('Възникна грешка. Моля опитайте отново.', 'bot', true);
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTyping();
            this.addMessage('Възникна техническа грешка. Моля опитайте отново.', 'bot', true);
        }
    }

    addMessage(text, sender, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        if (isError) {
            bubbleDiv.style.background = '#f8d7da';
            bubbleDiv.style.color = '#721c24';
            bubbleDiv.style.border = '1px solid #f5c6cb';
        }

        // Форматираме текста (нови редове, links, etc.)
        bubbleDiv.innerHTML = this.formatMessage(text);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString('bg-BG', {
            hour: '2-digit',
            minute: '2-digit'
        });

        messageDiv.appendChild(bubbleDiv);
        messageDiv.appendChild(timeDiv);
        this.messagesContainer.appendChild(messageDiv);

        this.messages.push({ text, sender, timestamp: new Date() });
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Заменяме нови редове с <br>
        text = text.replace(/\n/g, '<br>');
        
        // Заменяме email адреси с links
        text = text.replace(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g, 
            '<a href="mailto:$1" target="_blank">$1</a>');
        
        // Заменяме URLs с links
        text = text.replace(/(https?:\/\/[^\s]+)/g, 
            '<a href="$1" target="_blank">$1</a>');
        
        return text;
    }

    showQuickQuestions(questions) {
        if (!questions || questions.length === 0) return;

        this.quickQuestions.innerHTML = '';
        questions.forEach(question => {
            const btn = document.createElement('div');
            btn.className = 'quick-question';
            btn.textContent = question;
            btn.addEventListener('click', () => {
                this.input.value = question;
                this.sendMessage();
            });
            this.quickQuestions.appendChild(btn);
        });

        this.quickQuestions.classList.add('show');
        this.scrollToBottom();
    }

    hideQuickQuestions() {
        this.quickQuestions.classList.remove('show');
    }

    showTyping() {
        this.typingIndicator.classList.add('show');
        this.sendBtn.disabled = true;
        this.scrollToBottom();
    }

    hideTyping() {
        this.typingIndicator.classList.remove('show');
        this.sendBtn.disabled = false;
    }

    autoResizeTextarea() {
        this.input.style.height = 'auto';
        const newHeight = Math.min(this.input.scrollHeight, 80);
        this.input.style.height = newHeight + 'px';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }

    // Публични методи за управление
    open() {
        this.openChat();
    }

    close() {
        this.closeChat();
    }

    sendCustomMessage(message) {
        if (message) {
            this.input.value = message;
            this.sendMessage();
        }
    }
}

// Инициализираме чатбота когато документът е зареден
document.addEventListener('DOMContentLoaded', function() {
    // Проверяваме дали имаме Font Awesome
    if (!document.querySelector('link[href*="font-awesome"]') && 
        !document.querySelector('link[href*="fontawesome"]')) {
        
        const fontAwesome = document.createElement('link');
        fontAwesome.rel = 'stylesheet';
        fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css';
        document.head.appendChild(fontAwesome);
    }

    // Инициализираме чатбота
    window.helpchainChatbot = new HelpChainChatbot();
});

// Глобални функции за външно управление
window.openHelpChainChat = function() {
    if (window.helpchainChatbot) {
        window.helpchainChatbot.open();
    }
};

window.closeHelpChainChat = function() {
    if (window.helpchainChatbot) {
        window.helpchainChatbot.close();
    }
};

window.sendHelpChainMessage = function(message) {
    if (window.helpchainChatbot) {
        window.helpchainChatbot.sendCustomMessage(message);
    }
};