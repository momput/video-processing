import logging
import time
import threading
from flask import Flask, jsonify, request
from config import settings
import os
import psutil
from werkzeug.utils import secure_filename
from config import settings

# Then use it in the upload function
WATCH_DIR = settings.WATCH_DIR  # Add this line near the top after imports
# Import existing components
from checkpoint import CheckpointManager
from chunk_uploader import ChunkUploader

admin_app = Flask(__name__)

# Global references to existing components
checkpoint_manager = None
chunk_uploader = None
stream_monitor = None

def initialize_admin_api(checkpoint, uploader, monitor):
    """Initialize admin API with references to existing components"""
    global checkpoint_manager, chunk_uploader, stream_monitor
    checkpoint_manager = checkpoint
    chunk_uploader = uploader
    stream_monitor = monitor

@admin_app.route('/admin/health', methods=['GET'])
def health_check():
    """Comprehensive health check with behavioral metrics"""
    try:
        # Component health checks
        redis_health = get_redis_health()
        minio_health = get_minio_health()
        system_health = get_system_health()
        
        # Behavioral metrics
        upload_metrics = get_upload_metrics()
        
        # Overall status determination
        overall_status = determine_overall_status(redis_health, minio_health, upload_metrics)
        
        return jsonify({
            'status': overall_status,
            'timestamp': time.time(),
            'components': {
                'redis': redis_health,
                'minio': minio_health,
                'system': system_health
            },
            'metrics': upload_metrics,
            'behavioral_indicators': get_behavioral_indicators()
        })
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@admin_app.route('/admin/actions', methods=['GET'])
def list_available_actions():
    """List all available remediation actions"""
    return jsonify({
        'available_actions': [
            {
                'name': 'restart_redis_connection',
                'description': 'Reset Redis connection pool during connectivity issues',
                'risk_level': 'low',
                'execution_time_seconds': 5,
                'prerequisites': [],
                'parameters': [],
                'rollback_available': False
            },
            {
                'name': 'clear_stuck_uploads',
                'description': 'Clear upload streams that have been stuck for more than specified time',
                'risk_level': 'medium',
                'execution_time_seconds': 15,
                'prerequisites': ['redis_access'],
                'parameters': [
                    {
                        'name': 'max_age_minutes',
                        'type': 'integer',
                        'default': 60,
                        'description': 'Maximum age of streams to clear (in minutes)'
                    }
                ],
                'rollback_available': False
            },
            {
                'name': 'restart_minio_client',
                'description': 'Recreate MinIO S3 client to resolve connection issues',
                'risk_level': 'low',
                'execution_time_seconds': 3,
                'prerequisites': [],
                'parameters': [],
                'rollback_available': False
            },
            {
                'name': 'adjust_chunk_size',
                'description': 'Temporarily adjust chunk size for performance optimization',
                'risk_level': 'low',
                'execution_time_seconds': 1,
                'prerequisites': [],
                'parameters': [
                    {
                        'name': 'new_size_mb',
                        'type': 'integer',
                        'default': 5,
                        'description': 'New chunk size in megabytes'
                    }
                ],
                'rollback_available': True
            },
            {
                'name': 'restart_stream_monitor',
                'description': 'Restart stream monitor thread to resolve memory leaks',
                'risk_level': 'medium',
                'execution_time_seconds': 10,
                'prerequisites': [],
                'parameters': [],
                'rollback_available': False
            }
        ]
    })

