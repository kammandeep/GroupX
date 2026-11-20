"""SVG line-chart geometry. Drawn server-side, so no chart library is needed."""

# Chart size in SVG units (the page scales it to fit).
WIDTH, HEIGHT = 820, 340
PAD_L, PAD_R, PAD_T, PAD_B = 52, 12, 12, 30


def build_chart(dates, marks=(), **lines):
    """Geometry for one or more lines sharing a y-axis.

    `lines` maps a name to its values (all the same length as `dates`, at least 2).
    `marks` is [(index, kind)], placed on the first line.
    """
    if len(dates) < 2 or any(len(v) != len(dates) for v in lines.values()):
        raise ValueError("every line needs one value per date, and at least two dates")
    values = [v for line in lines.values() for v in line]
    low, high = min(values), max(values)
    span = (high - low) or 1
    plot_w, plot_h = WIDTH - PAD_L - PAD_R, HEIGHT - PAD_T - PAD_B
    last = len(dates) - 1
    decimals = 0 if high >= 100 else 2

    def x(i):
        return i / last * plot_w

    def y(value):
        return plot_h - (value - low) / span * plot_h

    first = next(iter(lines.values()))
    return {
        "width": WIDTH, "height": HEIGHT, "left": PAD_L, "top": PAD_T, "plot_w": plot_w, "plot_h": plot_h,
        "lines": {name: " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(line)) for name, line in lines.items()},
        "marks": [{"x": x(i), "y": y(first[i]), "kind": kind} for i, kind in marks],
        "y_ticks": [(y(low + span * k / 4), f"{low + span * k / 4:.{decimals}f}") for k in range(5)],
        "x_ticks": [(x(i), dates[i]) for i in (0, last // 2, last)],
    }
