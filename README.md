# svgs-to-font

Combines per-letter SVGs into a single SVG symbol file and generates a demo page.

## Setup (macOS)

**1. Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install svgelements fonttools
```

**3. Run the script**

```bash
python3 svgs.py <FontName> '<config>'
```

To deactivate the venv when you're done:

```bash
deactivate
```

---

## Usage

```
python3 svgs.py <FontName> '<config>' [--font <path>]
```

---

## Case 1 — SVGs already in directories

Prepare one directory per variant, each containing 26 SVGs named `A.svg` … `Z.svg`:

```
left/   A.svg  B.svg  … Z.svg
right/  A.svg  B.svg  … Z.svg
```

Then run:

```bash
python3 svgs.py MyFont '{"left": {"scale_mod": 1.0, "tx": 0, "ty": 0}, "right": {"scale_mod": 1.0, "tx": 0, "ty": 0}}'
```

---

## Case 2 — Start from a font file

Provide a TTF or OTF file with `--font`. The script will extract the 26 capital letters as SVGs and populate the config directories automatically before continuing.

```bash
python3 svgs.py MyFont '{"left": {"scale_mod": 0.5, "tx": -20, "ty": 0}, "right": {"scale_mod": 0.5, "tx": 20, "ty": 0}}' --font /path/to/source.ttf
```

---

## Config

The config is a JSON object where each key is a directory name and the value controls how that variant is transformed.

```json
{
  "left":   { "scale_mod": 0.5, "tx": -20, "ty": 0 },
  "middle": { "scale_mod": 0.6, "tx": 0,   "ty": -10 },
  "right":  { "scale_mod": 0.5, "tx": 20,  "ty": 0 }
}
```

| Property    | Description |
|-------------|-------------|
| `scale_mod` | Scale factor applied around the center of the 100×100 viewBox. `1.0` = no change, `0.5` = half size. |
| `tx`        | Horizontal translation in viewBox units (positive = right). |
| `ty`        | Vertical translation in viewBox units (positive = down). |

Transformations are applied **after** the glyph is fitted and centered inside the 100×100 viewBox.

---

## Output

| File | Description |
|------|-------------|
| `<FontName>.svg` | SVG file containing one `<symbol>` per letter per directory. Symbol IDs follow the pattern `FontNameLeft-A`. |
| `demo.html` | Preview page showing all symbols and an interactive typer. |

## Demo page

Open `demo.html` in a browser. Type letters in the input field — every N letters (where N = number of directories) form one stacked column, cycling through the directories in order.
