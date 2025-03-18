import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    # If you use a database, for example:
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///bubble.db'
    # SQLALCHEMY_TRACK_MODIFICATIONS = False
