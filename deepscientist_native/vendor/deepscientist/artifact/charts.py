from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:  # Optional chart rendering dependency.
    Image = ImageDraw = ImageFont = None
    _PIL_IMPORT_ERROR = exc
else:
    _PIL_IMPORT_ERROR = None


MORANDI_BG = "#F6F1EA"
MORANDI_PANEL = "#FFFDF8"
MORANDI_GRID = "#E2D8CB"
MORANDI_AXIS = "#A99A8A"
MORANDI_TEXT = "#4F4942"
MORANDI_TEXT_MUTED = "#7A736A"
MORANDI_BLUE = "#445F7D"
MORANDI_RED = "#8F5C62"
MORANDI_GOLD = "#C2A15C"
MORANDI_GOLD_STROKE = "#A78549"
MORANDI_BORDER = "#DED1C0"
MORANDI_SOFT_BLUE = "#D7E0E6"
MORANDI_SOFT_RED = "#E7D5D8"
MORANDI_CARD = "#FBF7F1"
MORANDI_PLOT_BG = "#FFFCF8"


def render_main_experiment_metric_timeline_chart(
    *,
    series: dict[str, Any],
    output_path: Path,
    style: str = "branded",
) -> dict[str, Any]:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("The optional `Pillow` package is required to render metric timeline charts.") from _PIL_IMPORT_ERROR
    normalized_style = "branded"
    baseline = _select_baseline(series)
    points = [dict(item) for item in (series.get("points") or []) if isinstance(item, dict)]
    direction = _normalize_direction(series.get("direction"))
    label = str(series.get("label") or series.get("metric_id") or "Metric").strip() or "Metric"
    metric_id = str(series.get("metric_id") or label).strip() or label
    decimals = series.get("decimals") if isinstance(series.get("decimals"), int) else None
    unit = str(series.get("unit") or "").strip() or None
    human_label = _humanize_metric_label(label)

    width = 1360
    height = 820
    header_height = 178
    footer_height = 132
    summary_width = 0
    padding = {"left": 92, "right": 56, "top": 38, "bottom": 42}
    plot_left = padding["left"]
    plot_top = header_height
    plot_right = width - 54
    plot_bottom = height - footer_height
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    values = [
        float(item["value"])
        for item in points
        if isinstance(item.get("value"), (int, float)) and math.isfinite(float(item["value"]))
    ]
    if isinstance(baseline.get("value"), (int, float)) and math.isfinite(float(baseline["value"])):
        values.append(float(baseline["value"]))
    if not values:
        values = [0.0, 1.0]
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        min_value -= 1.0
        max_value += 1.0
    padding_value = (max_value - min_value) * 0.12
    min_value -= padding_value
    max_value += padding_value
    value_range = max(max_value - min_value, 1e-9)

    image = Image.new("RGBA", (width, height), MORANDI_BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (18, 18, width - 18, height - 18),
        radius=30,
        fill=MORANDI_PANEL,
        outline=MORANDI_GRID,
        width=1,
    )
    draw.rounded_rectangle(
        (plot_left - 18, plot_top - 18, plot_right + 18, plot_bottom + 18),
        radius=26,
        fill=MORANDI_PLOT_BG,
        outline=MORANDI_BORDER,
        width=1,
    )

    title_font = _load_font(38, bold=True)
    subtitle_font = _load_font(18, bold=False)
    axis_font = _load_font(16, bold=False)
    badge_font = _load_font(17, bold=True)
    card_label_font = _load_font(15, bold=True)
    _draw_brand_lockup(draw, image, width=width)

    title = human_label
    subtitle_parts = [metric_id]
    subtitle_parts.append("higher is better" if direction == "maximize" else "lower is better")
    if unit:
        subtitle_parts.append(unit)
    subtitle = " · ".join(subtitle_parts)

    draw.text((52, 44), title, fill=MORANDI_TEXT, font=title_font)
    draw.text((52, 92), subtitle, fill=MORANDI_TEXT_MUTED, font=subtitle_font)
    _draw_header_badges(
        draw,
        x=52,
        y=122,
        labels=[
            "Main Experiment",
            f"{len(points)} runs",
            "Baseline reference" if isinstance(baseline.get("value"), (int, float)) else "No baseline line",
        ],
        font=badge_font,
    )

    for step in range(5):
        ratio = step / 4 if 4 else 0
        y = plot_top + plot_height - ratio * plot_height
        draw.line((plot_left, y, plot_right, y), fill=MORANDI_GRID, width=1)
        value = min_value + ratio * value_range
        label_text = _format_metric_value(value, decimals)
        bbox = draw.textbbox((0, 0), label_text, font=axis_font)
        draw.text(
            (plot_left - 16 - (bbox[2] - bbox[0]), y - (bbox[3] - bbox[1]) / 2),
            label_text,
            fill=MORANDI_TEXT_MUTED,
            font=axis_font,
        )

    axis_color = MORANDI_AXIS
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=axis_color, width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=axis_color, width=2)

    if isinstance(baseline.get("value"), (int, float)) and math.isfinite(float(baseline["value"])):
        baseline_y = _value_to_y(float(baseline["value"]), plot_top, plot_height, min_value, value_range)
        _draw_dashed_line(
            draw,
            (plot_left, baseline_y),
            (plot_right, baseline_y),
            fill=MORANDI_GOLD,
            width=3,
            dash=12,
            gap=8,
        )

    point_positions: list[tuple[float, float, dict[str, Any], bool, bool]] = []
    point_slots: list[dict[str, Any]] = []
    if isinstance(baseline.get("value"), (int, float)) and math.isfinite(float(baseline["value"])):
        point_slots.append(
            {
                "slot_key": "baseline",
                "display_label": "Base",
                "value": float(baseline["value"]),
                "delta_vs_baseline": 0.0,
                "baseline_slot": True,
            }
        )
    for point in points:
        point_slots.append(
            {
                "slot_key": point.get("seq"),
                "display_label": f"R{point.get('seq') or len(point_slots)}",
                "value": point.get("value"),
                "delta_vs_baseline": point.get("delta_vs_baseline"),
                "baseline_slot": False,
                **point,
            }
        )
    x_count = max(1, len(point_slots))
    for index, point in enumerate(point_slots):
        value = point.get("value")
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            continue
        x = plot_left if x_count == 1 else plot_left + (index / (x_count - 1)) * plot_width
        y = _value_to_y(float(value), plot_top, plot_height, min_value, value_range)
        beats_baseline = _beats_baseline(
            value=float(value),
            baseline_value=float(baseline["value"]) if isinstance(baseline.get("value"), (int, float)) else None,
            delta=point.get("delta_vs_baseline"),
            direction=direction,
        ) if not bool(point.get("baseline_slot")) else False
        point_positions.append((x, y, point, beats_baseline, bool(point.get("baseline_slot"))))

    for index in range(1, len(point_positions)):
        x0, y0, *_ = point_positions[index - 1]
        x1, y1, *_ = point_positions[index]
        draw.line((x0, y0, x1, y1), fill=MORANDI_BLUE, width=4)

    latest_index = len(point_positions) - 1
    for index, (x, y, point, beats_baseline, baseline_slot) in enumerate(point_positions):
        fill = MORANDI_GOLD if baseline_slot else MORANDI_RED if index == latest_index else MORANDI_BLUE
        radius = 8 if baseline_slot else 9 if index == latest_index else 7
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=MORANDI_PANEL, width=3)
        if beats_baseline:
            _draw_star(draw, x, y - 18, outer_radius=10, inner_radius=4.2, fill=MORANDI_GOLD, outline=MORANDI_GOLD_STROKE)
        tick_label = str(point.get("display_label") or f"R{index + 1}")
        bbox = draw.textbbox((0, 0), tick_label, font=axis_font)
        draw.text((x - (bbox[2] - bbox[0]) / 2, plot_bottom + 12), tick_label, fill=MORANDI_TEXT_MUTED, font=axis_font)

    _draw_plot_legend(
        draw,
        x=plot_right - 4,
        y=plot_top - 50,
        baseline_value=float(baseline["value"]) if isinstance(baseline.get("value"), (int, float)) else None,
        decimals=decimals,
        font=badge_font,
    )

    latest_value = point_positions[-1][2].get("value") if point_positions else None
    latest_delta = point_positions[-1][2].get("delta_vs_baseline") if point_positions else None
    latest_beats_baseline = point_positions[-1][3] if point_positions else False
    _draw_footer_summary(
        draw,
        left=plot_left,
        top=plot_bottom + 36,
        width=plot_right - plot_left,
        label_font=card_label_font,
        badge_font=badge_font,
        baseline_label=str(baseline.get("label") or "Baseline").strip() or "Baseline",
        baseline_value=baseline.get("value"),
        latest_value=latest_value,
        delta_value=latest_delta,
        decimals=decimals,
        direction=direction,
        beats_baseline=latest_beats_baseline,
        unit=unit,
    )

    if point_positions:
        latest_x, latest_y, latest_point, _, latest_is_baseline = point_positions[-1]
        latest_value = latest_point.get("value")
        if not latest_is_baseline:
            latest_text = _format_metric_value(latest_value, decimals)
            _draw_latest_value_callout(
                draw,
                x=latest_x,
                y=latest_y,
                value_text=latest_text,
                font=badge_font,
                fill=MORANDI_SOFT_RED if latest_beats_baseline else MORANDI_CARD,
            )

    ensure_parent(output_path)
    image.save(output_path, format="PNG")
    return {
        "metric_id": metric_id,
        "label": human_label,
        "path": str(output_path),
        "baseline_value": baseline.get("value"),
        "latest_value": next((point[2].get("value") for point in reversed(point_positions) if not point[4]), None),
        "point_count": len(point_positions),
        "direction": direction,
        "style": "branded",
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _select_baseline(series: dict[str, Any]) -> dict[str, Any]:
    baselines = [dict(item) for item in (series.get("baselines") or []) if isinstance(item, dict)]
    selected = next(
        (
            item
            for item in baselines
            if bool(item.get("selected"))
            and isinstance(item.get("value"), (int, float))
            and math.isfinite(float(item["value"]))
        ),
        None,
    )
    if selected is not None:
        return selected
    fallback = next(
        (
            item
            for item in baselines
            if isinstance(item.get("value"), (int, float))
            and math.isfinite(float(item["value"]))
        ),
        None,
    )
    return fallback or {}


def _normalize_direction(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"lower", "minimize", "lower_better", "less_is_better"}:
        return "minimize"
    return "maximize"


def _format_metric_value(value: object, decimals: int | None) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "—"
    number = float(value)
    if isinstance(decimals, int):
        return f"{number:.{decimals}f}"
    rendered = f"{number:.4f}"
    return rendered.rstrip("0").rstrip(".")


def _humanize_metric_label(value: str) -> str:
    parts = [part for part in str(value or "").replace("-", "_").split("_") if part]
    if not parts:
        return "Metric"
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in parts)


