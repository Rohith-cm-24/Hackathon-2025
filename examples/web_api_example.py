#!/usr/bin/env python3
"""
Example Flask web API that integrates with the Info Checker gRPC service.
This shows how a REST API can call the gRPC service.
"""

import sys
import os
import json
from typing import Dict, Any
import grpc
from flask import Flask, request, jsonify

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import info_checker_pb2
import info_checker_pb2_grpc

# Create Flask app
app = Flask(__name__)

# Configuration
INFO_CHECKER_HOST = os.getenv('INFO_CHECKER_HOST', 'localhost:50051')

class InfoCheckerClient:
    """Client for the Info Checker gRPC service."""
    
    def __init__(self):
        self.channel = None
        self.stub = None
    
    def connect(self):
        """Connect to the gRPC service."""
        self.channel = grpc.insecure_channel(INFO_CHECKER_HOST)
        self.stub = info_checker_pb2_grpc.InfoCheckerStub(self.channel)
    
    def disconnect(self):
        """Disconnect from the service."""
        if self.channel:
            self.channel.close()
    
    def check_text(self, text: str, threshold: float = 0.7) -> Dict[str, Any]:
        """Check text for sensitive content."""
        try:
            request = info_checker_pb2.CheckRequest(
                text=text,
                similarity_threshold=threshold
            )
            
            response = self.stub.CheckText(request)
            
            return {
                "is_sensitive": response.is_sensitive,
                "risk_level": response.overall_risk_level,
                "confidence_score": response.confidence_score,
                "matches": [
                    {
                        "match_type": match.match_type,
                        "rule_name": match.rule_name,
                        "matched_text": match.matched_text,
                        "confidence": match.confidence,
                        "start_position": match.start_position,
                        "end_position": match.end_position,
                        "explanation": match.explanation
                    }
                    for match in response.matches
                ]
            }
        except grpc.RpcError as e:
            raise Exception(f"gRPC error: {e}")

# Global client instance
client = InfoCheckerClient()

@app.before_first_request
def initialize():
    """Initialize the gRPC client."""
    client.connect()

@app.teardown_appcontext
def cleanup(error):
    """Cleanup on app shutdown."""
    client.disconnect()

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint."""
    return jsonify({
        "service": "Sensitive Content Checker API",
        "status": "running",
        "version": "1.0.0"
    })

@app.route('/check', methods=['POST'])
def check_text():
    """
    Check text for sensitive content.
    
    POST /check
    {
        "text": "Your text to check",
        "threshold": 0.7  // optional
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400
        
        text = data['text']
        threshold = data.get('threshold', 0.7)
        
        if not isinstance(text, str) or len(text.strip()) == 0:
            return jsonify({"error": "Text must be a non-empty string"}), 400
        
        result = client.check_text(text, threshold)
        
        return jsonify({
            "status": "success",
            "data": result
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check/batch', methods=['POST'])
def check_batch():
    """
    Check multiple texts for sensitive content.
    
    POST /check/batch
    {
        "texts": ["text1", "text2", "text3"],
        "threshold": 0.7  // optional
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'texts' not in data:
            return jsonify({"error": "Missing 'texts' field"}), 400
        
        texts = data['texts']
        threshold = data.get('threshold', 0.7)
        
        if not isinstance(texts, list) or len(texts) == 0:
            return jsonify({"error": "Texts must be a non-empty array"}), 400
        
        results = []
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                results.append({"error": f"Text at index {i} is not a string"})
                continue
            
            try:
                result = client.check_text(text, threshold)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        
        return jsonify({
            "status": "success",
            "data": results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Check the health of the info checker service."""
    try:
        request_obj = info_checker_pb2.HealthCheckRequest(service="info_checker")
        response = client.stub.HealthCheck(request_obj)
        
        return jsonify({
            "status": "success",
            "service_status": response.status,
            "message": response.message
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print(f"🌐 Starting Web API on port 8080")
    print(f"📡 Connecting to Info Checker at: {INFO_CHECKER_HOST}")
    print("\nAPI Endpoints:")
    print("  GET  /         - Service info")
    print("  POST /check    - Check single text")
    print("  POST /check/batch - Check multiple texts")
    print("  GET  /health   - Service health")
    
    app.run(host='0.0.0.0', port=8080, debug=True) 