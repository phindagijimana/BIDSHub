"""Page modules extracted from app.py (incremental de-monolithing).

Each module holds one Streamlit page function. To avoid a circular import with
app.py (which imports these and also defines shared chrome helpers), modules
import app-level helpers lazily inside the function body.
"""
