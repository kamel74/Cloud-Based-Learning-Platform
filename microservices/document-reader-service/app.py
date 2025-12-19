"""
Document Reader Service
Handles PDF/document processing and text extraction
Uses PyPDF2 for PDF text extraction (no AWS Textract needed)
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import io

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'document-reader-service'})

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload and process document - extracts text immediately"""
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
            # For Word docs, try to read as text or return info
            extracted_text = f"Word document uploaded: {filename}\nSize: {len(file_content)} bytes\n\nNote: Full Word document parsing requires additional libraries."
        else:
            # Try to read as text
            extracted_text = extract_text_from_txt(file_content)
        
        if extracted_text:
            return jsonify({
                'message': 'Document processed successfully',
                'filename': file.filename,
                'text': extracted_text,
                'preview': extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
                'total_characters': len(extracted_text)
            })
        else:
            return jsonify({
                'error': 'Could not extract text from document',
                'filename': file.filename
            }), 400
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)

