# Deal Intelligence Lab

A local app for keeping track of your M&A deal projects. Create a project,
upload the original deal documents, and come back to them any time —
everything is saved on your own computer.

This is an early milestone: it handles projects, original-document
storage, and a basic AI connection check. Document analysis by AI comes
in a later step.

## Requirements

- Python 3 (already installed on this Mac — nothing else to install)

## One-time setup

This app now uses two small add-on packages (to talk to the Claude API),
so it runs inside a Python "virtual environment" — an isolated folder of
packages that doesn't affect anything else on your computer. Set it up
once:

1. Open the Terminal app.
2. Go to this folder:
   ```
   cd ~/Projects/deal-intelligence-lab
   ```
3. Create the virtual environment:
   ```
   python3 -m venv venv
   ```
4. Activate it and install the packages:
   ```
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## How to run it

Every time you want to run the app:

1. Open the Terminal app.
2. Go to this folder and activate the virtual environment:
   ```
   cd ~/Projects/deal-intelligence-lab
   source venv/bin/activate
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

## Inspecting a PDF with Claude

On a project's page, PDF documents get an **Inspect with Claude** action.
Clicking it asks you to confirm before sending anything, since this is the
one action in the app that transmits a document outside your computer.
After you confirm:

- The **original PDF file, and only that file** (no other project
  documents), is sent directly to Claude using Anthropic's native PDF
  support — the app never extracts, OCRs, converts, or otherwise
  preprocesses the file itself.
- Claude reads the PDF and identifies what the document is, its principal
  subjects, and its material factual statements, citing the source page
  for every factual statement using Anthropic's native citation feature.
  Citations link straight back to the original PDF, opened at that page.
- You land on a results page showing the analysis, with a clearly marked
  "(uncited)" tag on any material statement Claude could not tie to a
  page — never a fabricated page reference.
- Every inspection (its outcome, the model used, token usage, stop
  reason, and how long it took) is recorded in `data/deal_lab.db` so
  there's an audit trail of what was sent and when.

Only PDF files are supported in this milestone. Files above ~23 MB, PDFs
that are password-protected or encrypted, and malformed files are
rejected with a clear error before or after the request, instead of
being silently mishandled.

**Design note:** the PDF is sent inline (base64) in the request rather
than uploaded to Anthropic's Files API first, since each inspection is a
one-off analysis of a single document — this keeps no remote copy on
Anthropic's side to track or delete afterwards.

## AI connection

On the home page, the **AI connection** card has a **Test AI connection**
button. It sends one tiny request to Claude asking it to reply with a
fixed confirmation phrase, and reports whether it worked, which model
responded, and how many tokens were used. It never sends any of your
uploaded documents — it's just a connectivity check.

To use it, you need an Anthropic API key (get one at
[console.anthropic.com](https://console.anthropic.com/)). Set it up
once:

```
cp .env.example .env.local
```

Then open `.env.local` in any text editor and paste your key after
`ANTHROPIC_API_KEY=`. This file is ignored by git and never shared —
only your own computer reads it. Restart the app (`Ctrl+C`, then
`python3 server.py` again) after editing it.

`ANTHROPIC_MODEL` in the same file controls which Claude model is used
for the test; leave it as-is unless you have a reason to change it.

## Running the tests (optional)

If you want to double-check everything still works after any changes
(this uses a stand-in for the AI connection, so it never contacts the
real API or uses any credit):

```
source venv/bin/activate
python3 -m unittest discover -s tests
```
