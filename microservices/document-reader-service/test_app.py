"""
Unit tests for Document Reader Service
"""
import pytest
from unittest.mock import patch, MagicMock
import json
from io import BytesIO

# Mock Kafka and Textract before importing app
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
    assert data['service'] == 'document-reader-service'


def test_upload_endpoint_no_file(client):
    """Test upload endpoint without file"""
    response = client.post('/api/documents/upload')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('app.s3')
@patch('app.producer')
def test_upload_endpoint_with_file(mock_producer, mock_s3, client):
    """Test upload endpoint with valid file"""
    mock_producer.send = MagicMock()
    mock_s3.upload_fileobj = MagicMock()
    
    data = {
        'file': (BytesIO(b'test pdf content'), 'test.pdf')
    }
    response = client.post('/api/documents/upload',
                          data=data,
                          content_type='multipart/form-data')
    assert response.status_code == 202
    result = json.loads(response.data)
    assert 'message' in result
