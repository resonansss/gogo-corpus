"""The clean, continuous text of the 1901 Gogo Reading Book."""

import re
from pathlib import Path

BOOK = Path(__file__).resolve().parent / "data/reading_book_1901/ocr"
SOURCE = BOOK / "reading_book_1901_reviewed.txt"
OUTPUT = BOOK / "reading_book_1901_clean.txt"

FOOTERS = {9: "13", 12: "16", 13: "B", 29: "C", 45: "D", 61: "E"}
PARAGRAPH_STARTS = {
    14: "Yakekala vilo vinji,",
    15: "U munhu yaza kuwona",
    16: "U munhu no mwanagwe",
    17: "Zo ng'ombe ko zalawilila.",
    19: "Wakatuluka kanhyi,",
    29: "U sogo yawo no nyinawo",
}
KEEP_HYPHENS = {"muhoma-nhembo", "nhembo-ndodo", "kuku-kuku", "nanjile-kunyuma"}
ENTRY = re.compile(r"^(\d+)\. ")


def page_body(page, number):
    lines = page.strip().splitlines()
    if number in range(4, 9) or number in (10, 11) or 13 <= number <= 75:
        header = lines.pop(0)
        if not header.isupper() or str(number + 4) not in header.split():
            raise ValueError(f"Unexpected running header on PDF page {number}: {header!r}")
    if number in FOOTERS:
        if lines[-1] != FOOTERS[number]:
            raise ValueError(f"Unexpected footer on PDF page {number}")
        lines.pop()
    return "\n".join(lines).strip()


def reflow(lines, removed_hyphens):
    parts = []
    previous = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        left = re.search(r"[A-Za-z']+-$", previous)
        right = re.match(r"[A-Za-z']+", line)
        if left and right:
            spelling = left[0] + right[0]
            if spelling.lower() not in KEEP_HYPHENS:
                parts[-1] = parts[-1][:-1]
                removed_hyphens.append(spelling)
        elif parts and not line.startswith("—"):
            parts.append(" ")
        parts.append(line)
        previous = line
    return "".join(parts)


def numbered_entries(lines, count):
    entries = []
    for line in lines:
        if not line.strip():
            continue
        if ENTRY.match(line):
            entries.append([line])
        elif entries:
            entries[-1].append(line)
        else:
            raise ValueError(f"Unexpected text before numbered entries: {line!r}")
    numbers = [int(ENTRY.match(entry[0])[1]) for entry in entries]
    if numbers != list(range(1, count + 1)):
        raise ValueError(f"Expected all {count} numbered entries in sequence.")
    return entries


def tale_blocks(bodies):
    pending = []
    heading = False
    for number in range(12, 76):
        lines = bodies[number - 1].splitlines()
        anchor = PARAGRAPH_STARTS.get(number)
        if anchor and sum(line.startswith(anchor) for line in lines) != 1:
            raise ValueError(f"Paragraph anchor changed on PDF page {number}: {anchor!r}")
        for line in lines:
            line = line.strip()
            song = number == 69 and line.startswith("“Pe pepe cipembe")
            if not line or song or (anchor and line.startswith(anchor)) or line.isupper() != heading:
                if pending:
                    yield pending
                    pending = []
            if song:
                yield [line]
            elif line:
                pending.append(line)
                heading = line.isupper()
    if pending:
        yield pending


def clean(pages):
    if len(pages) != 76 or any(not page.strip() for page in pages):
        raise ValueError("Expected 76 non-empty pages separated by form feeds.")
    bodies = [page_body(page, n) for n, page in enumerate(pages, 1)]
    blocks = []
    for body in bodies[:2]:
        blocks.extend(block.splitlines() for block in body.split("\n\n") if block.strip())
    for start, end, count, title in (
        (3, 8, 200, "ZIMBAZI ZE ZIFUMBO."),
        (9, 11, 63, "NHANDAGUZI."),
    ):
        lines = "\n".join(bodies[start - 1:end]).splitlines()
        if lines.pop(0) != title:
            raise ValueError(f"Unexpected section title on PDF page {start}.")
        blocks.append([title])
        blocks.extend(numbered_entries(lines, count))
    blocks.extend(tale_blocks(bodies))
    blocks.append(bodies[75].splitlines())

    removed_hyphens = []
    output = "\n\n".join(reflow(block, removed_hyphens) for block in blocks) + "\n"
    original = "\n".join(bodies)
    source_chars = "".join(original.split()).replace("-", "")
    output_chars = "".join(output.split()).replace("-", "")
    if source_chars != output_chars or original.count("-") - output.count("-") != len(removed_hyphens):
        raise ValueError("Unexpected content change during formatting.")
    return output, len(removed_hyphens)


def main():
    text, joined = clean(SOURCE.read_text(encoding="utf-8-sig").split("\f"))
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Clean text: {OUTPUT}")
    print(f"Joined printed word breaks: {joined}")


if __name__ == "__main__":
    main()
