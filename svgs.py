#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from xml.etree import ElementTree as ET
from svgelements import Path, Matrix

VIEWBOX_SIZE = 100
ALPHABET = [chr(c) for c in range(ord('A'), ord('Z') + 1)] \
         + [chr(c) for c in range(ord('a'), ord('z') + 1)]


def export_font_glyphs(font_path, dir_names, base_dir):
    """Extract A-Z glyphs from a TTF/OTF file and write SVGs into each directory."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font['head'].unitsPerEm

    for dir_name in dir_names:
        os.makedirs(os.path.join(base_dir, dir_name), exist_ok=True)

    for letter in ALPHABET:
        glyph_name = cmap.get(ord(letter))
        if not glyph_name:
            print(f'Warning: no glyph for {letter} in font, skipping.', file=sys.stderr)
            continue

        glyph = glyph_set[glyph_name]

        # Draw with Y-flip so SVG (Y-down) matches font (Y-up)
        pen = SVGPathPen(glyph_set)
        glyph.draw(TransformPen(pen, (1, 0, 0, -1, 0, upm)))
        d = pen.getCommands()

        if not d:
            print(f'Warning: empty glyph for {letter}, skipping.', file=sys.stderr)
            continue

        svg = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {glyph.width} {upm}">\n'
            f'  <path d="{d}" />\n'
            '</svg>\n'
        )

        for dir_name in dir_names:
            with open(os.path.join(base_dir, dir_name, f'{letter}.svg'), 'w') as f:
                f.write(svg)

    font.close()
    print(f'Exported glyphs from {font_path} into: {", ".join(dir_names)}')


def extract_path_strings(filepath):
    """Return all path `d` attribute values from an SVG file."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    result = []
    for elem in root.iter():
        if elem.tag.endswith('}path') or elem.tag == 'path':
            d = elem.get('d')
            if d:
                result.append(d)
    return result


def combined_bbox(d_strings):
    """Return (xmin, ymin, xmax, ymax) covering all given path strings."""
    xmin, ymin, xmax, ymax = float('inf'), float('inf'), float('-inf'), float('-inf')
    for d in d_strings:
        bx1, by1, bx2, by2 = Path(d).bbox()
        xmin = min(xmin, bx1)
        ymin = min(ymin, by1)
        xmax = max(xmax, bx2)
        ymax = max(ymax, by2)
    return xmin, ymin, xmax, ymax


def fit_matrix(d_strings, viewbox=VIEWBOX_SIZE):
    """Return the Matrix that scales + centers paths to fit a viewbox."""
    xmin, ymin, xmax, ymax = combined_bbox(d_strings)
    w = xmax - xmin
    h = ymax - ymin
    if w == 0 or h == 0:
        return Matrix()
    scale = min(viewbox / w, viewbox / h)
    tx = (viewbox - w * scale) / 2 - xmin * scale
    ty = (viewbox - h * scale) / 2 - ymin * scale
    return Matrix(scale, 0, 0, scale, tx, ty)


def config_matrix(cfg, viewbox=VIEWBOX_SIZE):
    """Return the Matrix for a dir config (scale_mod, tx, ty)."""
    s = cfg.get('scale_mod', 1.0)
    tx = cfg.get('tx', 0)
    ty = cfg.get('ty', 0)
    center = viewbox / 2
    # Scale around center, then translate
    return Matrix(s, 0, 0, s, center * (1 - s) + tx, center * (1 - s) + ty)


def apply_matrix(d_strings, matrix):
    """Apply a matrix to a list of path d strings and return new d strings."""
    return [(Path(d) * matrix).d() for d in d_strings]


def main():
    parser = argparse.ArgumentParser(description='Build an SVG symbol file from letter SVGs.')
    parser.add_argument('font_name', help='Font name (used in symbol IDs)')
    parser.add_argument('config', help='JSON config, e.g. {"left": {"scale_mod": 0.5, "tx": 0, "ty": 0}}')
    parser.add_argument('--font', help='Path to a TTF/OTF file; glyphs will be exported into the config directories')
    args = parser.parse_args()

    font_name = args.font_name
    config = json.loads(args.config)

    SVG_NS = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', SVG_NS)
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

    root = ET.Element(f'{{{SVG_NS}}}svg')
    root.set('version', '1.1')
    root.set('viewBox', f'0 0 {VIEWBOX_SIZE} {VIEWBOX_SIZE}')

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.font:
        export_font_glyphs(args.font, list(config.keys()), base_dir)

    for dir_name, dir_cfg in config.items():
        dir_path = os.path.join(base_dir, dir_name)
        if not os.path.isdir(dir_path):
            print(f'Warning: directory "{dir_path}" not found, skipping.', file=sys.stderr)
            continue

        cap_dir = dir_name[0].upper() + dir_name[1:]
        cfg_mat = config_matrix(dir_cfg)

        for letter in ALPHABET:
            svg_file = os.path.join(dir_path, f'{letter}.svg')
            if not os.path.exists(svg_file):
                print(f'Warning: {svg_file} not found, skipping.', file=sys.stderr)
                continue

            d_strings = extract_path_strings(svg_file)
            if not d_strings:
                print(f'Warning: no paths in {svg_file}, skipping.', file=sys.stderr)
                continue

            # 1. Fit to 100×100 viewBox (modify path coordinates)
            fit_mat = fit_matrix(d_strings)
            fitted = apply_matrix(d_strings, fit_mat)

            # 2. Apply config transform (modify path coordinates)
            final = apply_matrix(fitted, cfg_mat)

            # Build <symbol>
            symbol_id = f'{font_name}{cap_dir}-{letter}'
            symbol = ET.SubElement(root, f'{{{SVG_NS}}}symbol')
            symbol.set('id', symbol_id)
            symbol.set('viewBox', f'0 0 {VIEWBOX_SIZE} {VIEWBOX_SIZE}')

            path_elem = ET.SubElement(symbol, f'{{{SVG_NS}}}path')
            path_elem.set('d', ' '.join(final))
            path_elem.set('fill', '#000000')

    output_path = os.path.join(base_dir, f'{font_name}.svg')
    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    tree.write(output_path, encoding='unicode', xml_declaration=True)
    print(f'Written: {output_path}')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    python = sys.executable
    config_raw = args.config

    subprocess.run([python, os.path.join(script_dir, 'demo.py'), font_name], check=True)


if __name__ == '__main__':
    main()
