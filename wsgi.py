"""
WSGI entry point for PythonAnywhere (or any WSGI-based host)

On PythonAnywhere:
  1. Upload / clone the repo into your home directory, e.g. /home/<user>/kabekanji
  2. Create a virtualenv and pip install -r requirements.txt
  3. Run scripts/seed_db.py once to create data/kanji.db
  4. In the Web tab, edit your WSGI config file (path shown in the dashboard)
     and replace its contents with something like:

        import sys
        path = "/home/<user>/kabekanji"
        if path not in sys.path:
            sys.path.insert(0, path)

        from wsgi import app as application

  5. Set your env vars (SERVER_URL, SHORTCUT_URL) in the Web tab's
     "Environment variables" section
  6. Optional but faster: add a static-files mapping so PythonAnywhere serves
     static/ directly via nginx instead of routing through Flask
     URL /  →  /home/<user>/kabekanji/static
"""

from server.main import app

if __name__ == "__main__":
    app.run()
