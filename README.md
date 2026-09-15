# Deal Intelligence Lab

A local app for keeping track of your M&A deal projects. Create a project,
give it a name and description, and come back to it any time — everything
is saved on your own computer.

This is an early milestone: it only handles projects. Uploading documents
and AI-assisted analysis will come in a later step.

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

Everything you create is saved in a file at `data/deal_lab.db` inside this
folder. It stays there between restarts — closing the app, restarting your
computer, or quitting Terminal will not delete your projects. Do not delete
the `data` folder unless you want to erase everything.

## Running the tests (optional)

If you want to double-check everything still works after any changes:

```
python3 -m unittest discover -s tests
```
