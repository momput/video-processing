
import threading
import logging
import time
import os
from config import settings
TIME_OUT = 30

class StreamMonitor:
    def __init__(self, checkpoint, uploader):
        self.checkpoint = checkpoint
        self.uploader = uploader
        self._running = True
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def run(self):
        """Independent thread checking streams every 60s - It is less important that completion
           is detected ASAP. 
        """
        logging.info(f"Start Monitoring")

        while self._running:
            try:
                self.check_streams()
            except Exception as e:
                logging.error(f"Monitor error: {str(e)}")
            time.sleep(TIME_OUT)

    def check_streams(self):
        """Check all tracked streams for completion"""
        active_streams = self.checkpoint.get_all_streams()
        for file_path in active_streams:
            logging.info(f"Checking if {file_path} is complete")
            if self.is_video_stream_complete(file_path):
                logging.info(f"Finalizing stream {file_path}")
                self.finalize_stream(file_path)
            else:
                logging.info(f"Not Finalizing stream {file_path}")

    def is_video_stream_complete(self, file_path):
        """Completion criteria check"""
        if not os.path.exists(file_path):
            return False
        current_time = time.time()
        last_modified = self.checkpoint.get_last_modified(file_path)
        current_size = os.path.getsize(file_path)
        current_offset = self.checkpoint.get_offset(file_path)
        time_since_activity = current_time - last_modified
        
        # Completion conditions
        offset_complete = current_offset >= current_size
        timeout_reached = time_since_activity >= settings.STREAM_TIMEOUT # TBD is it in seconds?
            
        logging.info(f"Stream check: {file_path} "
                        f"offset={current_offset}/{current_size} "
                        f"last_mod={current_time - last_modified:.1f}s ago")
            
        return offset_complete and timeout_reached

    def finalize_stream(self, file_path):
        logging.info(f"Finalize stream for {file_path}")

        try:
            stream_id = self.checkpoint.get_stream_id(file_path)
            if not stream_id:
                logging.error(f"No stream ID found for {file_path}")
                return
            
            # Generate and upload metadata
            stream_id = self.checkpoint.get_stream_id(file_path)
            metadata = {
                "stream_id": stream_id,
                "chunks": self.uploader.get_chunk_list(stream_id),
                "completed_at": time.time(),
                "file_size": os.path.getsize(file_path)
            }
            self.uploader.upload_metadata(stream_id, metadata)
        
            # Clear state only after successful upload
            self.checkpoint.clear(file_path)
             
        except Exception as e:
            logging.error(f"Finalization failed for {file_path}: {str(e)}")

        self.checkpoint.remove_stream(file_path)  # New cleanup method
