from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import jwt
import requests
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'taaza-mandi-super-secret-key-change-in-production-2025'


# Supabase configuration
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

def verify_supabase_token(token):
    """Verify Supabase JWT token"""
    try:
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=['HS256'],
            audience='authenticated'
        )
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
    """Decorator to require authentication for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if not session.get('user'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """Landing page with Sign In and Sign Up buttons"""
    # If user is already logged in, redirect to user select
    if session.get('user'):
        return redirect(url_for('user_select'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if request.method == 'GET':
        # If already logged in, redirect to user select
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('login.html')
    
    # Handle POST request (form submission)
    if request.method == 'POST':
        try:
            data = request.get_json()
            token = data.get('token')
            user_data = data.get('user')
            
            if token and user_data:
                # Store user info in session
                session['access_token'] = token
                session['user'] = user_data
                
                return jsonify({
                    'status': 'success',
                    'message': 'Login successful',
                    'redirect_url': url_for('user_select')
                })
            else:
                return jsonify({'status': 'error', 'message': 'Invalid login data'}), 400
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup page and handler"""
    if request.method == 'GET':
        # If already logged in, redirect to user select
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('signup.html')
    
    # Handle POST request (form submission)
    if request.method == 'POST':
        try:
            data = request.get_json()
            token = data.get('token')
            user_data = data.get('user')
            
            if token and user_data:
                # Store user info in session
                session['access_token'] = token
                session['user'] = user_data
                
                return jsonify({
                    'status': 'success',
                    'message': 'Registration successful',
                    'redirect_url': url_for('user_select')
                })
            else:
                return jsonify({'status': 'error', 'message': 'Invalid registration data'}), 400
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page and handler"""
    if request.method == 'GET':
        # If already logged in, redirect to user select
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('forgot_password.html')
    
    # Handle POST request (reset email sending)
    if request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email')
            
            if not email:
                return jsonify({'status': 'error', 'message': 'Email is required'}), 400
            
            # Here you would typically integrate with your email service
            # For now, we'll just return success (Supabase handles this on the frontend)
            return jsonify({
                'status': 'success',
                'message': 'Password reset link sent successfully'
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/user-select', methods=['GET', 'POST'])
@require_auth
def user_select():
    """User role selection page"""
    if request.method == 'GET':
        # Check if user already has a role
        if session.get('user_role'):
            if session['user_role'] == 'buyer':
                return redirect(url_for('buyer_feed'))
            elif session['user_role'] == 'seller':
                return redirect(url_for('seller_feed'))
        
        return render_template('user_select.html')
    
    # Handle POST request (role selection)
    if request.method == 'POST':
        try:
            data = request.get_json()
            role = data.get('role')
            
            if role in ['buyer', 'seller']:
                # Store role in session
                session['user_role'] = role
                
                # Redirect based on role
                if role == 'buyer':
                    redirect_url = url_for('buyer_feed')
                else:
                    redirect_url = url_for('seller_feed')
                
                return jsonify({
                    'status': 'success',
                    'message': f'Role set as {role}',
                    'redirect_url': redirect_url
                })
            else:
                return jsonify({'status': 'error', 'message': 'Invalid role'}), 400
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/buyer-feed')
@require_auth
def buyer_feed():
    """Buyer feed page"""
    # Ensure user is a buyer
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))
    return render_template('buyer-feed.html')

@app.route('/seller-feed')  
@require_auth
def seller_feed():
    """Seller feed page"""
    # Ensure user is a seller
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    return render_template('seller-feed.html')

# ==================== ADDITIONAL ROUTES ====================

@app.route('/post-upload')
@require_auth
def post_upload():
    """Post upload page for sellers only"""
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    return render_template('post-upload.html')

@app.route('/equipment')
def equipment():
    """Equipment page"""
    return render_template('equipment.html')

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# ==================== API ROUTES ====================

@app.route('/api/check-auth', methods=['POST'])
def check_auth():
    """Check if user is authenticated"""
    if session.get('user'):
        return jsonify({
            'status': 'success',
            'authenticated': True,
            'user': session['user'],
            'role': session.get('user_role')
        })
    else:
        return jsonify({
            'status': 'error',
            'authenticated': False
        })

@app.route('/api/newsletter-signup', methods=['POST'])
def newsletter_signup():
    """Newsletter signup endpoint"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400
        
        # Here you would typically save to database
        return jsonify({'status': 'success', 'message': 'Subscribed successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    try:
        return render_template('404.html'), 404
    except:
        # Fallback if 404.html is missing
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for doesn't exist.</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    try:
        return render_template('500.html'), 500
    except:
        # Fallback if 500.html is missing
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>500 - Server Error</h1>
            <p>Something went wrong. Please try again later.</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 500


if __name__ == '__main__':
    app.run(debug=True)
