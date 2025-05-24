# Video Chunk Uploader

This project implements a Python-based video processing pipeline that monitors a specified input directory 
for new or modified MP4 files, chunks them (based on configured values), and uploads these chunks to an S3-compatible object storage (like MinIO). 
It leverages Redis for checkpointing to enable resumable uploads and to track the processing state of each video file.

The system is designed to be resilient to temporary outages of its external dependencies (Redis and MinIO) by implementing robust retry mechanisms and providing clear logging for troubleshooting.

## Features

* **Directory Monitoring:** Continuously watches a designated input directory for new or modified MP4 files.
* **Chunked Uploads:** Divides large video files into smaller chunks for efficient upload to object storage.
* **S3/MinIO Integration:** Uploads video chunks and metadata to an S3-compatible object storage.
* **Redis Checkpointing:** Uses Redis to store the upload offset and other state information, allowing uploads to resume from where they left off after interruptions.
* **Resilience:**
    * **Redis:** Implements intelligent retry logic and automatic re-connection for Redis operations, ensuring the application can recover from Redis service interruptions.
    * **MinIO/S3:** Configures `boto3` client-side retries and provides explicit logging for S3 connection issues, indicating when MinIO is unavailable.
* **Metadata Generation:** Generates a JSON metadata file for each completed video, containing details like stream ID, chunk list, and completion timestamp, uploaded alongside the video chunks.
* **Asynchronous Monitoring:** A separate thread monitors active video streams for completion based on file size and last activity, triggering finalization steps.

## Project Structure

* `main.py`: The entry point of the application, responsible for setting up logging, initializing components, and starting the file system observer.
* `config.py`: Defines environment variables for configuring Redis, S3/MinIO, chunk size, and the watch directory.
* `video_processor.py`: Implements the `watchdog` event handler to detect file system events (create, modify) and trigger the video upload process.
* `chunk_uploader.py`: Handles the logic for chunking video files, uploading them to S3/MinIO, and generating/uploading metadata. Includes enhanced S3 error logging.
* `checkpoint.py`: Manages the application's state in Redis. Provides methods for creating stream IDs, updating/retrieving upload offsets, tracking last activity, and robustly interacting with Redis with retry logic.
* `stream_monitor.py`: A separate thread that periodically checks the status of active video streams in Redis to determine if they are fully uploaded and then finalizes their processing (e.g., uploading metadata).

## Setup and Installation

This project is designed to run within a Dockerized environment, using `docker-compose` for setup of Redis and MinIO and local testing

### Prerequisites

* Docker Desktop (or Docker Engine and Docker Compose)

### Running the Application

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd video-chunk-uploader
    ```

2.  Run the following command in video-processor
    ```docker-compose build --no-cache && docker-compose up```

    

4.  **Create a `requirements.txt` file:**
    Create a `requirements.txt` file in the root of your project directory with the following content:

    ```
    watchdog
    redis
    boto3
    ```

5.  **Create the `input` directory:**
    ```bash
    mkdir input
    ```
    This directory will be mounted into the Docker container, and you will place your `.mp4` files here for processing.

6.  **Build and run the services:**
    ```bash
    docker-compose up --build -d
    ```
    This command will build your application image, start Redis, MinIO, and your application in detached mode.

### Monitoring Logs

You can monitor the application's logs to see the processing status:

```bash
docker-compose logs -f app