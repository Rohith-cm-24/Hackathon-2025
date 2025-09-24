#!/usr/bin/env python3
"""
Setup script for the Sensitive Information Checker.
Downloads required models and initializes the system.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    """Main setup function."""
    print("🔍 Setting up Sensitive Information Checker")
    print("=" * 60)
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment not detected.")
        print("   It's recommended to run this in a virtual environment.")
        response = input("   Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return 1
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return 1
    
    # Download spaCy English model
    if not run_command("python -m spacy download en_core_web_sm", "Downloading spaCy English model"):
        print("⚠️  Warning: spaCy model download failed. Some features may not work.")
    
    # Test imports
    print("🧪 Testing imports...")
    try:
        import grpc
        import sentence_transformers
        import spacy
        import presidio_analyzer
        print("✅ All core dependencies imported successfully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return 1
    
    # Test model loading
    print("🧪 Testing model loading...")
    try:
        # Test sentence transformers
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Sentence transformer model loaded successfully")
        
        # Test spaCy
        nlp = spacy.load("en_core_web_sm")
        print("✅ spaCy model loaded successfully")
        
    except Exception as e:
        print(f"❌ Model loading error: {e}")
        print("   Some features may not work properly.")
    
    # Create necessary directories
    dirs_to_create = ['logs', 'data', 'models']
    for dir_name in dirs_to_create:
        dir_path = Path(dir_name)
        dir_path.mkdir(exist_ok=True)
        print(f"📁 Created directory: {dir_name}")
    
    print("\n🎉 Setup completed successfully!")
    print("=" * 60)
    print("Next steps:")
    print("1. Start the server: python run_server.py")
    print("2. Test the client: python run_client.py --health")
    print("3. Run examples: python examples/client_example.py")
    print("4. Interactive mode: python run_client.py --interactive")
    print("\nFor more information, see README.md")
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 