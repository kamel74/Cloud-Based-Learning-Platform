"""
Unit tests for TTS Service
"""
import pytest
from unittest.mock import patch, MagicMock
import json

# Mock Kafka before importing app
with patch('kafka.KafkaProducer'):
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
    assert data['service'] == 'tts-service'


def test_tts_endpoint_no_text(client):
    """Test TTS endpoint without text"""
    response = client.post('/api/tts',
                          data=json.dumps({}),
                          content_type='application/json')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('app.producer')
def test_tts_endpoint_with_text(mock_producer, client):
    """Test TTS endpoint with valid text"""
    mock_producer.send = MagicMock()
    
    response = client.post('/api/tts',
                          data=json.dumps({'text': 'Hello world', 'document_id': 'test-123'}),
                          content_type='application/json')
    assert response.status_code == 202
    data = json.loads(response.data)
    assert 'message' in data
