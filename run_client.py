#!/usr/bin/env python3
"""
Simple client runner for the Sensitive Information Checker.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from client import main

if __name__ == '__main__':
    sys.exit(main()) 