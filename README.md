# Video Chunk Uploader

This project implements a Python-based video processing pipeline that monitors a specified input directory
for new or modified MP4 files, chunks them (as defined in a config file), and uploads these chunks to an S3-compatible object storage (like MinIO). 
It uses Redis for checkpointing to enable resumable uploads and to track the processing state of each video file.

## Features

* **Directory Monitoring:** Use watchdog library to continuously monitor a designated input directory for new or modified MP4 files.

* **Chunked Uploads:** Divides large video files into smaller (10MB) chunks for efficient upload to object storage.

* **MinIO Integration:** Uploads video chunks and metadata to an S3-compatible object storage/Only tested MinIO locally

* **Redis Checkpointing:** Uses Redis to store the upload offset and other state information, allowing uploads to resume from where they left off after interruptions.

* **Resilience:**
    * **Redis:** Implements intelligent retry logic and automatic re-connection for Redis operations, ensuring the application can recover from Redis service interruptions.
    * **MinIO/S3:** Configures `boto3` client-side retries and provides explicit logging for S3 connection issues, indicating when MinIO is unavailable. -- Initial implementation was blocking on file upload -- when I killed minio it did not error out. You will therefore see a `single_upload_file_attempt` method.  Also, I did not add code to create the bucket - would have added it as a separate script.

* **Metadata Generation:** Generates a JSON metadata file for each completed video, containing details like stream ID, chunk list, and completion timestamp, uploaded alongside the video chunks. (I would have wanted to make that file more readable, convert to date time but did not get to it
)
* **Asynchronous Monitoring:** A separate thread monitors active video streams for completion based on file size and last activity, triggering finalization steps. (I separated this since clean up unlike other functionalities should not be event-driven)

## Project Structure

* `main.py`: The entry point of the application, responsible for setting up logging, initializing components, and starting the file system observer.
* `config.py`: Defines environment variables for configuring Redis, S3/MinIO, chunk size, and the watch directory.
* `video_processor.py`: Implements the `watchdog` event handler to detect file system events (create, modify) and trigger the video upload process.
* `chunk_uploader.py`: Handles the logic for chunking video files, uploading them to S3/MinIO, and generating/uploading metadata. Includes enhanced S3 error logging.
* `checkpoint.py`: Manages the application's state in Redis. Provides methods for creating stream IDs, updating/retrieving upload offsets, tracking last activity, and robustly interacting with Redis with retry logic.
* `stream_monitor.py`: A separate thread that periodically checks the status of active video streams in Redis to determine if they are fully uploaded and then finalizes their processing (e.g., uploading metadata).

** Known Issues **
* Bucket needs to be created in minio manually (priority)
* Did not get to Prometheus monitoring (priority)
* Monitor that writes the JSON/finalizes the code cannot resume finalizing if an error occurs (Bug)
* Update to file after "finalizing" stream as complete will amount to re-write. (by-design)

## Setup and Installation

This project is designed to run within a Dockerized environment, using `docker-compose` for setup of dependent services (Redis and MinIO) and local testing

### Prerequisites

* Docker Desktop (or Docker Engine and Docker Compose)

### Running the Application

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/momput/video-processing.git
    cd video-processor
    ```

2.  ** Run **
    
    ```bash
    docker-compose up --build -d
    ```
    This command will build your application image, start Redis, MinIO, and your application in detached mode.

### Monitoring Logs

You can monitor the application's logs to see the processing status:

```bash
docker-compose logs -f app
```

### Testing

1. Interrupting MinIO
```
bash
dd if=/dev/urandom of=./input/minio_test.mp4 bs=1M count=100
```

2. On a separate terminal
```bash
 docker-compose stop minio
 ```

3. Review logs - you should see
```

```

4. Now stop redis
```docker-compose stop redis```

You should see

```
video-processor-1  | 2025-05-24 01:08:46,303 - INFO - Read chunk size: 10485760 chunk_number: 10485766
video-processor-1  | 2025-05-24 01:08:46,304 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485766.bin chunk_number: 10485766
redis-1            | 1:signal-handler (1748048927) Received SIGTERM scheduling shutdown...
redis-1            | 1:M 24 May 2025 01:08:47.823 * User requested shutdown...
redis-1            | 1:M 24 May 2025 01:08:47.823 * Saving the final RDB snapshot before exiting.
redis-1            | 1:M 24 May 2025 01:08:47.826 * DB saved on disk
redis-1            | 1:M 24 May 2025 01:08:47.826 # Redis is now ready to exit, bye bye...
redis-1 exited with code 0
video-processor-1  | 2025-05-24 01:08:49,788 - WARNING - Redis connection error during command 'hset' (attempt 1/3): Error -2 con

```

5. Now start redis
```docker-compose start redis```

You should see
```
redis-1            | 1:M 24 May 2025 01:09:06.355 * Ready to accept connections tcp
video-processor-1  | 2025-05-24 01:09:11,003 - INFO - Redis connection successful
video-processor-1  | 2025-05-24 01:09:11,093 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'83886080', b'last_modified': b'1748048951.0793974'}
video-processor-1  | 2025-05-24 01:09:11,116 - INFO - Read chunk size: 10485760 chunk_number: 10485767
video-processor-1  | 2025-05-24 01:09:11,116 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485767.bin chunk_number: 10485767
video-processor-1  | 2025-05-24 01:09:16,350 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'94371840', b'last_modified': b'1748048956.3363721'}
video-processor-1  | 2025-05-24 01:09:16,387 - INFO - Read chunk size: 10485760 chunk_number: 10485768
video-processor-1  | 2025-05-24 01:09:16,387 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485768.bin chunk_number: 10485768
video-processor-1  | 2025-05-24 01:09:23,049 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'104857600', b'last_modified': b'1748048963.0353959'}
video-processor-1  | 2025-05-24 01:09:23,063 - INFO - Read chunk size: 0 chunk_number: 10485769
video-processor-1  | 2025-05-24 01:09:23,070 - INFO - Successfully completed upload for /input/minio_test.mp4
```