import json
import time
import uuid
import os
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import sseclient

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
@app.route('/api/v3/chat/completions', methods=['POST'])
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
@app.route('/api/v2/chat/completions', methods=['POST'])
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

# Streaming RAG Chat Completions endpoint (via VSS backend)
@app.route('/api/v1/chat/completions', methods=['POST'])
def rag_chat_completions_streaming():
    """Streaming proxy endpoint: forwards chat request to VSS backend and streams response.

    Requires environment variables:
      - VSS_BACKEND: VSS server URL (default: http://localhost:8000)
      - VSS_ASSET_ID: Asset ID to use for chat (can be overridden in request)

    Request JSON:
      {
        "messages": [{"role": "user", "content": "your question"}],
        "model": "cosmos-reason1",
        "asset_id": "optional-override-id",
        "stream": true,
        "temperature": 0.7,
        "max_tokens": 1024
      }
    
    Response: Server-Sent Events (SSE) stream in OpenAI format
    """
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
    top_k = payload.get('top_k')
    seed = payload.get('seed')
    chunk_duration = payload.get('chunk_duration')
    enable_reasoning = payload.get('enable_reasoning', False)
    stream = payload.get('stream', True)
    
    print(f"[DEBUG] VSS Chat: backend={vss_backend}, asset_id={asset_id}, model={model}, stream={stream}")
    print(f"[DEBUG] Prompt: {prompt[:100]}...")
    
    # If streaming is not requested, use the non-streaming version
    if not stream:
        return handle_non_streaming_chat(
            asset_id, model, prompt, vss_backend,
            temperature, seed, top_p, top_k, max_tokens,
            chunk_duration, enable_reasoning
        )
    
    # Handle streaming request
    def generate():
        """Generator function that yields SSE-formatted chunks"""
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created_time = int(time.time())
        
        # Build request for VSS backend
        req_json = {
            "id": [asset_id] if isinstance(asset_id, str) else asset_id,
            "model": model,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"content": str(prompt), "role": "user"}]
        }
        
        if temperature is not None:
            req_json["temperature"] = temperature
        if seed is not None:
            req_json["seed"] = seed
        if top_p is not None:
            req_json["top_p"] = top_p
        if top_k is not None:
            req_json["top_k"] = top_k
        if max_tokens is not None:
            req_json["max_tokens"] = max_tokens
        if chunk_duration is not None:
            req_json["chunk_duration"] = chunk_duration
        if enable_reasoning:
            req_json["enable_reasoning"] = enable_reasoning
        
        # Make request to VSS backend
        vss_url = f"{vss_backend.rstrip('/')}/chat/completions"
        print(f"[DEBUG] Making request to: {vss_url}")
        
        try:
            response = requests.post(
                vss_url, 
                json=req_json, 
                stream=True,
                timeout=300
            )
            
            print(f"[DEBUG] VSS response status: {response.status_code}")
            
            if response.status_code >= 400:
                error_msg = f"VSS backend error: {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f" - {error_details}"
                except:
                    error_msg += f" - {response.text[:200]}"
                
                print(f"[ERROR] {error_msg}")
                error_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": f"Error: {error_msg}"},
                        "finish_reason": "error"
                    }]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # Check if response is SSE or JSON
            content_type = response.headers.get('content-type', '').lower()
            print(f"[DEBUG] Content-Type: {content_type}")
            
            if 'text/event-stream' in content_type or 'event-stream' in content_type:
                # True SSE streaming from VSS
                print("[DEBUG] Processing as SSE stream")
                try:
                    import sseclient
                    client = sseclient.SSEClient(response)
                    
                    for event in client.events():
                        if event.data == '[DONE]':
                            yield "data: [DONE]\n\n"
                            break
                        
                        try:
                            vss_chunk = json.loads(event.data)
                            openai_chunk = transform_vss_to_openai_chunk(vss_chunk, chat_id, created_time, model)
                            yield f"data: {json.dumps(openai_chunk)}\n\n"
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] Failed to parse SSE chunk: {e}")
                            continue
                    return
                except ImportError:
                    print("[ERROR] sseclient-py not installed, falling back to JSON mode")
            
            # Handle as JSON response - VSS returns complete response
            print("[DEBUG] Processing as JSON response, will simulate streaming")
            
            vss_response = response.json()
            print(f"[DEBUG] Got VSS response with {len(json.dumps(vss_response))} chars")
            
            # Extract content from VSS response
            content = ""
            usage = {}
            
            if "choices" in vss_response and len(vss_response["choices"]) > 0:
                choice = vss_response["choices"][0]
                if "message" in choice:
                    content = choice["message"].get("content", "")
                elif "text" in choice:
                    content = choice["text"]
            
            if "usage" in vss_response:
                usage = vss_response["usage"]
            
            print(f"[DEBUG] Extracted content length: {len(content)} chars")
            
            # 1. Send initial chunk with role (OpenAI always sends this first)
            initial_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(initial_chunk)}\n\n"
            
            # 2. Stream content in smaller chunks (more OpenAI-like)
            # Use word-level chunking for more natural streaming
            words = content.split(' ')
            chunk_size = 3  # 3-5 words per chunk is more realistic
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i+chunk_size]
                chunk_text = ' '.join(chunk_words)
                
                # Add space at end if not the last chunk
                if i + chunk_size < len(words):
                    chunk_text += ' '
                
                content_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(content_chunk)}\n\n"
                
                # Small delay to simulate realistic streaming speed
                time.sleep(0.02)  # 20ms per chunk
            
            # 3. Send final chunk with finish_reason (no usage here for compatibility)
            final_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            
            # 4. Optionally send usage in a separate chunk if stream_options.include_usage was true
            # This follows OpenAI's new streaming format with usage
            if usage and payload.get('stream_options', {}).get('include_usage'):
                usage_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model,
                    "choices": [],
                    "usage": usage
                }
                yield f"data: {json.dumps(usage_chunk)}\n\n"
            
            # 5. Send [DONE] signal
            yield "data: [DONE]\n\n"
            
            print(f"[DEBUG] Stream completed successfully")
        
        except requests.exceptions.Timeout:
            print("[ERROR] Request timeout")
            error_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": "Error: Request timeout"},
                    "finish_reason": "error"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            print(f"[ERROR] Streaming error: {e}")
            import traceback
            traceback.print_exc()
            error_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": f"Error: {str(e)}"},
                    "finish_reason": "error"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
    
    # Return streaming response
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream'
        }
    )


