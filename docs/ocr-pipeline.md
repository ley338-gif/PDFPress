# OCR-Pipeline

PDFPress verwendet im Default-Stack Tesseract 5 mit deutschen und englischen Sprachdaten. Der Grund ist die geringe Betriebs- und Docker-Komplexität, gute CPU-Tauglichkeit, etablierte Sprachpakete und TSV-Ausgabe mit Bounding Boxes sowie Confidence-Werten.

## Pro Seite

1. PyMuPDF extrahiert Text.
2. Eine Seite mit genügend brauchbaren alphanumerischen Zeichen bleibt auf dem schnellen `embedded_text`-Pfad.
3. Andernfalls rendert PyMuPDF die Seite mit `OCR_DPI` in PNG.
4. Pillow führt Graustufen, Autokontrast und leichtes Schärfen aus.
5. Tesseract verarbeitet die Seite mit automatischer Seitensegmentierung (`--psm 3`) und TSV-Ausgabe.
6. Wörter werden zu Zeilenblöcken inklusive Bounding Boxes und mittlerem Confidence-Wert zusammengeführt.
7. Die Strukturheuristik erkennt Überschriften, nummerierte Abschnitte und Listen.
8. OCR-Artefakte wie weiche Trennstriche und einfache Zeilenumbruch-Worttrennung werden bereinigt.

Eine Confidence unter 70 % wird im UI als Qualitätswarnung markiert.

## Bekannte Grenzen

Komplexe wissenschaftliche Tabellen, Handschrift, ungewöhnliche Schriften und stark degradierte Scans können zusätzliche spezialisierte OCR/Layout-Modelle erfordern. PDFPress bevorzugt absichtlich eine robuste CPU-first Basis vor einer schweren ML-Pipeline.
