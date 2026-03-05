/**
 * svgs-to-font — JS rendering library
 * Zero-dependency ES module for rendering multi-variant SVG symbol fonts.
 */

/**
 * Parse a combined font SVG string into structured FontData.
 * @param {string} svgString
 * @returns {FontData}
 */
export function parseFontSvg(svgString) {
  const symbols = [];

  // Environment-aware XML parsing
  if (typeof DOMParser !== 'undefined') {
    // Browser
    const doc = new DOMParser().parseFromString(svgString, 'image/svg+xml');
    for (const sym of doc.querySelectorAll('symbol[id]')) {
      const id = sym.getAttribute('id');
      // Serialize inner XML
      const inner = Array.from(sym.childNodes)
        .map(n => serializeNode(n))
        .join('');
      const viewBox = sym.getAttribute('viewBox') || '0 0 100 100';
      symbols.push({ id, inner, viewBox });
    }
  } else {
    // Node.js — regex extraction (safe: machine-generated input)
    const symbolRe = /<symbol\s[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/symbol>/g;
    const viewBoxRe = /viewBox="([^"]+)"/;
    let m;
    while ((m = symbolRe.exec(svgString)) !== null) {
      const id = m[1];
      const inner = m[2];
      // Extract viewBox from the opening tag
      const tagEnd = svgString.indexOf('>', svgString.indexOf(`id="${id}"`));
      const tagStart = svgString.lastIndexOf('<symbol', tagEnd);
      const tag = svgString.slice(tagStart, tagEnd + 1);
      const vbMatch = viewBoxRe.exec(tag);
      const viewBox = vbMatch ? vbMatch[1] : '0 0 100 100';
      symbols.push({ id, inner, viewBox });
    }
  }

  // Detect fontName and dirs from symbol IDs like "MyFontLeft-A"
  // Strip the "-{letter}" suffix
  const prefixes = symbols.map(s => s.id.replace(/-[^-]+$/, ''));
  const uniquePrefixes = [...new Set(prefixes)];

  // Find longest common prefix among all deduplicated prefixes
  const fontName = uniquePrefixes.length === 1
    ? uniquePrefixes[0].replace(/[A-Z][a-z]+$/, '') // strip trailing CamelWord (the dir part)
    : longestCommonPrefix(uniquePrefixes).replace(/([A-Z][^A-Z]*)$/, ''); // trim partial trailing word

  // Extract dirs (insertion-ordered, deduplicated)
  const dirs = [];
  for (const prefix of prefixes) {
    const dir = prefix.slice(fontName.length);
    if (dir && !dirs.includes(dir)) dirs.push(dir);
  }

  // Build chars map
  const chars = {};
  const rawSymbols = new Map();

  for (const { id, inner, viewBox } of symbols) {
    // Normalize fill for color support
    const normalizedInner = inner.replace(/fill="#000000"/g, 'fill="currentColor"');
    const symbolXml = `<symbol id="${id}" viewBox="${viewBox}">${normalizedInner}</symbol>`;

    rawSymbols.set(id, symbolXml);

    // Parse letter and dir from id
    const dashIdx = id.lastIndexOf('-');
    if (dashIdx === -1) continue;
    const letter = id.slice(dashIdx + 1);
    const prefix = id.slice(0, dashIdx);
    const dir = prefix.slice(fontName.length);

    if (!chars[letter]) chars[letter] = {};
    chars[letter][dir] = { symbolId: id, symbolXml };
  }

  return { fontName, dirs, chars, rawSymbols };
}

/**
 * Create a FontInstance from parsed FontData.
 * @param {FontData} fontData
 * @returns {FontInstance}
 */
export function createFont(fontData) {
  return {
    meta: {
      fontName: fontData.fontName,
      dirs: fontData.dirs,
      availableChars: Object.keys(fontData.chars),
    },
    render(text, options) {
      return render(text, fontData, options);
    },
  };
}

/**
 * Render text as an SVG string.
 * @param {string} text
 * @param {FontData|FontInstance} fontDataOrInstance
 * @param {object} [options]
 * @param {number} [options.size=120]
 * @param {number} [options.letterSpacing=8]
 * @param {string|null} [options.fill=null]
 * @param {boolean} [options.caseSensitive=false]
 * @returns {string}
 */
