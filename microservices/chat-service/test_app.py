"""
Unit tests for Chat Service
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
    assert data['service'] == 'chat-service'


def test_chat_endpoint_no_message(client):
    """Test chat endpoint without message"""
    response = client.post('/api/chat',
                          data=json.dumps({}),
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('app.generate_ai_response')
@patch('app.producer')
def test_chat_endpoint_with_message(mock_producer, mock_ai, client):
    """Test chat endpoint with valid message"""
    mock_producer.send = MagicMock()
    mock_ai.return_value = "This is a test response"
    
    response = client.post('/api/chat',
                          data=json.dumps({
                              'message': 'Hello',
                              'session_id': 'test-session'
                          }),
                          content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'response' in data


def test_chat_history_endpoint(client):
    """Test chat history endpoint"""
    response = client.get('/api/chat/history/test-session')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'history' in data
