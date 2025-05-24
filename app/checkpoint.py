import redis
import hashlib
from config import settings
import logging
import os
import time

class CheckpointManager:
    def __init__(self):
        self.redis = None
        self._connect_redis() # Initial connection attempt

    def _connect_redis(self, retries=5, delay=5):
        """Attempts to connect to Redis with retries."""
        for i in range(retries):
            try:
                self.redis = redis.Redis.from_url(settings.REDIS_URL)
                self.redis.ping()
                logging.info("Redis connection successful")
                return True
            except redis.ConnectionError as e:
                logging.error(f"Failed to connect to Redis (attempt {i+1}/{retries}): {e}")
                self.redis = None # Ensure redis object is None if connection fails
                if i < retries - 1:
                    time.sleep(delay)
        logging.critical("Exceeded max retries. Could not connect to Redis. Application may not function correctly.")
        return False

    def _execute_redis_command(self, command, *args, retries=3, delay=1):
        """
        Executes a Redis command with retry logic for connection errors.
        Re-establishes connection if needed.
        """
        for i in range(retries):
            try:
                if self.redis is None:
                    logging.warning("Redis connection lost. Attempting to reconnect...")
                    if not self._connect_redis():
                        raise redis.ConnectionError("Failed to re-establish Redis connection.")
                
                return command(*args)
            except redis.ConnectionError as e:
                logging.warning(f"Redis connection error during command '{command.__name__}' (attempt {i+1}/{retries}): {e}. Retrying...")
                self.redis = None # Invalidate connection
                if i < retries - 1:
                    time.sleep(delay)
            except Exception as e:
                logging.error(f"An unexpected error occurred during Redis command '{command.__name__}': {e}")
                raise # Re-raise other exceptions
        
        logging.error(f"Failed to execute Redis command '{command.__name__}' after {retries} attempts.")
        raise redis.ConnectionError(f"Persistent Redis connection failure for command '{command.__name__}'")

    def create_stream_id(self, file_path):
        """
        Creates a new stream ID for a file path if one doesn't exist,
        or retrieves the existing one. Always returns bytes.
        """
        def _get_or_create_stream_id_bytes():
            stream_id_bytes = self.redis.hget(file_path, 'stream_id')
            if stream_id_bytes:
                return stream_id_bytes

            new_stream_id_str = hashlib.sha256(file_path.encode('utf-8')).hexdigest()
            new_stream_id_bytes = new_stream_id_str.encode('utf-8')

            self.redis.hset(file_path, 'stream_id', new_stream_id_bytes)
            self.redis.hset(file_path, 'offset', 0)
            
            return new_stream_id_bytes

        result_bytes = self._execute_redis_command(_get_or_create_stream_id_bytes)
        
        return result_bytes.decode('utf-8') if result_bytes else None

    def get_stream_id(self, file_path):
        stream_id_bytes = self._execute_redis_command(self.redis.hget, file_path, 'stream_id')
        return stream_id_bytes.decode('utf-8') if stream_id_bytes else None

    def get_offset(self, file_path):
        offset_bytes = self._execute_redis_command(self.redis.hget, file_path, 'offset')
        return int(offset_bytes) if offset_bytes else 0

    def update_offset(self, file_path, offset):
        logging.debug(f"Updating offset for {file_path} to {offset}")
        self._execute_redis_command(self.redis.hset, file_path, 'offset', offset)
        self._execute_redis_command(self.redis.expire, file_path, settings.STREAM_TIMEOUT * 2)
        logging.debug(f"Updated offset: {file_path} => {offset}")

    def clear(self, file_path):
        current_offset = self.get_offset(file_path)
        try:
            file_size = os.path.getsize(file_path)
            if current_offset >= file_size:
                self._execute_redis_command(self.redis.delete, file_path)
        except FileNotFoundError:
            logging.warning(f"Attempted to clear checkpoint for non-existent file: {file_path}. Deleting checkpoint.")
            self._execute_redis_command(self.redis.delete, file_path)
        except Exception as e:
            logging.error(f"Error checking file size for clearing checkpoint {file_path}: {e}")


    def update_last_activity_time(self, file_path):
        self._execute_redis_command(self.redis.hset, file_path, 'last_modified', time.time())

    def get_last_modified(self, file_path):
        last_mod_bytes = self._execute_redis_command(self.redis.hget, file_path, 'last_modified')
        return float(last_mod_bytes) if last_mod_bytes else 0

    def get_all_streams(self):
        all_keys_bytes = self._execute_redis_command(self.redis.keys, '*')
        
        stream_keys = []
        if all_keys_bytes:
            for key_bytes in all_keys_bytes:
                decoded_key = key_bytes.decode('utf-8')
                try:
                    stream_keys.append(decoded_key)
                except redis.ConnectionError:
                    logging.warning(f"Redis connection error in get_all_streams. Skipping.")
                    continue
                except Exception as e:
                    logging.error(f"Unexpected error checking key '{decoded_key}': {e}")
                    continue
        return stream_keys

    def remove_stream(self, file_path):
        self._execute_redis_command(self.redis.delete, file_path)