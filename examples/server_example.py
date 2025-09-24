#!/usr/bin/env python3
"""
Example script for starting the Sensitive Information Checker gRPC server.
"""

import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from info_checker_service import serve

def main():
    """Start the server with custom configuration."""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    print("🔍 Starting Sensitive Information Checker gRPC Server")
    print("=" * 60)
    print("Features:")
    print("  • Explicit content detection (keywords, regex, PII)")
    print("  • Semantic analysis with sentence transformers")
    print("  • Real-time processing with low latency")
    print("  • Configurable business rules")
    print("  • Multi-threaded concurrent processing")
    print("=" * 60)
    
    try:
        # Start the server
        serve(port=50051, max_workers=10)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 