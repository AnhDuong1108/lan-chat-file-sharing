import hashlib
import os
import re
from pathlib import Path
from typing import Generator, Iterable, Union

from config import BUFFER_SIZE, MAX_FILE_SIZE


def calculate_file_hash(file_path: Union[str, Path]) -> str:
    """
    Tính mã SHA-256 của file bằng cách đọc tuần tự theo từng chunk để tối ưu RAM.

    :param file_path: Đường dẫn tới file cần tính hash.
    :return: Chuỗi 64 ký tự hex chữ thường biểu diễn mã SHA-256.
    :raises FileNotFoundError: Khi file không tồn tại.
    :raises OSError: Khi gặp lỗi truy cập hoặc đọc file.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found or is not a regular file: {file_path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(BUFFER_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def get_file_info(file_path: Union[str, Path]) -> dict:
    """
    Lấy thông tin cơ bản của file (tên, kích thước, phần mở rộng, SHA-256 hash).

    :param file_path: Đường dẫn tới file.
    :return: Dictionary chứa thông tin file:
        {
            "filename": str,
            "filesize": int,
            "extension": str,
            "filehash": str,
            "file_hash": str
        }
    :raises FileNotFoundError: Nếu file không tồn tại.
    :raises ValueError: Nếu đường dẫn không hợp lệ hoặc kích thước vượt ngưỡng.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {file_path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {file_path}")

    filesize = path.stat().st_size
    extension = path.suffix
    filehash = calculate_file_hash(path)

    return {
        "filename": path.name,
        "filesize": filesize,
        "extension": extension,
        "filehash": filehash,
        "file_hash": filehash,
    }


def validate_file(file_path: Union[str, Path], mode: str = "source") -> bool:
    """
    Kiểm tra tính hợp lệ của file cho phía gửi (source) hoặc phía nhận (destination).

    - File nguồn (mode="source"):
        + Phải tồn tại và là regular file.
        + Có quyền đọc (os.R_OK).
        + Kích thước không âm và không vượt quá MAX_FILE_SIZE.
    - File đích (mode="destination"):
        + Tên file hợp lệ (không chứa ký tự cấm, không rỗng, không phải reserved name).
        + Thư mục chứa file phải tồn tại hoặc có thể tạo được và có quyền ghi.
        + Nếu file đích đã tồn tại, phải có quyền ghi.

    :param file_path: Đường dẫn file cần kiểm tra.
    :param mode: 'source' cho file gửi đi, 'destination' cho file nhận về.
    :return: True nếu file hợp lệ, False nếu không.
    """
    if not file_path:
        return False

    try:
        path = Path(file_path)
    except Exception:
        return False

    if mode == "source":
        try:
            if not path.exists() or not path.is_file():
                return False
            if not os.access(path, os.R_OK):
                return False
            size = path.stat().st_size
            if size < 0 or size > MAX_FILE_SIZE:
                return False
            return True
        except (OSError, ValueError):
            return False

    elif mode == "destination":
        try:
            filename = path.name
            if not filename or filename in (".", ".."):
                return False
            if filename.endswith((" ", ".")) or any(
                ord(c) < 32 or c in '<>:"/\\|?*' for c in filename
            ):
                return False

            stem = filename.split(".", 1)[0].rstrip(" ").upper()
            reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            if stem in reserved or re.fullmatch(r"(COM|LPT)[1-9¹²³]", stem):
                return False

            parent = path.parent
            if parent.exists():
                if not parent.is_dir() or not os.access(parent, os.W_OK):
                    return False
            else:
                # Kiểm tra thư mục ông bà / có thể tạo được không
                current = parent
                while not current.exists() and current != current.parent:
                    current = current.parent
                if not os.access(current, os.W_OK):
                    return False

            if path.exists():
                if not path.is_file() or not os.access(path, os.W_OK):
                    return False

            return True
        except (OSError, ValueError):
            return False

    return False


def read_file_chunks(
    file_path: Union[str, Path], chunk_size: int = BUFFER_SIZE
) -> Generator[bytes, None, None]:
    """
    Generator đọc file nhị phân thành từng chunk nhỏ liên tiếp để tiết kiệm RAM.

    :param file_path: Đường dẫn file cần đọc.
    :param chunk_size: Kích thước mỗi chunk đọc (mặc định BUFFER_SIZE).
    :yield: Từng khối dữ liệu bytes.
    """
    if chunk_size <= 0:
        chunk_size = BUFFER_SIZE

    path = Path(file_path)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def write_file_chunks(file_path: Union[str, Path], chunks: Iterable[bytes]) -> int:
    """
    Ghi tuần tự các chunk nhận được xuống file ở chế độ nhị phân 'wb'.

    :param file_path: Đường dẫn file đích cần ghi.
    :param chunks: Iterable hoặc Generator cung cấp các khối bytes.
    :return: Tổng số byte đã ghi thành công.
    """
    path = Path(file_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    with open(path, "wb") as f:
        for chunk in chunks:
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)
    return total_bytes
