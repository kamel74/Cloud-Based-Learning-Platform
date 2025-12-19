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

def extract_text_from_pdf(file_content):
    """Extract text from PDF using PyPDF2"""
    try:
        import io
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return ""

def generate_quiz(topic, num_questions=5):
    """Generate quiz questions using Bedrock"""
    try:
        prompt = f"""You are a quiz generator. Create exactly {num_questions} multiple choice questions about "{topic}".

You MUST respond with ONLY a JSON array, no other text. Format:
[
  {{"question": "Question text here?", "options": ["First option", "Second option", "Third option", "Fourth option"], "correct": 0}},
  {{"question": "Another question?", "options": ["A", "B", "C", "D"], "correct": 1}}
]

Rules:
- Each question must have exactly 4 options
- "correct" is the index (0, 1, 2, or 3) of the correct answer
- Do NOT include any text before or after the JSON array
- Make questions educational and relevant to the topic

Respond with ONLY the JSON array:"""

        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 2000,
                "temperature": 0.5,
                "topP": 0.9
            }
        })
        
        response = bedrock.invoke_model(
            modelId='amazon.titan-text-express-v1',
            body=body,
            contentType='application/json'
        )
        
        result = json.loads(response['body'].read())
        completion = result.get('results', [{}])[0].get('outputText', '[]')
        
        logger.info(f"Bedrock response: {completion[:300]}")
        
        # Parse JSON from response
        try:
            # Find JSON array in the response
            start = completion.find('[')
            end = completion.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = completion[start:end]
                questions = json.loads(json_str)
                logger.info(f"Successfully parsed {len(questions)} questions")
                return questions
            else:
                logger.error(f"No JSON array found in response")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Attempted to parse: {completion[:500]}")
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
    """Generate quiz from topic or uploaded document - synchronous"""
    try:
        content_text = ""
        topic = ""
        num_questions = 5
        
        # Check if this is a file upload (multipart form data)
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload
            file = None
            if 'document' in request.files:
                file = request.files['document']
            elif 'file' in request.files:
                file = request.files['file']
            
            if file and file.filename:
                # Extract text from file
                filename = file.filename.lower()
                file_content = file.read()
                
                if filename.endswith('.pdf'):
                    content_text = extract_text_from_pdf(file_content)
                elif filename.endswith('.txt'):
                    content_text = file_content.decode('utf-8', errors='ignore')
                else:
                    content_text = file_content.decode('utf-8', errors='ignore')
                
                logger.info(f"Extracted {len(content_text)} chars from {filename}")
            
            # Get optional topic and count from form data
            topic = request.form.get('topic', '')
            num_questions = int(request.form.get('count', 5))
            
        else:
            # Handle JSON request
            data = request.json or {}
            topic = data.get('topic', data.get('text', ''))
            num_questions = data.get('count', data.get('num_questions', 5))
        
        # Combine content and topic for quiz generation
        if content_text and topic:
            quiz_source = f"Content from document:\n{content_text[:4000]}\n\nFocus on topic: {topic}"
        elif content_text:
            quiz_source = f"Content from document:\n{content_text[:5000]}"
        elif topic:
            quiz_source = topic
        else:
            return jsonify({'error': 'Topic or document is required'}), 400
        
        # Generate quiz synchronously
        questions = generate_quiz(quiz_source, num_questions)
        
        if questions:
            return jsonify({
                'message': 'Quiz generated successfully',
                'questions': questions,
                'source': 'document' if content_text else 'topic'
            })
        else:
            return jsonify({'error': 'Failed to generate quiz'}), 500
        
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