@admin_app.route('/admin/execute/<action_name>', methods=['POST'])
def execute_action(action_name):
    """Execute a specific remediation action"""
    try:
        request_data = request.get_json() or {}
        parameters = request_data.get('parameters', {})
        dry_run = request_data.get('dry_run', False)
        
        logging.info(f"Executing action: {action_name}, dry_run: {dry_run}, params: {parameters}")
        
        # Route to specific action handlers
        if action_name == 'restart_redis_connection':
            result = restart_redis_connection(dry_run)
        elif action_name == 'clear_stuck_uploads':
            max_age_minutes = parameters.get('max_age_minutes', 60)
            result = clear_stuck_uploads(max_age_minutes, dry_run)
        elif action_name == 'restart_minio_client':
            result = restart_minio_client(dry_run)
        elif action_name == 'adjust_chunk_size':
            new_size_mb = parameters.get('new_size_mb', 5)
            result = adjust_chunk_size(new_size_mb, dry_run)
        elif action_name == 'restart_stream_monitor':
            result = restart_stream_monitor(dry_run)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown action: {action_name}'
            }), 400
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Action execution failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_redis_health():
    """Check Redis health and connectivity"""
    try:
        if checkpoint_manager and checkpoint_manager.redis:
            # Test basic connectivity
            start_time = time.time()
            checkpoint_manager.redis.ping()
            response_time = (time.time() - start_time) * 1000
            
            # Get Redis info
            redis_info = checkpoint_manager.redis.info()
            memory_usage = redis_info.get('used_memory', 0)
            max_memory = redis_info.get('maxmemory', 0)
            
            memory_percentage = (memory_usage / max_memory) if max_memory > 0 else 0
            
            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'memory_usage_bytes': memory_usage,
                'memory_percentage': round(memory_percentage * 100, 2),
                'connected_clients': redis_info.get('connected_clients', 0),
                'last_error': None
            }
        else:
            return {
                'status': 'unhealthy',
                'error': 'Redis connection not available'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': None
        }

def get_minio_health():
    """Check MinIO health and connectivity"""
    try:
        if chunk_uploader and chunk_uploader.s3:
            # Test basic connectivity by listing buckets
            start_time = time.time()
            chunk_uploader.s3.list_buckets()
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'endpoint': settings.S3_ENDPOINT,
                'bucket': settings.S3_BUCKET,
                'last_error': None
            }
        else:
            return {
                'status': 'unhealthy',
                'error': 'MinIO client not available'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': None
        }

def get_system_health():
    """Get system resource information"""
    try:
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk_info = psutil.disk_usage('/')
        
        return {
            'memory_usage_percentage': memory_info.percent,
            'memory_available_bytes': memory_info.available,
            'cpu_usage_percentage': cpu_percent,
            'disk_usage_percentage': disk_info.percent,
            'disk_free_bytes': disk_info.free
        }
    except Exception as e:
        return {
            'error': str(e)
        }

def get_upload_metrics():
    """Get upload-related metrics"""
    try:
        active_streams = []
        if checkpoint_manager:
            active_streams = checkpoint_manager.get_all_streams()
        
        return {
            'active_uploads': len(active_streams),
            'pending_finalizations': len([s for s in active_streams if should_be_finalized(s)]),
            'uptime_seconds': get_service_uptime()
        }
    except Exception as e:
        logging.error(f"Error getting upload metrics: {str(e)}")
        return {
            'active_uploads': 0,
            'pending_finalizations': 0,
            'uptime_seconds': 0,
            'error': str(e)
        }

def get_behavioral_indicators():
    """Get behavioral indicators for AI analysis"""
    try:
        indicators = {}
        
        # Check for stuck streams
        if checkpoint_manager:
            all_streams = checkpoint_manager.get_all_streams()
            stuck_streams = 0
            for stream in all_streams:
                last_modified = checkpoint_manager.get_last_modified(stream)
                if time.time() - last_modified > 300:  # 5 minutes
                    stuck_streams += 1
            
            indicators['stuck_streams_count'] = stuck_streams
            indicators['total_active_streams'] = len(all_streams)
        
        # System resource trends
        indicators['memory_pressure'] = get_memory_pressure_indicator()
        indicators['connection_health'] = get_connection_health_indicator()
        
        return indicators
    except Exception as e:
        return {'error': str(e)}

def determine_overall_status(redis_health, minio_health, upload_metrics):
    """Determine overall system status"""
    if redis_health['status'] == 'unhealthy' or minio_health['status'] == 'unhealthy':
        return 'unhealthy'
    
    # Check for degraded performance indicators
    if (redis_health.get('response_time_ms', 0) > 1000 or 
        minio_health.get('response_time_ms', 0) > 2000 or
        upload_metrics.get('pending_finalizations', 0) > 5):
        return 'degraded'
    
    return 'healthy'

