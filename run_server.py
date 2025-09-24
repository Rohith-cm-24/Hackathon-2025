#!/usr/bin/env python3
"""
Simple server runner for the Sensitive Information Checker.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from info_checker_service import serve

if __name__ == '__main__':
    serve() 