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

2.  Run
    
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
video-processor-1  | 2025-05-24 01:07:47,558 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_000000.bin chunk_number: 0
video-processor-1  | 2025-05-24 01:07:53,753 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'10485760', b'last_modified': b'1748048873.7321723'}
video-processor-1  | 2025-05-24 01:07:53,785 - INFO - Read chunk size: 10485760 chunk_number: 1
video-processor-1  | 2025-05-24 01:07:53,785 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_000001.bin chunk_number: 1
minio-1            | INFO: Exiting on signal: TERMINATED
minio-1 exited with code 0
video-processor-1  | 2025-05-24 01:07:58,632 - ERROR - MinIO/S3 connection unavailable or error during upload_chunk c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6, 1
video-processor-1  | 2025-05-24 01:07:58,645 - ERROR - Critical upload error: Could not connect to the endpoint URL: "http://minio:9000/videos/c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_000001.bin"
video-processor-1  | 2025-05-24 01:07:58,645 - ERROR - S3 error during upload of /input/minio_test.mp4 (attempt 1/5): Could not connect to the endpoint URL: "http://minio:9000/videos/c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_000001.bin"
video-processor-1  | 2025-05-24 01:07:58,645 - INFO - Retrying S3 upload for /input/minio_test.mp4 in 5 seconds...
video-processor-1  | 2025-05-24 01:08:03,680 - INFO - Starting upload from offset 10485760
video-processor-1  | 2025-05-24 01:08:03,740 - INFO - Read chunk size: 10485760 chunk_number: 10485760
video-processor-1  | 2025-05-24 01:08:03,747 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485760.bin chunk_number: 10485760
video-processor-1  | 2025-05-24 01:08:07,160 - ERROR - MinIO/S3 connection unavailable or error during upload_chunk c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6, 10485760
video-processor-1  | 2025-05-24 01:08:07,167 - ERROR - Critical upload error: Could not connect to the endpoint URL: "http://minio:9000/videos/c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485760.bin"
video-processor-1  | 2025-05-24 01:08:07,167 - ERROR - S3 error during upload of /input/minio_test.mp4 (attempt 2/5): Could not connect to the endpoint URL: "http://minio:9000/videos/c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485760.bin"
video-processor-1  | 2025-05-24 01:08:07,167 - INFO - Retrying S3 upload for /input/minio_test.mp4 in 5 seconds...
minio-1            | MinIO Object Storage Server
minio-1            | Copyright: 2015-2025 MinIO, Inc.
minio-1            | License: GNU AGPLv3 - https://www.gnu.org/licenses/agpl-3.0.html
minio-1            | Version: RELEASE.2025-04-22T22-12-26Z (go1.24.2 linux/arm64)
minio-1            | 
minio-1            | API: http://172.21.0.3:9000  http://127.0.0.1:9000 
minio-1            | WebUI: http://172.21.0.3:9001 http://127.0.0.1:9001  
minio-1            | 
minio-1            | Docs: https://docs.min.io
minio-1            | WARN: Detected default credentials 'minioadmin:minioadmin', we recommend that you change these values with 'MINIO_ROOT_USER' and 'MINIO_ROOT_PASSWORD' environment variables
video-processor-1  | 2025-05-24 01:08:12,214 - INFO - Starting upload from offset 10485760
video-processor-1  | 2025-05-24 01:08:12,285 - INFO - Read chunk size: 10485760 chunk_number: 10485760
video-processor-1  | 2025-05-24 01:08:12,291 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485760.bin chunk_number: 10485760
video-processor-1  | 2025-05-24 01:08:19,239 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'20971520', b'last_modified': b'1748048899.2259817'}
video-processor-1  | 2025-05-24 01:08:19,282 - INFO - Read chunk size: 10485760 chunk_number: 10485761
video-processor-1  | 2025-05-24 01:08:19,289 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485761.bin chunk_number: 10485761
```

4. Now stop redis
```docker-compose stop redis```

You should see

```
video-processor-1  | 2025-05-24 01:08:35,861 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485764.bin chunk_number: 10485764
video-processor-1  | 2025-05-24 01:08:41,164 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'62914560', b'last_modified': b'1748048921.149959'}
video-processor-1  | 2025-05-24 01:08:41,191 - INFO - Read chunk size: 10485760 chunk_number: 10485765
video-processor-1  | 2025-05-24 01:08:41,197 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485765.bin chunk_number: 10485765
video-processor-1  | 2025-05-24 01:08:46,259 - INFO - New Redis state: {b'stream_id': b'c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6', b'offset': b'73400320', b'last_modified': b'1748048926.2449746'}
video-processor-1  | 2025-05-24 01:08:46,303 - INFO - Read chunk size: 10485760 chunk_number: 10485766
video-processor-1  | 2025-05-24 01:08:46,304 - INFO - Uploading chunk: c39f53d4d8ebc7b66b8a942066ef4e9730d96b5ce01179e39876354c4484a5a6/chunk_10485766.bin chunk_number: 10485766
redis-1            | 1:signal-handler (1748048927) Received SIGTERM scheduling shutdown...
redis-1            | 1:M 24 May 2025 01:08:47.823 * User requested shutdown...
redis-1            | 1:M 24 May 2025 01:08:47.823 * Saving the final RDB snapshot before exiting.
redis-1            | 1:M 24 May 2025 01:08:47.826 * DB saved on disk
redis-1            | 1:M 24 May 2025 01:08:47.826 # Redis is now ready to exit, bye bye...
redis-1 exited with code 0
video-processor-1  | 2025-05-24 01:08:49,788 - WARNING - Redis connection error during command 'hset' (attempt 1/3): Error -2 connecting to redis:6379. Name or service not known.. Retrying...
video-processor-1  | 2025-05-24 01:08:50,807 - WARNING - Redis connection lost. Attempting to reconnect...
video-processor-1  | 2025-05-24 01:08:50,825 - ERROR - Failed to connect to Redis (attempt 1/5): Error -2 connecting to redis:6379. Name or service not known.
video-processor-1  | 2025-05-24 01:08:55,854 - ERROR - Failed to connect to Redis (attempt 2/5): Error -2 connecting to redis:6379. Name or service not known.
video-processor-1  | 2025-05-24 01:09:00,901 - ERROR - Failed to connect to Redis (attempt 3/5): Error -2 connecting to redis:6379. Name or service not known.
video-processor-1  | 2025-05-24 01:09:05,935 - ERROR - Failed to connect to Redis (attempt 4/5): Error -2 connecting to redis:6379. Name or service not known.
```

5. Now start redis
```docker-compose start redis```

You should see
```
redis-1            | 1:C 24 May 2025 01:09:06.328 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
redis-1            | 1:C 24 May 2025 01:09:06.328 * Redis version=8.0.1, bits=64, commit=00000000, modified=1, pid=1, just started
redis-1            | 1:C 24 May 2025 01:09:06.328 * Configuration loaded
redis-1            | 1:M 24 May 2025 01:09:06.329 * monotonic clock: POSIX clock_gettime
redis-1            | 1:M 24 May 2025 01:09:06.330 * Running mode=standalone, port=6379.
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf> RedisBloom version 8.0.1 (Git=unknown)
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf> Registering configuration options: [
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { bf-error-rate       :      0.01 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { bf-initial-size     :       100 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { bf-expansion-factor :         2 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { cf-bucket-size      :         2 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { cf-initial-size     :      1024 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { cf-max-iterations   :        20 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { cf-expansion-factor :         1 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf>        { cf-max-expansions   :        32 }
redis-1            | 1:M 24 May 2025 01:09:06.330 * <bf> ]
redis-1            | 1:M 24 May 2025 01:09:06.331 * Module 'bf' loaded from /usr/local/lib/redis/modules//redisbloom.so
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Redis version found by RedisSearch : 8.0.1 - oss
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> RediSearch version 8.0.1 (Git=5688fcc)
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Low level api version 1 initialized successfully
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> gc: ON, prefix min length: 2, min word length to stem: 4, prefix max expansions: 200, query timeout (ms): 500, timeout policy: return, cursor read size: 1000, cursor max idle (ms): 300000, max doctable size: 1000000, max number of search results:  1000000, 
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Initialized thread pools!
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Disabled workers threadpool of size 0
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Subscribe to config changes
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Enabled role change notification
redis-1            | 1:M 24 May 2025 01:09:06.336 * <search> Cluster configuration: AUTO partitions, type: 0, coordinator timeout: 0ms
redis-1            | 1:M 24 May 2025 01:09:06.337 * <search> Register write commands
redis-1            | 1:M 24 May 2025 01:09:06.337 * Module 'search' loaded from /usr/local/lib/redis/modules//redisearch.so
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries> RedisTimeSeries version 80001, git_sha=577bfa8b5909e7ee572f0b651399be8303dc6641
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries> Redis version found by RedisTimeSeries : 8.0.1 - oss
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries> Registering configuration options: [
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-compaction-policy   :              }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-num-threads         :            3 }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-retention-policy    :            0 }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-duplicate-policy    :        block }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-chunk-size-bytes    :         4096 }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-encoding            :   compressed }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-ignore-max-time-diff:            0 }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries>        { ts-ignore-max-val-diff :     0.000000 }
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries> ]
redis-1            | 1:M 24 May 2025 01:09:06.338 * <timeseries> Detected redis oss
redis-1            | 1:M 24 May 2025 01:09:06.339 * Module 'timeseries' loaded from /usr/local/lib/redis/modules//redistimeseries.so
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Created new data type 'ReJSON-RL'
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> version: 80001 git sha: unknown branch: unknown
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Exported RedisJSON_V1 API
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Exported RedisJSON_V2 API
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Exported RedisJSON_V3 API
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Exported RedisJSON_V4 API
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Exported RedisJSON_V5 API
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Enabled diskless replication
redis-1            | 1:M 24 May 2025 01:09:06.341 * <ReJSON> Initialized shared string cache, thread safe: false.
redis-1            | 1:M 24 May 2025 01:09:06.342 * Module 'ReJSON' loaded from /usr/local/lib/redis/modules//rejson.so
redis-1            | 1:M 24 May 2025 01:09:06.342 * <search> Acquired RedisJSON_V5 API
redis-1            | 1:M 24 May 2025 01:09:06.354 * Server initialized
redis-1            | 1:M 24 May 2025 01:09:06.354 * <search> Loading event starts
redis-1            | 1:M 24 May 2025 01:09:06.354 * <search> Enabled workers threadpool of size 4
redis-1            | 1:M 24 May 2025 01:09:06.354 * Loading RDB produced by version 8.0.1
redis-1            | 1:M 24 May 2025 01:09:06.354 * RDB age 19 seconds
redis-1            | 1:M 24 May 2025 01:09:06.354 * RDB memory usage when created 1.14 Mb
redis-1            | 1:M 24 May 2025 01:09:06.354 * Done loading RDB, keys loaded: 1, keys expired: 0.
redis-1            | 1:M 24 May 2025 01:09:06.355 * <search> Disabled workers threadpool of size 4
redis-1            | 1:M 24 May 2025 01:09:06.355 * <search> Loading event ends
redis-1            | 1:M 24 May 2025 01:09:06.355 * DB loaded from disk: 0.001 seconds
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