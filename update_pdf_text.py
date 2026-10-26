"""Replacing OCR text layer with the reviewed TXT."""

import argparse
import ctypes
import difflib
import re
import statistics
import tempfile
from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pypdfium2.raw as raw

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / "data/reading_book_1901/ocr"


def normalized(char):
    return {"\ufffe": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}.get(char, char).lower()


def align(old, new):
    return difflib.SequenceMatcher(
        None, [normalized(c) for c in old], [normalized(c) for c in new], autojunk=False
    ).get_opcodes()


def characters(textpage):
    result = []
    for index in range(textpage.count_chars()):
        char = chr(raw.FPDFText_GetUnicode(textpage.raw, index))
        if char.isspace() or char == "\0":
            continue
        x, y = ctypes.c_double(), ctypes.c_double()
        raw.FPDFText_GetCharOrigin(textpage.raw, index, x, y)
        result.append(dict(char=char, x=x.value, y=y.value,
                           right=textpage.get_charbox(index)[2],
                           size=raw.FPDFText_GetFontSize(textpage.raw, index)))
    return result


def baseline(anchors):
    slopes = [(b['y'] - a['y']) / (b['x'] - a['x'])
              for a in anchors for b in anchors
              if b['x'] - a['x'] > 50 and abs(b['y'] - a['y']) < 20]
    slopes = [s for s in slopes if abs(s) < 0.06]
    slope = statistics.median(slopes) if slopes else 0
    intercepts = [a['y'] - slope * a['x'] for a in anchors]
    center = max(intercepts, key=lambda y: sum(abs(v - y) < 3 for v in intercepts))
    intercept = statistics.median(v for v in intercepts if abs(v - center) < 3)
    return slope, intercept


def word_boxes(line, glyphs):
    text = ''.join(line.split())
    positions = [None] * len(text)
    for tag, a, b, c, d in align([g['char'] for g in glyphs], text):
        if tag == 'equal':
            for offset in range(d - c):
                g = glyphs[a + offset]
                positions[c + offset] = (g['x'], g['right'])
        elif d > c:
            left = glyphs[a]['x'] if a < len(glyphs) else glyphs[-1]['right']
            right = glyphs[b - 1]['right'] if b > a else left
            if right <= left:
                left = glyphs[a - 1]['right'] if a else glyphs[0]['x']
                right = glyphs[a]['x'] if a < len(glyphs) else left + 6 * (d - c)
            if right <= left:
                right = left + 6 * (d - c)
            for offset in range(d - c):
                positions[c + offset] = (
                    left + (right - left) * offset / (d - c),
                    left + (right - left) * (offset + 1) / (d - c))
    result, offset = [], 0
    for word in line.split():
        assigned = positions[offset:offset + len(word)]
        result.append((word, min(v[0] for v in assigned), max(v[1] for v in assigned)))
        offset += len(word)

    for i in range(len(result) - 1):
        word, left, right = result[i]
        next_left = result[i + 1][1]
        if next_left <= left:
            raise ValueError(f"Words overlap: {line!r}")
        result[i] = word, left, min(right, next_left - 0.25)
    return result