def transform_vss_to_openai_chunk(vss_chunk, chat_id, created_time, model):
    """Transform VSS SSE chunk to OpenAI format"""
    openai_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": []
    }
    
    if "choices" in vss_chunk:
        for choice in vss_chunk["choices"]:
            openai_choice = {
                "index": choice.get("index", 0),
                "delta": {},
                "finish_reason": choice.get("finish_reason")
            }
            
            if "delta" in choice:
                delta = choice["delta"]
                if "role" in delta:
                    openai_choice["delta"]["role"] = delta["role"]
                if "content" in delta:
                    openai_choice["delta"]["content"] = delta["content"]
                if "reasoning" in delta:
                    openai_choice["delta"]["reasoning"] = delta["reasoning"]
            
            openai_chunk["choices"].append(openai_choice)
    
    if "usage" in vss_chunk:
        openai_chunk["usage"] = vss_chunk["usage"]
    
    return openai_chunk


def handle_non_streaming_chat(asset_id, model, prompt, vss_backend,
                               temperature, seed, top_p, top_k, max_tokens,
                               chunk_duration, enable_reasoning):
    """Handle non-streaming chat request"""
    from api.vss_client import call_vss_chat
    
    try:
        result = call_vss_chat(
            asset_ids=asset_id,
            model=model,
            prompt=prompt,
            backend=vss_backend,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            chunk_duration=chunk_duration,
            enable_reasoning=enable_reasoning,
            stream=False,
        )
    except Exception as e:
        print(f"[DEBUG] VSS Chat error: {e}")
        import traceback
        traceback.print_exc()
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

# @app.route('/api/v1/chat/completions', methods=['POST'])
# def rag_chat_completions_stream():
#     """Proxy endpoint: forwards chat request to VSS backend for RAG-enabled streaming responses.

#     Requires environment variables:
#       - VSS_BACKEND: VSS server URL (default: http://localhost:8000)
#       - VSS_ASSET_ID: Asset ID to use for chat (can be overridden in request)

#     Request JSON:
#       {
#         "messages": [{"role": "user", "content": "your question"}],
#         "model": "cosmos-reason1",
#         "asset_id": "optional-override-id",
#         "temperature": 0.7,
#         "max_tokens": 1024
#       }
    
#     Returns: Server-Sent Events (SSE) stream of chat completion chunks
#     """
#     import requests
#     import sseclient
    
#     payload = request.get_json(silent=True)
#     if payload is None:
#         return jsonify({"error": "Invalid JSON payload"}), 400
    
#     # Extract parameters
#     vss_backend = os.getenv('VSS_BACKEND', 'http://localhost:8000')
#     asset_id = get_vss_asset_id(payload)
    
#     if not asset_id:
#         return jsonify({"error": "VSS_ASSET_ID not configured and asset_id not in request"}), 400
    
#     # Extract prompt from messages (OpenAI format)
#     messages = payload.get('messages', [])
#     if not messages or not isinstance(messages, list):
#         return jsonify({"error": "messages must be a non-empty list"}), 400
    
#     # Find last user message
#     prompt = None
#     for msg in reversed(messages):
#         if msg.get('role') == 'user':
#             prompt = msg.get('content', '')
#             break
    
#     if not prompt:
#         return jsonify({"error": "No user message found in messages"}), 400
    
