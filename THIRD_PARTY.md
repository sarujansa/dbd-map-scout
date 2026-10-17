# Quellen und Lizenzen

| Bestandteil | Quelle | Lizenz |
|---|---|---|
| OCR-Modelle `models/ch_PP-OCRv4_det_infer.onnx`, `models/ch_PP-OCRv4_rec_infer.onnx` | PaddleOCR (PaddlePaddle), ONNX-Fassung aus RapidOCR 1.4.4 | Apache License 2.0 |
| Map- und Realm-Namen inkl. Übersetzungen in `maps.json` | [LucaFontanot/dbd-map-overlay](https://github.com/LucaFontanot/dbd-map-overlay), `src/i18n` | Apache License 2.0 |
| Kartenbilder in `maps/` | aus deinem Archiv `map_1.7z` (Community-Callout-Karten) | Rechte bei den jeweiligen Erstellern, nicht weiterverbreiten ohne deren Erlaubnis |
| numpy, OpenCV, ONNX Runtime, Pillow, mss | PyPI (werden von `start.bat` installiert) | BSD-3 / Apache-2.0 / MIT / MIT-CMU / MIT |
| pystray 0.19.5 (Symbol im Infobereich), six | PyPI, von `start.bat` installiert | LGPL-3.0 (unverändert als Bibliothek genutzt) / MIT |
| windows-capture 2.0.1 (Fensteraufnahme per Windows Graphics Capture) | [NiiightmareXD/windows-capture](https://github.com/NiiightmareXD/windows-capture), PyPI, von `start.bat` ohne Abhängigkeiten installiert | MIT |
| Idee der Regionswahl per hosts-Datei (Tab „Server“) | [crweul/make-your-choice](https://github.com/crweul/make-your-choice) (GPL-3.0) – nur die Idee, **kein Code übernommen**, eigene Umsetzung | – |
| Arbeitsschritte und Hintergrundfarben für eigene Kartenbilder (`mapimage.py`) | Skript `convert-images.sh` aus dem Projekt dbd-callouts (Snoggles), vom Nutzer bereitgestellt – nur Farbwerte und Ablauf übernommen, eigene Umsetzung mit Pillow, kein Code übernommen | – |
| Schrift `dbdmapscout/fonts/FiraSans-ExtraBold.ttf` (Map-Namen über Karten ohne Namen: Trickster's Delusion, Fallen Refuge, Freddy Fazbear's Pizza und eigene Bilder) | Fira Sans, Mozilla Foundation / Telefonica, über Google Fonts; Lizenztext in `dbdmapscout/fonts/OFL.txt` | SIL Open Font License 1.1 |
| Schrift `dbdmapscout/fonts/Inter-*.otf` (Overlay-Stile Glas-Karten / Chips & Icons / Minimal Line, seit 1.3; Subsets der vier Gewichte Regular/Medium/SemiBold/Bold, mit fontTools auf Latein + Satzzeichen gekürzt) | [Inter](https://github.com/rsms/inter), The Inter Project Authors; Lizenztext in `dbdmapscout/fonts/OFL-Inter.txt` | SIL Open Font License 1.1 |
| PySide6-Essentials 6.11.2 und shiboken6 (Qt for Python, neues Steuerfenster) | PyPI, von `start.bat` installiert | LGPL-3.0 (unverändert als Bibliothek genutzt, austauschbar) |
| UDP-Ping-Beacons (Port 7770) | [AWS GameLift Dokumentation](https://docs.aws.amazon.com/gameliftservers/latest/developerguide/reference-udp-ping-beacons.html) | – |

Apache License 2.0: <https://www.apache.org/licenses/LICENSE-2.0>

Dead by Daylight ist eine Marke von Behaviour Interactive. Dieses Programm steht in keiner Verbindung zu Behaviour Interactive.
