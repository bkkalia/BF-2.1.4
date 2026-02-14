"""
Thread-safe message queue for worker-to-UI communication.

This module provides non-blocking communication between scraping workers
and the UI thread, preventing app freezing.

Usage in workers:
    from ui_message_queue import send_log, send_progress, send_complete
    
    send_log(worker_id="W1", message="Processing department...")
    send_progress(worker_id="W1", current=10, total=50, status="Working")
    send_complete(worker_id="W1", data={"tenders": 150})

Usage in GUI:
    from ui_message_queue import get_pending_messages
    
    def process_ui_queue(self):
        messages = get_pending_messages()
        for msg in messages:
            if msg['type'] == 'log':
                self.log_area.insert('end', msg['message'])
        
        # Schedule next check
        self.root.after(100, self.process_ui_queue)
"""

import queue
import time
from threading import Lock
from datetime import datetime
from typing import Dict, List, Any, Optional


# Global message queue (thread-safe)
_message_queue = queue.Queue()

# Worker health tracking
_worker_health: Dict[str, Dict] = {}
_health_lock = Lock()


def send_log(worker_id: str, message: str, level: str = "INFO"):
    """
    Send a log message from worker to UI (non-blocking).
    
    Args:
        worker_id: Worker identifier (e.g., "W1", "MAIN")
        message: Log message text
        level: Log level ("INFO", "WARNING", "ERROR")
    """
    _message_queue.put({
        'type': 'log',
        'worker_id': worker_id,
        'message': message,
        'level': level,
        'timestamp': datetime.now()
    })
    
    # Update worker heartbeat
    _update_heartbeat(worker_id, f"Logging: {message[:30]}...")


def send_progress(worker_id: str, current: int, total: int, status: str = ""):
    """
    Send progress update from worker to UI (non-blocking).
    
    Args:
        worker_id: Worker identifier
        current: Current progress value
        total: Total/max progress value
        status: Status text (e.g., "Processing department X")
    """
    _message_queue.put({
        'type': 'progress',
        'worker_id': worker_id,
        'current': current,
        'total': total,
        'status': status,
        'percent': (current / total * 100) if total > 0 else 0,
        'timestamp': datetime.now()
    })
    
    # Update worker heartbeat
    _update_heartbeat(worker_id, status or f"Progress: {current}/{total}")


def send_complete(worker_id: str, data: Optional[Dict] = None, success: bool = True):
    """
    Send completion message from worker to UI.
    
    Args:
        worker_id: Worker identifier
        data: Optional result data
        success: Whether worker completed successfully
    """
    _message_queue.put({
        'type': 'complete',
        'worker_id': worker_id,
        'data': data or {},
        'success': success,
        'timestamp': datetime.now()
    })
    
    # Mark worker as completed
    with _health_lock:
        if worker_id in _worker_health:
            _worker_health[worker_id]['status'] = 'completed'
            _worker_health[worker_id]['success'] = success


def send_error(worker_id: str, error: str, exception: Optional[Exception] = None):
    """
    Send error message from worker to UI.
    
    Args:
        worker_id: Worker identifier
        error: Error message
        exception: Optional exception object
    """
    _message_queue.put({
        'type': 'error',
        'worker_id': worker_id,
        'error': error,
        'exception': str(exception) if exception else None,
        'timestamp': datetime.now()
    })
    
    # Mark worker as failed
    with _health_lock:
        if worker_id in _worker_health:
            _worker_health[worker_id]['status'] = 'error'
            _worker_health[worker_id]['error'] = error


def get_pending_messages(max_messages: int = 100) -> List[Dict]:
    """
    Get all pending messages from queue (call from UI thread).
    
    Args:
        max_messages: Maximum number of messages to retrieve in one call
    
    Returns:
        List of message dictionaries
    """
    messages = []
    
    try:
        # Get up to max_messages without blocking
        for _ in range(max_messages):
            try:
                msg = _message_queue.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break  # No more messages
    
    except Exception as e:
        # Should never happen, but log it just in case
        print(f"Error getting messages from queue: {e}")
    
    return messages


def clear_queue():
    """Clear all pending messages (useful for reset)"""
    try:
        while True:
            _message_queue.get_nowait()
    except queue.Empty:
        pass


def get_queue_size() -> int:
    """Get number of pending messages in queue"""
    return _message_queue.qsize()


# ============================================================================
# Worker Health Monitoring
# ============================================================================

def _update_heartbeat(worker_id: str, current_task: str):
    """Update worker heartbeat (internal)"""
    with _health_lock:
        if worker_id not in _worker_health:
            _worker_health[worker_id] = {
                'status': 'running',
                'started_at': time.time()
            }
        
        _worker_health[worker_id]['last_heartbeat'] = time.time()
        _worker_health[worker_id]['current_task'] = current_task


def register_worker(worker_id: str):
    """Register a new worker (call at worker start)"""
    with _health_lock:
        _worker_health[worker_id] = {
            'status': 'starting',
            'started_at': time.time(),
            'last_heartbeat': time.time(),
            'current_task': 'Initializing',
            'success': None,
            'error': None
        }


