from pathlib import Path
from uuid import uuid4

from app.domain.repositories import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, contents: bytes) -> Path:
        suffix = Path(filename).suffix.lower()
        stored_name = f"{uuid4().hex}{suffix}"
        path = self._upload_dir / stored_name
        path.write_bytes(contents)
        return path

    def delete(self, file_path: str) -> None:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
