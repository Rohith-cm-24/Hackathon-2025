"""
gRPC client for the sensitive information checker service.
Provides both programmatic interface and command-line tool.
"""

import logging
import sys
import argparse
from typing import List, Dict, Optional
import grpc

import info_checker_pb2
import info_checker_pb2_grpc

logger = logging.getLogger(__name__)

class InfoCheckerClient:
    """
    gRPC client for the sensitive information checker service.
    """
    
    def __init__(self, server_address: str = "localhost:50051"):
        """
        Initialize the client.
        
        Args:
            server_address: Address of the gRPC server
        """
        self.server_address = server_address
        self.channel = None
        self.stub = None
        
    def connect(self):
        """Connect to the gRPC server."""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = info_checker_pb2_grpc.InfoCheckerStub(self.channel)
            logger.info(f"Connected to server at {self.server_address}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from the server."""
        if self.channel:
            self.channel.close()
            logger.info("Disconnected from server")
    
    def check_text(self, 
                   text: str, 
                   custom_rules: Optional[List[str]] = None,
                   similarity_threshold: Optional[float] = None) -> Dict:
        """
        Check a single text for sensitive content.
        
        Args:
            text: Text to check
            custom_rules: Optional custom rules for this check
            similarity_threshold: Optional custom similarity threshold
            
        Returns:
            Dictionary containing the check results
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        try:
            # Create request
            request = info_checker_pb2.CheckRequest(
                text=text,
                custom_rules=custom_rules or [],
                similarity_threshold=similarity_threshold or 0.0
            )
            
            # Make the gRPC call
            response = self.stub.CheckText(request)
            
            # Convert response to dictionary
            result = {
                "is_sensitive": response.is_sensitive,
                "overall_risk_level": response.overall_risk_level,
                "confidence_score": response.confidence_score,
                "matches": []
            }
            
            for match in response.matches:
                match_dict = {
                    "match_type": match.match_type,
                    "rule_name": match.rule_name,
                    "matched_text": match.matched_text,
                    "confidence": match.confidence,
                    "start_position": match.start_position,
                    "end_position": match.end_position,
                    "explanation": match.explanation
                }
                result["matches"].append(match_dict)
            
            return result
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error in check_text: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in check_text: {e}")
            raise
    
    def check_batch(self, texts: List[str]) -> List[Dict]:
        """
        Check multiple texts in batch.
        
        Args:
            texts: List of texts to check
            
        Returns:
            List of dictionaries containing check results
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        try:
            # Create batch request
            requests = []
            for text in texts:
                request = info_checker_pb2.CheckRequest(text=text)
                requests.append(request)
            
            batch_request = info_checker_pb2.BatchCheckRequest(requests=requests)
            
            # Make the gRPC call
            response = self.stub.CheckBatch(batch_request)
            
            # Convert responses to list of dictionaries
            results = []
            for resp in response.responses:
                result = {
                    "is_sensitive": resp.is_sensitive,
                    "overall_risk_level": resp.overall_risk_level,
                    "confidence_score": resp.confidence_score,
                    "matches": []
                }
                
                for match in resp.matches:
                    match_dict = {
                        "match_type": match.match_type,
                        "rule_name": match.rule_name,
                        "matched_text": match.matched_text,
                        "confidence": match.confidence,
                        "start_position": match.start_position,
                        "end_position": match.end_position,
                        "explanation": match.explanation
                    }
                    result["matches"].append(match_dict)
                
                results.append(result)
            
            return results
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error in check_batch: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in check_batch: {e}")
            raise
    
    def health_check(self) -> Dict:
        """
        Check service health.
        
        Returns:
            Dictionary containing health status
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        try:
            request = info_checker_pb2.HealthCheckRequest(service="info_checker")
            response = self.stub.HealthCheck(request)
            
            status_map = {
                0: "UNKNOWN",
                1: "SERVING", 
                2: "NOT_SERVING"
            }
            
            return {
                "status": status_map.get(response.status, "UNKNOWN"),
                "message": response.message
            }
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error in health_check: {e}")
            return {"status": "ERROR", "message": str(e)}
        except Exception as e:
            logger.error(f"Error in health_check: {e}")
            return {"status": "ERROR", "message": str(e)}

def print_results(result: Dict, text: str = None):
    """
    Pretty print the check results.
    
    Args:
        result: Result dictionary from check_text
        text: Original text (for context)
    """
    print("\n" + "="*60)
    print("SENSITIVE INFORMATION CHECK RESULTS")
    print("="*60)
    
    if text:
        print(f"Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        print("-" * 60)
    
    print(f"Sensitive: {'YES' if result['is_sensitive'] else 'NO'}")
    print(f"Risk Level: {result['overall_risk_level']}")
    print(f"Confidence: {result['confidence_score']:.3f}")
    print(f"Matches Found: {len(result['matches'])}")
    
    if result['matches']:
        print("\nDETAILED MATCHES:")
        print("-" * 60)
        
        for i, match in enumerate(result['matches'], 1):
            print(f"\n{i}. {match['match_type']} Match")
            print(f"   Rule: {match['rule_name']}")
            print(f"   Text: '{match['matched_text']}'")
            print(f"   Confidence: {match['confidence']:.3f}")
            print(f"   Position: {match['start_position']}-{match['end_position']}")
            print(f"   Explanation: {match['explanation']}")
    
    print("\n" + "="*60)

def interactive_mode(client: InfoCheckerClient):
    """
    Run the client in interactive mode.
    
    Args:
        client: Connected InfoCheckerClient instance
    """
    print("\n🔍 Sensitive Information Checker - Interactive Mode")
    print("Type 'quit' to exit, 'health' to check service health")
    print("-" * 60)
    
    while True:
        try:
            text = input("\nEnter text to check: ").strip()
            
            if text.lower() in ['quit', 'exit', 'q']:
                break
            elif text.lower() == 'health':
                health = client.health_check()
                print(f"\nService Status: {health['status']}")
                print(f"Message: {health['message']}")
                continue
            elif not text:
                continue
            
            # Check the text
            result = client.check_text(text)
            print_results(result, text)
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Sensitive Information Checker Client")
    parser.add_argument(
        "--server", 
        default="localhost:50051",
        help="gRPC server address (default: localhost:50051)"
    )
    parser.add_argument(
        "--text",
        help="Text to check for sensitive content"
    )
    parser.add_argument(
        "--file",
        help="File containing text to check"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Check service health and exit"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        help="Custom similarity threshold (0.0-1.0)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and connect client
    client = InfoCheckerClient(args.server)
    
    try:
        client.connect()
        
        # Health check mode
        if args.health:
            health = client.health_check()
            print(f"Service Status: {health['status']}")
            print(f"Message: {health['message']}")
            return 0 if health['status'] == 'SERVING' else 1
        
        # Interactive mode
        if args.interactive:
            interactive_mode(client)
            return 0
        
        # File input mode
        if args.file:
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception as e:
                print(f"Error reading file: {e}")
                return 1
        # Direct text input mode
        elif args.text:
            text = args.text
        else:
            print("Please provide --text, --file, --interactive, or --health")
            return 1
        
        # Check the text
        result = client.check_text(text, similarity_threshold=args.threshold)
        print_results(result, text)
        
        return 0
        
    except Exception as e:
        logger.error(f"Client error: {e}")
        return 1
    finally:
        client.disconnect()

if __name__ == '__main__':
    sys.exit(main()) 