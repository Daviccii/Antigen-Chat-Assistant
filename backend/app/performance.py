"""Performance tracking utility for monitoring request latency."""

import time
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Track timing for different stages of request processing."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.timings: Dict[str, float] = {}
        self.start_time = time.time()
        self.logger = logger
        
    def mark(self, stage: str):
        """Mark a timing checkpoint."""
        elapsed = time.time() - self.start_time
        self.timings[stage] = elapsed
        self.logger.debug(f"[{self.request_id}] {stage}: {elapsed:.3f}s")
        
    def get_timing(self, stage: str) -> Optional[float]:
        """Get timing for a specific stage."""
        return self.timings.get(stage)
    
    def calculate_delta(self, start_stage: str, end_stage: str) -> Optional[float]:
        """Calculate time difference between two stages."""
        start_time = self.timings.get(start_stage)
        end_time = self.timings.get(end_stage)
        if start_time is not None and end_time is not None:
            return end_time - start_time
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        total_time = time.time() - self.start_time
        
        summary = {
            "request_id": self.request_id,
            "total_time": total_time,
            "timings": self.timings.copy(),
            "deltas": {}
        }
        
        # Calculate key deltas
        stages = list(self.timings.keys())
        for i in range(len(stages) - 1):
            delta = self.timings[stages[i + 1]] - self.timings[stages[i]]
            summary["deltas"][f"{stages[i]}_to_{stages[i+1]}"] = delta
        
        return summary
    
    def log_summary(self):
        """Log performance summary."""
        summary = self.get_summary()
        self.logger.info(f"[{self.request_id}] Performance summary: {summary}")


@contextmanager
def track_performance(tracker: PerformanceTracker, stage: str):
    """Context manager to track performance of a code block."""
    tracker.mark(f"{stage}_start")
    try:
        yield
    finally:
        tracker.mark(f"{stage}_end")