def _beats_baseline(*, value: float, baseline_value: float | None, delta: object, direction: str) -> bool:
    if baseline_value is not None and math.isfinite(baseline_value):
        return value < baseline_value if direction == "minimize" else value > baseline_value
    if isinstance(delta, (int, float)) and math.isfinite(float(delta)):
        return float(delta) < 0 if direction == "minimize" else float(delta) > 0
    return False


def _value_to_y(value: float, plot_top: float, plot_height: float, min_value: float, value_range: float) -> float:
    return plot_top + plot_height - ((value - min_value) / value_range) * plot_height


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: str,
    width: int,
    dash: int,
    gap: int,
) -> None:
    x0, y0 = start
    x1, y1 = end
    total = math.dist((x0, y0), (x1, y1))
    if total <= 0:
        return
    dx = (x1 - x0) / total
    dy = (y1 - y0) / total
    progress = 0.0
    while progress < total:
        segment = min(progress + dash, total)
        draw.line(
            (
                x0 + dx * progress,
                y0 + dy * progress,
                x0 + dx * segment,
                y0 + dy * segment,
            ),
            fill=fill,
            width=width,
        )
        progress += dash + gap


def _draw_star(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    *,
    outer_radius: float,
    inner_radius: float,
    fill: str,
    outline: str,
) -> None:
    points: list[tuple[float, float]] = []
    for index in range(10):
        angle = -math.pi / 2 + (index * math.pi) / 5
        radius = outer_radius if index % 2 == 0 else inner_radius
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    draw.polygon(points, fill=fill, outline=outline)


