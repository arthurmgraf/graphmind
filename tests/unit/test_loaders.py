from __future__ import annotations

import pytest

from graphmind.ingestion.loaders import DocumentLoader, UnsupportedFormatError


class TestDocumentLoader:
    def test_load_markdown_content(self):
        loader = DocumentLoader()
        result = loader.load("# Hello World\n\nSome content", "md")
        assert "Hello World" in result
        assert "Some content" in result

    def test_load_txt_content(self):
        loader = DocumentLoader()
        result = loader.load("Plain text content", "txt")
        assert result == "Plain text content"

    def test_load_html_content(self):
        loader = DocumentLoader()
        result = loader.load("<h1>Title</h1>", "html")
        assert "<h1>Title</h1>" in result

    def test_load_python_code_wraps_in_fence(self):
        loader = DocumentLoader()
        result = loader.load("print('hello')", "py")
        assert result == "```python\nprint('hello')\n```"

    def test_load_typescript_code_wraps_in_fence(self):
        loader = DocumentLoader()
        result = loader.load("const x: number = 1;", "ts")
        assert result == "```typescript\nconst x: number = 1;\n```"

    def test_load_javascript_code_wraps_in_fence(self):
        loader = DocumentLoader()
        result = loader.load("const x = 1;", "js")
        assert result == "```javascript\nconst x = 1;\n```"

    def test_unsupported_format_raises(self):
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError):
            loader.load("content", "docx")

    def test_format_normalization(self):
        loader = DocumentLoader()
        result = loader.load("content", " .MD ")
        assert result == "content"

    def test_load_markdown_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# File Content", encoding="utf-8")
        loader = DocumentLoader()
        result = loader.load(str(md_file), "md")
        assert result == "# File Content"
