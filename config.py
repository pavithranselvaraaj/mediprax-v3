import os
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mediprax-secret-2026')
    DATABASE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mediprax.db')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'prescriptions')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 5 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
