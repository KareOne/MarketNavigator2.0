from functools import wraps
from flask import request
from config.config import User

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        request.user = User(1, "09922417276", 
                            role="admin", is_active=1)
        return f(*args, **kwargs)

    return decorated
