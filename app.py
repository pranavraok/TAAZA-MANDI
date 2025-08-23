from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import jwt
import os
from functools import wraps
from supabase import create_client, Client 
import joblib
import numpy as np

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'taaza-mandi-super-secret-key-change-in-production-2025')

# ---------- Supabase configuration ----------
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://wesrjuxmbudivggitawl.supabase.co')
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '/1l7yuaS34mIaYd7Qa0863vr2uHzT559zGDIYSX/mIAjop+t2PhbfEOYq6IORyxS3T03W+WbVsmJ1cZElPFaKA==')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indlc3JqdXhtYnVkaXZnZ2l0YXdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4NDA3OTYsImV4cCI6MjA3MTQxNjc5Nn0.KTHwj3jAGWC-9d5gIL6Znr2u22ycdpo1VXq8JHJq3Jg')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Load ML model
model = joblib.load('final_model.pkl')


# ==================== AUTH HELPERS ====================

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

# Make config available in templates
@app.context_processor
def inject_config():
    return {
        'config': {
            'SUPABASE_URL': SUPABASE_URL,
            'SUPABASE_ANON_KEY': SUPABASE_ANON_KEY
        }
    }


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

    try:
        data = request.get_json(force=True, silent=False)
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400

        token = data.get('token')
        user_data = data.get('user', {})
        email = user_data.get('email')
        if not email:
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400

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


# ==================== DASHBOARD ====================

@app.route('/seller-feed')
@require_auth
def seller_feed():
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))

    response = supabase.table("products") \
        .select("*") \
        .eq("seller_email", session['user']['email']) \
        .execute()

    return render_template('seller_feed.html', products=response.data)


@app.route('/buyer-feed')
@require_auth
def buyer_feed():
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))

    products = supabase.table("products").select("*").execute()
    return render_template('buyer_feed.html', products=products.data)


# ==================== PROFILE ====================

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

    try:
        data = request.get_json(force=True, silent=True) or {}
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

    try:
        data = request.get_json(force=True, silent=True) or {}
        return jsonify({'status': 'success', 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== PRODUCT UPLOAD ====================

@app.route('/upload-product', methods=['POST'])
@require_auth
def upload_product():
    if session.get('user_role') != 'seller':
        return jsonify({'status': 'error', 'message': 'Only sellers can upload products'}), 403

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    quantity = request.form.get('quantity', '').strip()
    price = request.form.get('price', '').strip()
    category = request.form.get('category', '').strip()
    location = request.form.get('location', '').strip()

    missing = [k for k, v in {
        'title': title,
        'description': description,
        'quantity': quantity,
        'price': price,
        'category': category,
        'location': location
    }.items() if not v]

    if missing:
        return jsonify({'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'}), 400

    image_file = request.files.get('image')
    image_url = ''
    bucket = 'products'

    try:
        if image_file:
            file_bytes = image_file.read()
            file_name = f"{session['user']['id']}/{image_file.filename}"
            upload_res = supabase.storage.from_(bucket).upload(file_name, file_bytes)
            if upload_res.get('error'):
                raise Exception(upload_res['error']['message'])
            public_url = supabase.storage.from_(bucket).get_public_url(file_name)
            image_url = public_url.get('public_url', '')
        else:
            image_url = f"https://via.placeholder.com/400x240?text={category}"

        product_data = {
            'title': title,
            'description': description,
            'quantity': quantity,
            'price': price,
            'category': category,
            'location': location,
            'images': [image_url],
            'seller_email': session['user']['email']
        }

        supabase.table('products').insert(product_data).execute()
        return jsonify({'status': 'success', 'message': 'Product uploaded successfully', 'product': product_data})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Upload failed: {str(e)}'}), 500


@app.route('/post-upload')
@require_auth
def post_upload():
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))

    try:
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


# ==================== PREDICTOR ====================

@app.route('/predictor', methods=['GET', 'POST'])
def predictor():
    crop = None
    if request.method == 'POST':
        try:
            n = float(request.form['n'])
            p = float(request.form['p'])
            k = float(request.form['k'])
            humidity = float(request.form['humidity'])
            rainfall = float(request.form['rainfall'])

            features = np.array([[n, p, k, humidity, rainfall]])
            prediction = model.predict(features)[0]
            crop = prediction.upper()
        except Exception as e:
            crop = f"❌ Error during prediction: {e}"

    return render_template('predictor.html', crop=crop)


# ==================== STATIC PAGES ====================

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

@app.route('/market')
def market():
    try:
        return render_template('market.html')
    except Exception:
        return '<h1>Market</h1><p>Explore the market for various products.</p>'

@app.route('/equipment')
def equipment():
    try:
        return render_template('equipment.html')
    except Exception as e:
        return f'<h1>Equipment</h1><p>Error: {e}</p>'

@app.route('/schemes')
def schemes():
    try:
        return render_template('schemes.html')
    except Exception:
        return '<h1>Government Schemes</h1><p>Explore various government schemes for farmers.</p>'


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


# ==================== RUN ====================

if __name__ == '__main__':
    print("Starting TAAZA MANDI Flask App...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"   {rule} -> {rule.endpoint}")
    app.run(debug=True)
