# Monogram

Build multi-variant SVG monogram fonts from per-letter SVGs and render them as scalable SVG strings.

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

Prepare one directory per variant, each containing SVGs named `A.svg` … `Z.svg` (and optionally `a.svg` … `z.svg`):

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

Provide a TTF or OTF file with `--font`. The script will extract the letters as SVGs and populate the config directories automatically before continuing.

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

Open `demo.html` in a browser. Type letters in the input field — every N letters (where N = number of directories) form one stacked monogram unit, cycling through the directories in order.

---

## Lowercase Letter Support

To enable lowercase rendering, add `a.svg` – `z.svg` alongside `A.svg` – `Z.svg` in each directory. `svgs.py` processes both cases automatically; missing files are warned and skipped.

```
left/   A.svg … Z.svg   a.svg … z.svg
right/  A.svg … Z.svg   a.svg … z.svg
```

---

## JavaScript Library

`index.js` is a zero-dependency ES module that takes the generated combined SVG and renders text as a self-contained SVG string.

### Installation

```bash
npm install svg-monogram-maker
```

### Quick start — Node.js

```js
import { readFileSync } from 'fs';
import { parseFontSvg, createFont } from 'svg-monogram-maker';

const font = createFont(parseFontSvg(readFileSync('MyFont.svg', 'utf-8')));

console.log(font.render('Hello World'));
```

### Quick start — Browser

```html
<script type="module">
  import { parseFontSvg, createFont } from './index.js';

  const res = await fetch('MyFont.svg');
  const font = createFont(parseFontSvg(await res.text()));

  document.getElementById('output').innerHTML = font.render('Hello', { size: 120 });
</script>
```

### API

#### `parseFontSvg(svgString)` → `FontData`

Parses the combined font SVG produced by `svgs.py`. Detects the font name, variant directories, and all available characters. Normalises `fill="#000000"` to `fill="currentColor"` so CSS `color` controls glyph colour.

#### `createFont(fontData)` → `FontInstance`

Wraps `FontData` in a convenient object:

```js
{
  meta: { fontName, dirs, availableChars },
  render(text, options) { /* → svgString */ }
}
```

#### `render(text, fontDataOrInstance, options)` → `string`

| Option | Type | Default | Description |
|---|---|---|---|
| `size` | `number` | `120` | Width & height in px of each stacked unit |
| `letterSpacing` | `number` | `8` | Gap in px between units |
| `fill` | `string\|null` | `null` | CSS colour applied via `color` attribute (uses `currentColor`) |
| `caseSensitive` | `boolean` | `false` | If `false`, falls back to the other case when a character is missing |

Returns a self-contained `<svg>` string with only the used symbols embedded in `<defs>`.
