import logging
from watchdog.observers import Observer
from video_processor import VideoEventHandler
from config import settings
from chunk_uploader import ChunkUploader
from checkpoint import CheckpointManager
from stream_monitor import StreamMonitor
from admin_api import initialize_and_start_admin_api  # Add this import

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    try:
        # CheckpointManager uses redis to manage upload state 
        checkpoint = CheckpointManager()
        # ChunkUploader handles uploading small chunks of the video to minIO
        uploader = ChunkUploader()
        # StreamMonitor checks file upload state to figure out if the the processing is complete
        stream_monitor = StreamMonitor(checkpoint, uploader)
        
        # Initialize and start admin API
        admin_thread = initialize_and_start_admin_api(checkpoint, uploader, stream_monitor)
        logging.info("Admin API started successfully")
        
        # VideoEventHandler responds to Watchdog's specific events oncreate/onupdate
        video_event_handler = VideoEventHandler(checkpoint, uploader)
        observer = Observer()
        observer.schedule(video_event_handler, settings.WATCH_DIR, recursive=False)
        observer.start()
        
        try:
            while True:
                pass
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except Exception as e:
        logging.error("Raised in main: %s", e)

if __name__ == "__main__":
    main()