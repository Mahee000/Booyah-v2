import io
import time
import threading
import unittest
from src.core.resource_governor import ResourceGovernor

class TestResourceGovernor(unittest.TestCase):
    def setUp(self):
        self.governor = ResourceGovernor.get()

    def test_singleton_integrity(self):
        g1 = ResourceGovernor.get()
        g2 = ResourceGovernor.get()
        self.assertIs(g1, g2, "ResourceGovernor must be a singleton")

    def test_screencap_buffer_pool(self):
        buf1 = self.governor.acquire_screencap_buffer()
        self.assertIsInstance(buf1, io.BytesIO)
        buf1.write(b"test data 12345")
        self.assertEqual(buf1.tell(), 15)

        # Release back to pool
        self.governor.release_screencap_buffer(buf1)

        # Re-acquire from pool, should be reset to 0 length and seek 0
        buf2 = self.governor.acquire_screencap_buffer()
        self.assertEqual(buf2.tell(), 0)
        self.assertEqual(len(buf2.getvalue()), 0)
        self.governor.release_screencap_buffer(buf2)

    def test_ai_semaphore_serializes_inference(self):
        """
        Verify that ai_semaphore enforces strictly 1-thread execution.
        If 5 threads attempt inference simultaneously, peak concurrent
        executions must never exceed 1.
        """
        max_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        def dummy_inference(duration):
            nonlocal max_concurrent, current_concurrent
            with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            
            time.sleep(duration)

            with lock:
                current_concurrent -= 1
            return True

        threads = []
        for _ in range(5):
            t = threading.Thread(
                target=self.governor.run_inference_guarded,
                args=(dummy_inference, 0.05)
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(max_concurrent, 1, "AI inference must be strictly serialized to 1 thread")

    def test_cpu_and_ram_limits_exist(self):
        self.assertTrue(hasattr(self.governor, "max_ram_mb"))
        self.assertTrue(hasattr(self.governor, "max_cpu_pct"))
        self.assertGreater(self.governor.max_ram_mb, 100)
        self.assertGreater(self.governor.max_cpu_pct, 10.0)

if __name__ == "__main__":
    unittest.main()
