from __future__ import annotations

import html
from pathlib import Path

from ..shared import ensure_dir, write_json, write_text
from .service import current_branch, head_commit, log_graph_lines


def _write_png(path: Path, *, branch: str, head: str | None, lines: list[str]) -> str | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    rendered_lines = lines or ["No commits yet."]
    line_height = 24
    width = 1400
    height = max(180, 60 + len(rendered_lines) * line_height)
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    header = f"branch: {branch}  head: {head or 'none'}"
    draw.text((24, 16), header, fill="#64748b", font=font)
    for index, line in enumerate(rendered_lines, start=1):
        draw.text((24, 24 + index * line_height), line, fill="#334155", font=font)
    image.save(path)
    return str(path)


def export_git_graph(repo: Path, output_dir: Path) -> dict:
    ensure_dir(output_dir)
    lines = log_graph_lines(repo)
    payload = {
        "branch": current_branch(repo),
        "head": head_commit(repo),
        "lines": lines,
    }
    json_path = output_dir / "git-graph.json"
    write_json(json_path, payload)

    line_height = 22
    width = 1200
    height = max(120, (len(lines) + 2) * line_height)
    rendered_lines = lines or ["No commits yet."]
    text_blocks = []
    for index, line in enumerate(rendered_lines, start=1):
        y = 30 + (index - 1) * line_height
        text_blocks.append(
            f'<text x="24" y="{y}" font-family="monospace" font-size="14" fill="#334155">{html.escape(line)}</text>'
        )
    svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f8fafc" />',
            f'<text x="24" y="18" font-family="sans-serif" font-size="12" fill="#64748b">branch: {html.escape(payload["branch"])}  head: {html.escape(payload["head"] or "none")}</text>',
            *text_blocks,
            "</svg>",
        ]
    )
    svg_path = output_dir / "git-graph.svg"
    write_text(svg_path, svg)
    png_path = output_dir / "git-graph.png"
    png_result = _write_png(png_path, branch=payload["branch"], head=payload["head"], lines=rendered_lines)
    return {
        "json_path": str(json_path),
        "svg_path": str(svg_path),
        "png_path": png_result,
        "branch": payload["branch"],
        "head": payload["head"],
        "lines": rendered_lines,
    }
