import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def pytest_configure(config):
    # Ensure src is in the Python path
    if "src" not in sys.path:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
