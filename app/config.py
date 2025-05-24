import os

class Settings:
    WATCH_DIR = os.getenv('WATCH_DIR', '/input')
    S3_BUCKET = os.getenv('S3_BUCKET', 'videos')
    S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'http://minio:9000')
    S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'minioadmin')
    S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'minioadmin')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 10 * 1024 * 1024))  # 10MB
    STREAM_TIMEOUT = int(os.getenv('STREAM_TIMEOUT', 30))  # Seconds

settings = Settings()