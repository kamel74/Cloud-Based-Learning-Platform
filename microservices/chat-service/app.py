"""
Chat Service
Handles AI-powered chat functionality using AWS Bedrock
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from kafka import KafkaProducer, KafkaConsumer
import boto3
import json
import os
import threading
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', '10.0.10.10:9092,10.0.10.11:9092,10.0.10.12:9092')
S3_BUCKET = os.getenv('S3_BUCKET', 'chat-service-storage')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# In-memory chat history (use Redis/DynamoDB in production)
chat_sessions = {}

def generate_ai_response(prompt, context=""):
    """Generate AI response using Bedrock"""
    try:
        # Use Amazon Titan which is available by default
        body = json.dumps({
            "inputText": f"Context: {context}\n\nUser: {prompt}\n\nAssistant:",
            "textGenerationConfig": {
                "maxTokenCount": 500,
                "temperature": 0.7,
                "topP": 0.9
            }
        })
        
        response = bedrock.invoke_model(
            modelId='amazon.titan-text-lite-v1',
            body=body,
            contentType='application/json'
        )
        
        result = json.loads(response['body'].read())
        return result.get('results', [{}])[0].get('outputText', 'I could not generate a response.')
        
    except Exception as e:
        logger.error(f"Bedrock error: {str(e)}")
        return f"AI service error: {str(e)}"

def process_chat_message(message):
    """Process chat message from Kafka"""
    try:
        data = json.loads(message.value.decode('utf-8'))
        session_id = data.get('session_id', '')
        user_message = data.get('message', '')
        document_context = data.get('context', '')
        
        response = generate_ai_response(user_message, document_context)
        
        # Store in session
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []
        chat_sessions[session_id].append({
            'user': user_message,
            'assistant': response
        })
        
        logger.info(f"Chat processed for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Chat processing error: {str(e)}")

def start_kafka_consumer():
    """Start Kafka consumer in background"""
    consumer = KafkaConsumer(
        'chat.message',
        bootstrap_servers=KAFKA_BROKERS.split(','),
        group_id='chat-service-group',
        auto_offset_reset='earliest'
    )
    
    for message in consumer:
        process_chat_message(message)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'chat-service'})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat message"""
    try:
        data = request.json
        session_id = data.get('session_id', '')
        message = data.get('message', '')
        context = data.get('context', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Generate response synchronously for better UX
        response = generate_ai_response(message, context)
        
        # Store in session
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []
        chat_sessions[session_id].append({
            'user': message,
            'assistant': response
        })
        
        # Also publish to Kafka for logging
        producer.send('chat.message', {
            'session_id': session_id,
            'message': message,
            'context': context
        })
        
        return jsonify({
            'response': response,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Chat API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/history/<session_id>', methods=['GET'])
def get_history(session_id):
    """Get chat history for session"""
    history = chat_sessions.get(session_id, [])
    return jsonify({'history': history})

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5003)
