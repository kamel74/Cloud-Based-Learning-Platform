"""
TTS (Text-to-Speech) Service
Converts text to audio files using AWS Polly
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
S3_BUCKET = os.getenv('S3_BUCKET', 'tts-service-storage')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
polly = boto3.client('polly', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def process_tts_request(message):
    """Process TTS request from Kafka"""
    try:
        data = json.loads(message.value.decode('utf-8'))
        text = data.get('text', '')
        document_id = data.get('document_id', '')
        voice_id = data.get('voice_id', 'Joanna')
        
        # Generate audio using Polly
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id
        )
        
        # Save to S3
        audio_key = f"audio/{document_id}.mp3"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=audio_key,
            Body=response['AudioStream'].read(),
            ContentType='audio/mpeg'
        )
        
        # Publish completion event
        producer.send('notes.generated', {
            'document_id': document_id,
            'audio_url': f"s3://{S3_BUCKET}/{audio_key}",
            'status': 'completed'
        })
        
        logger.info(f"TTS completed for document: {document_id}")
        
    except Exception as e:
        logger.error(f"TTS processing error: {str(e)}")

def start_kafka_consumer():
    """Start Kafka consumer in background"""
    consumer = KafkaConsumer(
        'tts.requested',
        bootstrap_servers=KAFKA_BROKERS.split(','),
        group_id='tts-service-group',
        auto_offset_reset='earliest'
    )
    
    for message in consumer:
        process_tts_request(message)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'tts-service'})

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """Convert text to speech synchronously"""
    try:
        data = request.json
        text = data.get('text', '')
        voice_id = data.get('voice_id', 'Joanna')
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Generate audio using Polly synchronously
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id
        )
        
        # Read audio stream and encode as base64
        import base64
        audio_data = response['AudioStream'].read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        logger.info(f"TTS generated successfully for text: {text[:50]}...")
        
        return jsonify({
            'message': 'Audio generated successfully',
            'audio': audio_base64,
            'content_type': 'audio/mpeg'
        })
        
    except Exception as e:
        logger.error(f"TTS API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Start Kafka consumer thread
    consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5001)
