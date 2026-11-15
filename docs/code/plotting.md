# plotting

Back to [Home](../Home.md)

Dark chart style for the notebooks. Needs matplotlib (`.[notebooks]` extra).

- `use_style()`: call once at the top of a notebook
- `titles(ax, title, subtitle)`
- `price_axis_right(ax)`
- `area_line(ax, x, y)`: line with a light fill
- `last_value(ax, x, y)`: tag on the last point
- `ref_line(ax, y, label)`, `ref_vline(ax, x, label)`

Colours are at the top of the file (`SURFACE`, `TEXT`, `SERIES`...).
