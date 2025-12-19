// API Base URL - Update this with your ALB DNS
const API_BASE_URL = 'http://API-Load-Balancer-1954519291.us-east-1.elb.amazonaws.com';

// ===== Page Navigation =====
function switchPage(pageName) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    // Show selected page
    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageName) {
            item.classList.add('active');
        }
    });

    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'tts': 'Text to Speech',
        'chat': 'AI Chat',
        'quiz': 'Quiz Generator',
        'documents': 'Document Reader'
    };
    document.getElementById('page-title').textContent = titles[pageName] || 'Dashboard';

    // Close sidebar on mobile
    document.querySelector('.sidebar').classList.remove('open');
}

function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}

// ===== Utility Functions =====
function showLoading() {
    document.getElementById('loading-overlay').classList.add('show');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('show');
}

function showResult(elementId, content, isError = false) {
    const element = document.getElementById(elementId);
    element.innerHTML = content;
    element.classList.add('show');
    element.style.color = isError ? '#ef4444' : '#f8fafc';
}

// ===== Text to Speech =====
async function convertTTS() {
    const text = document.getElementById('tts-input').value.trim();

    if (!text) {
        showResult('tts-result', '<p style="color: #f59e0b;"><i class="fas fa-exclamation-triangle"></i> Please enter some text to convert.</p>', true);
        return;
    }

    showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/api/tts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });

        const data = await response.json();

        if (response.ok && data.audio) {
            const audioSrc = `data:audio/mpeg;base64,${data.audio}`;
            showResult('tts-result', `
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                    <i class="fas fa-check-circle" style="color: #10b981; font-size: 1.25rem;"></i>
                    <span style="font-weight: 600;">Audio Generated Successfully!</span>
                </div>
                <audio controls style="width: 100%;">
                    <source src="${audioSrc}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            `);
        } else {
            showResult('tts-result', `<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> ${data.error || 'Failed to convert text'}</p>`, true);
        }
    } catch (error) {
        showResult('tts-result', `<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> Connection error: ${error.message}</p>`, true);
    }

    hideLoading();
}

// ===== Chat =====
const chatMessages = [];

function addChatMessage(message, isUser = false) {
    chatMessages.push({ message, isUser });

    const chatBox = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${isUser ? 'user' : 'bot'}`;
    messageDiv.textContent = message;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function handleChatKeypress(event) {
    if (event.key === 'Enter') {
        sendChat();
    }
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    addChatMessage(message, true);
    input.value = '';

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        if (response.ok) {
            addChatMessage(data.response || data.reply);
        } else {
            addChatMessage('Sorry, I could not process your request.');
        }
    } catch (error) {
        addChatMessage('Connection error. Please try again.');
    }
}

// ===== Quiz Generator =====
let currentQuiz = [];

async function generateQuiz() {
    const topic = document.getElementById('quiz-topic').value.trim();

    if (!topic) {
        document.getElementById('quiz-container').innerHTML = '<p style="color: #f59e0b;"><i class="fas fa-exclamation-triangle"></i> Please enter a topic for the quiz.</p>';
        return;
    }

    showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/api/quiz/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ topic: topic, count: 5 })
        });

        const data = await response.json();

        if (response.ok && data.questions) {
            currentQuiz = data.questions;
            displayQuiz();
        } else {
            document.getElementById('quiz-container').innerHTML = '<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> Failed to generate quiz. Please try again.</p>';
        }
    } catch (error) {
        document.getElementById('quiz-container').innerHTML = '<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> Connection error. Please try again.</p>';
    }

    hideLoading();
}

function displayQuiz() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';

    currentQuiz.forEach((q, qIndex) => {
        const questionDiv = document.createElement('div');
        questionDiv.className = 'quiz-question';
        questionDiv.innerHTML = `
            <h4>Question ${qIndex + 1}: ${q.question}</h4>
            <div class="quiz-options">
                ${q.options.map((opt, oIndex) => `
                    <div class="quiz-option" onclick="checkAnswer(${qIndex}, ${oIndex}, this)">
                        ${String.fromCharCode(65 + oIndex)}. ${opt}
                    </div>
                `).join('')}
            </div>
        `;
        container.appendChild(questionDiv);
    });
}

function checkAnswer(questionIndex, optionIndex, element) {
    const question = currentQuiz[questionIndex];
    const options = element.parentElement.querySelectorAll('.quiz-option');

    // Disable all options
    options.forEach(opt => {
        opt.style.pointerEvents = 'none';
    });

    // Show correct/incorrect
    if (optionIndex === question.correct) {
        element.classList.add('correct');
    } else {
        element.classList.add('incorrect');
        options[question.correct].classList.add('correct');
    }
}

// ===== Document Reader =====
async function readDocument() {
    const fileInput = document.getElementById('doc-file');
    const file = fileInput.files[0];

    if (!file) {
        showResult('doc-result', '<p style="color: #f59e0b;"><i class="fas fa-exclamation-triangle"></i> Please upload a document first.</p>', true);
        return;
    }

    showLoading();

    try {
        const formData = new FormData();
        formData.append('document', file);

        const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && (data.text || data.preview)) {
            showResult('doc-result', `
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                    <i class="fas fa-check-circle" style="color: #10b981; font-size: 1.25rem;"></i>
                    <span style="font-weight: 600;">Document Analyzed! (${data.total_characters || 0} characters)</span>
                </div>
                <div style="background: #0f172a; padding: 15px; border-radius: 10px; max-height: 300px; overflow-y: auto;">
                    <pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">${data.preview || data.text}</pre>
                </div>
            `);
        } else {
            showResult('doc-result', `<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> ${data.error || 'Failed to read document'}</p>`, true);
        }
    } catch (error) {
        showResult('doc-result', `<p style="color: #ef4444;"><i class="fas fa-times-circle"></i> Connection error: ${error.message}</p>`, true);
    }

    hideLoading();
}

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    // Setup nav click handlers
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchPage(item.dataset.page);
        });
    });

    // Add initial chat message
    addChatMessage('Hello! I\'m your AI learning assistant powered by AWS Bedrock. How can I help you today?');

    // File upload label update
    document.getElementById('doc-file').addEventListener('change', function () {
        const zone = this.closest('.upload-zone');
        if (this.files[0]) {
            zone.querySelector('span').textContent = this.files[0].name;
        }
    });
});
