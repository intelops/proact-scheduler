import os

TEMPORAL_HOST = os.getenv('PROACT_TEMPORAL_HOST', 'localhost:7233')

SERVER_PORT = os.getenv('PROACT_SERVER_PORT', 5000)