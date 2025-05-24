import logging
import os
import time
import threading
from watchdog.events import FileSystemEventHandler
from chunk_uploader import ChunkUploader
from checkpoint import CheckpointManager
from config import settings

class VideoEventHandler(FileSystemEventHandler):
    def __init__(self, checkpoint, uploader):
        self.checkpoint = checkpoint
        self.uploader = uploader

    def on_created(self, event):
        logging.info(f"on_create Event detected: {event.src_path}")
        self.process_event(event)

    def on_modified(self, event):
        logging.info(f"on_modified Event detected: {event.src_path}")
        self.process_event(event)

    def on_deleted(self, event):
        # Just log/notify?
        logging.info(f"on_deleted Event detected: {event.src_path}")

    def process_event(self, event):
        try:
            if event.is_directory or not event.src_path.endswith(".mp4"):
                logging.info(f"Ignoring non-MP4/directory event: {event.src_path}")
                return
                
            file_path = os.path.abspath(event.src_path)
            if not os.path.exists(file_path):  # Handle deleted files
                logging.warning(f"File deleted: {file_path}")
                return

            self.uploader.upload_file(file_path, self.checkpoint)
            self.checkpoint.update_last_activity_time(file_path)                # Update monitoring timestamp
        except Exception as e:
            logging.error(f"Failed processing event {event}: {str(e)}", exc_info=True)

    
