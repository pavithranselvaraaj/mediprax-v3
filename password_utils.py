import hashlib

# Using hashlib (built-in) instead of bcrypt to avoid extra dependency
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hashlib.sha256(password.encode()).hexdigest() == hashed
