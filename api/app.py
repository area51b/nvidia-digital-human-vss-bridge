from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv

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
