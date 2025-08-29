from __future__ import annotations
import joblib
import os
import json  # Fixed import
from datetime import datetime, timedelta, timezone
from functools import wraps
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client
import jwt
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
)

# ==================== APP & CONFIG ====================

load_dotenv()

app = Flask(__name__)

# Secret key: don't ship the default in prod
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "taaza-mandi-super-secret-key-change-in-production-2025"
)

# Session security (works on modern Flask)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),
)

# Make sessions permanent by default
@app.before_request
def _make_session_permanent():
    session.permanent = True

# Timezone helper (Asia/Kolkata = UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

# ==================== SUPABASE CONFIG ====================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

missing_env = [
    name
    for name, val in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_JWT_SECRET": SUPABASE_JWT_SECRET,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
    }.items()
    if not val
]
if missing_env:
    raise RuntimeError(
        f"Missing required env vars: {', '.join(missing_env)}. Check your .env file"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ==================== LOAD ML MODEL (resilient) ====================

MODEL_PATH = os.environ.get("MODEL_PATH", "model/final_model.pkl")
model = None
try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    # Don't crash the whole app if model is missing; predictor route will handle it.
    print(f"[WARN] Could not load ML model at {MODEL_PATH}: {e}")

# ==================== AUTH HELPERS ====================

def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase GoTrue JWT locally using the service JWT secret.

    Notes:
      * In Supabase, user JWTs usually have aud="authenticated".
      * Some projects disable audience or change it; we set verify_aud=False for dev friendliness.
    """
    try:
        print(f"Verifying token: {token[:20]}...")  # Only log first 20 chars for security
        
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},  # avoid false negatives across setups
        )
        
        print(f"Token verification successful for user: {payload.get('email')}")
        
        return {
            "status": "success",
            "user": {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "user_metadata": payload.get("user_metadata", {}),
                "aud": payload.get("aud"),
                "role": payload.get("role"),
            },
        }
    except jwt.ExpiredSignatureError:
        print("Token verification failed: Token expired")
        return {"status": "error", "message": "Token expired"}
    except jwt.InvalidTokenError as e:
        print(f"Token verification failed: Invalid token: {e}")
        return {"status": "error", "message": f"Invalid token: {e}"}
    except Exception as e:
        print(f"Token verification failed: Unexpected error: {e}")
        return {"status": "error", "message": f"Token verification failed: {e}"}

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user") or not session.get("access_token"):
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        # Verify token validity
        token_verification = verify_supabase_token(session["access_token"])
        if token_verification["status"] != "success":
            session.clear()
            flash(token_verification["message"], "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function

# Make limited config available in templates
@app.context_processor
def inject_config():
    return {
        "config": {"SUPABASE_URL": SUPABASE_URL, "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY}
    }

# ==================== MAIN ROUTES ====================

@app.route("/")
def index():
    if session.get("user") and session.get("user_role"):
        return redirect(url_for("user_select"))
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user") and session.get("user_role"):
            return redirect(url_for("user_select"))
        return render_template("auth/login.html")

    try:
        data = request.get_json(force=True, silent=True) or {}
        token = data.get("token")
        if not token:
            return jsonify({"status": "error", "message": "Token is required"}), 400

        token_verification = verify_supabase_token(token)
        if token_verification["status"] != "success":
            return (
                jsonify({"status": "error", "message": token_verification["message"]}),
                401,
            )

        session["access_token"] = token
        session["user"] = token_verification["user"]
        # Don't set role yet; user_select will pick it.
        print(f"Login successful: {session['user']}")
        return jsonify(
            {
                "status": "success",
                "message": "Login successful",
                "redirect_url": url_for("user_select"),
            }
        )
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if session.get("user") and session.get("user_role"):
            return redirect(url_for("user_select"))
        return render_template("auth/signup.html")

    try:
        print(f"Request method: {request.method}")
        print(f"Content-Type: {request.headers.get('Content-Type')}")
        print(f"Request data length: {len(request.data) if request.data else 0}")
        
        # Check if request has data
        if not request.data:
            print("ERROR: No request data received")
            return jsonify({
                "status": "error", 
                "message": "No data received"
            }), 400
        
        # Try to get JSON data with better error handling
        try:
            data = request.get_json(force=True)
            print(f"Successfully parsed JSON data: {data}")
        except Exception as json_error:
            print(f"JSON parsing error: {json_error}")
            print(f"Raw request data: {request.data}")
            return jsonify({
                "status": "error", 
                "message": f"Invalid JSON format: {str(json_error)}"
            }), 400
        
        if not data:
            print("ERROR: Parsed data is None or empty")
            return jsonify({
                "status": "error", 
                "message": "Empty data received"
            }), 400
        
        # Validate required fields
        token = data.get("token")
        email = data.get("email")
        
        if not token:
            print("ERROR: Missing token")
            return jsonify({"status": "error", "message": "Token is required"}), 400
        
        if not email:
            print("ERROR: Missing email")
            return jsonify({"status": "error", "message": "Email is required"}), 400

        print(f"Processing signup for email: {email}")

        # Verify the token
        print("Verifying Supabase token...")
        token_verification = verify_supabase_token(token)
        print(f"Token verification result: {token_verification['status']}")
        
        if token_verification["status"] != "success":
            print(f"Token verification failed: {token_verification['message']}")
            return jsonify({
                "status": "error", 
                "message": token_verification["message"]
            }), 401

        # Extract user info from verified token
        verified_user = token_verification["user"]
        user_id = data.get("user_id") or verified_user.get("id") or verified_user.get("sub")

        # Create user session data
        user_data = {
            "id": user_id,
            "email": email,
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "phone": data.get("phone", ""),
            "state": data.get("state", ""),
            "full_name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            "user_type": "pending",
            # Include any additional metadata from the verified token
            **verified_user.get("user_metadata", {})
        }

        # Store in session
        session["access_token"] = token
        session["user"] = user_data
        session.permanent = True

        print(f"Signup successful for user: {user_data['email']}")
        print(f"User data stored in session: {user_data}")
        
        return jsonify({
            "status": "success",
            "message": "Registration successful",
            "redirect_url": url_for("user_select"),
            "user": user_data
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return jsonify({"status": "error", "message": "Invalid JSON data"}), 400
    except Exception as e:
        print(f"Unexpected signup error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        if session.get("user") and session.get("user_role"):
            return redirect(url_for("user_select"))
        return render_template("auth/forgot_password.html")

    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get("email")
        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400
        # TODO: Hook into Supabase Auth password reset (magic link)
        return jsonify(
            {"status": "success", "message": "Password reset link sent successfully"}
        )
    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/user-select", methods=["GET", "POST"])
@require_auth
def user_select():
    if request.method == "GET":
        role = session.get("user_role")
        if role == "buyer":
            return redirect(url_for("buyer_feed"))
        if role == "seller":
            return redirect(url_for("seller_feed"))
        return render_template("auth/user_select.html")

    try:
        data = request.get_json(force=True, silent=True) or {}
        role = data.get("role")
        if role not in ["buyer", "seller"]:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Invalid role: {role}. Must be buyer or seller.",
                    }
                ),
                400,
            )
        session["user_role"] = role
        redirect_url = url_for("buyer_feed") if role == "buyer" else url_for("seller_feed")
        print(f"Role set: {role}, redirecting to {redirect_url}")
        return jsonify(
            {"status": "success", "message": f"Role set as {role}", "redirect_url": redirect_url}
        )
    except Exception as e:
        print(f"User select error: {e}")
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500

# ==================== DASHBOARD ====================

@app.route("/seller-feed")
@require_auth
def seller_feed():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    try:
        resp = (
            supabase.table("products")
            .select("*")
            .eq("seller_email", session["user"]["email"])
            .execute()
        )
        products = getattr(resp, "data", resp)  # supabase-py returns .data
        return render_template("feeds/seller_feed.html", products=products, session=session)
    except Exception as e:
        print(f"Seller feed error: {e}")
        return (
            f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Seller Feed</h1>
            <p>Error loading products: {e}</p>
            <a href="/user-select">Back to Role Selection</a>
        </div>
        """
        )

