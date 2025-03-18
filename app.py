from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# (Optional) If you plan to use a database, you can initialize it here.
# For this example, we use in‑memory data structures so we don't need a DB.
# from flask_sqlalchemy import SQLAlchemy
# db = SQLAlchemy(app)

# Import the routes so that they are registered with the app.
import routes
