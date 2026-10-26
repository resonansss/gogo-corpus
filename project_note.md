# Preparing the *Gogo Reading Book* (1901) for a Gogo text corpus

## Material and aims

This note describes the preparation of the *Gogo Reading Book (Native Proverbs, Riddles, and Fables)* (1901) for a Gogo (Cigogo) text corpus. The main aim of this stage is to obtain a machine-readable version of the printed material with the ability to verify it against the original source.

The material consists of a scanned copy of the book published in London by the Society for Promoting Christian Knowledge. The PDF contains 76 pages, including the title page, preface and printer's information. The Gogo material comprises 200 numbered proverbs, 63 numbered riddles and a collection of tales. 

## Text preparation

The work was carried out in three stages: optical character recognition (OCR), preliminary comparison of the recognised text with the scan, and replacement of the PDF's text layer with the corrected version. OCR was performed using a Python script based on OCRmyPDF and Tesseract. The initial output comprised a plain-text file and a PDF with a hidden text layer.

Then the recognised text was compared with all 76 pages. Corrections concerned incorrectly recognized letters, omitted words, numbering, headings and punctuation. For example, the preliminary recognition output `camera` was replaced with `yakalindiliza` on the page 65, following the printed text.

The text was not modernised, translated or morphologically annotated. Page boundaries, printed word breaks, headings and page numbers remain in the revised file, while quotation marks, apostrophes and spacing were treated consistently as described in the [review notes](data\reading_book_1901\ocr\review.md).

## Results and further work

The result of this stage is a revised text covering the entire scanned book and a searchable PDF containing the revised text. 

The prepared material requires further verification, particularly where the scan is unclear. The next stage will involve thoroughly human comparison with the source, resolution of uncertain readings and segmentation into individual proverbs, riddles and tales. Thus, the current result constitutes a preliminary textual basis for corpus development and subsequent linguistic analysis.