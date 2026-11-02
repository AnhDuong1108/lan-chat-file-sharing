import os
import sys

# Thêm thư mục src vào sys.path để chạy từ thư mục gốc
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from main import main

if __name__ == "__main__":
    sys.exit(main())
