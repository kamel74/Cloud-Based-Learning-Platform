"""
STT (Speech-to-Text) Service
Converts audio files to text using AWS Transcribe
"""
from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
import boto3
import json
import os
import threading
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', '10.0.10.10:9092,10.0.10.11:9092,10.0.10.12:9092')
S3_BUCKET = os.getenv('S3_BUCKET', 'stt-service-storage')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
transcribe = boto3.client('transcribe', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def process_stt_request(message):
    """Process STT request from Kafka"""
    try:
        data = json.loads(message.value.decode('utf-8'))
        audio_url = data.get('audio_url', '')
        document_id = data.get('document_id', '')
        
        job_name = f"transcribe-{document_id}-{int(time.time())}"
        
        # Start transcription job
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': audio_url},
            MediaFormat='mp3',
            LanguageCode='en-US',
            OutputBucketName=S3_BUCKET
        )
        
        # Wait for job completion (simplified)
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status == 'COMPLETED':
                transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                producer.send('document.processed', {
                    'document_id': document_id,
                    'transcript_url': transcript_uri,
                    'status': 'completed'
                })
                break
            elif job_status == 'FAILED':
                logger.error(f"Transcription failed for: {document_id}")
                break
            
            time.sleep(5)
        
        logger.info(f"STT completed for document: {document_id}")
        
    except Exception as e:
        logger.error(f"STT processing error: {str(e)}")

def start_kafka_consumer():
    """Start Kafka consumer in background"""
    consumer = KafkaConsumer(
        'stt.requested',
        bootstrap_servers=KAFKA_BROKERS.split(','),
        group_id='stt-service-group',
        auto_offset_reset='earliest'
    )
    
    for message in consumer:
        process_stt_request(message)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'stt-service'})

@app.route('/api/stt', methods=['POST'])
def speech_to_text():
    """Convert speech to text"""
    try:
        data = request.json
        audio_url = data.get('audio_url', '')
        document_id = data.get('document_id', '')
        
        if not audio_url:
            return jsonify({'error': 'Audio URL is required'}), 400
        
        # Publish to Kafka for async processing
        producer.send('stt.requested', {
            'audio_url': audio_url,
            'document_id': document_id
        })
        
        return jsonify({
            'message': 'STT request submitted',
            'document_id': document_id
        }), 202
        
    except Exception as e:
        logger.error(f"STT API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5002)
