from __future__ import annotations

import shutil
import subprocess
import sys


def write_pdf(svg_text: str, W: int, H: int, path: str) -> str:
    """Write a PDF using one of three optional backends."""
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2pdf(bytestring=svg_text.encode(), write_to=path)
        return "cairosvg"
    except ImportError:
        pass
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", path], input=svg_text.encode(), check=True)
        return "rsvg-convert"
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.set_content(f'<html><body style="margin:0">{svg_text}</body></html>')
            pg.pdf(path=path, width=f"{W}px", height=f"{H}px", print_background=True,
                   margin=dict(top="0", right="0", bottom="0", left="0"))
            b.close()
        return "Chromium"
    except ImportError:
        sys.exit(
            "No PDF backend found. Either `pip install cairosvg`, install rsvg-convert, "
            "or open the .html file and use the PDF button (browser → Save as PDF)."
        )
