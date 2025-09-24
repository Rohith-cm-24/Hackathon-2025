#!/usr/bin/env python3
"""
Example script demonstrating the Sensitive Information Checker gRPC client.
"""

import sys
import os
import time

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from client import InfoCheckerClient, print_results

def test_examples():
    """Test the service with various example texts."""
    
    # Test cases with different types of sensitive content
    test_cases = [
        {
            "text": "Hello, this is a regular message with no sensitive content.",
            "description": "Non-sensitive text"
        },
        {
            "text": "My credit card number is 4532-1234-5678-9012 and my SSN is 123-45-6789.",
            "description": "PII - Credit card and SSN"
        },
        {
            "text": "I just got a salary increase to $85,000 per year! The company is doing well.",
            "description": "Salary information"
        },
        {
            "text": "We're planning layoffs next month due to budget constraints. About 20% of the engineering team will be affected.",
            "description": "Layoff information"
        },
        {
            "text": "The client ABC Corp signed a $2M deal yesterday. Their CEO seemed very happy with our proposal.",
            "description": "Client information"
        },
        {
            "text": "Our quarterly revenue was $5.2M, up 15% from last quarter. Profit margins improved to 18%.",
            "description": "Company financials"
        },
        {
            "text": "John's performance review was poor this year. He's been put on a performance improvement plan.",
            "description": "Employee performance"
        },
        {
            "text": "We're acquiring TechStart Inc for $50M. The deal should close next quarter.",
            "description": "Merger/acquisition"
        },
        {
            "text": "There's a security vulnerability in our payment system. We need to patch it urgently.",
            "description": "Technical security issue"
        },
        {
            "text": "The lawsuit against our company was settled for $1.5M. Legal advised us to keep this confidential.",
            "description": "Legal matters"
        }
    ]
    
    # Create client
    client = InfoCheckerClient("localhost:50051")
    
    try:
        print("🔍 Sensitive Information Checker - Client Examples")
        print("=" * 60)
        
        # Connect to server
        print("Connecting to server...")
        client.connect()
        
        # Check server health
        health = client.health_check()
        print(f"Server Status: {health['status']} - {health['message']}")
        
        if health['status'] != 'SERVING':
            print("❌ Server is not available. Please start the server first.")
            return 1
        
        print("\n🧪 Running test cases...")
        print("=" * 60)
        
        # Test each case
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📝 Test Case {i}: {test_case['description']}")
            print("-" * 40)
            
            start_time = time.time()
            result = client.check_text(test_case['text'])
            processing_time = time.time() - start_time
            
            print(f"⏱️  Processing time: {processing_time:.3f}s")
            print(f"🚨 Sensitive: {'YES' if result['is_sensitive'] else 'NO'}")
            print(f"⚠️  Risk Level: {result['overall_risk_level']}")
            print(f"📊 Confidence: {result['confidence_score']:.3f}")
            print(f"🔍 Matches: {len(result['matches'])}")
            
            if result['matches']:
                for match in result['matches']:
                    print(f"   • {match['match_type']}: {match['rule_name']} ({match['confidence']:.3f})")
        
        # Test batch processing
        print(f"\n🔄 Testing batch processing...")
        print("-" * 40)
        
        batch_texts = [case['text'] for case in test_cases[:3]]
        start_time = time.time()
        batch_results = client.check_batch(batch_texts)
        batch_time = time.time() - start_time
        
        print(f"⏱️  Batch processing time: {batch_time:.3f}s for {len(batch_texts)} texts")
        print(f"📈 Average per text: {batch_time/len(batch_texts):.3f}s")
        
        sensitive_count = sum(1 for result in batch_results if result['is_sensitive'])
        print(f"🚨 Sensitive texts found: {sensitive_count}/{len(batch_texts)}")
        
        print(f"\n✅ All tests completed successfully!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        client.disconnect()

def interactive_demo():
    """Run an interactive demo."""
    client = InfoCheckerClient("localhost:50051")
    
    try:
        client.connect()
        
        print("🔍 Interactive Demo - Sensitive Information Checker")
        print("=" * 60)
        print("Enter text to check for sensitive content.")
        print("Type 'examples' to run test cases, 'quit' to exit.")
        print("-" * 60)
        
        while True:
            text = input("\nEnter text: ").strip()
            
            if text.lower() in ['quit', 'exit', 'q']:
                break
            elif text.lower() == 'examples':
                return test_examples()
            elif not text:
                continue
            
            try:
                result = client.check_text(text)
                print_results(result, text)
            except Exception as e:
                print(f"Error: {e}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()

def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        return interactive_demo()
    else:
        return test_examples()

if __name__ == '__main__':
    sys.exit(main()) 