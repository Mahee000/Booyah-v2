"""
Booyah Studio v2 - Modern Emulator Management & Automation
Entrypoint script launching the PyQt6 Obsidian Studio application.
"""
import sys
import os

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Force strict single-threaded math, BLAS, OpenMP, and PaddlePaddle execution
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["FLAGS_cpu_num_threads"] = "1"
os.environ["PADDLE_NUM_THREADS"] = "1"

from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    if sys.platform == "win32":
        try:
            import ctypes
            # Explicit AppUserModelID tells Windows to show the app's own icon on taskbar instead of python.exe
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("etherious.booyah.app.v2")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Booyah")
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "favicon.ico"))
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
