import logging
from watchdog.observers import Observer
from video_processor import VideoEventHandler
from config import settings
from chunk_uploader import ChunkUploader
from checkpoint import CheckpointManager
from stream_monitor import StreamMonitor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Entry point - infinite loop watching for events in a folder defined in config.settings
def main():
    try:
        # CheckpointManager uses redis to manage upload state 
        checkpoint = CheckpointManager()
        # ChunkUploader handles uploading small chunks of the video to minIO
        uploader = ChunkUploader()
        # StreamMonitor checks file upload state to figure out if the the processing is complete
        StreamMonitor(checkpoint, uploader)
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
        logging.error("Raised in main", e)

if __name__ == "__main__":
    main()