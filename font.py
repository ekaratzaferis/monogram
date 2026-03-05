import argparse
import json
import os
import time
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from svgelements import SVG, Path, Matrix, Move, Line, Polyline, QuadraticBezier, CubicBezier

def get_true_ink_bounds(path):
    points = []
    for seg in path:
        if hasattr(seg, 'start') and seg.start: points.append(seg.start)
        if hasattr(seg, 'end') and seg.end: points.append(seg.end)
        if hasattr(seg, 'control'): points.append(seg.control)
        if hasattr(seg, 'control1'): points.append(seg.control1)
        if hasattr(seg, 'control2'): points.append(seg.control2)
    if not points: return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def get_stretched_path(svg_path, box_size=1000.0):
    if not os.path.exists(svg_path): return None
    try:
        svg = SVG.parse(svg_path)
        combined_path = Path()
        for element in svg.elements():
            if isinstance(element, Path): combined_path += element
            elif isinstance(element, (Polyline, Line)): combined_path += Path(element)

        bounds = get_true_ink_bounds(combined_path)
        if not bounds: return Path()
        
        x_min, y_min, x_max, y_max = bounds
        width, height = x_max - x_min, y_max - y_min
        scale = box_size / max(width, height)
        
        m = Matrix()
        m.post_translate(-x_min, -y_min) 
        m.post_scale(scale, scale)
        m.post_translate((box_size - (width * scale)) / 2, (box_size - (height * scale)) / 2)
        
        combined_path @= m
        return combined_path
    except Exception as e:
        print(f"Error processing {svg_path}: {e}")
        return Path()

def build_dynamic_font(output_name, configs):
    modes = list(configs.keys())
    suffixes = { "left": ".l", "middle": ".m", "right": ".r" }
    UPM = 1000
    fb = FontBuilder(UPM, isTTF=False)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    # Initialize glyphs dict with the mandatory .notdef
    # .notdef is what shows up when a character is missing
    notdef_pen = T2CharStringPen(600, None)
    notdef_pen.moveTo((50, 0)); notdef_pen.lineTo((50, 700)); notdef_pen.lineTo((450, 700)); notdef_pen.lineTo((450, 0)); notdef_pen.closePath()
    glyphs = {".notdef": notdef_pen.getCharString()}
    
    cmap = {}
    glyph_order = [".notdef"]

    for char in letters:
        for mode in modes:
            g_name = f"{char}{suffixes[mode]}"
            glyph_order.append(g_name)
            
            if mode == "left":
                cmap[ord(char)] = g_name
            
            path = get_stretched_path(os.path.join(mode, f"{char}.svg"), UPM)
            
            if path:
                c = configs.get(mode, {"scale_mod": 1.0, "tx": 0, "ty": 0})
                
                # Apply User Config (Scale then Offset)
                s = c.get('scale_mod', 1.0)
                if s != 1.0:
                    path @= Matrix.translate(-500, -500)
                    path @= Matrix.scale(s, s)
                    path @= Matrix.translate(500, 500)
                
                path @= Matrix.translate(c.get('tx', 0), c.get('ty', 0))

            pen = T2CharStringPen(UPM, None)
            if path:
                for seg in path:
                    def to_font(pt): return (pt[0], UPM - pt[1])
                    if isinstance(seg, Move): pen.moveTo(to_font(seg.end))
                    elif isinstance(seg, Line): pen.lineTo(to_font(seg.end))
                    elif isinstance(seg, QuadraticBezier): pen.qCurveTo(to_font(seg.control), to_font(seg.end))
                    elif isinstance(seg, CubicBezier): pen.curveTo(to_font(seg.control1), to_font(seg.control2), to_font(seg.end))
            
            glyphs[g_name] = pen.getCharString()

    # Define setup in correct order
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    
    # Ensure every glyph in our order has a metric
    metrics = {name: (UPM, 0) for name in glyph_order}
    fb.setupHorizontalMetrics(metrics)
    
    fb.setupCFF(output_name, {"FullName": "DynamicFont", "Weight": "Regular"}, glyphs, {})
    
    fb.setupHorizontalHeader(ascent=UPM, descent=0)
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, usWinAscent=UPM, usWinDescent=0)
    fb.setupNameTable({"familyName": "DynamicFont", "styleName": "Regular"})
    fb.setupPost()
    
    # OT Features
    lists = {m: [f"{c}{suffixes[m]}" for c in letters] for m in modes}
    ot_code = "\n".join([f"@{m.upper()} = [{' '.join(lists[m])}];" for m in modes])
    ot_code += "\nfeature calt {\n"
    if len(modes) == 3:
        ot_code += "    sub @LEFT @LEFT' by @MIDDLE;\n    sub @MIDDLE @LEFT' by @RIGHT;\n    sub @RIGHT @LEFT' by @LEFT;\n"
    else:
        ot_code += "    sub @LEFT @LEFT' by @RIGHT;\n    sub @RIGHT @LEFT' by @LEFT;\n"
    ot_code += "} calt;"
    
    fb.addOpenTypeFeatures(ot_code)
    fb.save(output_name)
    print(f"Successfully generated: {output_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build an OTF font from letter SVGs.')
    parser.add_argument('font_name', help='Font name (output will be FontName.otf)')
    parser.add_argument('config', help='JSON config, e.g. {"left": {"scale_mod": 0.5, "tx": 0, "ty": 0}}')
    args = parser.parse_args()
    build_dynamic_font(f"{args.font_name}.otf", json.loads(args.config))