def _draw_brand_lockup(draw: ImageDraw.ImageDraw, image: Image.Image, *, width: int) -> None:
    mark = _load_brand_mark()
    text_right = width - 52
    brand_font = _load_font(22, bold=True)
    caption_font = _load_font(13, bold=False)
    text_bbox = draw.textbbox((0, 0), "DeepScientist", font=brand_font)
    caption_bbox = draw.textbbox((0, 0), "Autonomous Research Update", font=caption_font)
    content_width = max(text_bbox[2] - text_bbox[0], caption_bbox[2] - caption_bbox[0])
    mark_width = mark.width if mark is not None else 0
    total_width = content_width + (mark_width + 12 if mark is not None else 0)
    left = max(52, text_right - total_width)
    if mark is not None:
        image.alpha_composite(mark, (left, 42))
    text_left = left + (mark_width + 12 if mark is not None else 0)
    draw.text((text_left, 46), "DeepScientist", fill=MORANDI_TEXT, font=brand_font)
    draw.text((text_left, 74), "Autonomous Research Update", fill=MORANDI_TEXT_MUTED, font=caption_font)


def _draw_header_badges(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    labels: list[str],
    font: ImageFont.ImageFont,
) -> None:
    cursor_x = x
    for label in labels:
        if not label:
            continue
        text = str(label).strip()
        bbox = draw.textbbox((0, 0), text, font=font)
        width = (bbox[2] - bbox[0]) + 24
        draw.rounded_rectangle(
            (cursor_x, y, cursor_x + width, y + 30),
            radius=14,
            fill=MORANDI_CARD,
            outline=MORANDI_BORDER,
            width=1,
        )
        draw.text((cursor_x + 12, y + 6), text, fill=MORANDI_TEXT_MUTED, font=font)
        cursor_x += width + 10


