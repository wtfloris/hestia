import sys
import os
import json
import types
from unittest.mock import MagicMock

# Add hestia source directory to sys.path
hestia_dir = os.path.join(os.path.dirname(__file__), '..', 'hestia')
sys.path.insert(0, hestia_dir)

# Mock the secrets module before any hestia imports
mock_secrets = types.ModuleType('hestia_utils.secrets')
mock_secrets.TOKEN = "fake-token-for-testing"
mock_secrets.DB = {
    "database": "test_db",
    "host": "localhost",
    "user": "test_user",
    "password": "test_pass",
    "port": "5432"
}
mock_secrets.OWN_CHAT_ID = 12345
mock_secrets.PRIVILEGED_USERS = [12345]
mock_secrets.WORKDIR = "/tmp/"
sys.modules['hestia_utils.secrets'] = mock_secrets

# Patch logging.basicConfig to avoid writing to /data/hestia.log
import logging
_original_basicConfig = logging.basicConfig
def _patched_basicConfig(**kwargs):
    kwargs.pop('filename', None)
    _original_basicConfig(**kwargs)
logging.basicConfig = _patched_basicConfig

# Mock telegram.Bot to avoid network calls during import of meta.py
import telegram
telegram.Bot = MagicMock()

import pytest
import requests


@pytest.fixture
def mock_response():
    """Factory fixture that creates mock requests.models.Response objects."""
    def _make(content, status_code=200):
        r = MagicMock(spec=requests.models.Response)
        # Commonly used by parsers for content-type sniffing.
        r.headers = {}
        if isinstance(content, dict) or isinstance(content, list):
            r.content = json.dumps(content).encode('utf-8')
        elif isinstance(content, str):
            r.content = content.encode('utf-8')
        elif isinstance(content, bytes):
            r.content = content
        else:
            r.content = str(content).encode('utf-8')
        r.status_code = status_code
        return r
    return _make
