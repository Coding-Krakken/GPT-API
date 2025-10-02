import os

def get_api_key():
    """Get API key from environment or .env file."""
    return os.getenv("API_KEY", "test-key-123")