def _draw_plot_legend(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    baseline_value: float | None,
    decimals: int | None,
    font: ImageFont.ImageFont,
) -> None:
    if baseline_value is None:
        return
    label = f"Baseline · {_format_metric_value(baseline_value, decimals)}"
    bbox = draw.textbbox((0, 0), label, font=font)
    width = (bbox[2] - bbox[0]) + 48
    left = x - width
    draw.rounded_rectangle(
        (left, y, x, y + 30),
        radius=15,
        fill="#FFF7E9",
        outline="#E7D2A7",
        width=1,
    )
    _draw_dashed_line(draw, (left + 12, y + 15), (left + 34, y + 15), fill=MORANDI_GOLD, width=3, dash=7, gap=5)
    draw.text((left + 42, y + 6), label, fill=MORANDI_GOLD_STROKE, font=font)


def _draw_footer_summary(
    draw: ImageDraw.ImageDraw,
    *,
    left: int,
    top: int,
    width: int,
    label_font: ImageFont.ImageFont,
    badge_font: ImageFont.ImageFont,
    baseline_label: str,
    baseline_value: object,
    latest_value: object,
    delta_value: object,
    decimals: int | None,
    direction: str,
    beats_baseline: bool,
    unit: str | None,
) -> None:
    card_height = 54
    gap = 14
    value_font = _load_font(24, bold=True)
    cards = [
        ("Latest", _format_metric_value(latest_value, decimals), MORANDI_SOFT_RED if beats_baseline else MORANDI_CARD),
        ("Baseline", _format_metric_value(baseline_value, decimals), "#FFF7E9"),
        ("Delta", _format_metric_value(delta_value, decimals) if isinstance(delta_value, (int, float)) else "—", MORANDI_SOFT_BLUE),
    ]
    card_width = int((width - gap * 2) / 3)
    for index, (title, value, fill) in enumerate(cards):
        x = left + index * (card_width + gap)
        y = top
        draw.rounded_rectangle(
            (x, y, x + card_width, y + card_height),
            radius=18,
            fill=fill,
            outline=MORANDI_BORDER,
            width=1,
        )
        draw.text((x + 16, y + 12), title, fill=MORANDI_TEXT_MUTED, font=label_font)
        draw.text((x + 102, y + 8), value, fill=MORANDI_TEXT, font=value_font)
        if title == "Baseline":
            draw.text((x + 16, y + 36), _truncate_text(baseline_label, 24), fill=MORANDI_TEXT_MUTED, font=badge_font)
        elif title == "Delta":
            hint = "lower is better" if direction == "minimize" else "higher is better"
            draw.text((x + 16, y + 36), hint, fill=MORANDI_TEXT_MUTED, font=badge_font)
        elif title == "Latest":
            latest_hint = "beats baseline" if beats_baseline else "latest recorded point"
            if unit:
                latest_hint = f"{latest_hint} · {unit}"
            draw.text((x + 16, y + 36), latest_hint, fill=MORANDI_TEXT_MUTED, font=badge_font)


def _draw_latest_value_callout(
    draw: ImageDraw.ImageDraw,
    *,
    x: float,
    y: float,
    value_text: str,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    label = f"Latest {value_text}"
    bbox = draw.textbbox((0, 0), label, font=font)
    width = (bbox[2] - bbox[0]) + 24
    height = 28
    left = x - width / 2
    top = y - 42
    draw.rounded_rectangle(
        (left, top, left + width, top + height),
        radius=14,
        fill=fill,
        outline=MORANDI_BORDER,
        width=1,
    )
    draw.text((left + 12, top + 5), label, fill=MORANDI_TEXT, font=font)


def _truncate_text(value: str, limit: int) -> str:
    glyphs = list(value)
    if len(glyphs) <= limit:
        return value
    return "".join(glyphs[: max(0, limit - 1)]).rstrip() + "…"


@functools.lru_cache(maxsize=1)
def _load_brand_mark() -> Image.Image | None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "branding" / "logo-raster.png",
        Path(__file__).resolve().parents[3] / "assets" / "branding" / "deepscientist-mark.png",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            bbox = alpha.getbbox()
            if bbox:
                image = image.crop(bbox)
            image.thumbnail((42, 42))
            return image
        except Exception:
            continue
    return None


def _load_font(size: int, *, bold: bool) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()
