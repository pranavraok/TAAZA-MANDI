from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Supabase JWT verification (simplified)
def verify_token(token):
    try:
        payload = jwt.decode(token, SUPABASE_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get('token')
        if not token or not verify_token(token):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # This is a placeholder; actual auth will be handled by Supabase JS in auth.js
        session['token'] = request.form.get('token')  # Expect token from frontend
        return redirect(url_for('user_select'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Placeholder; auth.js will handle registration with Supabase
        session['token'] = request.form.get('token')
        return redirect(url_for('user_select'))
    return render_template('index.html')

@app.route('/user-select', methods=['GET', 'POST'])
@login_required
def user_select():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        if user_type:
            session['user_type'] = user_type
            if user_type == 'buyer':
                return redirect(url_for('buyer_feed'))
            elif user_type == 'seller':
                return redirect(url_for('seller_feed'))
    return render_template('user_select.html')

@app.route('/buyer-feed')
@login_required
def buyer_feed():
    return render_template('buyer-feed.html')

@app.route('/seller-feed')
@login_required
def seller_feed():
    return render_template('seller-feed.html')

@app.route('/logout')
def logout():
    session.pop('token', None)
    session.pop('user', None)
    session.pop('user_type', None)
    return redirect(url_for('login'))

@app.route('/verify-token', methods=['POST'])
def verify_token_endpoint():
    token = request.json.get('token')
    if verify_token(token):
        return jsonify({"status": "success", "message": "Token is valid"})
    return jsonify({"status": "error", "message": "Invalid token"}), 401

if __name__ == '__main__':
    app.run(debug=True)