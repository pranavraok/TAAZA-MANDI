from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import jwt
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'taaza-mandi-super-secret-key-change-in-production-2025')

# ---------- Supabase configuration ----------
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://wesrjuxmbudivggitawl.supabase.co')
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '/1l7yuaS34mIaYd7Qa0863vr2uHzT559zGDIYSX/mIAjop+t2PhbfEOYq6IORyxS3T03W+WbVsmJ1cZElPFaKA==')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indlc3JqdXhtYnVkaXZnZ2l0YXdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4NDA3OTYsImV4cCI6MjA3MTQxNjc5Nn0.KTHwj3jAGWC-9d5gIL6Znr2u22ycdpo1VXq8JHJq3Jg')

# Make config available to templates
@app.context_processor
def inject_config():
    return {
        'config': {
            'SUPABASE_URL': SUPABASE_URL,
            'SUPABASE_ANON_KEY': SUPABASE_ANON_KEY
        }
    }

# ---------- Auth helpers ----------
def verify_supabase_token(token):
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=['HS256'], audience='authenticated')
        return {
            'status': 'success',
            'user': {
                'id': payload.get('sub'),
                'email': payload.get('email'),
                'user_metadata': payload.get('user_metadata', {}),
                'aud': payload.get('aud'),
                'role': payload.get('role')
            }
        }
    except jwt.ExpiredSignatureError:
        return {'status': 'error', 'message': 'Token expired'}
    except jwt.InvalidTokenError:
        return {'status': 'error', 'message': 'Invalid token'}

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    if session.get('user'):
        return redirect(url_for('user_select'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('login.html')
    # POST
    try:
        data = request.get_json(force=True, silent=True) or {}
        token = data.get('token')
        user_data = data.get('user')
        if token and user_data:
            session['access_token'] = token
            session['user'] = user_data
            return jsonify({'status': 'success', 'message': 'Login successful', 'redirect_url': url_for('user_select')})
        return jsonify({'status': 'error', 'message': 'Invalid login data'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('signup.html')

    # POST
    try:
        data = request.get_json(force=True, silent=False)
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400

        token = data.get('token')
        user_data = data.get('user', {})
        email = user_data.get('email')
        if not email:
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400

        # store session
        session['access_token'] = token
        session['user'] = user_data

        return jsonify({'status': 'success', 'message': 'Registration successful', 'redirect_url': url_for('user_select')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('forgot_password.html')

    # POST
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email')
        if not email:
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400
        # TODO: send reset email
        return jsonify({'status': 'success', 'message': 'Password reset link sent successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/user-select', methods=['GET', 'POST'])
@require_auth
def user_select():
    if request.method == 'GET':
        role = session.get('user_role')
        if role == 'buyer':
            return redirect(url_for('buyer_feed'))
        if role == 'seller':
            return redirect(url_for('seller_feed'))
        return render_template('user_select.html')

    # POST
    try:
        data = request.get_json(force=True, silent=True) or {}
        role = data.get('role')
        if role not in ['buyer', 'seller']:
            return jsonify({'status': 'error', 'message': f'Invalid role: {role}. Must be buyer or seller.'}), 400
        session['user_role'] = role
        redirect_url = url_for('buyer_feed') if role == 'buyer' else url_for('seller_feed')
        return jsonify({'status': 'success', 'message': f'Role set as {role}', 'redirect_url': redirect_url})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

# ==================== DASHBOARD ROUTES ====================

@app.route('/buyer-feed')
@require_auth
def buyer_feed():
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))
    try:
        return render_template('buyer_feed.html')
    except Exception:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Buyer Dashboard</h1>
            <p>Welcome to the buyer dashboard! This page will show fresh produce from farmers.</p>
            <p><strong>Template: buyer_feed.html not found</strong></p>
            <a href="/buyer-profile">My Profile</a> | <a href="/logout">Logout</a>
        </div>
        '''

@app.route('/seller-feed')
@require_auth
def seller_feed():
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    try:
        return render_template('seller_feed.html')
    except Exception:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Seller Dashboard</h1>
            <p>Welcome to the seller dashboard! Here you can post your produce for sale.</p>
            <p><strong>Template: seller_feed.html not found</strong></p>
            <a href="/seller-profile">My Profile</a> | <a href="/post-upload">Post New Product</a> | <a href="/logout">Logout</a>
        </div>
        '''

# ==================== PROFILE ROUTES ====================

# Provide BOTH kebab and snake paths so your links never 404
@app.route('/buyer_profile', methods=['GET', 'POST'])
@app.route('/buyer-profile', methods=['GET', 'POST'])
@require_auth
def buyer_profile():
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))

    if request.method == 'GET':
        try:
            return render_template('buyer_profile.html')
        except Exception:
            return '''
            <div style="text-align:center; padding:50px; font-family:Arial;">
                <h1>Buyer Profile</h1>
                <p><strong>Template: buyer_profile.html not found</strong></p>
                <a href="/buyer-feed">Back to Dashboard</a>
            </div>
            '''

    # POST
    try:
        data = request.get_json(force=True, silent=True) or {}
        # TODO: persist to Supabase
        return jsonify({'status': 'success', 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/seller_profile', methods=['GET', 'POST'])
@app.route('/seller-profile', methods=['GET', 'POST'])
@require_auth
def seller_profile():
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))

    if request.method == 'GET':
        try:
            return render_template('seller_profile.html')
        except Exception:
            return '''
            <div style="text-align:center; padding:50px; font-family:Arial;">
                <h1>Seller Profile</h1>
                <p><strong>Template: seller_profile.html not found</strong></p>
                <a href="/seller-feed">Back to Dashboard</a>
            </div>
            '''

    # POST
    try:
        data = request.get_json(force=True, silent=True) or {}
        # TODO: persist to Supabase
        return jsonify({'status': 'success', 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== PRODUCT UPLOAD (MISSING ENDPOINT FIX) ====================

# This matches your frontend JS: fetch('{{ url_for("upload_product") }}', { method: 'POST', body: formData })
@app.route('/upload-product', methods=['POST'])
@require_auth
def upload_product():
    # Only sellers can upload
    if session.get('user_role') != 'seller':
        return jsonify({'status': 'error', 'message': 'Only sellers can upload products'}), 403

    # Expect multipart/form-data with files
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    quantity = request.form.get('quantity', '').strip()
    price = request.form.get('price', '').strip()
    category = request.form.get('category', '').strip()
    location = request.form.get('location', '').strip()

    # Basic validation
    missing = [k for k, v in {
        'title': title, 'description': description, 'quantity': quantity,
        'price': price, 'category': category, 'location': location
    }.items() if not v]
    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    # Gather up to 5 images
    images = []
    for i in range(5):
        f = request.files.get(f'image_{i}')
        if f:
            images.append(f.filename)

    # TODO: persist product + upload images to storage (Supabase Storage / S3)
    # For now, simulate success
    product = {
        'title': title,
        'description': description,
        'quantity': quantity,
        'price': price,
        'category': category,
        'location': location,
        'images': images,
        'seller_email': session.get('user', {}).get('email')
    }

    return jsonify({'status': 'success', 'message': 'Product uploaded', 'product': product})

# ==================== ADDITIONAL ROUTES ====================

@app.route('/post-upload')
@require_auth
def post_upload():
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))

    try:
        # templates/post_upload.html must exist
        return render_template('post_upload.html')
    except Exception:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Post New Product</h1>
            <p>Upload your farm produce here!</p>
            <p><strong>Template: post_upload.html not found</strong></p>
            <a href="/seller-feed">Back to Dashboard</a>
        </div>
        '''

@app.route('/about')
def about():
    try:
        return render_template('about.html')
    except Exception:
        return '<h1>About TAAZA MANDI</h1><p>Connecting farmers directly to buyers.</p>'

@app.route('/contact')
def contact():
    try:
        return render_template('contact.html')
    except Exception:
        return '<h1>Contact Us</h1><p>Get in touch with TAAZA MANDI team.</p>'

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# ==================== API ROUTES ====================

@app.route('/api/check-auth', methods=['POST'])
def check_auth():
    if session.get('user'):
        return jsonify({
            'status': 'success',
            'authenticated': True,
            'user': session['user'],
            'role': session.get('user_role')
        })
    else:
        return jsonify({'status': 'error', 'authenticated': False})

@app.route('/api/update-profile', methods=['POST'])
@require_auth
def update_profile():
    try:
        data = request.get_json(force=True, silent=True) or {}
        user_role = session.get('user_role')
        # TODO: persist profile changes
        return jsonify({'status': 'success', 'message': 'Profile updated successfully', 'data': data, 'role': user_role})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    try:
        return render_template('404.html'), 404
    except Exception:
        return f'''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for doesn't exist.</p>
            <p><strong>Requested path:</strong> {request.path}</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 404

@app.errorhandler(500)
def internal_error(error):
    try:
        return render_template('500.html'), 500
    except Exception:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>500 - Server Error</h1>
            <p>Something went wrong. Please try again later.</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 500

# ==================== DEV ENTRY ====================

if __name__ == '__main__':
    print("Starting TAAZA MANDI Flask App...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"   {rule} -> {rule.endpoint}")
    app.run(debug=True)
