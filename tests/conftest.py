"""
Shared pytest configuration.
Adds the project root to sys.path so all imports resolve correctly
regardless of which directory pytest is invoked from.
"""

import sys
import os

# Insert the project root (parent of this tests/ dir) into the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
