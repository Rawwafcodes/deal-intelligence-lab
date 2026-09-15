# Deal Intelligence Lab

A local app for keeping track of your M&A deal projects. Create a project,
upload the original deal documents, and come back to them any time —
everything is saved on your own computer.

This is an early milestone: it handles projects and original-document
storage. AI-assisted analysis will come in a later step.

## Requirements

- Python 3 (already installed on this Mac — nothing else to install)

## How to run it

1. Open the Terminal app.
2. Go to this folder:
   ```
   cd ~/Projects/deal-intelligence-lab
   ```
3. Start the app:
   ```
   python3 server.py
   ```
4. Open your browser to:
   ```
   http://localhost:8765
   ```

Leave the Terminal window open while you use the app. To stop the app,
click back in that Terminal window and press `Ctrl+C`.

## Your data

Your projects (name, description) are saved in `data/deal_lab.db` inside
this folder. It stays there between restarts.

**Uploaded documents are stored separately**, outside this app folder, at:

```
~/DealLabData/projects/<project-id>/originals
```

This keeps confidential deal documents out of the application's code
folder entirely (and out of git, if you ever put this folder under
version control). Don't delete `~/DealLabData` unless you want to erase
every document you've uploaded.

### Uploading documents

On a project's page, use **Choose files** to upload one or more files at
once, or **Choose a folder** (where your browser supports it) to upload
an entire folder, preserving its internal structure. Each uploaded file
is stored exactly as-is (byte-for-byte) and listed in an inventory with
its file type, size, checksum, and upload time. You can download the
original file back at any time, or remove it (after confirming).

Supported file types: PDF, DOCX, XLSX, PPTX, TXT, and common image
formats (PNG, JPG, GIF, BMP, TIFF, WEBP). Uploading the exact same file
twice to a project is detected and skipped rather than stored again.

By default, a single upload request is limited to 500 MB total and 200
files. To change these, set environment variables before starting the
app, for example:

```
DEAL_LAB_MAX_UPLOAD_BYTES=1000000000 DEAL_LAB_MAX_FILES_PER_UPLOAD=500 python3 server.py
```

You can also change where documents are stored with `DEAL_LAB_DATA_DIR`,
for example:

```
DEAL_LAB_DATA_DIR=/path/to/somewhere/else python3 server.py
```

## Running the tests (optional)

If you want to double-check everything still works after any changes:

```
python3 -m unittest discover -s tests
```