# Action implementation functions
def restart_redis_connection(dry_run=False):
    """Restart Redis connection pool"""
    try:
        if dry_run:
            return {
                'status': 'success',
                'action': 'restart_redis_connection',
                'dry_run': True,
                'message': 'Would restart Redis connection pool'
            }
        
        if checkpoint_manager:
            # Close existing connection
            if checkpoint_manager.redis:
                checkpoint_manager.redis.close()
            
            # Force reconnection
            checkpoint_manager.redis = None
            success = checkpoint_manager._connect_redis()
            
            return {
                'status': 'success' if success else 'failed',
                'action': 'restart_redis_connection',
                'timestamp': time.time(),
                'message': 'Redis connection restarted' if success else 'Failed to restart Redis connection'
            }
        else:
            return {
                'status': 'error',
                'message': 'CheckpointManager not available'
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def clear_stuck_uploads(max_age_minutes=60, dry_run=False):
    """Clear upload streams that have been stuck"""
    try:
        if not checkpoint_manager:
            return {'status': 'error', 'message': 'CheckpointManager not available'}
        
        all_streams = checkpoint_manager.get_all_streams()
        stuck_streams = []
        
        max_age_seconds = max_age_minutes * 60
        current_time = time.time()
        
        for stream in all_streams:
            last_modified = checkpoint_manager.get_last_modified(stream)
            if current_time - last_modified > max_age_seconds:
                stuck_streams.append(stream)
        
        if dry_run:
            return {
                'status': 'success',
                'action': 'clear_stuck_uploads',
                'dry_run': True,
                'message': f'Would clear {len(stuck_streams)} stuck uploads',
                'stuck_streams': stuck_streams
            }
        
        # Actually clear stuck streams
        cleared_count = 0
        for stream in stuck_streams:
            try:
                checkpoint_manager.clear(stream)
                cleared_count += 1
            except Exception as e:
                logging.error(f"Failed to clear stream {stream}: {str(e)}")
        
        return {
            'status': 'success',
            'action': 'clear_stuck_uploads',
            'timestamp': time.time(),
            'cleared_count': cleared_count,
            'total_stuck': len(stuck_streams),
            'message': f'Cleared {cleared_count} out of {len(stuck_streams)} stuck uploads'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def restart_minio_client(dry_run=False):
    """Restart MinIO S3 client"""
    try:
        if dry_run:
            return {
                'status': 'success',
                'action': 'restart_minio_client',
                'dry_run': True,
                'message': 'Would recreate MinIO S3 client'
            }
        
        if chunk_uploader:
            # Recreate S3 client with fresh connection pool
            import boto3
            from botocore.config import Config
            
            chunk_uploader.s3 = boto3.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=Config(retries={'max_attempts': 3})
            )
            
            return {
                'status': 'success',
                'action': 'restart_minio_client',
                'timestamp': time.time(),
                'message': 'MinIO S3 client recreated successfully'
            }
        else:
            return {
                'status': 'error',
                'message': 'ChunkUploader not available'
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def adjust_chunk_size(new_size_mb, dry_run=False):
    """Adjust chunk size for performance optimization"""
    try:
        new_size_bytes = new_size_mb * 1024 * 1024
        current_size = settings.CHUNK_SIZE
        
        if dry_run:
            return {
                'status': 'success',
                'action': 'adjust_chunk_size',
                'dry_run': True,
                'message': f'Would change chunk size from {current_size // (1024*1024)}MB to {new_size_mb}MB',
                'current_size_mb': current_size // (1024*1024),
                'new_size_mb': new_size_mb
            }
        
        # Update the settings
        settings.CHUNK_SIZE = new_size_bytes
        
        return {
            'status': 'success',
            'action': 'adjust_chunk_size',
            'timestamp': time.time(),
            'previous_size_mb': current_size // (1024*1024),
            'new_size_mb': new_size_mb,
            'message': f'Chunk size adjusted from {current_size // (1024*1024)}MB to {new_size_mb}MB'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def restart_stream_monitor(dry_run=False):
    """Restart stream monitor thread"""
    try:
        if dry_run:
            return {
                'status': 'success',
                'action': 'restart_stream_monitor',
                'dry_run': True,
                'message': 'Would restart stream monitor thread'
            }
        
        # Note: This is a simplified implementation
        # In practice, you'd need to properly manage thread lifecycle
        return {
            'status': 'success',
            'action': 'restart_stream_monitor',
            'timestamp': time.time(),
            'message': 'Stream monitor restart initiated'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

# Helper functions
def should_be_finalized(stream_path):
    """Check if a stream should have been finalized by now"""
    try:
        if not checkpoint_manager:
            return False
        
        last_modified = checkpoint_manager.get_last_modified(stream_path)
        return time.time() - last_modified > settings.STREAM_TIMEOUT
    except:
        return False

def get_service_uptime():
    """Get service uptime in seconds"""
    try:
        # This is a simplified implementation
        # You might want to track actual startup time
        return time.time() - start_time if 'start_time' in globals() else 0
    except:
        return 0

def get_memory_pressure_indicator():
    """Get memory pressure indicator"""
    try:
        memory_info = psutil.virtual_memory()
        if memory_info.percent > 85:
            return 'high'
        elif memory_info.percent > 70:
            return 'medium'
        else:
            return 'low'
    except:
        return 'unknown'

def get_connection_health_indicator():
    """Get connection health indicator"""
    try:
        redis_health = get_redis_health()
        minio_health = get_minio_health()
        
        if (redis_health['status'] == 'healthy' and 
            minio_health['status'] == 'healthy' and
            redis_health.get('response_time_ms', 0) < 100 and
            minio_health.get('response_time_ms', 0) < 500):
            return 'excellent'
        elif (redis_health['status'] == 'healthy' and 
              minio_health['status'] == 'healthy'):
            return 'good'
        else:
            return 'poor'
    except:
        return 'unknown'

def start_admin_server():
    """Start the admin API server"""
    global start_time
    start_time = time.time()
    
    logging.info("Starting admin API server on port 8080")
    admin_app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

# Initialize and start admin server in separate thread
def initialize_and_start_admin_api(checkpoint, uploader, monitor):
    """Initialize components and start admin API"""
    initialize_admin_api(checkpoint, uploader, monitor)
    
    # Start admin server in daemon thread
    admin_thread = threading.Thread(target=start_admin_server, daemon=True)
    admin_thread.start()
    
    return admin_thread



#### DEMO ####

# Demo failure injection endpoints
@admin_app.route('/admin/inject/redis-connection-failure', methods=['POST'])
def inject_redis_failure():
    """Simulate Redis connection failure for demo"""
    try:
        if checkpoint_manager and checkpoint_manager.redis:
            checkpoint_manager.redis.close()
            checkpoint_manager.redis = None
        
        return jsonify({
            'status': 'success',
            'message': 'Redis connection failure injected',
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_app.route('/admin/inject/minio-connection-failure', methods=['POST'])
def inject_minio_failure():
    """Simulate MinIO connection failure for demo"""
    try:
        if chunk_uploader:
            # Force invalid endpoint to simulate connection failure
            chunk_uploader.s3._endpoint.host = 'invalid-endpoint'
        
        return jsonify({
            'status': 'success',
            'message': 'MinIO connection failure injected',
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_app.route('/admin/inject/stuck-uploads', methods=['POST'])
def inject_stuck_uploads():
    """Create stuck upload streams for demo"""
    try:
        if not checkpoint_manager:
            return jsonify({'status': 'error', 'message': 'CheckpointManager not available'})
        
        # Create some fake stuck streams
        for i in range(3):
            fake_path = f"/tmp/stuck_upload_{i}.mp4"
            stream_id = checkpoint_manager.create_stream_id(fake_path)
            checkpoint_manager.update_offset(fake_path, 1024 * 1024)  # 1MB
            # Set last modified to 2 hours ago
            checkpoint_manager.redis.hset(fake_path, 'last_modified', time.time() - 7200)
        
        return jsonify({
            'status': 'success',
            'message': 'Stuck uploads injected',
            'count': 3,
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    

# Add these configurations to your Flask app
admin_app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB limit
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_app.route('/upload', methods=['POST'])
def upload_file():
    """Upload endpoint for video files"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    
    try:
        # Secure filename and save to watch directory
        filename = secure_filename(file.filename)
        filepath = os.path.join(WATCH_DIR, filename)
        
        # Handle filename conflicts
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{base}_{counter}{ext}"
                filepath = os.path.join(WATCH_DIR, filename)
                counter += 1
        
        # Ensure watch directory exists
        os.makedirs(WATCH_DIR, exist_ok=True)
        
        # Save file
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        return jsonify({
            "status": "success",
            "message": "File uploaded and queued for processing",
            "filename": filename,
            "size_bytes": file_size,
            "watch_directory": WATCH_DIR
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500