from __future__ import annotations

from pathlib import Path

from graphmind.config import get_settings

_CODE_EXTENSIONS: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "js": "javascript",
}

_PLAINTEXT_FORMATS: frozenset[str] = frozenset({"md", "html", "txt"})


class UnsupportedFormatError(Exception):
    pass


class DocumentLoader:
    def __init__(self) -> None:
        self._settings = get_settings()

    def load(self, path_or_content: str, format: str) -> str:
        fmt = format.lower().strip().lstrip(".")
        self._validate_format(fmt)

        if fmt == "pdf":
            return self._load_pdf(path_or_content)

        if fmt in _PLAINTEXT_FORMATS:
            return self._load_text(path_or_content)

        if fmt in _CODE_EXTENSIONS:
            return self._load_code(path_or_content, fmt)

        raise UnsupportedFormatError(f"Format '{fmt}' is not supported")

    def _validate_format(self, fmt: str) -> None:
        supported = self._settings.ingestion.supported_formats
        if fmt not in supported:
            raise UnsupportedFormatError(f"Format '{fmt}' is not in supported formats: {supported}")

    def _load_pdf(self, path_or_content: str) -> str:
        import fitz

        path = Path(path_or_content)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path_or_content}")

        pages: list[str] = []
        with fitz.open(str(path)) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text)

        return "\n\n".join(pages)

    def _load_text(self, path_or_content: str) -> str:
        path = Path(path_or_content)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return path_or_content

    def _load_code(self, path_or_content: str, fmt: str) -> str:
        lang = _CODE_EXTENSIONS[fmt]
        path = Path(path_or_content)
        source = path.read_text(encoding="utf-8") if path.exists() else path_or_content
        return f"```{lang}\n{source}\n```"


def load_document(path_or_content: str, format: str) -> str:
    loader = DocumentLoader()
    return loader.load(path_or_content, format)