#     model = payload.get('model', 'cosmos-reason1')
#     temperature = payload.get('temperature')
#     max_tokens = payload.get('max_tokens')
#     top_p = payload.get('top_p')
#     seed = payload.get('seed')
#     chunk_duration = payload.get('chunk_duration')
#     enable_reasoning = payload.get('enable_reasoning', False)
    
#     print(f"[DEBUG] VSS Streaming Chat: backend={vss_backend}, asset_id={asset_id}, model={model}")
#     print(f"[DEBUG] Prompt: {prompt[:100]}...")
    
#     def stream_response():
#         """Generator function to stream VSS response chunks to client."""
#         try:
#             from api.vss_client import call_vss_chat
            
#             # Call VSS with streaming enabled
#             # First, we need to make a raw streaming request since call_vss_chat 
#             # doesn't fully support streaming return
#             req_json = {
#                 "id": [asset_id] if isinstance(asset_id, str) else asset_id,
#                 "model": model,
#                 "stream": True,
#                 "stream_options": {"include_usage": True},
#                 "messages": [{"content": str(prompt), "role": "user"}]
#             }
            
#             if temperature is not None:
#                 req_json["temperature"] = temperature
#             if seed is not None:
#                 req_json["seed"] = seed
#             if top_p is not None:
#                 req_json["top_p"] = top_p
#             if max_tokens is not None:
#                 req_json["max_tokens"] = max_tokens
#             if chunk_duration is not None:
#                 req_json["chunk_duration"] = chunk_duration
#             if enable_reasoning:
#                 req_json["enable_reasoning"] = enable_reasoning
            
#             # Make streaming request to VSS backend (match vss_client path)
#             vss_url = f"{vss_backend}/chat/completions"
#             print(f"[DEBUG] Requesting VSS stream from: {vss_url}")
            
#             resp = requests.post(vss_url, json=req_json, stream=True, timeout=600)
            
#             if resp.status_code >= 400:
#                 print(f"[DEBUG] VSS streaming error: {resp.status_code}")
#                 error_msg = f"data: {json.dumps({'error': f'VSS API error: {resp.status_code}', 'details': resp.text[:200]})}\n\n"
#                 yield error_msg
#                 return
            
#             # Parse SSE events from VSS and forward to client
#             # Wrap resp.iter_lines to ensure compatibility with sseclient versions
#             try:
#                 iterable = resp.iter_lines(decode_unicode=True)
#                 client = sseclient.SSEClient(iterable)
#             except Exception:
#                 client = sseclient.SSEClient(resp)

#             events_iter = None
#             if hasattr(client, 'events') and callable(getattr(client, 'events')):
#                 events_iter = client.events()
#             else:
#                 events_iter = client

#             for event in events_iter:
#                 if event.data:
#                     try:
#                         # Parse VSS event data
#                         vss_event = json.loads(event.data)
                        
#                         # Convert to OpenAI streaming format
#                         oa_chunk = {
#                             "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
#                             "object": "chat.completion.chunk",
#                             "created": int(time.time()),
#                             "model": model,
#                             "choices": []
#                         }
                        
#                         # Handle different event types
#                         if "choices" in vss_event:
#                             for choice in vss_event.get("choices", []):
#                                 delta = {}
#                                 if "delta" in choice:
#                                     delta = choice["delta"]
#                                 elif "message" in choice:
#                                     # Convert message to delta format
#                                     msg = choice["message"]
#                                     delta = {"content": msg.get("content", "")}
                                
#                                 oa_choice = {
#                                     "index": choice.get("index", 0),
#                                     "delta": delta,
#                                     "finish_reason": choice.get("finish_reason")
#                                 }
#                                 oa_chunk["choices"].append(oa_choice)
                        
#                         # Add usage if present
#                         if "usage" in vss_event:
#                             oa_chunk["usage"] = vss_event["usage"]
                        
#                         yield f"data: {json.dumps(oa_chunk)}\n\n"
#                     except json.JSONDecodeError:
#                         print(f"[DEBUG] Failed to parse VSS event: {event.data[:100]}")
#                         continue
            
#             # Send final stream completion marker
#             final_chunk = {
#                 "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
#                 "object": "chat.completion.chunk",
#                 "created": int(time.time()),
#                 "model": model,
#                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
#             }
#             yield f"data: {json.dumps(final_chunk)}\n\n"
#             yield "data: [DONE]\n\n"
            
#         except Exception as e:
#             print(f"[DEBUG] Streaming error: {e}")
#             error_chunk = f"data: {json.dumps({'error': str(e)})}\n\n"
#             yield error_chunk
    
#     return Response(stream_response(), mimetype='text/event-stream', headers={
#         'Cache-Control': 'no-cache',
#         'Connection': 'keep-alive',
#         'Content-Type': 'text/event-stream',
#         'X-Accel-Buffering': 'no'
#     })


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
