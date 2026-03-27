import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mediprax-erhosiptalsp-2026')
    DATABASE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mediprax.db')
