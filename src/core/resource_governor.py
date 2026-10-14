import os
import gc
import io
import time
import psutil
import logging
import threading
from typing import Optional, Any
from PIL import Image

logger = logging.getLogger(__name__)


class ResourceGovernor:
    """
    Central Governor for System Resource Management:
    1. Global AI Inference Semaphore (strict 1-thread execution limit across all nodes).
    2. Shared Unified PaddleOCR Singleton (saves 700MB+ duplicate RAM).
    3. Re-usable Screencap Byte Buffer (prevents RAM garbage collector bloat).
    4. RAM & CPU Watchdog to enforce maximum hardware boundaries.
    """
    _instance = None
    _init_lock = threading.Lock()

    def __init__(self):
        # 1. Global AI Semaphore (strictly limited to 1 thread at a time)
        self.ai_semaphore = threading.Semaphore(1)
        
        # 2. Shared single PaddleOCR instance
        self._shared_ocr: Optional[Any] = None
        self._ocr_lock = threading.Lock()

        # 3. Screencap binary buffer pool
        self._screencap_pool: list[io.BytesIO] = [io.BytesIO() for _ in range(4)]
        self._pool_lock = threading.Lock()

        # 4. Limits and Monitoring
        try:
            from src.core.config_manager import load_app_settings
            settings = load_app_settings()
            self.max_ram_mb: int = int(settings.get("max_ram_mb", 800))
            self.max_cpu_pct: float = float(settings.get("max_cpu_pct", 75.0))
        except Exception:
            self.max_ram_mb = 800
            self.max_cpu_pct = 75.0

        self.last_gc_time: float = 0.0
        self.last_cpu_time: float = 0.0

    @classmethod
    def get(cls) -> "ResourceGovernor":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = ResourceGovernor()
        return cls._instance

    def get_shared_ocr(self) -> Any:
        """
        Returns the single shared PaddleOCR engine instance.
        Eliminates duplicate 350MB AI model weights in RAM across detector modules.
        """
        if self._shared_ocr is None:
            with self._ocr_lock:
                if self._shared_ocr is None:
                    logger.info("Initializing Unified Single PaddleOCR Engine (PP-OCRv4)...")
                    from paddleocr import PaddleOCR
                    self._shared_ocr = PaddleOCR(
                        ocr_version='PP-OCRv4',
                        use_angle_cls=False,
                        lang='en',
                        show_log=False,
                        enable_mkldnn=False,
                        cpu_threads=1,
                        drop_score=0.45,
                        det_limit_side_len=960,
                        det_limit_type='max'
                    )
        return self._shared_ocr

    def acquire_screencap_buffer(self) -> io.BytesIO:
        """Borrows a reusable BytesIO buffer from the pool."""
        with self._pool_lock:
            if self._screencap_pool:
                buf = self._screencap_pool.pop()
                buf.seek(0)
                buf.truncate(0)
                return buf
            return io.BytesIO()

    def release_screencap_buffer(self, buf: io.BytesIO):
        """Returns a BytesIO buffer to the pool after use."""
        if buf is None or buf.closed:
            return
        with self._pool_lock:
            if len(self._screencap_pool) < 8:
                try:
                    buf.seek(0)
                    buf.truncate(0)
                    self._screencap_pool.append(buf)
                except Exception:
                    pass

    def run_inference_guarded(self, func, *args, **kwargs) -> Any:
        """
        Executes AI inference under the strict 1-thread global Semaphore lock.
        Also inspects process memory and CPU to enforce hardware ceilings.
        """
        with self.ai_semaphore:
            self.check_cpu_watchdog()
            self.check_ram_watchdog()
            return func(*args, **kwargs)

    def check_cpu_watchdog(self):
        """Checks if process CPU utilization is above max_cpu_pct and yields briefly if needed."""
        now = time.time()
        if now - self.last_cpu_time < 3.0:
            return
        self.last_cpu_time = now
        try:
            p = psutil.Process(os.getpid())
            cpu_pct = p.cpu_percent(interval=None)
            if cpu_pct > self.max_cpu_pct:
                logger.info(f"CPU Watchdog: CPU at {cpu_pct:.1f}% (threshold: {self.max_cpu_pct}%). Yielding briefly to cool down...")
                time.sleep(0.05)
        except Exception:
            pass

    def check_ram_watchdog(self):
        """Watches process RSS memory and runs garbage collection if exceeding bounds."""
        now = time.time()
        # Check every 10 seconds max
        if now - self.last_gc_time < 10.0:
            return

        self.last_gc_time = now
        try:
            p = psutil.Process(os.getpid())
            mem_mb = p.memory_info().rss / (1024 * 1024)
            if mem_mb > self.max_ram_mb:
                logger.info(f"RAM Watchdog: Memory at {mem_mb:.1f}MB (threshold: {self.max_ram_mb}MB). Running garbage collection...")
                gc.collect()
        except Exception:
            pass
