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

def validate_s3_bucket():
    """Validate that the required S3 bucket exists before starting service"""
    logging.info("In validate s3 bucket")
    print("print In validate s3 bucket")
    try:
        uploader = ChunkUploader()
        uploader.s3.head_bucket(Bucket=settings.S3_BUCKET)
        logging.info(f"S3 bucket validation successful: {settings.S3_BUCKET}")
        return True
    except Exception as e:
        logging.critical(f"S3 bucket validation failed: {settings.S3_BUCKET} - {str(e)}")
        logging.critical("Service cannot start without S3 bucket access")
        return False

def main():
    try:
        # Validate S3 bucket exists before starting service
        if not validate_s3_bucket():
            logging.critical("Exiting due to S3 bucket validation failure")
            exit(1)

        # CheckpointManager uses redis to manage upload state 
        checkpoint = CheckpointManager()
        # ChunkUploader handles uploading small chunks of the video to minIO
        uploader = ChunkUploader()
        # StreamMonitor checks file upload state to figure out if the the processing is complete
        stream_monitor = StreamMonitor(checkpoint, uploader)
        
        # Initialize and start admin API
        admin_thread = initialize_and_start_admin_api(checkpoint, uploader, stream_monitor)
        logging.info("Admin API started successfully .. v2")
        
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