def layout(textpage, reviewed, page_number):
    old = characters(textpage)
    text = ''.join(reviewed.split())
    mapping = [None] * len(text)
    for tag, a, b, c, d in align([g['char'] for g in old], text):
        if tag == 'equal':
            for offset in range(d - c):
                mapping[c + offset] = a + offset
        elif tag == 'replace' and b > a:
            for offset in range(d - c):
                mapping[c + offset] = a + min(b - a - 1, offset * (b - a) // (d - c))
    lines, offset = [], 0

    title_boxes = [
        (64, 779, 518, 36), (156, 710, 432, 36), (64, 647, 520, 36),
        (192, 477, 389, 17), (131, 454, 461, 16),
        (59, 72, 530, 17), (126, 48, 457, 16), (272, 22, 308, 16)]
    for line in reviewed.splitlines():
        if not line.strip():
            continue
        count = len(''.join(line.split()))
        anchors = [old[k] for k in mapping[offset:offset + count] if k is not None]
        offset += count
        if page_number == 1:
            x, y, right, size = title_boxes[len(lines)]
            lines.append(dict(text=line, slope=0, y=y, size=size,
                              words=[(line, x, right)]))
            continue
        if not anchors:
            raise ValueError(f"Page {page_number}: no geometry for {line!r}")
        slope, y = baseline(anchors)
        glyphs = sorted([g for g in old if abs(g['y'] - slope * g['x'] - y) < 3],
                        key=lambda g: g['x'])
        if not glyphs:
            raise ValueError(f"Page {page_number}: empty line")
        lines.append(dict(text=line, slope=slope, y=y,
                          size=statistics.median(g['size'] for g in glyphs),
                          words=word_boxes(line, glyphs)))
    if any(a['y'] - b['y'] < 5 for a, b in zip(lines, lines[1:])):
        raise ValueError(f"Page {page_number}: invalid line order")
    return lines


def font_encoding(font):
    cmap = font.ToUnicode.read_bytes().decode('ascii')
    encoding = {chr(int(b, 16)): int(a, 16) for a, b in
                re.findall(r'<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4})>', cmap)}
    descendant = font.DescendantFonts[0]
    default = int(descendant.get('/DW', 1000))
    widths, values, i = {}, descendant.W, 0
    while i < len(values):
        start, value = int(values[i]), values[i + 1]
        if isinstance(value, pikepdf.Array):
            widths.update((start + j, float(w)) for j, w in enumerate(value))
            i += 2
        else:
            widths.update((j, float(values[i + 2])) for j in range(start, int(value) + 1))
            i += 3
    return encoding, widths, default


def replace_layer(source, reviewed, target):
    pages = reviewed.read_text(encoding='utf-8').split('\f')
    with pikepdf.Pdf.open(source) as pdf, pdfium.PdfDocument(source) as rendered:
        if len(pages) != len(pdf.pages) or any(not s.strip() for s in pages):
            raise ValueError('Reviewed TXT must have one non-empty segment per PDF page.')
        forms = []
        for page in pdf.pages:
            found = [(k, v) for k, v in page.Resources.XObject.items()
                     if str(k).startswith('/OCR-')]
            if len(found) == 1:
                forms.append(found[0])
            elif not found and '/FReviewed' in page.Resources.get('/Font', {}):
                forms.append((None, None))
            else:
                raise ValueError('Unsupported PDF text layer.')
        font = (forms[0][1].Resources.Font.F1 if forms[0][1] is not None
                else pdf.pages[0].Resources.Font.FReviewed)
        encoding, widths, default = font_encoding(font)
        missing = set(''.join(pages)) - encoding.keys() - set('\n\r\t')
        if missing:
            raise ValueError(f'Characters missing from the embedded font: {missing!r}')
        for number, (page, text, (name, form)) in enumerate(zip(pdf.pages, pages, forms), 1):
            image_page = rendered[number - 1]
            textpage = image_page.get_textpage()
            lines = layout(textpage, text, number)
            textpage.close()
            image_page.close()
            parts = ['q', 'BT', '3 Tr']
            for line in lines:
                size = line['size']
                center = (line['words'][0][1] + line['words'][-1][2]) / 2
                y = line['y'] + line['slope'] * center
                for word, left, right in line['words']:
                    codes = [encoding[c] for c in word]
                    natural = sum(widths.get(c, default) for c in codes) * size / 1000
                    scale = (right - left) / natural
                    if scale <= 0:
                        raise ValueError(f'Page {number}: invalid word width')
                    value = ''.join(f'{c:04x}' for c in codes + [encoding[' ']])
                    parts.extend([f'/FReviewed {size:.5f} Tf', f'{scale * 100:.5f} Tz',
                                  f'1 0 0 1 {left:.5f} {y:.5f} Tm',
                                  f'<{value}> Tj'])
            parts.extend(['ET', 'Q'])
            original = []
            inside_text = False
            for op in pikepdf.parse_content_stream(page):
                operator = str(op.operator)
                if name is None and operator == 'BT':
                    inside_text = True
                    continue
                if name is None and operator == 'ET':
                    inside_text = False
                    continue
                if inside_text or (operator == 'Do' and op.operands[0] == name):
                    continue
                original.append(op)
            page.Contents = pdf.make_stream(('\n'.join(parts) + '\n').encode('ascii')
                                           + pikepdf.unparse_content_stream(original))
            if name is not None:
                del page.Resources.XObject[name]
            page.Resources.Font = pikepdf.Dictionary(FReviewed=font)
        pdf.save(target)


def verify_text(pdf_path, text_path):
    expected = text_path.read_text(encoding='utf-8').split('\f')
    with pdfium.PdfDocument(pdf_path) as pdf:
        if len(pdf) != len(expected):
            raise ValueError('Output page count changed.')
        for number, page_text in enumerate(expected):
            page = pdf[number]
            textpage = page.get_textpage()
            actual = textpage.get_text_range().replace('\ufffe', '-')
            textpage.close()
            page.close()
            if ''.join(actual.split()) != ''.join(page_text.split()):
                raise ValueError(f'Output text differs from reviewed TXT on page {number + 1}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, default=BOOK / 'reading_book_1901.pdf')
    parser.add_argument('--text', type=Path, default=BOOK / 'reading_book_1901_reviewed.txt')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='pdf-text-', dir=args.pdf.parent) as temp:
        target = Path(temp) / 'reviewed.pdf'
        replace_layer(args.pdf, args.text, target)
        verify_text(target, args.text)
        target.replace(args.pdf)
    print(f'Updated text layer: {args.pdf}')


if __name__ == '__main__':
    main()
