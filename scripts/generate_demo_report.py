from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    subprocess.run([sys.executable, str(scripts / "render_demo_charts.py")], check=True, cwd=root)
    subprocess.run([sys.executable, str(scripts / "build_sample_pdf.py")], check=True, cwd=root)
    print("Demo artifacts regenerated:")
    print(f"- {root / 'examples/reports/NVDA_sample_report.md'}")
    print(f"- {root / 'examples/reports/NVDA_sample_report.pdf'}")
    print(f"- {root / 'examples/reports/NVDA_sample_report_polished.pdf'}")
    for path in sorted((root / "examples/charts").glob("*.png")):
        print(f"- {path}")


if __name__ == "__main__":
    main()
