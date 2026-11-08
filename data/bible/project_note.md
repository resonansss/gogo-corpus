# Preparing Gogo and Swahili Bible texts for a Gogo corpus

## Material and aims

This note describes the preparation of two Bible translations for the Gogo (Cigogo) text corpus. The aim was to obtain a machine-readable Gogo text and a corresponding Swahili text for later comparison. The source editions are *Luganuzi Luswanu Kuli Wanhu Wose 2002* (Gogo, LLKWW, Bible.com ID 3039) and *Biblia Habari Njema* (Swahili, BHN, Bible.com ID 74). 
*See more:*
- [Gogo Bible](https://www.bible.com/versions/3039-llkww-luganuzi-luswanu-kuli-wanhu-wose-2002)
- [Swahili Bible](https://www.bible.com/versions/74-bhn-biblia-habari-njema)

The collection covers the numbered chapters listed in the Old and New Testament sections of both online editions. Each translation contributes 66 books and 1189 chapters, comprising 39 books and 929 chapters of the Old Testament and 27 books and 260 chapters of the New Testament.

## Text preparation

A Python script downloads the chapter pages from Bible.com with `python export_bible_com_texts.py --download`, saves them as HTML, and extracts the chapter bodies as UTF-8 plain text. The export preserves verse labels, headings, paragraph breaks, and the reading order of each edition, with whitespace normalised. Separate book introductions and pop-up footnotes fall outside the scope of the export.
*See more:* 
- [Export script](../../export_bible_com_texts.py) 
- [Export documentation](bible_com/README.md)

The resulting 2378 chapter files are grouped by language and book. Each book folder carries a Testament label and retains the title used in that translation. The collection also includes combined files for each book, each Testament, and each translation. The manifest records the source URL, local HTML file, exported text file, and SHA-256 checksum for every chapter.
*See more:*
- [Manifest](bible_com/manifest.json)

The same script can rebuild the collection offline from the original HTML snapshots.

## Results and further work

The two collections have the same book codes and chapter numbers. 
However, the boundaries between verses may differ, which is the next clarifying stage in working with biblical texts in the Gogo and Swahili languages for their subsequent comparison and analysis.
That is, a coincidence based only on verse numbers may result in some corresponding excerpts in different languages being missing.

