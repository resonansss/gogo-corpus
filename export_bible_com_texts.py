"""Saving Bible.com reader pages as plain text, grouped by language/book/chapter.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request


ROOT = Path(__file__).resolve().parent / "data/bible"
CACHE = ROOT / "raw/review_sources"
VERSIONS = [("gogo", 3039, "LLKWW", "Luganuzi Luswanu Kuli Wanhu Wose 2002"),
            ("swahili", 74, "BHN", "Biblia Habari Njema")]
BOOKS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB "
         "PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP "
         "HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH "
         "1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}


def has_class(classes, name):
    return any(value == name or value.endswith("_" + name) for value in classes)


class ReaderText(HTMLParser):

    def __init__(self, chapter):
        super().__init__(convert_charrefs=True)
        self.chapter = chapter
        self.stack = []
        self.parts = []
        self.titles = []
        self.title_parts = None
        self.depth = None
        self.chapters_found = 0
        self.last_verse = None
        self.verse_refs = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "h1":
            self.title_parts = []
        if tag in VOID_TAGS:
            if tag == "br" and self.depth is not None:
                self.parts.append("\n")
            return
        skip = ((self.stack[-1]["skip"] if self.stack else False)
                or has_class(classes, "note")
                or (tag == "div" and has_class(classes, "label")))
        self.stack.append({"tag": tag, "classes": classes, "skip": skip})
        if tag == "div" and attrs.get("data-usfm") == self.chapter and has_class(classes, "chapter"):
            self.depth = len(self.stack)
            self.chapters_found += 1
        if self.depth is None or skip:
            return
        if tag == "div":
            self.parts.append("\n\n")
        usfm = attrs.get("data-usfm", "")
        if tag == "span" and has_class(classes, "verse"):
            if usfm and usfm != self.last_verse:
                self.parts.append("\n")
                self.verse_refs.update(usfm.split("+"))
            self.last_verse = usfm

    def handle_endtag(self, tag):
        if tag == "h1" and self.title_parts is not None:
            self.titles.append(" ".join("".join(self.title_parts).split()))
            self.title_parts = None
        index = next((i for i in range(len(self.stack)-1, -1, -1)
                      if self.stack[i]["tag"] == tag), None)
        if index is None:
            return
        entry = self.stack[index]
        if self.depth is not None and not entry["skip"]:
            if tag == "div":
                self.parts.append("\n\n")
            elif has_class(entry["classes"], "label"):
                self.parts.append(" ")
        if self.depth is not None and index + 1 == self.depth:
            self.depth = None
        del self.stack[index:]

    def handle_data(self, data):
        if self.title_parts is not None:
            self.title_parts.append(data)
        if self.depth is not None and not self.stack[-1]["skip"]:
            self.parts.append(data)

    def result(self):
        if self.chapters_found != 1 or not self.verse_refs:
            raise ValueError(f"Expected one complete readable chapter: {self.chapter}")
        body = "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines())
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        number = self.chapter.split(".")[1]
        titles = [title for title in self.titles if re.search(r"\s" + number + r"$", title)]
        if len(titles) != 1:
            raise ValueError(f"Cannot identify the reader's chapter title: {self.chapter}")
        return titles[0], titles[0] + "\n\n" + body + "\n"


def cached_path(version, book, chapter):
    plain = CACHE / f"{version}_{book}_{chapter}.html"
    return plain if plain.exists() else plain.with_suffix(".html.gz")


def read_html(path):
    data = path.read_bytes()
    return (gzip.decompress(data) if path.suffix == ".gz" else data).decode("utf-8")


def download_missing():
    CACHE.mkdir(parents=True, exist_ok=True)
    for language, version, abbreviation, _ in VERSIONS:
        url = f"https://www.bible.com/versions/{version}"
        with urllib.request.urlopen(url, timeout=45) as response:
            index = response.read().decode("utf-8")
        references = set(re.findall(r"/bible/" + str(version)
                                   + r"/([A-Z0-9]{3})\.(\d+)(?:[.\"'/])", index))
        if {book for book, _ in references} != set(BOOKS):
            raise ValueError(f"Unexpected book index for {language}; inspect the version page")
        for book, number in sorted(references, key=lambda item: (BOOKS.index(item[0]), int(item[1]))):
            path = cached_path(version, book, int(number))
            if path.exists():
                continue
            chapter_url = f"https://www.bible.com/bible/{version}/{book}.{number}.{abbreviation}"
            with urllib.request.urlopen(chapter_url, timeout=45) as response:
                data = response.read()
            if f'data-vid="{version}"' not in data.decode("utf-8"):
                raise ValueError(f"Unexpected Bible version: {chapter_url}")
            path.write_bytes(gzip.compress(data, mtime=0))


def export(output):
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(),
                "source": "Bible.com HTML reader pages", "versions": []}
    for language, version, abbreviation, version_title in VERSIONS:
        folder = output / language
        folder.mkdir(parents=True, exist_ok=True)
        version_info = {"language": language, "bible_com_version": version,
                        "title": version_title, "books": []}
        whole_bible = [version_title]
        testament_texts = {"OT": [version_title + " — Old Testament"],
                           "NT": [version_title + " — New Testament"]}
        contents = [version_title, "", "№ | Завет | Книга | Глав", ""]
        for order, book in enumerate(BOOKS, 1):
            testament = "OT" if order <= 39 else "NT"
            numbers = sorted({int(match.group(1)) for path in CACHE.glob(f"{version}_{book}_*.html*")
                              if (match := re.fullmatch(str(version) + "_" + book
                                                       + r"_(\d+)\.html(?:\.gz)?", path.name))})
            if not numbers or numbers != list(range(1, max(numbers) + 1)):
                raise ValueError(f"Missing chapter snapshots: {language} {book}")
            book_texts = []
            book_info = {"order": order, "code": book, "testament": testament, "chapters": []}
            book_folder = None
            for number in numbers:
                source_path = cached_path(version, book, number)
                html = read_html(source_path)
                if f'data-vid="{version}"' not in html:
                    raise ValueError(f"Wrong Bible version in {source_path}")
                parser = ReaderText(f"{book}.{number}")
                parser.feed(html)
                parser.close()
                title, text = parser.result()
                if number == 1:
                    book_name = re.sub(r"\s+1$", "", title)
                    safe_name = re.sub(r'[<>:"/\\|?*]', "_", book_name).rstrip(" .")
                    book_folder = folder / f"{order:02d}_{testament}_{safe_name}"
                    book_folder.mkdir(parents=True, exist_ok=True)
                    book_info["title"] = book_name
                    contents.append(f"{order:02d} | {testament} | {book_name} | {len(numbers)}")
                path = book_folder / f"{number:03d}.txt"
                path.write_text(text, encoding="utf-8")
                book_texts.append(text)
                book_info["chapters"].append({
                    "number": number, "file": str(path.relative_to(output)),
                    "source_url": f"https://www.bible.com/bible/{version}/{book}.{number}.{abbreviation}",
                    "source_snapshot": str(source_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            combined = "\n\n".join(book_texts)
            (book_folder / "book.txt").write_text(combined, encoding="utf-8")
            whole_bible.append(combined)
            testament_texts[testament].append(combined)
            version_info["books"].append(book_info)
        (folder / "bible.txt").write_text("\n\n".join(whole_bible), encoding="utf-8")
        version_info["testaments"] = []
        for testament, texts in testament_texts.items():
            path = folder / f"{testament.lower()}_bible.txt"
            path.write_text("\n\n".join(texts), encoding="utf-8")
            books = [book for book in version_info["books"] if book["testament"] == testament]
            version_info["testaments"].append({
                "code": testament, "file": str(path.relative_to(output)),
                "book_count": len(books), "chapter_count": sum(len(book["chapters"]) for book in books)})
        (folder / "contents.txt").write_text("\n".join(contents) + "\n", encoding="utf-8")
        chapter_count = sum(len(book["chapters"]) for book in version_info["books"])
        version_info["chapter_count"] = chapter_count
        manifest["versions"].append(version_info)
        print(f"{language}: {len(version_info['books'])} books, {chapter_count} chapters", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Fetch missing HTML pages first")
    parser.add_argument("--output", type=Path, default=ROOT / "bible_com")
    args = parser.parse_args()
    if args.download:
        download_missing()
    export(args.output)
