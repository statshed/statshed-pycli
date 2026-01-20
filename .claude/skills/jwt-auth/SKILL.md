---
name: jwt-auth
description: Flask JWT authentication boilerplate with flask-jwt-extended. Use when implementing JWT auth, login/logout endpoints, token refresh, or protected routes in Flask.
---

# Flask JWT Authentication

## Requirements
```bash
pip install flask flask-jwt-extended bcrypt
```

## Basic Setup
```python
from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from datetime import timedelta
import bcrypt

app = Flask(__name__)

# Configuration
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change in production!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)

jwt = JWTManager(app)
```

## User Model (SQLAlchemy)
```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )
    
    def to_dict(self):
        return {'id': self.id, 'email': self.email}
```

## Registration Endpoint
```python
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    user = User(email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User created', 'user': user.to_dict()}), 201
```

## Login Endpoint
```python
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account disabled'}), 403
    
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200
```

## Token Refresh Endpoint
```python
@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({'access_token': access_token}), 200
```

## Protected Route
```python
@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify({'message': f'Hello {user.email}', 'user': user.to_dict()})
```

## Token Blocklist (Logout)
```python
# In-memory blocklist (use Redis in production)
BLOCKLIST = set()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in BLOCKLIST

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    BLOCKLIST.add(jti)
    return jsonify({'message': 'Successfully logged out'}), 200
```

## Custom Claims
```python
@jwt.additional_claims_loader
def add_claims_to_access_token(identity):
    user = User.query.get(identity)
    return {
        'email': user.email,
        'roles': ['admin'] if user.is_admin else ['user']
    }

# Access claims in protected routes
@app.route('/api/admin', methods=['GET'])
@jwt_required()
def admin_only():
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({'error': 'Admin required'}), 403
    return jsonify({'message': 'Admin access granted'})
```

## Error Handlers
```python
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'Authorization required'}), 401

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has been revoked'}), 401
```

## Blueprint Organization
```python
# auth/routes.py
from flask import Blueprint
from flask_jwt_extended import jwt_required

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    # ... login logic

@auth_bp.route('/register', methods=['POST'])
def register():
    # ... register logic

# app.py
from auth.routes import auth_bp
app.register_blueprint(auth_bp)
```

## Testing with curl
```bash
# Register
curl -X POST http://localhost:7828/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'

# Login
curl -X POST http://localhost:7828/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'

# Access protected route
curl http://localhost:7828/api/protected \
  -H "Authorization: Bearer <access_token>"

# Refresh token
curl -X POST http://localhost:7828/api/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

## Production Checklist
- [ ] Use strong JWT_SECRET_KEY from environment variable
- [ ] Use Redis for token blocklist
- [ ] Enable HTTPS only
- [ ] Set appropriate token expiration times
- [ ] Add rate limiting to auth endpoints
- [ ] Log authentication events
```

## Verify Installation

Check skills are loaded:
```
/skills
```

Or test by asking:
```
"Help me add JWT authentication to my Flask app"
