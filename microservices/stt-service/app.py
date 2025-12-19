"""
STT (Speech-to-Text) Service
Converts audio files to text using AWS Transcribe
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import json
import os
import logging
import time
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
S3_BUCKET = os.getenv('S3_BUCKET', 'shared-assets-storage-ih1qtx')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
transcribe = boto3.client('transcribe', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'stt-service'})

@app.route('/api/stt', methods=['POST'])
def speech_to_text():
    """Convert speech to text - handles file upload"""
    try:
        # Check if file was uploaded
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        # Generate unique filename
        file_ext = audio_file.filename.rsplit('.', 1)[-1].lower() if '.' in audio_file.filename else 'mp3'
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"audio-uploads/{unique_id}.{file_ext}"
        
        # Upload to S3
        logger.info(f"Uploading audio to S3: {s3_key}")
        s3.upload_fileobj(audio_file, S3_BUCKET, s3_key)
        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        
        # Determine media format
        media_format_map = {
            'mp3': 'mp3',
            'mp4': 'mp4',
            'wav': 'wav',
            'flac': 'flac',
            'ogg': 'ogg',
            'webm': 'webm'
        }
        media_format = media_format_map.get(file_ext, 'mp3')
        
        # Start transcription job
        job_name = f"transcribe-{unique_id}-{int(time.time())}"
        logger.info(f"Starting transcription job: {job_name}")
        
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': s3_uri},
            MediaFormat=media_format,
            LanguageCode='en-US'
        )
        
        # Poll for completion (max 60 seconds)
        max_wait = 60
        wait_time = 0
        while wait_time < max_wait:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status == 'COMPLETED':
                # Get transcript
                transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # Fetch the transcript
                import urllib.request
                with urllib.request.urlopen(transcript_uri) as response:
                    transcript_data = json.loads(response.read().decode('utf-8'))
                
                transcript_text = transcript_data['results']['transcripts'][0]['transcript']
                
                logger.info(f"Transcription completed: {transcript_text[:100]}...")
                
                return jsonify({
                    'message': 'Transcription completed',
                    'text': transcript_text,
                    'transcription': transcript_text
                })
                
            elif job_status == 'FAILED':
                error_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown error')
                logger.error(f"Transcription failed: {error_reason}")
                return jsonify({'error': f'Transcription failed: {error_reason}'}), 500
            
            time.sleep(3)
            wait_time += 3
        
        return jsonify({'error': 'Transcription timeout - please try a shorter audio file'}), 504
        
    except Exception as e:
        logger.error(f"STT API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)

