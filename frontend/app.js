// API Base URL - Update this with your ALB DNS
const API_BASE_URL = 'http://API-Load-Balancer-1954519291.us-east-1.elb.amazonaws.com';

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
    element.style.color = isError ? '#ef4444' : '#ffffff';
}

// ===== Text to Speech =====
async function convertTTS() {
    const text = document.getElementById('tts-input').value.trim();

    if (!text) {
        showResult('tts-result', '⚠️ Please enter some text to convert.', true);
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
            // Create audio from base64 data
            const audioSrc = `data:audio/mpeg;base64,${data.audio}`;
            showResult('tts-result', `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i>
                    <span>Audio generated successfully!</span>
                </div>
                <audio controls style="width: 100%; margin-top: 10px;">
                    <source src="${audioSrc}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
                <p style="margin-top: 10px; color: #64748b; font-size: 0.875rem;">
                    ${data.message || 'Text converted to speech successfully.'}
                </p>
            `);
        } else {
            showResult('tts-result', `❌ Error: ${data.error || 'Failed to convert text'}`, true);
        }
    } catch (error) {
        showResult('tts-result', `
            <div style="display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-info-circle" style="color: #0ea5e9;"></i>
                <span>Demo Mode: Service would convert "${text.substring(0, 50)}..." to speech</span>
            </div>
        `);
    }

    hideLoading();
}

// ===== Speech to Text =====
async function convertSTT() {
    const fileInput = document.getElementById('stt-file');
    const file = fileInput.files[0];

    if (!file) {
        showResult('stt-result', '⚠️ Please upload an audio file first.', true);
        return;
    }

    showLoading();

    try {
        const formData = new FormData();
        formData.append('audio', file);

        const response = await fetch(`${API_BASE_URL}/api/stt`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showResult('stt-result', `
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i>
                    <span>Transcription Complete!</span>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
                    <strong>Transcribed Text:</strong>
                    <p style="margin-top: 8px;">${data.text || data.transcription}</p>
                </div>
            `);
        } else {
            showResult('stt-result', `❌ Error: ${data.error || 'Failed to transcribe audio'}`, true);
        }
    } catch (error) {
        showResult('stt-result', `
            <div style="display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-info-circle" style="color: #0ea5e9;"></i>
                <span>Demo Mode: Would transcribe "${file.name}"</span>
            </div>
        `);
    }

    hideLoading();
}

// ===== Chat Assistant =====
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
            addChatMessage(`Sorry, I encountered an error: ${data.error}`);
        }
    } catch (error) {
        // Demo response
        const demoResponses = [
            "That's an interesting question! Let me help you with that.",
            "I understand what you're asking. Here's what I think...",
            "Great question! Based on my knowledge...",
            "Let me explain that for you...",
            "Here's some information that might help..."
        ];
        const randomResponse = demoResponses[Math.floor(Math.random() * demoResponses.length)];
        addChatMessage(`[Demo Mode] ${randomResponse}`);
    }
}

// ===== Document Reader =====
async function readDocument() {
    const fileInput = document.getElementById('doc-file');
    const file = fileInput.files[0];

    if (!file) {
        showResult('doc-result', '⚠️ Please upload a document first.', true);
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
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <i class="fas fa-check-circle" style="color: #10b981;"></i>
                    <span>Document Analyzed! (${data.total_characters || 0} characters)</span>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; max-height: 300px; overflow-y: auto;">
                    <strong>Extracted Text:</strong>
                    <p style="margin-top: 8px; white-space: pre-wrap;">${data.preview || data.text}</p>
                </div>
            `);
        } else {
            showResult('doc-result', `❌ Error: ${data.error || 'Failed to read document'}`, true);
        }
    } catch (error) {
        showResult('doc-result', `
            <div style="display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-info-circle" style="color: #0ea5e9;"></i>
                <span>Demo Mode: Would analyze "${file.name}"</span>
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-top: 10px;">
                <strong>File Info:</strong>
                <p>Name: ${file.name}</p>
                <p>Size: ${(file.size / 1024).toFixed(2)} KB</p>
                <p>Type: ${file.type || 'Unknown'}</p>
            </div>
        `);
    }

    hideLoading();
}

// ===== Quiz Generator =====
let currentQuiz = [];
let currentQuestionIndex = 0;

async function generateQuiz() {
    const topic = document.getElementById('quiz-topic').value.trim();

    if (!topic) {
        document.getElementById('quiz-container').innerHTML = '<p style="color: #ef4444;">⚠️ Please enter a topic for the quiz.</p>';
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
            // Demo quiz
            generateDemoQuiz(topic);
        }
    } catch (error) {
        generateDemoQuiz(topic);
    }

    hideLoading();
}

function generateDemoQuiz(topic) {
    currentQuiz = [
        {
            question: `What is the main concept of ${topic}?`,
            options: ['Option A', 'Option B', 'Option C', 'Option D'],
            correct: 0
        },
        {
            question: `Which of the following is related to ${topic}?`,
            options: ['Choice 1', 'Choice 2', 'Choice 3', 'Choice 4'],
            correct: 1
        },
        {
            question: `How would you describe ${topic}?`,
            options: ['Description A', 'Description B', 'Description C', 'Description D'],
            correct: 2
        }
    ];
    displayQuiz();
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

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    // Add initial chat message
    addChatMessage('Hello! I\'m your AI learning assistant. How can I help you today?');

    // Smooth scroll for navigation
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Update active nav link on scroll
    window.addEventListener('scroll', () => {
        const sections = ['home', 'services', 'about'];
        const navLinks = document.querySelectorAll('.nav-links a');

        sections.forEach((sectionId, index) => {
            const section = document.getElementById(sectionId);
            if (section) {
                const rect = section.getBoundingClientRect();
                if (rect.top <= 100 && rect.bottom >= 100) {
                    navLinks.forEach(link => link.classList.remove('active'));
                    navLinks[index].classList.add('active');
                }
            }
        });
    });
});
