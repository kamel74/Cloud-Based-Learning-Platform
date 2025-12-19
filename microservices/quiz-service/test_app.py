"""
Unit tests for Quiz Service
"""
import pytest
from unittest.mock import patch, MagicMock
import json

# Mock Kafka and Bedrock before importing app
with patch('kafka.KafkaProducer'):
    with patch('boto3.client'):
        from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['service'] == 'quiz-service'


def test_quiz_generate_no_text(client):
    """Test quiz generate endpoint without text"""
    response = client.post('/api/quiz/generate',
                          data=json.dumps({}),
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('app.producer')
def test_quiz_generate_with_text(mock_producer, client):
    """Test quiz generate endpoint with valid text"""
    mock_producer.send = MagicMock()
    
    response = client.post('/api/quiz/generate',
                          data=json.dumps({
                              'text': 'This is a test document about Python programming.',
                              'document_id': 'test-123',
                              'num_questions': 5
                          }),
                          content_type='application/json')
    assert response.status_code == 202
    data = json.loads(response.data)
    assert 'message' in data
