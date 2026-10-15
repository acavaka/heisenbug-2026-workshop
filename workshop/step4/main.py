"""Legacy entrypoint: step4 now runs the file-only exercise (no traffic generation)."""
import runpy
from pathlib import Path
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'exercises/trace_to_logs/run.py'),run_name='__main__')
