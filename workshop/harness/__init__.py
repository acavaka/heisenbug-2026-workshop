import sys

# Windows-консоль по умолчанию cp1252: кириллица в отчётах агента падает с UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
