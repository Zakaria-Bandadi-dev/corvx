# Corvx News — Modular Flask Structure

Pure organization/refactoring of the supplied Flask application.

Start:
```bash
python app.py
```

The original Flask host/port behavior is retained:
- host: `0.0.0.0`
- port: `int(os.getenv("PORT", "5000"))`
- debug: `False`

Keep existing static assets such as `static/logo.png` from the original project.