@app.route("/buyer-feed")
@require_auth
def buyer_feed():
    if session.get("user_role") != "buyer":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    try:
        resp = supabase.table("products").select("*").execute()
        products = getattr(resp, "data", resp)
        return render_template("feeds/buyer_feed.html", products=products, session=session)
    except Exception as e:
        print(f"Buyer feed error: {e}")
        return (
            f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Buyer Feed</h1>
            <p>Error loading products: {e}</p>
            <a href="/user-select">Back to Role Selection</a>
        </div>
        """
        )

# ==================== PROFILE ====================

@app.route("/buyer_profile", methods=["GET", "POST"])
@app.route("/buyer-profile", methods=["GET", "POST"])
@require_auth
def buyer_profile():
    if session.get("user_role") != "buyer":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    if request.method == "GET":
        try:
            return render_template("profiles/buyer_profile.html", session=session)
        except Exception as e:
            print(f"Buyer profile template error: {e}")
            return (
                """
            <div style="text-align:center; padding:50px; font-family:Arial;">
                <h1>Buyer Profile</h1>
                <p><strong>Template: buyer_profile.html not found</strong></p>
                <a href="/buyer-feed">Back to Dashboard</a>
            </div>
            """
            )

    try:
        data = request.get_json(force=True, silent=True) or {}
        # TODO: persist profile to DB if needed
        return jsonify({"status": "success", "message": "Profile updated successfully"})
    except Exception as e:
        print(f"Buyer profile update error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/seller_profile", methods=["GET", "POST"])
@app.route("/seller-profile", methods=["GET", "POST"])
@require_auth
def seller_profile():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    if request.method == "GET":
        try:
            return render_template("profiles/seller_profile.html", session=session)
        except Exception as e:
            print(f"Seller profile template error: {e}")
            return (
                """
            <div style="text-align:center; padding:50px; font-family:Arial;">
                <h1>Seller Profile</h1>
                <p><strong>Template: seller_profile.html not found</strong></p>
                <a href="/seller-feed">Back to Dashboard</a>
            </div>
            """
            )

    try:
        data = request.get_json(force=True, silent=True) or {}
        # TODO: persist profile to DB if needed
        return jsonify({"status": "success", "message": "Profile updated successfully"})
    except Exception as e:
        print(f"Seller profile update error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== PRODUCT UPLOAD ====================

@app.route("/upload-product", methods=["POST"])
@require_auth
def upload_product():
    if session.get("user_role") != "seller":
        return jsonify({"status": "error", "message": "Only sellers can upload products"}), 403

    if not session.get("user") or not session["user"].get("email"):
        return jsonify({"status": "error", "message": "User session data missing"}), 401

    access_token = session.get("access_token")
    if not access_token:
        return jsonify({"status": "error", "message": "No access token found"}), 401

    token_verification = verify_supabase_token(access_token)
    if token_verification["status"] != "success":
        return jsonify({"status": "error", "message": token_verification["message"]}), 401

    try:
        # Recreate client with bearer so RLS policies using auth() are applied
        supabase_auth = create_client(
            SUPABASE_URL, SUPABASE_ANON_KEY, options={"headers": {"Authorization": f"Bearer {access_token}"}}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to initialize Supabase client: {e}"}), 500

    # Form fields
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    quantity = (request.form.get("quantity") or "").strip()
    price = (request.form.get("price") or "").strip()
    category = (request.form.get("category") or "").strip()
    location = (request.form.get("location") or "").strip()

    missing = [
        k
        for k, v in {
            "title": title,
            "description": description,
            "quantity": quantity,
            "price": price,
            "category": category,
            "location": location,
        }.items()
        if not v
    ]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    image_file = request.files.get("images")
    image_urls: list[str] = []
    bucket = "products"

    try:
        if image_file and image_file.filename:
            # Use a namespaced path per user
            # If you need unique names, append datetime or uuid4
            safe_name = image_file.filename.replace("..", "/")
            path = f"{session['user']['id']}/{int(datetime.now(tz=IST).timestamp())}_{safe_name}"
            # supabase-py expects bytes or file-like under `file`, and target `path`
            file_bytes = image_file.read()
            upload_res = supabase_auth.storage.from_(bucket).upload(path=path, file=file_bytes)

            # Newer clients return dict-like with possible 'error' or raise; be defensive
            if getattr(upload_res, "error", None):
                return jsonify({"status": "error", "message": f"Storage upload failed: {upload_res.error.message}"}), 500

            public_url_resp = supabase_auth.storage.from_(bucket).get_public_url(path)
            # Handle both string and dict return shapes
            if isinstance(public_url_resp, str):
                image_urls = [public_url_resp]
            else:
                image_urls = [public_url_resp.get("publicURL") or public_url_resp.get("publicUrl") or ""]
        else:
            # Fallback placeholder
            image_urls = [f"https://via.placeholder.com/400x240?text={category or 'Product'}"]

        product_data = {
            "title": title,
            "description": description,
            "quantity": quantity,
            "price": price,
            "category": category,
            "location": location,
            "images": image_urls,
            "seller_email": session["user"]["email"],
        }

        response = supabase_auth.table("products").insert(product_data).execute()
        if getattr(response, "error", None):
            return jsonify({"status": "error", "message": f"DB insert failed: {response.error}"}), 500

        return jsonify(
            {
                "status": "success",
                "message": "Product uploaded successfully",
                "product": product_data,
                "redirect_url": url_for("seller_feed"),
            }
        )

    except Exception as e:
        print(f"Error in upload-product: {e}")
        return jsonify({"status": "error", "message": f"Upload failed: {e}"}), 500

@app.route("/post-upload")
@require_auth
def post_upload():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    try:
        return render_template("constants/seller/post_upload.html", session=session)
    except Exception as e:
        print(f"Post upload template error: {e}")
        return (
            """
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Post New Product</h1>
            <p>Upload your farm produce here!</p>
            <p><strong>Template: post_upload.html not found</strong></p>
            <a href="/seller-feed">Back to Dashboard</a>
        </div>
        """
        )

# ==================== PREDICTOR ====================

# Load once globally - Fixed duplicate loading
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model/final_model.pkl")
try:
    if model is None:  # Only load if not already loaded
        model = joblib.load(MODEL_PATH)
        print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

@app.route("/predictor", methods=["GET", "POST"])
@require_auth
def predictor():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    if request.method == "POST":
        try:
            if model is None:
                return jsonify({"status": "error", "message": "Model not loaded on server"}), 503

            # Grab inputs
            n = float(request.form.get("n", 0))
            p = float(request.form.get("p", 0))
            k = float(request.form.get("k", 0))
            humidity = float(request.form.get("humidity", 0))
            rainfall = float(request.form.get("rainfall", 0))

            # Validation
            inputs = [
                ("n", n, 0, 200),
                ("p", p, 0, 150),
                ("k", k, 0, 200),
                ("humidity", humidity, 0, 100),
                ("rainfall", rainfall, 0, 3000),
            ]
            for name, value, min_val, max_val in inputs:
                if value < min_val or value > max_val:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": f"{name} must be between {min_val} and {max_val}",
                            }
                        ),
                        400,
                    )

            # Predict
            features = np.array([[n, p, k, humidity, rainfall]], dtype=float)
            prediction = model.predict(features)[0]
            crop = str(prediction).upper()
            current_time = datetime.now(tz=IST).strftime("%I:%M %p IST on %B %d, %Y")

            return jsonify(
                {
                    "status": "success",
                    "crop_name": crop,
                    "n": n,
                    "p": p,
                    "k": k,
                    "humidity": humidity,
                    "rainfall": rainfall,
                    "timestamp": current_time,
                }
            )

        except Exception as e:
            print(f"Prediction error: {e}")
            return jsonify({"status": "error", "message": f"Error during prediction: {e}"}), 500

    # Render template
    try:
        return render_template("constants/seller/predictor.html", session=session)
    except Exception as e:
        print(f"Template rendering error: {e}")
        return (
            """
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Smart Crop Predictor</h1>
            <p>Predict the best crop for your conditions!</p>
            <p><strong>Template: constants/seller/predictor.html not found</strong></p>
            <a href="/seller-feed">Back to Seller Feed</a>
        </div>
        """
        )

# ==================== STATIC PAGES ====================

@app.route("/about")
@require_auth
def about():
    try:
        user_role = session.get("user_role")
        if not user_role:
            flash("Please select whether you are a buyer or seller.", "info")
            return redirect(url_for("user_select"))

        if user_role == "buyer":
            return render_template("constants/buyer/about_buy.html", session=session)
        elif user_role == "seller":
            return render_template("constants/seller/about_sell.html", session=session)
        else:
            flash("Invalid user role. Please select your role again.", "error")
            session.pop("user_role", None)
            return redirect(url_for("user_select"))

    except Exception as e:
        print(f"About route error: {e}")
        safe_role = (session.get("user_role") or "User").title()
        fallback_to = (session.get("user_role") or "buyer") + "-feed"
        return f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>About - {safe_role}</h1>
            <p>Learn more about Taaza Mandi.</p>
            <p><strong>Template error:</strong> {e}</p>
            <a href="/{fallback_to}">Back to Dashboard</a>
        </div>
        """

@app.route("/contact")
@require_auth
def contact():
    try:
        user_role = session.get("user_role")
        if not user_role:
            flash("Please select whether you are a buyer or seller.", "info")
            return redirect(url_for("user_select"))

        if user_role == "buyer":
            return render_template("constants/buyer/contact_buy.html", session=session)
        elif user_role == "seller":
            return render_template("constants/seller/contact_sell.html", session=session)
        else:
            flash("Invalid user role. Please select your role again.", "error")
            session.pop("user_role", None)
            return redirect(url_for("user_select"))

    except Exception as e:
        print(f"Contact route error: {e}")
        safe_role = (session.get("user_role") or "User").title()
        fallback_to = (session.get("user_role") or "buyer") + "-feed"
        return f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Contact - {safe_role}</h1>
            <p>Get in touch with us.</p>
            <p><strong>Template error:</strong> {e}</p>
            <a href="/{fallback_to}">Back to Dashboard</a>
        </div>
        """

@app.route("/market")
@require_auth
def market():
    try:
        user_role = session.get("user_role")
        if not user_role:
            flash("Please select whether you are a buyer or seller.", "info")
            return redirect(url_for("user_select"))

        if user_role == "buyer":
            return render_template("constants/buyer/market_buy.html", session=session)
        elif user_role == "seller":
            return render_template("constants/seller/market_sell.html", session=session)
        else:
            flash("Invalid user role. Please select your role again.", "error")
            session.pop("user_role", None)
            return redirect(url_for("user_select"))

    except Exception as e:
        print(f"Market route error: {e}")
        safe_role = (session.get("user_role") or "User").title()
        fallback_to = (session.get("user_role") or "buyer") + "-feed"
        return f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Market - {safe_role}</h1>
            <p>Explore the market for various products.</p>
            <p><strong>Template error:</strong> {e}</p>
            <a href="/{fallback_to}">Back to Dashboard</a>
        </div>
        """

@app.route("/equipment")
@require_auth
def equipment():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    try:
        return render_template("constants/seller/equipment.html", session=session)
    except Exception as e:
        print(f"Equipment route error: {e}")
        return f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Equipment</h1>
            <p>Explore equipment bazaar.</p>
            <p><strong>Template error:</strong> {e}</p>
            <a href="/seller-feed">Back to Dashboard</a>
        </div>
        """

@app.route("/schemes")
@require_auth
def schemes():
    if session.get("user_role") != "seller":
        flash("Please select your role.", "info")
        return redirect(url_for("user_select"))

    try:
        return render_template("constants/seller/schemes.html", session=session)
    except Exception as e:
        print(f"Schemes route error: {e}")
        return f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Government Schemes</h1>
            <p>Explore various government schemes for farmers.</p>
            <p><strong>Template error:</strong> {e}</p>
            <a href="/seller-feed">Back to Dashboard</a>
        </div>
        """

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))

