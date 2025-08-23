from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import jwt
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
        if not session.get('user'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """Landing page with Sign In and Sign Up buttons"""
    if session.get('user'):
        return redirect(url_for('user_select'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('login.html')
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            token = data.get('token')
            user_data = data.get('user')
            
            if token and user_data:
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
    print(f"DEBUG: Signup route accessed - Method: {request.method}")
    
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('signup.html')
    
    # Handle POST request
    if request.method == 'POST':
        try:
            # Debug: Print request info
            print(f"DEBUG: Content-Type: {request.content_type}")
            print(f"DEBUG: Is JSON: {request.is_json}")
            print(f"DEBUG: Raw data: {request.get_data()}")
            
            # Get JSON data
            if not request.is_json:
                return jsonify({'status': 'error', 'message': 'Expected JSON data'}), 400
            
            data = request.get_json()
            print(f"DEBUG: Parsed JSON: {data}")
            
            if not data:
                return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
            # Extract data with proper error handling
            try:
                token = data.get('token')
                user_data = data.get('user', {})
                
                # Get basic user info
                email = user_data.get('email')
                if not email:
                    return jsonify({'status': 'error', 'message': 'Email is required'}), 400
                
                # Get user metadata
                user_metadata = user_data.get('user_metadata', {})
                first_name = user_metadata.get('first_name', '')
                last_name = user_metadata.get('last_name', '')
                phone = user_metadata.get('phone', '')
                state = user_metadata.get('state', '')
                
                print(f"DEBUG: Extracted data - Email: {email}, Name: {first_name} {last_name}")
                
                # Store user info in session
                session['access_token'] = token
                session['user'] = user_data
                
                print(f"SUCCESS: User registered successfully: {email}")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Registration successful',
                    'redirect_url': url_for('user_select')
                })
                
            except Exception as e:
                print(f"ERROR: Data extraction error: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Invalid data structure: {str(e)}'}), 400
                
        except Exception as e:
            print(f"ERROR: Signup exception: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page and handler"""
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('user_select'))
        return render_template('forgot_password.html')
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email')
            
            if not email:
                return jsonify({'status': 'error', 'message': 'Email is required'}), 400
            
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
    
    if request.method == 'POST':
        try:
            if not request.is_json:
                return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'No data received'}), 400
            
            role = data.get('role')
            if role not in ['buyer', 'seller']:
                return jsonify({'status': 'error', 'message': f'Invalid role: {role}. Must be buyer or seller.'}), 400
            
            # Store role in session
            session['user_role'] = role
            
            # Generate redirect URL
            if role == 'buyer':
                redirect_url = url_for('buyer_feed')
            else:
                redirect_url = url_for('seller_feed')
            
            return jsonify({
                'status': 'success',
                'message': f'Role set as {role}',
                'redirect_url': redirect_url
            })
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

# ==================== DASHBOARD ROUTES ====================

@app.route('/buyer-feed')
@require_auth
def buyer_feed():
    """Buyer feed page"""
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))
    
    try:
        return render_template('buyer_feed.html')
    except:
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
    """Seller feed page"""
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    
    try:
        return render_template('seller_feed.html')
    except:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Seller Dashboard</h1>
            <p>Welcome to the seller dashboard! Here you can post your produce for sale.</p>
            <p><strong>Template: seller_feed.html not found</strong></p>
            <a href="/seller-profile">My Profile</a> | <a href="/post-upload">Post New Product</a> | <a href="/logout">Logout</a>
        </div>
        '''

# ==================== PROFILE ROUTES ====================

@app.route('/buyer_profile', methods=['GET', 'POST'])
@require_auth
def buyer_profile():
    """Buyer profile page"""
    # Ensure user is a buyer
    if session.get('user_role') != 'buyer':
        return redirect(url_for('user_select'))
    
    if request.method == 'GET':
        return render_template('buyer_profile.html')
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # Here you would update user profile in Supabase
            # For now, just simulate success
            
            return jsonify({
                'status': 'success',
                'message': 'Profile updated successfully'
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/seller-profile', methods=['GET', 'POST'])
@require_auth
def seller_profile():
    """Seller profile page"""
    # Ensure user is a seller
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    
    if request.method == 'GET':
        return render_template('seller_profile.html')
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # Here you would update user profile in Supabase
            # For now, just simulate success
            
            return jsonify({
                'status': 'success',
                'message': 'Profile updated successfully'
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== ADDITIONAL ROUTES ====================

@app.route('/post-upload')
@require_auth
def post_upload():
    """Post upload page for sellers only"""
    if session.get('user_role') != 'seller':
        return redirect(url_for('user_select'))
    
    try:
        return render_template('post_upload.html')
    except:
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
    """About page"""
    try:
        return render_template('about.html')
    except:
        return '<h1>About TAAZA MANDI</h1><p>Connecting farmers directly to buyers.</p>'

@app.route('/contact')
def contact():
    """Contact page"""
    try:
        return render_template('contact.html')
    except:
        return '<h1>Contact Us</h1><p>Get in touch with TAAZA MANDI team.</p>'

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

@app.route('/api/update-profile', methods=['POST'])
@require_auth
def update_profile():
    """Update user profile via API"""
    try:
        data = request.get_json()
        user_role = session.get('user_role')
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        # Here you would update the profile in Supabase
        # For now, just return success
        
        return jsonify({
            'status': 'success',
            'message': 'Profile updated successfully',
            'data': data
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    try:
        return render_template('404.html'), 404
    except:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for doesn't exist.</p>
            <p><strong>Requested path:</strong> ''' + request.path + '''</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    try:
        return render_template('500.html'), 500
    except:
        return '''
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>500 - Server Error</h1>
            <p>Something went wrong. Please try again later.</p>
            <a href="/">Back to Home</a>
        </div>
        ''', 500

if __name__ == '__main__':
    print("Starting TAAZA MANDI Flask App...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"   {rule}")
    app.run(debug=True)