def unregister_worker(worker_id: str):
    """Unregister a worker (call at worker end)"""
    with _health_lock:
        if worker_id in _worker_health:
            del _worker_health[worker_id]


def get_worker_health(worker_id: str) -> Optional[Dict]:
    """Get health status for a specific worker"""
    with _health_lock:
        return _worker_health.get(worker_id, None)


def get_all_workers_health() -> Dict[str, Dict]:
    """Get health status for all workers"""
    with _health_lock:
        return dict(_worker_health)  # Return copy


def check_stuck_workers(timeout_seconds: int = 300) -> List[str]:
    """
    Check for workers that haven't sent heartbeat recently.
    
    Args:
        timeout_seconds: Seconds since last heartbeat to consider stuck
    
    Returns:
        List of stuck worker IDs
    """
    current_time = time.time()
    stuck_workers = []
    
    with _health_lock:
        for worker_id, health in _worker_health.items():
            if health['status'] == 'running':
                time_since_heartbeat = current_time - health.get('last_heartbeat', 0)
                
                if time_since_heartbeat > timeout_seconds:
                    stuck_workers.append(worker_id)
                    health['status'] = 'stuck'
    
    return stuck_workers


def reset_all_workers():
    """Reset all worker health data (useful for new scrape)"""
    with _health_lock:
        _worker_health.clear()
    
    clear_queue()


# ============================================================================
# Statistics and Diagnostics
# ============================================================================

def get_stats() -> Dict:
    """Get current queue and worker statistics"""
    with _health_lock:
        active_workers = sum(1 for w in _worker_health.values() if w['status'] == 'running')
        stuck_workers = sum(1 for w in _worker_health.values() if w['status'] == 'stuck')
        completed_workers = sum(1 for w in _worker_health.values() if w['status'] == 'completed')
        error_workers = sum(1 for w in _worker_health.values() if w['status'] == 'error')
    
    return {
        'queue_size': get_queue_size(),
        'total_workers': len(_worker_health),
        'active_workers': active_workers,
        'stuck_workers': stuck_workers,
        'completed_workers': completed_workers,
        'error_workers': error_workers
    }


def print_diagnostics():
    """Print diagnostic information (for debugging)"""
    stats = get_stats()
    print(f"\n{'='*60}")
    print(f"UI MESSAGE QUEUE DIAGNOSTICS")
    print(f"{'='*60}")
    print(f"Queue size: {stats['queue_size']} messages")
    print(f"Total workers: {stats['total_workers']}")
    print(f"  Active: {stats['active_workers']}")
    print(f"  Stuck: {stats['stuck_workers']}")
    print(f"  Completed: {stats['completed_workers']}")
    print(f"  Errors: {stats['error_workers']}")
    
    print(f"\nWorker Details:")
    workers = get_all_workers_health()
    for worker_id, health in workers.items():
        last_hb = health.get('last_heartbeat', 0)
        if last_hb:
            time_since_hb = time.time() - last_hb
            hb_str = f"{time_since_hb:.1f}s ago"
        else:
            hb_str = "never"
        
        print(f"  {worker_id}: {health['status']} | Last heartbeat: {hb_str}")
        print(f"    Current task: {health.get('current_task', 'Unknown')}")
    
    print(f"{'='*60}\n")


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Example usage demonstration"""
    import threading
    import time
    
    def example_worker(worker_id: str, num_items: int):
        """Simulate a worker processing items"""
        register_worker(worker_id)
        
        send_log(worker_id, f"Worker {worker_id} started")
        
        for i in range(num_items):
            # Simulate work
            time.sleep(0.5)
            
            # Send progress update
            send_progress(worker_id, current=i+1, total=num_items, 
                         status=f"Processing item {i+1}")
            
            # Send log message
            if (i + 1) % 5 == 0:
                send_log(worker_id, f"Processed {i+1} items")
        
        send_complete(worker_id, data={"items_processed": num_items})
        send_log(worker_id, f"Worker {worker_id} completed")
    
    def example_ui_processor():
        """Simulate UI thread processing messages"""
        print("UI processor starting...")
        
        for _ in range(30):  # Run for 30 iterations
            messages = get_pending_messages()
            
            for msg in messages:
                if msg['type'] == 'log':
                    print(f"[{msg['worker_id']}] {msg['message']}")
                elif msg['type'] == 'progress':
                    print(f"[{msg['worker_id']}] Progress: {msg['percent']:.0f}% - {msg['status']}")
                elif msg['type'] == 'complete':
                    print(f"[{msg['worker_id']}] ✓ COMPLETED")
            
            # Check for stuck workers
            stuck = check_stuck_workers(timeout_seconds=10)
            if stuck:
                print(f"⚠️  Stuck workers detected: {stuck}")
            
            time.sleep(0.2)  # Simulate 100ms UI update interval
        
        print_diagnostics()
    
    # Start workers
    print("Starting example workers...")
    worker_threads = []
    for i in range(3):
        t = threading.Thread(target=example_worker, args=(f"W{i+1}", 10))
        t.start()
        worker_threads.append(t)
    
    # Start UI processor in main thread
    example_ui_processor()
    
    # Wait for workers
    for t in worker_threads:
        t.join()
    
    print("\nExample complete!")
