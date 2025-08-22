from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime

# Load environment variables (though hardcoded for now)
load_dotenv()
SUPABASE_URL = "https://wesrjuxmbudivggitawl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indlc3JqdXhtYnVkaXZnZ2l0YXdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4NDA3OTYsImV4cCI6MjA3MTQxNjc5Nn0.KTHwj3jAGWC-9d5gIL6Znr2u22ycdpo1VXq8JHJq3Jg"

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
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        token = request.form.get('token')  # Expect token from Supabase JS
        if token and verify_token(token):
            session['token'] = token
            return redirect(url_for('user_select'))
        else:
            return render_template('index.html', error="Invalid login credentials. Please try again.")
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        token = request.form.get('token')  # Expect token from Supabase JS after registration
        if token and verify_token(token):
            session['token'] = token
            return redirect(url_for('user_select'))
        else:
            return render_template('index.html', error="Registration failed. Please try again.")
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
    return redirect(url_for('index'))

@app.route('/verify-token', methods=['POST'])
def verify_token_endpoint():
    token = request.json.get('token')
    if verify_token(token):
        return jsonify({"status": "success", "message": "Token is valid"})
    return jsonify({"status": "error", "message": "Invalid token"}), 401

@app.route('/api/newsletter', methods=['POST'])
def newsletter_signup():
    try:
        data = request.get_json()
        email = data.get('email')
        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400
        # Here you would typically save the email to a database
        # For now, just simulate a successful response
        return jsonify({"status": "success", "message": "Subscription successful"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)