# ==================== API ROUTES ====================

@app.route("/api/check-auth", methods=["POST"])  # keep POST if called via fetch
def check_auth():
    if session.get("user") and session.get("access_token"):
        token_verification = verify_supabase_token(session["access_token"])
        if token_verification["status"] != "success":
            session.clear()
            return jsonify(
                {"status": "error", "authenticated": False, "message": token_verification["message"]}
            )
        return jsonify(
            {
                "status": "success",
                "authenticated": True,
                "user": session["user"],
                "role": session.get("user_role"),
            }
        )
    else:
        return jsonify({"status": "error", "authenticated": False, "message": "No user session"})

@app.route("/api/update-profile", methods=["POST"])
@require_auth
def update_profile():
    try:
        data = request.get_json(force=True, silent=True) or {}
        user_role = session.get("user_role")
        if data.get("user_metadata"):
            session["user"]["user_metadata"] = data["user_metadata"]
        # Persist in DB if needed
        print(f"Profile updated: {data}")
        return jsonify(
            {"status": "success", "message": "Profile updated successfully", "data": data, "role": user_role}
        )
    except Exception as e:
        print(f"Update profile error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    try:
        return render_template("errors/404.html", session=session), 404
    except Exception:
        return (
            f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for doesn't exist.</p>
            <p><strong>Requested path:</strong> {request.path}</p>
            <a href="/">Back to Home</a>
        </div>
        """,
            404,
        )

@app.errorhandler(500)
def internal_error(error):
    try:
        return render_template("errors/500.html", session=session), 500
    except Exception:
        return (
            """
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>500 - Server Error</h1>
            <p>Something went wrong. Please try again later.</p>
            <a href="/">Back to Home</a>
        </div>
        """,
            500,
        )

# ==================== RUN ====================

if __name__ == "__main__":
    print("Starting TAAZA MANDI Flask App...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"   {rule} -> {rule.endpoint}")
    app.run(debug=True)

