"""
Quiz Service
Generates quizzes from document content using AI
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
S3_BUCKET = os.getenv('S3_BUCKET', 'quiz-service-storage')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def generate_quiz(text, num_questions=5):
    """Generate quiz questions using Bedrock"""
    try:
        prompt = f"""Based on the following text, generate {num_questions} multiple choice questions.
        
Text: {text[:3000]}

Generate questions in JSON format:
[{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A", "explanation": "..."}}]

Only respond with valid JSON array."""

        body = json.dumps({
            "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
            "max_tokens_to_sample": 2000,
            "temperature": 0.5,
        })
        
        response = bedrock.invoke_model(
            modelId='anthropic.claude-v2',
            body=body,
            contentType='application/json'
        )
        
        result = json.loads(response['body'].read())
        completion = result.get('completion', '[]')
        
        # Parse JSON from response
        try:
            questions = json.loads(completion)
            return questions
        except:
            return []
        
    except Exception as e:
        logger.error(f"Quiz generation error: {str(e)}")
        return []

def process_quiz_request(message):
    """Process quiz request from Kafka"""
    try:
        data = json.loads(message.value.decode('utf-8'))
        document_id = data.get('document_id', '')
        text = data.get('text', '')
        num_questions = data.get('num_questions', 5)
        
        # Generate quiz
        questions = generate_quiz(text, num_questions)
        
        # Save to S3
        quiz_key = f"quizzes/{document_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=quiz_key,
            Body=json.dumps(questions).encode('utf-8'),
            ContentType='application/json'
        )
        
        # Publish completion event
        producer.send('quiz.generated', {
            'document_id': document_id,
            'quiz_url': f"s3://{S3_BUCKET}/{quiz_key}",
            'num_questions': len(questions),
            'status': 'completed'
        })
        
        logger.info(f"Quiz generated for document: {document_id}")
        
    except Exception as e:
        logger.error(f"Quiz processing error: {str(e)}")

def start_kafka_consumer():
    """Start Kafka consumer in background"""
    consumer = KafkaConsumer(
        'quiz.requested',
        bootstrap_servers=KAFKA_BROKERS.split(','),
        group_id='quiz-service-group',
        auto_offset_reset='earliest'
    )
    
    for message in consumer:
        process_quiz_request(message)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'quiz-service'})

@app.route('/api/quiz/generate', methods=['POST'])
def create_quiz():
    """Generate quiz from text"""
    try:
        data = request.json
        document_id = data.get('document_id', '')
        text = data.get('text', '')
        num_questions = data.get('num_questions', 5)
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Publish to Kafka for async processing
        producer.send('quiz.requested', {
            'document_id': document_id,
            'text': text,
            'num_questions': num_questions
        })
        
        return jsonify({
            'message': 'Quiz generation started',
            'document_id': document_id
        }), 202
        
    except Exception as e:
        logger.error(f"Quiz API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/<document_id>', methods=['GET'])
def get_quiz(document_id):
    """Get generated quiz"""
    try:
        quiz_key = f"quizzes/{document_id}.json"
        response = s3.get_object(Bucket=S3_BUCKET, Key=quiz_key)
        quiz = json.loads(response['Body'].read().decode('utf-8'))
        
        return jsonify({
            'document_id': document_id,
            'questions': quiz
        })
        
    except Exception as e:
        logger.error(f"Get quiz error: {str(e)}")
        return jsonify({'error': 'Quiz not found'}), 404

@app.route('/api/quiz/<document_id>/submit', methods=['POST'])
def submit_quiz(document_id):
    """Submit quiz answers and get score"""
    try:
        data = request.json
        answers = data.get('answers', {})
        
        # Get quiz
        quiz_key = f"quizzes/{document_id}.json"
        response = s3.get_object(Bucket=S3_BUCKET, Key=quiz_key)
        questions = json.loads(response['Body'].read().decode('utf-8'))
        
        # Calculate score
        correct = 0
        results = []
        for i, q in enumerate(questions):
            user_answer = answers.get(str(i), '')
            is_correct = user_answer == q.get('correct', '')
            if is_correct:
                correct += 1
            results.append({
                'question': q['question'],
                'correct_answer': q['correct'],
                'user_answer': user_answer,
                'is_correct': is_correct,
                'explanation': q.get('explanation', '')
            })
        
        return jsonify({
            'score': correct,
            'total': len(questions),
            'percentage': (correct / len(questions)) * 100 if questions else 0,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Submit quiz error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5005)