export function render(text, fontDataOrInstance, options = {}) {
  // Accept either FontData or FontInstance
  const fontData = fontDataOrInstance.chars
    ? fontDataOrInstance
    : fontDataOrInstance.meta && fontDataOrInstance.render
      ? null // can't unwrap FontInstance here easily; require FontData
      : fontDataOrInstance;

  const {
    size = 120,
    letterSpacing = 8,
    fill = null,
    caseSensitive = false,
  } = options;

  const { dirs, chars } = fontData;
  const numDirs = dirs.length;

  // Group text into chunks of numDirs
  const chunks = [];
  for (let i = 0; i < text.length; i += numDirs) {
    chunks.push(text.slice(i, i + numDirs));
  }

  const usedSymbolIds = new Set();
  const groups = [];

  let x = 0;
  let unitCount = 0;

  for (const chunk of chunks) {
    const uses = [];

    for (let j = 0; j < chunk.length; j++) {
      const char = chunk[j];
      const dir = dirs[j];
      if (!dir) continue;

      // Space: skip <use>, but still occupies unit position
      if (char === ' ') continue;

      // Look up char, with optional case-fold fallback
      let charData = chars[char];
      if (!charData && !caseSensitive) {
        const folded = char === char.toUpperCase() ? char.toLowerCase() : char.toUpperCase();
        charData = chars[folded];
      }

      if (!charData || !charData[dir]) continue;

      const { symbolId } = charData[dir];
      usedSymbolIds.add(symbolId);
      uses.push(`<use href="#${symbolId}" width="${size}" height="${size}"/>`);
    }

    // Skip entirely empty units (all chars missing, not just spaces)
    const allMissing = chunk.split('').every(c => {
      if (c === ' ') return false; // space occupies a slot, don't skip
      return true; // will check below
    });

    // Check if all non-space chars are missing
    const hasContent = chunk.split('').some((c, j) => {
      if (c === ' ') return false;
      const dir = dirs[j];
      if (!dir) return false;
      let charData = chars[c];
      if (!charData && !caseSensitive) {
        const folded = c === c.toUpperCase() ? c.toLowerCase() : c.toUpperCase();
        charData = chars[folded];
      }
      return !!(charData && charData[dir]);
    });

    // A chunk with only spaces still advances position
    const hasAnyNonSpace = chunk.split('').some(c => c !== ' ');

    if (hasAnyNonSpace && !hasContent) {
      // All non-space chars are missing — skip this unit entirely
      continue;
    }

    const translateX = unitCount * (size + letterSpacing);
    groups.push(`  <g transform="translate(${translateX}, 0)">\n    ${uses.join('\n    ')}\n  </g>`);
    unitCount++;
  }

  const totalWidth = unitCount === 0 ? 0 : unitCount * size + (unitCount - 1) * letterSpacing;

  // Collect only used symbols for defs
  const defsXml = [...usedSymbolIds]
    .map(id => fontData.rawSymbols.get(id) || '')
    .join('\n    ');

  const fillAttr = fill ? ` color="${fill}"` : '';

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalWidth} ${size}"${fillAttr}>`,
    `  <defs>`,
    `    ${defsXml}`,
    `  </defs>`,
    ...groups,
    `</svg>`,
  ].join('\n');
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function longestCommonPrefix(strs) {
  if (!strs.length) return '';
  let prefix = strs[0];
  for (let i = 1; i < strs.length; i++) {
    while (!strs[i].startsWith(prefix)) {
      prefix = prefix.slice(0, -1);
      if (!prefix) return '';
    }
  }
  return prefix;
}

function serializeNode(node) {
  if (node.nodeType === 3) return node.textContent; // text node
  if (node.nodeType !== 1) return ''; // not element
  const tag = node.tagName;
  const attrs = Array.from(node.attributes)
    .map(a => `${a.name}="${a.value}"`)
    .join(' ');
  const children = Array.from(node.childNodes).map(serializeNode).join('');
  return attrs
    ? `<${tag} ${attrs}>${children}</${tag}>`
    : `<${tag}>${children}</${tag}>`;
}
