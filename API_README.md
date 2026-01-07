# REST API Project

A Python Flask-based REST API project with sample endpoints.

## Project Structure

```
api/
├── __init__.py          # Package initialization
├── app.py               # Main Flask application with API endpoints
requirements.txt         # Python dependencies
.env.example            # Environment variables template
```

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

Copy `.env.example` to `.env` and update values if needed:
```bash
cp .env.example .env
```

### 4. Run the API

```bash
python -m api.app
```

The API will be available at `http://localhost:5000`

## Available Endpoints

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

## Testing the API

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
```

## Environment Variables

- `FLASK_ENV`: Development or production mode
- `FLASK_DEBUG`: Enable debug mode for development
- `FLASK_HOST`: Server host (default: 0.0.0.0)
- `FLASK_PORT`: Server port (default: 5000)

## Adding New Endpoints

Edit [api/app.py](api/app.py) and add new route handlers as needed:

```python
@app.route('/api/your-endpoint', methods=['GET', 'POST'])
def your_endpoint():
    """Your endpoint description"""
    return jsonify({'key': 'value'}), 200
```
