from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import os
from dotenv import load_dotenv
import time
import uuid
import requests
import json

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running'
    }), 200


# Example endpoint 1
@app.route('/api/data', methods=['GET'])
def get_data():
    """Retrieve sample data"""
    return jsonify({
        'success': True,
        'data': {
            'id': 1,
            'name': 'Sample Data',
            'description': 'This is a sample data endpoint'
        }
    }), 200


# Example endpoint 2
@app.route('/api/echo', methods=['POST'])
def echo():
    """Echo endpoint that returns the received data"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No JSON data provided'
        }), 400
    
    return jsonify({
        'success': True,
        'echo': data
    }), 200


# OpenAI Chat Completions compatible endpoint (mock)
@app.route('/api/v1/chat/completions', methods=['POST'])
def chat_completions():
    """Proxy endpoint: forwards request JSON to a configured NIMs endpoint and returns response.

    Configure target with environment variable `NIM_ENDPOINT`.
    If not set, returns 500.
    """
    nim_endpoint = os.getenv('NIM_ENDPOINT')
    if not nim_endpoint:
        return jsonify({"error": "NIM_ENDPOINT not configured"}), 500

    # Read incoming JSON
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid JSON payload"}), 400

    # Build headers to forward (preserve common headers but avoid Host)
    forward_headers = {}
    for h, v in request.headers.items():
        if h.lower() in ('host', 'content-length'):
            continue
        # Forward Accept and Authorization if present
        if h.lower() in ('accept', 'authorization', 'content-type') or h.lower().startswith('x-'):
            forward_headers[h] = v

    # DEBUG: print what we will send upstream
    print(f"[DEBUG] NIM_ENDPOINT={nim_endpoint}")
    print(f"[DEBUG] Forward headers: {forward_headers}")
    try:
        print(f"[DEBUG] Payload (truncated): {json.dumps(payload)[:1000]}")
    except Exception:
        print("[DEBUG] Payload: <non-json or too large>")

    try:
        resp = requests.post(nim_endpoint, json=payload, headers=forward_headers, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] Upstream request failed: {e}")
        return jsonify({"error": "Failed to contact NIM endpoint", "details": str(e)}), 502

    # DEBUG: show upstream status and small body snippet
    try:
        print(f"[DEBUG] Upstream status: {resp.status_code}")
        print(f"[DEBUG] Upstream headers: {dict(resp.headers)}")
        print(f"[DEBUG] Upstream body (truncated): {resp.text[:1000]}")
    except Exception:
        pass

    # Return the NIM response as-is (status code, headers, body)
    excluded_resp_headers = ['content-encoding', 'transfer-encoding', 'connection']
    response_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded_resp_headers]

    return Response(resp.content, status=resp.status_code, headers=response_headers, content_type=resp.headers.get('Content-Type', 'application/json'))


# Error handling
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Get configuration from environment variables
    debug = os.getenv('FLASK_DEBUG', False)
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    
    app.run(host=host, port=port, debug=debug)
