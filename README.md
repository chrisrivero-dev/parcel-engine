# Parcel Engine

Parcel Engine is a local Python tool for parsing metes-and-bounds legal descriptions, converting calls into geometry, validating closure, and previewing parcel shapes.

The goal is to support Mapping workflow research and testing by turning legal-description text into structured COGO calls and drawable parcel geometry.

> This repository does not contain official County data, real APNs, private legal descriptions, Q-drive files, or internal production records.

---

## Purpose

Parcel Engine is designed to help test whether legal descriptions can be converted into:

- Parsed line calls
- Parsed curve calls
- Coordinate paths
- Parcel preview geometry
- Closure validation
- DXF / GeoJSON exports

This project is experimental and should be treated as a local mapping support tool, not an authoritative legal or surveying system.

---

## Current Capabilities

- Parse structured COGO-style legal description text
- Parse quadrant bearings such as `N 45°32'10" E 100.23 FT`
- Parse compact bearings such as `N45°32'10"E 100.23`
- Parse cardinal calls such as `E 100`
- Parse selected curve calls with radius, handedness, delta, or arc length
- Build coordinate geometry from parsed calls
- Preview parcel geometry in a desktop UI
- Validate closure / misclosure
- Export geometry to DXF and GeoJSON

---

## Project Structure

```text
parcel_engine/
├── exporters/
│   ├── dxf.py
│   ├── geojson.py
│   └── shapefile.py
├── geometry/
│   ├── bearings.py
│   ├── builder.py
│   ├── commencement.py
│   ├── curves.py
│   ├── hierarchy.py
│   └── lines.py
├── models/
│   ├── errors.py
│   └── schema.py
├── transcription/
│   ├── parser.py
│   ├── validator.py
│   └── llm_contract.md
├── validation/
│   ├── closure.py
│   ├── curve_checks.py
│   ├── intersections.py
│   └── report.py
├── ui/
│   ├── desktop_app.py
│   ├── live_renderer.py
│   └── state.py
├── tests/
├── main.py
├── requirements.txt
├── pyproject.toml
└── README.md

---

## OCR Setup

Parcel Engine supports loading a legal-description image and running OCR
to populate the source text box. OCR is optional — manual paste/edit of
legal descriptions works without it.

To enable **Load Image OCR**:

1. Install the Python libraries:

   ```
   pip install pytesseract Pillow
   ```

2. Install the **Tesseract** executable:

   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`

3. Either add the Tesseract install folder to your `PATH`, or set the
   `PARCEL_ENGINE_TESSERACT` environment variable to the full path of
   the executable, for example:

   ```
   setx PARCEL_ENGINE_TESSERACT "C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

When you click **Load Image OCR**, the app resolves Tesseract in this
order:

1. `PARCEL_ENGINE_TESSERACT` environment variable
2. Common Windows install locations (`C:\Program Files\Tesseract-OCR\…`)
3. `tesseract` on `PATH`

If none of these resolve, the app shows a setup dialog explaining the
options instead of crashing.
