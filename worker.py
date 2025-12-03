"""
Celery Worker Entry Point
Run this in separate pods for distributed PDF processing

Usage:
    python worker.py

Or with Celery command:
    celery -A celery_app worker --loglevel=info --concurrency=3 --queues=pdf_processing
"""

import os
import sys
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    # Start worker
    # This will process tasks from the queue
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=3',  # 3 concurrent tasks per worker pod
        '--queues=pdf_processing,quiz_generation',
        '--max-tasks-per-child=50',  # Restart after 50 tasks (memory management)
        '--time-limit=3600',  # 1 hour hard limit
        '--soft-time-limit=3000',  # 50 minutes soft limit
    ])
