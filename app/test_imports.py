try:
    import flask
    print(f"Flask is installed at: {flask.__file__}")
except ImportError:
    print("Flask is not installed in the current Python environment")

try:
    import sqlalchemy
    print(f"SQLAlchemy is installed at: {sqlalchemy.__file__}")
except ImportError:
    print("SQLAlchemy is not installed in the current Python environment")