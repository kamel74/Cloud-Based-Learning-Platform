"""
Document Reader Service
Handles PDF/document processing and text extraction
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from kafka import KafkaProducer, KafkaConsumer
import boto3
import json
import os
import threading
import logging
from io import BytesIO

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', '10.0.10.10:9092,10.0.10.11:9092,10.0.10.12:9092')
S3_BUCKET = os.getenv('S3_BUCKET', 'document-reader-storage')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
textract = boto3.client('textract', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def extract_text_from_document(bucket, key):
    """Extract text from document using Textract"""
    try:
        response = textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )
        
        text = ""
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text += block.get('Text', '') + "\n"
        
        return text
        
    except Exception as e:
        logger.error(f"Textract error: {str(e)}")
        return ""

def process_document_upload(message):
    """Process document upload from Kafka"""
    try:
        data = json.loads(message.value.decode('utf-8'))
        document_id = data.get('document_id', '')
        s3_key = data.get('s3_key', '')
        bucket = data.get('bucket', S3_BUCKET)
        
        # Extract text
        extracted_text = extract_text_from_document(bucket, s3_key)
        
        # Save extracted text
        text_key = f"extracted/{document_id}.txt"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=text_key,
            Body=extracted_text.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Publish completion event
        producer.send('document.processed', {
            'document_id': document_id,
            'text_url': f"s3://{S3_BUCKET}/{text_key}",
            'text_preview': extracted_text[:500],
            'status': 'completed'
        })
        
        logger.info(f"Document processed: {document_id}")
        
    except Exception as e:
        logger.error(f"Document processing error: {str(e)}")

def start_kafka_consumer():
    """Start Kafka consumer in background"""
    consumer = KafkaConsumer(
        'document.uploaded',
        bootstrap_servers=KAFKA_BROKERS.split(','),
        group_id='document-reader-group',
        auto_offset_reset='earliest'
    )
    
    for message in consumer:
        process_document_upload(message)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'document-reader-service'})

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload and process document"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        document_id = request.form.get('document_id', file.filename)
        
        # Upload to S3
        s3_key = f"uploads/{document_id}"
        s3.upload_fileobj(file, S3_BUCKET, s3_key)
        
        # Publish to Kafka
        producer.send('document.uploaded', {
            'document_id': document_id,
            's3_key': s3_key,
            'bucket': S3_BUCKET
        })
        
        return jsonify({
            'message': 'Document uploaded successfully',
            'document_id': document_id
        }), 202
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get processed document text"""
    try:
        text_key = f"extracted/{document_id}.txt"
        response = s3.get_object(Bucket=S3_BUCKET, Key=text_key)
        text = response['Body'].read().decode('utf-8')
        
        return jsonify({
            'document_id': document_id,
            'text': text
        })
        
    except Exception as e:
        logger.error(f"Get document error: {str(e)}")
        return jsonify({'error': 'Document not found'}), 404

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5004)
