#!/usr/bin/env python3
"""
Example of how another service can call the Sensitive Information Checker gRPC service.
This demonstrates various integration patterns.
"""

import sys
import os
import asyncio
import json
from typing import List, Dict, Optional
import grpc
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import info_checker_pb2
import info_checker_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SensitiveContentService:
    """
    Example service that integrates with the Info Checker gRPC service.
    This could represent any microservice that needs to check content.
    """
    
    def __init__(self, info_checker_host: str = "localhost:50051"):
        self.info_checker_host = info_checker_host
        self.channel = None
        self.stub = None
        
    def connect(self):
        """Connect to the info checker service."""
        try:
            self.channel = grpc.insecure_channel(self.info_checker_host)
            self.stub = info_checker_pb2_grpc.InfoCheckerStub(self.channel)
            logger.info(f"Connected to Info Checker service at {self.info_checker_host}")
        except Exception as e:
            logger.error(f"Failed to connect to Info Checker service: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from the service."""
        if self.channel:
            self.channel.close()
            logger.info("Disconnected from Info Checker service")
    
    def check_user_message(self, user_id: str, message: str) -> Dict:
        """
        Check a user message for sensitive content.
        Example: Chat application checking messages before storing/displaying.
        """
        try:
            request = info_checker_pb2.CheckRequest(
                text=message,
                similarity_threshold=0.8  # Higher threshold for user messages
            )
            
            response = self.stub.CheckText(request)
            
            result = {
                "user_id": user_id,
                "message": message,
                "is_sensitive": response.is_sensitive,
                "risk_level": response.overall_risk_level,
                "confidence": response.confidence_score,
                "matches": [
                    {
                        "type": match.match_type,
                        "rule": match.rule_name,
                        "text": match.matched_text,
                        "confidence": match.confidence,
                        "explanation": match.explanation
                    }
                    for match in response.matches
                ]
            }
            
            # Log sensitive content detection
            if response.is_sensitive:
                logger.warning(f"Sensitive content detected from user {user_id}: {response.overall_risk_level}")
            
            return result
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error checking user message: {e}")
            raise
    
    def check_document_batch(self, documents: List[Dict]) -> List[Dict]:
        """
        Check multiple documents for sensitive content.
        Example: Document management system processing uploads.
        """
        try:
            # Prepare batch request
            requests = []
            for doc in documents:
                request = info_checker_pb2.CheckRequest(
                    text=doc.get('content', ''),
                    similarity_threshold=0.7
                )
                requests.append(request)
            
            batch_request = info_checker_pb2.BatchCheckRequest(requests=requests)
            batch_response = self.stub.CheckBatch(batch_request)
            
            results = []
            for i, (doc, response) in enumerate(zip(documents, batch_response.responses)):
                result = {
                    "document_id": doc.get('id', f'doc_{i}'),
                    "filename": doc.get('filename', 'unknown'),
                    "is_sensitive": response.is_sensitive,
                    "risk_level": response.overall_risk_level,
                    "confidence": response.confidence_score,
                    "match_count": len(response.matches),
                    "matches": [
                        {
                            "type": match.match_type,
                            "rule": match.rule_name,
                            "confidence": match.confidence
                        }
                        for match in response.matches
                    ]
                }
                results.append(result)
            
            return results
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error in batch check: {e}")
            raise
    
    def check_service_health(self) -> bool:
        """Check if the info checker service is healthy."""
        try:
            request = info_checker_pb2.HealthCheckRequest(service="info_checker")
            response = self.stub.HealthCheck(request)
            
            is_healthy = response.status == info_checker_pb2.HealthCheckResponse.SERVING
            logger.info(f"Info Checker service health: {'HEALTHY' if is_healthy else 'UNHEALTHY'}")
            return is_healthy
            
        except grpc.RpcError as e:
            logger.error(f"Health check failed: {e}")
            return False

# Example usage patterns
def example_chat_service():
    """Example: Chat service checking messages"""
    print("\n🗨️  Chat Service Example")
    print("-" * 40)
    
    service = SensitiveContentService()
    service.connect()
    
    try:
        # Simulate user messages
        messages = [
            {"user_id": "user123", "message": "Hey everyone, how's it going?"},
            {"user_id": "user456", "message": "My credit card number is 4532-1234-5678-9012"},
            {"user_id": "user789", "message": "We're planning layoffs next month, keep it quiet"},
        ]
        
        for msg in messages:
            result = service.check_user_message(msg["user_id"], msg["message"])
            
            print(f"\nUser: {result['user_id']}")
            print(f"Message: {result['message'][:50]}...")
            print(f"Sensitive: {'🚨 YES' if result['is_sensitive'] else '✅ NO'}")
            print(f"Risk: {result['risk_level']}")
            
            if result['matches']:
                print(f"Issues: {', '.join([m['type'] for m in result['matches']])}")
    
    finally:
        service.disconnect()

def example_document_service():
    """Example: Document management service"""
    print("\n📄 Document Service Example")
    print("-" * 40)
    
    service = SensitiveContentService()
    service.connect()
    
    try:
        # Simulate document uploads
        documents = [
            {
                "id": "doc001",
                "filename": "meeting_notes.txt",
                "content": "Regular team meeting notes. No sensitive information."
            },
            {
                "id": "doc002", 
                "filename": "financial_report.pdf",
                "content": "Q3 revenue was $5.2M with 18% profit margins. Confidential data."
            },
            {
                "id": "doc003",
                "filename": "employee_data.xlsx", 
                "content": "Employee John Smith, SSN: 123-45-6789, Salary: $75,000"
            }
        ]
        
        results = service.check_document_batch(documents)
        
        for result in results:
            print(f"\nDocument: {result['filename']}")
            print(f"Sensitive: {'🚨 YES' if result['is_sensitive'] else '✅ NO'}")
            print(f"Risk: {result['risk_level']} (confidence: {result['confidence']:.2f})")
            print(f"Issues found: {result['match_count']}")
    
    finally:
        service.disconnect()

def example_api_gateway():
    """Example: API Gateway checking requests"""
    print("\n🌐 API Gateway Example")
    print("-" * 40)
    
    service = SensitiveContentService()
    service.connect()
    
    try:
        # Check service health before processing
        if not service.check_service_health():
            print("❌ Info Checker service is not healthy!")
            return
        
        # Simulate API requests with payloads
        api_requests = [
            "Create user with email john@example.com",
            "Update profile: My phone number is 555-123-4567",
            "Support ticket: There's a security vulnerability in the payment system"
        ]
        
        for i, request_text in enumerate(api_requests, 1):
            result = service.check_user_message(f"api_request_{i}", request_text)
            
            print(f"\nAPI Request {i}:")
            print(f"Content: {request_text}")
            
            if result['is_sensitive']:
                print(f"🚫 BLOCKED - {result['risk_level']} risk detected")
                print(f"Reason: {', '.join([m['rule'] for m in result['matches']])}")
            else:
                print("✅ ALLOWED - No sensitive content detected")
    
    finally:
        service.disconnect()

def main():
    """Run all examples"""
    print("🔍 Sensitive Information Checker - Integration Examples")
    print("=" * 60)
    
    try:
        example_chat_service()
        example_document_service() 
        example_api_gateway()
        
        print(f"\n✅ All integration examples completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 