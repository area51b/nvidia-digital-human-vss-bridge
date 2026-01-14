# NVIDIA Digital Human VSS Bridge

A Flask-based REST API bridge that facilitates a front-facing digital human interface for NVIDIA's Video Search & Summarization (VSS) blueprint. This service provides intelligent routing between multiple LLM backends with support for both streaming and non-streaming responses.

## Features

- **Dual LLM Backend Support**: Routes between VSS RAG backend and NVIDIA NIM endpoint
- **Intelligent Query Routing**: Whitelist-based keyword matching to determine appropriate backend
- **Streaming Support**: Full Server-Sent Events (SSE) streaming for real-time responses
- **OpenAI Compatible API**: Compatible with OpenAI's chat completion format
- **Dynamic Configuration**: Support for environment variables and file-based configuration

## Quick Start

### Prerequisites
- Python 3.8+
- Flask and dependencies (see [requirements.txt](requirements.txt))

### Installation & Setup

See [API_README.md](API_README.md) for detailed setup instructions and API endpoint documentation.

### Environment Configuration

Key environment variables:
```bash
# NIM Endpoint Configuration
NIM_ENDPOINT=<your-nim-endpoint-url>

# VSS Backend Configuration
VSS_BACKEND=http://localhost:8000
VSS_ASSET_ID=<your-asset-id>
VSS_ASSET_ID_FILE=<path-to-configmap-file>  # For dynamic updates

# Routing Configuration
WHITELIST_KEYWORDS=document,file,knowledge,context,rag

# Server Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

## API Endpoints

### Main Endpoints

| Endpoint | Purpose | Details |
|----------|---------|---------|
| `/api/v5/chat/completions` | **Intelligent Router** | Routes queries to v1 (VSS) or v4 (NIM) based on whitelist keywords |
| `/api/v1/chat/completions` | VSS RAG Backend | Streaming support, RAG-enhanced responses from VSS |
| `/api/v4/chat/completions` | NIM Endpoint | Streaming support, direct LLM responses |
| `/api/v3/chat/completions` | Legacy NIM Endpoint | Non-streaming only |
| `/api/v2/chat/completions` | Non-Streaming VSS | RAG-enhanced without streaming |

### Utility Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/data` | GET | Sample data endpoint |
| `/api/echo` | POST | Echo endpoint |

## Usage Example

### Query with Whitelist Keyword (Routes to VSS RAG)
```bash
curl -X POST http://localhost:5000/api/v5/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is in this document?"}],
    "temperature": 0.7,
    "max_tokens": 1024,
    "stream": false
  }'
```

### Query without Whitelist Keyword (Routes to NIM)
```bash
curl -X POST http://localhost:5000/api/v5/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the weather?"}],
    "temperature": 0.7,
    "max_tokens": 1024,
    "stream": true
  }'
```

## Project Structure

```
.
├── api/
│   ├── __init__.py
│   ├── app.py              # Main Flask application
│   ├── vss_client.py       # VSS backend client
│   └── __pycache__/
├── k8s/                    # Kubernetes deployment files
├── API_README.md           # Detailed API documentation
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container image definition
├── LICENSE
└── docker-compose.yml      # (if available)
```

## For Detailed API Documentation

Please see [API_README.md](API_README.md) for:
- Complete setup instructions
- Detailed endpoint specifications
- Request/response examples
- Environment variable reference
- Testing procedures

## Architecture

### Routing Logic (`/api/v5/chat/completions`)

1. Extracts user query from request
2. Checks if query contains any whitelist keywords (configurable via `WHITELIST_KEYWORDS`)
3. Routes to appropriate backend:
   - **VSS RAG Backend** (`/api/v1`): For document/context-aware queries
   - **NIM Endpoint** (`/api/v4`): For general-purpose queries

### Model Configuration

- **VSS RAG Backend**: Uses `cosmos-reason1` model for RAG-enhanced reasoning
- **NIM Endpoint**: Uses `nvidia/llama-3.3-nemotron-super-49b-v1` model

## Deployment

### Docker Deployment
See [Dockerfile](Dockerfile) for containerization details.

### Kubernetes Deployment
See [k8s/](k8s/) directory for Kubernetes manifests including:
- Deployment configuration
- Service definition
- ConfigMaps for dynamic configuration
- Network policies
- HPA (Horizontal Pod Autoscaler)

## Contributing

When adding new endpoints or modifying existing ones, ensure:
- All endpoints follow OpenAI-compatible format where applicable
- Streaming endpoints use proper SSE format
- Environment variables are documented
- Error handling is comprehensive

## License

See [LICENSE](LICENSE) file for details.
