# REST API Documentation

Detailed API endpoint documentation for the NVIDIA Digital Human VSS Bridge. For an overview of the project, see [README.md](README.md).

## Table of Contents

1. [Setup Instructions](#setup-instructions)
2. [Core Endpoints](#core-endpoints)
3. [Utility Endpoints](#utility-endpoints)
4. [Request/Response Formats](#requestresponse-formats)
5. [Environment Variables](#environment-variables)
6. [Testing](#testing)
7. [Streaming](#streaming)

## Setup Instructions

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file with required variables:

```bash
# Backend Configuration
NIM_ENDPOINT=https://your-nim-endpoint.com/v1/chat/completions
VSS_BACKEND=http://localhost:8000
VSS_ASSET_ID=your-asset-id

# Routing Configuration (for /api/v5/chat/completions)
WHITELIST_KEYWORDS=document,file,knowledge,context,rag

# Server Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
FLASK_ENV=production
```

### 4. Run the API

```bash
python -m api.app
```

The API will be available at `http://localhost:5000`

---

## Core Endpoints

### 1. Intelligent Router: `/api/v5/chat/completions`

**Purpose:** Smart routing endpoint that directs queries to VSS RAG or NIM based on whitelist keywords

**Method:** `POST`

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your question"}],
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false
}
```

**Response:** OpenAI-compatible chat completion or SSE stream

**Routing Logic:**
- If user query contains any `WHITELIST_KEYWORDS` → Routes to `/api/v1` (VSS RAG)
- Otherwise → Routes to `/api/v4` (NIM Endpoint)

**Example:**
```bash
# Routes to VSS (contains "document" keyword)
curl -X POST http://localhost:5000/api/v5/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What information is in this document?"}],
    "stream": false
  }'

# Routes to NIM (no whitelist keywords)
curl -X POST http://localhost:5000/api/v5/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me a joke"}],
    "stream": false
  }'
```

---

### 2. VSS RAG with Streaming: `/api/v1/chat/completions`

**Purpose:** Streaming chat completions with RAG-enhanced responses from VSS backend

**Method:** `POST`

**Requires:**
- `VSS_BACKEND` environment variable
- `VSS_ASSET_ID` or `asset_id` in request

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your question"}],
  "model": "cosmos-reason1",
  "asset_id": "optional-override",
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 1024,
  "top_p": 0.9,
  "top_k": 40,
  "seed": 42,
  "enable_reasoning": false,
  "stream_options": {"include_usage": true}
}
```

**Response:** Server-Sent Events (SSE) stream of chat completion chunks

**Example:**
```bash
curl -X POST http://localhost:5000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is RAG?"}],
    "asset_id": "my-asset-123",
    "stream": true
  }'
```

---

### 3. NIM Endpoint with Streaming: `/api/v4/chat/completions`

**Purpose:** Streaming chat completions directly to NVIDIA NIM endpoint

**Method:** `POST`

**Requires:**
- `NIM_ENDPOINT` environment variable

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your question"}],
  "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false
}
```

**Response:** OpenAI-compatible chat completion or SSE stream

**Example:**
```bash
curl -X POST http://localhost:5000/api/v4/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is machine learning?"}],
    "stream": false
  }'
```

---

### 4. Legacy NIM Endpoint: `/api/v3/chat/completions`

**Purpose:** Non-streaming chat completions to NIM endpoint (legacy)

**Method:** `POST`

**Requires:**
- `NIM_ENDPOINT` environment variable

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your question"}],
  "model": "your-model",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**Response:** OpenAI-compatible chat completion

---

### 5. VSS RAG without Streaming: `/api/v2/chat/completions`

**Purpose:** Non-streaming RAG-enhanced responses from VSS backend

**Method:** `POST`

**Requires:**
- `VSS_BACKEND` environment variable
- `VSS_ASSET_ID` or `asset_id` in request

**Request:**
```json
{
  "messages": [{"role": "user", "content": "your question"}],
  "model": "cosmos-reason1",
  "asset_id": "optional-override",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**Response:** OpenAI-compatible chat completion

---

## Utility Endpoints

### 1. Health Check
- **URL:** `/api/health`
- **Method:** `GET`
- **Response:**
```json
{
  "status": "healthy",
  "message": "API is running"
}
```

### 2. Get Data
- **URL:** `/api/data`
- **Method:** `GET`
- **Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Sample Data",
    "description": "This is a sample data endpoint"
  }
}
```

### 3. Echo
- **URL:** `/api/echo`
- **Method:** `POST`
- **Request Body:**
```json
{
  "message": "Hello API"
}
```
- **Response:**
```json
{
  "success": true,
  "echo": {
    "message": "Hello API"
  }
}
```

---

## Request/Response Formats

### Common Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `messages` | array | Yes | Array of message objects with `role` and `content` |
| `model` | string | No | Model identifier (overridden by routing) |
| `stream` | boolean | No | Enable streaming response (default: false) |
| `temperature` | number | No | Sampling temperature (0-2, default: 0.7) |
| `max_tokens` | number | No | Maximum response tokens |
| `top_p` | number | No | Nucleus sampling parameter (0-1) |
| `top_k` | number | No | Top-k sampling parameter |
| `seed` | number | No | Random seed for reproducibility |
| `asset_id` | string | No | Override asset ID for VSS (for v1, v2, v5) |
| `enable_reasoning` | boolean | No | Enable reasoning in VSS responses |
| `stream_options` | object | No | Stream options (e.g., `{"include_usage": true}`) |

### Response Format (Non-Streaming)

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "cosmos-reason1",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Response text"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

### Response Format (Streaming - SSE)

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"cosmos-reason1","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"cosmos-reason1","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"cosmos-reason1","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"cosmos-reason1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NIM_ENDPOINT` | NVIDIA NIM endpoint URL | `https://nim.nvidia.com/v1/chat/completions` |
| `VSS_BACKEND` | VSS backend URL | `http://localhost:8000` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VSS_ASSET_ID` | None | Default asset ID for VSS queries |
| `VSS_ASSET_ID_FILE` | None | Path to file containing asset ID (re-read on each call) |
| `WHITELIST_KEYWORDS` | None | Comma-separated keywords for routing (e.g., `"document,file,knowledge"`) |
| `FLASK_HOST` | `0.0.0.0` | Server host |
| `FLASK_PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `False` | Debug mode |
| `FLASK_ENV` | `production` | Environment (development/production) |

---

## Testing

### Using curl

```bash
# Health check
curl http://localhost:5000/api/health

# Get data
curl http://localhost:5000/api/data

# Echo (POST)
curl -X POST http://localhost:5000/api/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello API"}'

# Chat completions (v5 - intelligent router)
curl -X POST http://localhost:5000/api/v5/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is this document about?"}],
    "stream": false
  }'
```

### Using Python

```python
import requests
import json

# Non-streaming request
response = requests.post(
    'http://localhost:5000/api/v5/chat/completions',
    headers={'Content-Type': 'application/json'},
    json={
        'messages': [{'role': 'user', 'content': 'Hello!'}],
        'stream': False
    }
)
print(response.json())

# Streaming request
response = requests.post(
    'http://localhost:5000/api/v1/chat/completions',
    headers={'Content-Type': 'application/json'},
    json={
        'messages': [{'role': 'user', 'content': 'What is in this document?'}],
        'asset_id': 'my-asset',
        'stream': True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

---

## Streaming

### Server-Sent Events (SSE) Format

All streaming endpoints return responses in SSE format:

- Each message prefixed with `data: `
- Empty line between messages
- Stream ends with `data: [DONE]`

### Consuming Streaming Response (Python)

```python
import sseclient
import requests
import json

response = requests.post(
    'http://localhost:5000/api/v1/chat/completions',
    json={
        'messages': [{'role': 'user', 'content': 'Explain RAG'}],
        'stream': True
    },
    stream=True
)

client = sseclient.SSEClient(response)
for event in client.events():
    if event.data != '[DONE]':
        chunk = json.loads(event.data)
        content = chunk['choices'][0]['delta'].get('content', '')
        print(content, end='', flush=True)
```

### Consuming Streaming Response (JavaScript)

```javascript
const response = await fetch('http://localhost:5000/api/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Explain RAG' }],
    stream: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  const lines = text.split('\n');
  
  lines.forEach(line => {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data !== '[DONE]') {
        const chunk = JSON.parse(data);
        const content = chunk.choices[0].delta.content || '';
        process.stdout.write(content);
      }
    }
  });
}
```
