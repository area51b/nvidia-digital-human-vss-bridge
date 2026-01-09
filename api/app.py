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


def get_vss_asset_id(payload=None):
    """Return the asset id to use for a request.

    Priority:
      1. `asset_id` in request payload (if provided)
      2. Contents of file pointed by `VSS_ASSET_ID_FILE` env var (read on every call)
      3. `VSS_ASSET_ID` env var (legacy)

    Reading from file allows updating the ConfigMap mounted as a file without restarting pods.
    """
    # 1) request override
    if payload and isinstance(payload, dict):
        aid = payload.get('asset_id')
        if aid:
            return aid

    # 2) file-backed value
    aid_file = os.getenv('VSS_ASSET_ID_FILE')
    if aid_file:
        try:
            with open(aid_file, 'r') as f:
                val = f.read().strip()
                if val:
                    return val
        except Exception:
            # ignore read errors and fallback
            pass

    # 3) env var fallback
    return os.getenv('VSS_ASSET_ID')

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
@app.route('/api/v2/chat/completions', methods=['POST'])
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


# RAG Chat Completions endpoint (via VSS backend)
@app.route('/api/v1/chat/completions', methods=['POST'])
def rag_chat_completions():
    """Proxy endpoint: forwards chat request to VSS backend for RAG-enabled responses.

    Requires environment variables:
      - VSS_BACKEND: VSS server URL (default: http://localhost:8000)
      - VSS_ASSET_ID: Asset ID to use for chat (can be overridden in request)

    Request JSON:
      {
        "messages": [{"role": "user", "content": "your question"}],
        "model": "cosmos-reason1",
        "asset_id": "optional-override-id",
        "temperature": 0.7,
        "max_tokens": 1024
      }
    """
    # Import here to avoid circular dependencies
    from api.vss_client import call_vss_chat
    
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    # Extract parameters
    vss_backend = os.getenv('VSS_BACKEND', 'http://localhost:8000')
    asset_id = get_vss_asset_id(payload)
    
    if not asset_id:
        return jsonify({"error": "VSS_ASSET_ID not configured and asset_id not in request"}), 400
    
    # Extract prompt from messages (OpenAI format)
    messages = payload.get('messages', [])
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages must be a non-empty list"}), 400
    
    # Find last user message
    prompt = None
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            prompt = msg.get('content', '')
            break
    
    if not prompt:
        return jsonify({"error": "No user message found in messages"}), 400
    
    model = payload.get('model', 'cosmos-reason1')
    temperature = payload.get('temperature')
    max_tokens = payload.get('max_tokens')
    top_p = payload.get('top_p')
    seed = payload.get('seed')
    chunk_duration = payload.get('chunk_duration')
    enable_reasoning = payload.get('enable_reasoning', False)
    
    print(f"[DEBUG] VSS Chat: backend={vss_backend}, asset_id={asset_id}, model={model}")
    print(f"[DEBUG] Prompt: {prompt[:100]}...")
    
    try:
        result = call_vss_chat(
            asset_ids=asset_id,
            model=model,
            prompt=prompt,
            backend=vss_backend,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
            max_tokens=max_tokens,
            chunk_duration=chunk_duration,
            enable_reasoning=enable_reasoning,
            stream=False,
        )
    except Exception as e:
        print(f"[DEBUG] VSS Chat error: {e}")
        return jsonify({"error": "Failed to call VSS chat API", "details": str(e)}), 502
    
    if result is None:
        return jsonify({"error": "VSS chat API returned error"}), 502
    
    # Format response in OpenAI ChatCompletion format
    response = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["content"]},
                "finish_reason": "stop",
                "logprobs": None
            }
        ],
        "usage": result.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        "system_fingerprint": f"fp_{uuid.uuid4().hex[:8]}"
    }
    
    return jsonify(response), 200


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
