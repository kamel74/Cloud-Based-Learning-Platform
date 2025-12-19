"""
Document Reader Service
Handles PDF/document processing, text extraction, and AI summarization
Uses PyPDF2 for PDF text extraction and AWS Bedrock for summarization
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import json
import logging
import io
import os

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)

def extract_text_from_pdf(file_content):
    """Extract text from PDF using PyPDF2"""
    try:
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
        return None

def extract_text_from_txt(file_content):
    """Extract text from plain text file"""
    try:
        return file_content.decode('utf-8')
    except:
        try:
            return file_content.decode('latin-1')
        except:
            return None

def generate_summary(text):
    """Generate summary using AWS Bedrock"""
    try:
        # Limit text to avoid token limits
        text_to_summarize = text[:8000] if len(text) > 8000 else text
        
        prompt = f"""Please provide a concise summary of the following document. 
Include the main topics, key points, and important details.
Format the summary with bullet points for clarity.

Document:
{text_to_summarize}

Summary:"""

        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 1000,
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
        summary = result.get('results', [{}])[0].get('outputText', '')
        
        logger.info(f"Summary generated successfully")
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Summary generation error: {str(e)}")
        return None

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'document-reader-service'})

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload, extract text, and generate AI summary"""
    try:
        # Check for file in different field names
        file = None
        if 'document' in request.files:
            file = request.files['document']
        elif 'file' in request.files:
            file = request.files['file']
        
        if not file or file.filename == '':
            return jsonify({'error': 'No file provided'}), 400
        
        filename = file.filename.lower()
        file_content = file.read()
        
        logger.info(f"Processing document: {filename}, size: {len(file_content)} bytes")
        
        # Extract text based on file type
        extracted_text = None
        
        if filename.endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_content)
        elif filename.endswith('.txt'):
            extracted_text = extract_text_from_txt(file_content)
        elif filename.endswith(('.doc', '.docx')):
            extracted_text = f"Word document uploaded: {file.filename}\nNote: Word document parsing requires additional libraries."
        else:
            extracted_text = extract_text_from_txt(file_content)
        
        if not extracted_text:
            return jsonify({
                'error': 'Could not extract text from document',
                'filename': file.filename
            }), 400
        
        # Generate AI summary
        summary = generate_summary(extracted_text)
        
        response_data = {
            'message': 'Document processed successfully',
            'filename': file.filename,
            'text': extracted_text,
            'preview': extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            'total_characters': len(extracted_text)
        }
        
        if summary:
            response_data['summary'] = summary
            response_data['notes'] = summary  # Alias for compatibility
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)
