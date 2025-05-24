import logging
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionError as BotoConnectionError
from checkpoint import CheckpointManager
from config import settings
import hashlib
import base64
import json
import time

class ChunkUploader:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(retries={'max_attempts': 3})
        )

    def upload_file(self, file_path, checkpoint, max_s3_retries=5, s3_retry_delay=5):        
        for attempt in range(max_s3_retries):
            try:
                self.single_upload_file_attempt(file_path, checkpoint)
                logging.info(f"Successfully completed upload for {file_path}")
                return # File completely uploaded, exit the retry loop

            # Catch specific S3-related errors for retry
            except (ClientError, BotoConnectionError) as e:
                logging.error(f"S3 error during upload of {file_path} (attempt {attempt + 1}/{max_s3_retries}): {e}")
                if attempt < max_s3_retries - 1:
                    logging.info(f"Retrying S3 upload for {file_path} in {s3_retry_delay} seconds...")
                    time.sleep(s3_retry_delay)
                else:
                    logging.critical(f"Failed to upload {file_path} to S3 after {max_s3_retries} attempts due to persistent S3 issues.")
                    raise
            except (FileNotFoundError, PermissionError, IOError) as e:
                logging.error(f"File I/O error during upload of {file_path}: {e}")
                raise 
            except Exception as e:
                logging.error(f"Critical upload error for {file_path}: {e}", exc_info=True)
                raise
        
    def single_upload_file_attempt(self, file_path, checkpoint):
        stream_id = checkpoint.create_stream_id(file_path)
        current_offset = checkpoint.get_offset(file_path)
        logging.info(f"Starting upload from offset {current_offset}")

        try:
            if not os.path.isfile(file_path): # Redundant with FileNotFound :/
                logging.warning(f"File not found: {file_path}")
                return

            with open(file_path, 'rb') as f:
                f.seek(current_offset)
                chunk_number = current_offset
                
                while True:
                    chunk = f.read(settings.CHUNK_SIZE)
                    logging.info(f"Read chunk size: {len(chunk)} chunk_number: {chunk_number}")

                    if not chunk:
                        break
                    
                    self.upload_chunk(stream_id, chunk_number, chunk)
                    checkpoint.update_offset(file_path, f.tell())
                    checkpoint.update_last_activity_time(file_path)
                    logging.info(f"New Redis state: {checkpoint.redis.hgetall(file_path)}")
                    chunk_number += 1
        except (FileNotFoundError, PermissionError, IOError) as e:
            logging.error(f"File I/O error: {str(e)}")
        except Exception as e:
            logging.error(f"Critical upload error: {str(e)}")
            raise

    def upload_chunk(self, stream_id, chunk_number, chunk):
        key = f"{stream_id}/chunk_{chunk_number:06d}.bin"
        logging.info(f"Uploading chunk: {key} chunk_number: {chunk_number}")

        try:
            chunk_md5 = base64.b64encode(hashlib.md5(chunk).digest()).decode('utf-8')

            self.s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=chunk,
                ContentMD5=chunk_md5
            )
        except (ClientError, BotoConnectionError) as e:
            logging.error(f"MinIO/S3 connection unavailable or error during upload_chunk {stream_id}, {chunk_number}")
            raise
        except Exception as e:
            logging.error(f"Upload failed for {key}: {str(e)}")
            raise

    def get_chunk_list(self, stream_id):
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=settings.S3_BUCKET,
                Prefix=f"{stream_id}/chunk_"
            )
            
            return sorted(
                [obj['Key'] for page in pages for obj in page.get('Contents', [])],
                key=lambda x: int(x.split('_')[-1].split('.')[0])  # Sort by chunk number
            )
        except (ClientError, BotoConnectionError) as e:
            logging.error(f"MinIO/S3 connection unavailable or error during get_chunk_list for {stream_id}")
            raise
        except Exception as e:
            logging.error(f"Chunk list failed: {str(e)}")
            return []
        
    def upload_metadata(self, stream_id, metadata):
        try:
            self.s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=f"{stream_id}/metadata.json",
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )
            logging.info(f"Metadata uploaded for {stream_id}")
        except (ClientError, BotoConnectionError) as e:
            logging.error(f"MinIO/S3 connection unavailable or error during metadata upload for {key}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Metadata upload failed: {str(e)}")
            raise