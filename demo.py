#!/usr/bin/env python3
import argparse
import os
import sys
from xml.etree import ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'


def parse_symbols(svg_path, font_name):
    """
    Returns:
      - symbol_elements: list of (ET.Element) for inlining
      - dirs: ordered list of directory names (e.g. ["Left", "Right"])
      - by_letter: dict { "A": ["FontLeft-A", "FontRight-A"], ... }
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    dirs = []         # ordered, unique dir names
    by_letter = {}    # letter -> [id, ...]
    symbol_elements = []

    for sym in root.iter(f'{{{SVG_NS}}}symbol'):
        sid = sym.get('id', '')
        if not sid.startswith(font_name):
            continue
        rest = sid[len(font_name):]        # e.g. "Left-A"
        parts = rest.split('-', 1)
        if len(parts) != 2:
            continue
        dir_part, letter = parts

        if dir_part not in dirs:
            dirs.append(dir_part)
        by_letter.setdefault(letter, []).append(sid)
        symbol_elements.append(sym)

    return symbol_elements, dirs, by_letter


def symbol_card(sid, size=60):
    letter = sid.split('-')[-1]
    return f'''<div class="card">
  <svg viewBox="0 0 100 100" width="{size}" height="{size}"><use href="#{sid}" /></svg>
  <span>{letter}</span>
</div>'''


def main():
    parser = argparse.ArgumentParser(description='Generate demo.html from a font SVG.')
    parser.add_argument('font_name', help='Font name (matches the generated SVG filename)')
    args = parser.parse_args()

    font_name = args.font_name
    base_dir = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(base_dir, f'{font_name}.svg')

    if not os.path.exists(svg_path):
        print(f'Error: {svg_path} not found. Run svgs.py first.', file=sys.stderr)
        sys.exit(1)

    index_js_path = os.path.join(base_dir, 'index.js')
    if not os.path.exists(index_js_path):
        print(f'Error: {index_js_path} not found.', file=sys.stderr)
        sys.exit(1)

    ET.register_namespace('', SVG_NS)
    symbol_elements, dirs, by_letter = parse_symbols(svg_path, font_name)

    # ── Inline SVG defs ────────────────────────────────────────────────────────
    inline_defs = '\n'.join(ET.tostring(s, encoding='unicode') for s in symbol_elements)

    # ── All-symbols grid, grouped by directory ─────────────────────────────────
    groups = {d: [] for d in dirs}
    for letter in sorted(by_letter.keys()):
        for sid in by_letter[letter]:
            rest = sid[len(font_name):]
            d = rest.split('-')[0]
            groups[d].append(sid)

    grid_html = ''
    for d in dirs:
        grid_html += f'<h2>{d}</h2>\n<div class="grid">\n'
        for sid in groups[d]:
            grid_html += symbol_card(sid) + '\n'
        grid_html += '</div>\n'

    # ── Read index.js ──────────────────────────────────────────────────────────
    with open(index_js_path, encoding='utf-8') as f:
        index_js = f.read()

    # ── Read and escape font SVG for template literal embedding ────────────────
    with open(svg_path, encoding='utf-8') as f:
        font_svg_escaped = f.read().replace('`', '\\`').replace('${', '\\${')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{font_name} — Demo</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: sans-serif; background: #f5f5f5; padding: 2rem; color: #222; }}
    h1 {{ margin-bottom: 0.5rem; }}
    h2 {{ margin-top: 2rem; color: #666; font-size: 1rem; text-transform: uppercase; letter-spacing: .05em; }}

    /* All-symbols grid */
    .grid {{ display: flex; flex-wrap: nowrap; gap: 10px; margin-bottom: 1rem; overflow-x: auto; padding-bottom: 6px; }}
    .card {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 6px; text-align: center; flex-shrink: 0; }}
    .card span {{ display: block; font-size: 11px; color: #888; margin-top: 2px; }}

    /* Typer */
    #typer {{ margin-top: 3rem; }}
    #typer input {{
      font-size: 1.25rem; padding: 0.5rem 0.75rem; border: 2px solid #ccc;
      border-radius: 6px; width: 100%; max-width: 500px; outline: none;
    }}
    #typer input:focus {{ border-color: #888; }}
    #render {{ margin-top: 1.5rem; height: 200px; }}
    #render svg {{ height: 100%; width: auto; display: block; }}
  </style>
</head>
<body>

<!-- Inline symbol defs (hidden) — used by the grid cards -->
<svg xmlns="{SVG_NS}" style="display:none">
{inline_defs}
</svg>

<h1>{font_name}</h1>

{grid_html}

<section id="typer">
  <h2>Type to preview</h2>
  <input type="text" id="input" placeholder="Type letters…" autocomplete="off" spellcheck="false" />
  <div id="render"></div>
</section>

<script type="module">
{index_js}

const font = createFont(parseFontSvg(`{font_svg_escaped}`));
const input    = document.getElementById('input');
const renderDiv = document.getElementById('render');

input.addEventListener('input', () => {{
  renderDiv.innerHTML = input.value.trim()
    ? font.render(input.value, {{ size: 120, letterSpacing: 8 }})
    : '';
}});
</script>
</body>
</html>'''

    demo_path = os.path.join(base_dir, 'demo.html')
    with open(demo_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Written: {demo_path}')


if __name__ == '__main__':
    main()
