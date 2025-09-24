"""
gRPC service implementation for the sensitive information checker.
Combines explicit content detection and semantic analysis.
"""

import logging
import time
from concurrent import futures
from typing import List, Dict, Optional
import grpc

import info_checker_pb2
import info_checker_pb2_grpc
from detectors import ExplicitContentDetector, DetectionMatch
from semantic_analyzer import SemanticAnalyzer, BusinessRule

logger = logging.getLogger(__name__)

class InfoCheckerService(info_checker_pb2_grpc.InfoCheckerServicer):
    """
    gRPC service implementation for sensitive information checking.
    """
    
    def __init__(self, 
                 similarity_threshold: float = 0.7,
                 enable_semantic_analysis: bool = True,
                 enable_explicit_detection: bool = True):
        """
        Initialize the info checker service.
        
        Args:
            similarity_threshold: Threshold for semantic similarity matching
            enable_semantic_analysis: Whether to enable semantic analysis
            enable_explicit_detection: Whether to enable explicit content detection
        """
        self.similarity_threshold = similarity_threshold
        self.enable_semantic_analysis = enable_semantic_analysis
        self.enable_explicit_detection = enable_explicit_detection
        
        # Initialize detectors
        logger.info("Initializing sensitive information checker service...")
        
        if self.enable_explicit_detection:
            try:
                self.explicit_detector = ExplicitContentDetector()
                logger.info("Explicit content detector initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize explicit detector: {e}")
                self.explicit_detector = None
        else:
            self.explicit_detector = None
        
        if self.enable_semantic_analysis:
            try:
                self.semantic_analyzer = SemanticAnalyzer(
                    similarity_threshold=self.similarity_threshold
                )
                logger.info("Semantic analyzer initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize semantic analyzer: {e}")
                self.semantic_analyzer = None
        else:
            self.semantic_analyzer = None
        
        logger.info("Info checker service initialization complete")
    
    def CheckText(self, request, context):
        """
        Check a single text for sensitive content.
        """
        start_time = time.time()
        
        try:
            # Extract parameters from request
            text = request.text
            custom_threshold = request.similarity_threshold if request.similarity_threshold > 0 else None
            
            if not text.strip():
                return info_checker_pb2.CheckResponse(
                    is_sensitive=False,
                    matches=[],
                    overall_risk_level="LOW",
                    confidence_score=0.0
                )
            
            # Collect all matches
            all_matches = []
            
            # Run explicit content detection
            if self.explicit_detector and self.enable_explicit_detection:
                try:
                    explicit_matches = self.explicit_detector.detect_all(text)
                    all_matches.extend(explicit_matches)
                    logger.debug(f"Found {len(explicit_matches)} explicit matches")
                except Exception as e:
                    logger.error(f"Error in explicit detection: {e}")
            
            # Run semantic analysis
            if self.semantic_analyzer and self.enable_semantic_analysis:
                try:
                    # Use sentence-level analysis for better granularity
                    semantic_matches = self.semantic_analyzer.analyze_sentences(text, custom_threshold)
                    all_matches.extend(semantic_matches)
                    logger.debug(f"Found {len(semantic_matches)} semantic matches")
                except Exception as e:
                    logger.error(f"Error in semantic analysis: {e}")
            
            # Process and deduplicate matches
            processed_matches = self._process_matches(all_matches)
            
            # Determine overall sensitivity and risk level
            is_sensitive = len(processed_matches) > 0
            risk_level, confidence_score = self._calculate_risk_level(processed_matches)
            
            # Convert matches to protobuf format
            pb_matches = []
            for match in processed_matches:
                pb_match = info_checker_pb2.SensitiveMatch(
                    match_type=match.match_type,
                    rule_name=match.rule_name,
                    matched_text=match.matched_text,
                    confidence=match.confidence,
                    start_position=match.start_position,
                    end_position=match.end_position,
                    explanation=match.explanation
                )
                pb_matches.append(pb_match)
            
            # Create response
            response = info_checker_pb2.CheckResponse(
                is_sensitive=is_sensitive,
                matches=pb_matches,
                overall_risk_level=risk_level,
                confidence_score=confidence_score
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Processed text check in {processing_time:.3f}s - "
                       f"Sensitive: {is_sensitive}, Matches: {len(processed_matches)}, "
                       f"Risk: {risk_level}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in CheckText: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return info_checker_pb2.CheckResponse()
    
    def CheckBatch(self, request, context):
        """
        Check multiple texts in batch.
        """
        start_time = time.time()
        
        try:
            responses = []
            
            for check_request in request.requests:
                # Process each request individually
                response = self.CheckText(check_request, context)
                responses.append(response)
            
            batch_response = info_checker_pb2.BatchCheckResponse(responses=responses)
            
            processing_time = time.time() - start_time
            logger.info(f"Processed batch of {len(request.requests)} texts in {processing_time:.3f}s")
            
            return batch_response
            
        except Exception as e:
            logger.error(f"Error in CheckBatch: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return info_checker_pb2.BatchCheckResponse()
    
    def HealthCheck(self, request, context):
        """
        Health check endpoint.
        """
        try:
            # Check if core components are working
            status = info_checker_pb2.HealthCheckResponse.SERVING
            message = "Service is healthy"
            
            if not self.explicit_detector and self.enable_explicit_detection:
                status = info_checker_pb2.HealthCheckResponse.NOT_SERVING
                message = "Explicit detector not available"
            elif not self.semantic_analyzer and self.enable_semantic_analysis:
                status = info_checker_pb2.HealthCheckResponse.NOT_SERVING
                message = "Semantic analyzer not available"
            
            return info_checker_pb2.HealthCheckResponse(
                status=status,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error in HealthCheck: {e}")
            return info_checker_pb2.HealthCheckResponse(
                status=info_checker_pb2.HealthCheckResponse.NOT_SERVING,
                message=f"Health check failed: {str(e)}"
            )
    
    def _process_matches(self, matches: List[DetectionMatch]) -> List[DetectionMatch]:
        """
        Process and deduplicate matches.
        """
        if not matches:
            return []
        
        # Sort by confidence (highest first)
        sorted_matches = sorted(matches, key=lambda x: x.confidence, reverse=True)
        
        # Remove low-confidence matches
        filtered_matches = [m for m in sorted_matches if m.confidence >= 0.5]
        
        # For semantic matches, keep only the highest confidence match per rule type
        seen_semantic_rules = set()
        final_matches = []
        
        for match in filtered_matches:
            if match.match_type == "SEMANTIC":
                if match.rule_name not in seen_semantic_rules:
                    final_matches.append(match)
                    seen_semantic_rules.add(match.rule_name)
            else:
                final_matches.append(match)
        
        return final_matches
    
    def _calculate_risk_level(self, matches: List[DetectionMatch]) -> tuple[str, float]:
        """
        Calculate overall risk level and confidence score based on matches.
        """
        if not matches:
            return "LOW", 0.0
        
        # Calculate weighted confidence score
        total_weight = 0
        weighted_sum = 0
        high_risk_count = 0
        
        for match in matches:
            # Assign weights based on match type
            weight = 1.0
            if match.match_type == "REGEX":
                weight = 1.2  # Regex patterns are quite reliable
            elif match.match_type == "PII":
                weight = 1.3  # PII detection is very important
            elif match.match_type == "KEYWORD":
                weight = 0.9  # Keywords might have false positives
            elif match.match_type == "SEMANTIC":
                weight = 1.1  # Semantic matches are contextual
            
            weighted_sum += match.confidence * weight
            total_weight += weight
            
            # Count high-confidence matches
            if match.confidence >= 0.8:
                high_risk_count += 1
        
        # Calculate overall confidence
        overall_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Determine risk level
        if high_risk_count >= 2 or overall_confidence >= 0.85:
            risk_level = "HIGH"
        elif len(matches) >= 3 or overall_confidence >= 0.7:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return risk_level, overall_confidence
    
    def add_custom_rule(self, rule: BusinessRule):
        """Add a custom business rule to the semantic analyzer."""
        if self.semantic_analyzer:
            self.semantic_analyzer.add_custom_rule(rule)
    
    def get_business_rules(self) -> List[Dict]:
        """Get list of all business rules."""
        if self.semantic_analyzer:
            return self.semantic_analyzer.list_rules()
        return []

def create_server(port: int = 50051, 
                 max_workers: int = 10,
                 similarity_threshold: float = 0.7) -> grpc.Server:
    """
    Create and configure the gRPC server.
    
    Args:
        port: Port to listen on
        max_workers: Maximum number of worker threads
        similarity_threshold: Threshold for semantic similarity
        
    Returns:
        Configured gRPC server
    """
    # Create thread pool executor for handling concurrent requests
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    
    # Create and add the service
    info_checker_service = InfoCheckerService(
        similarity_threshold=similarity_threshold
    )
    info_checker_pb2_grpc.add_InfoCheckerServicer_to_server(
        info_checker_service, server
    )
    
    # Add listening port
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"gRPC server configured to listen on {listen_addr}")
    
    return server

def serve(port: int = 50051, max_workers: int = 10):
    """
    Start the gRPC server and serve requests.
    
    Args:
        port: Port to listen on
        max_workers: Maximum number of worker threads
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start server
    server = create_server(port=port, max_workers=max_workers)
    
    try:
        server.start()
        logger.info(f"Sensitive Information Checker gRPC server started on port {port}")
        logger.info("Server is ready to accept requests...")
        
        # Keep the server running
        server.wait_for_termination()
        
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(grace=5)
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        server.stop(grace=0)

if __name__ == '__main__':
    serve() 