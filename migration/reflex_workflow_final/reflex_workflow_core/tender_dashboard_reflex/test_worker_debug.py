"""
Debug script to test worker process startup independently.
"""
import multiprocessing as mp
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def simple_worker(worker_id, result_queue):
    """Minimal worker function - MUST be module-level for Windows pickling."""
    try:
        result_queue.put({
            "type": "log",
            "message": f"Worker {worker_id} started successfully!"
        })
        result_queue.put({
            "type": "status",
            "worker_id": worker_id,
            "status": "running"
        })
        import time
        time.sleep(1)
        result_queue.put({
            "type": "log",
            "message": f"Worker {worker_id} completing..."
        })
        result_queue.put(None)  # Signal completion
    except Exception as e:
        result_queue.put({
            "type": "error",
            "message": f"Worker {worker_id} error: {str(e)}"
        })


def test_worker_spawn():
    """Test if worker processes can spawn and communicate."""
    
    print("Testing multiprocessing worker spawn...")
    result_queue = mp.Queue()
    workers = []
    
    # Spawn 3 workers
    for i in range(3):
        p = mp.Process(target=simple_worker, args=(i, result_queue))
        p.daemon = True
        p.start()
        workers.append(p)
        print(f"Started worker {i} with PID {p.pid}")
    
    # Collect results
    active_workers = len(workers)
    timeout = 10
    start_time = __import__('time').time()
    
    while active_workers > 0:
        try:
            elapsed = __import__('time').time() - start_time
            if elapsed > timeout:
                print(f"TIMEOUT after {timeout}s - {active_workers} workers still active")
                break
                
            result = result_queue.get(timeout=1)
            if result is None:
                active_workers -= 1
                print(f"Worker completed. {active_workers} remaining")
            else:
                print(f"Received: {result}")
        except __import__('queue').Empty:
            print(f"Queue empty... {active_workers} workers still active")
            continue
    
    # Wait for workers
    for p in workers:
        p.join(timeout=2)
        if p.is_alive():
            print(f"Worker {p.pid} still alive - terminating")
            p.terminate()
        else:
            print(f"Worker {p.pid} finished cleanly")
    
    print("\nTest complete!")


if __name__ == "__main__":
    # Set multiprocessing start method (important on Windows)
    mp.set_start_method('spawn', force=True)
    test_worker_spawn()
