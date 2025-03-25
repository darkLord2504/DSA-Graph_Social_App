from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Import routes so they're registered with the app
import routes
