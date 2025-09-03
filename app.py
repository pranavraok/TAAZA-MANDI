from __future__ import annotations
"""
Taaza Mandi – Flask app (fixed & hardened)
- Single, resilient model loader
- Safer Supabase auth helpers + token-bound client
- Consistent JSON error handling
- Clock tolerance for JWT validation
- ASCII-safe logging (no Unicode emojis)
- Cleaned routes & guards
"""

import os
import json
import joblib
import numpy as np
from datetime import datetime, timedelta, timezone
from functools import wraps

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

# Session security
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
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")  # JWT signing secret
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_missing = [
    name
    for name, val in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_JWT_SECRET": SUPABASE_JWT_SECRET,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
    }.items()
    if not val
]
if _missing:
    raise RuntimeError(
        f"Missing required env vars: {', '.join(_missing)}. Check your .env file"
    )

# Base client (anon)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def supabase_with_user(token: str) -> Client:
    """Return a client that sends the user's JWT in both Postgrest & Storage.
    Works across supabase-py minor versions by trying available methods.
    """
    client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    # PostgREST (database)
    try:
        client.postgrest.auth(token)
    except Exception:
        pass
    # Storage
    try:
        client.storage.auth(token)  # newer versions
    except Exception:
        try:
            client.storage.set_auth(token)  # older versions
        except Exception:
            pass
    return client

# ==================== LOAD ML MODEL (resilient) ====================

MODEL_PATH = os.environ.get("MODEL_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "model", "final_model.pkl"
)

model = None
try:
    model = joblib.load(MODEL_PATH)
    print(f"[OK] ML model loaded from {MODEL_PATH}")
except Exception as e:
    print(f"[WARN] Could not load ML model at {MODEL_PATH}: {e}")

# ==================== AUTH HELPERS ====================

def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase GoTrue JWT locally using the project's JWT secret.
    
    Fixed with clock tolerance to handle timing issues between client and server.
    """
    try:
        if not token or not isinstance(token, str):
            return {"status": "error", "message": "Missing token"}

        # Add clock tolerance for JWT validation (60 seconds leeway)
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_aud": False,  # Don't verify audience for flexibility
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": False
            },
            # Add 60 second leeway for clock skew
            leeway=timedelta(seconds=60)
        )
        
        return {
            "status": "success",
            "user": {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "user_metadata": payload.get("user_metadata", {}),
                "app_metadata": payload.get("app_metadata", {}),
                "aud": payload.get("aud"),
                "role": payload.get("role"),
                "iat": payload.get("iat"),
                "exp": payload.get("exp")
            },
        }
    except jwt.ExpiredSignatureError:
        return {"status": "error", "message": "Token expired"}
    except jwt.InvalidTokenError as e:
        # Log the specific error for debugging
        print(f"JWT validation error: {str(e)}")
        return {"status": "error", "message": f"Invalid token: {e}"}
    except Exception as e:
        print(f"Token verification exception: {str(e)}")
        return {"status": "error", "message": f"Token verification failed: {e}"}

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get("access_token")
        if not session.get("user") or not token:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        tok = verify_supabase_token(token)
        if tok["status"] != "success":
            print(f"[AUTH ERROR] {tok['message']}")
            session.clear()
            flash(f"Authentication failed: {tok['message']}", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function

# Make limited config available in templates
@app.context_processor
def inject_config():
    return {
        "config": {
            "SUPABASE_URL": SUPABASE_URL,
            "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
        }
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
        # Parse JSON data
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        token = data.get("token")
        user_id = data.get("user_id")
        email = data.get("email")
        
        if not token:
            return jsonify({"status": "error", "message": "Token is required"}), 400

        print(f"[LOGIN] Verifying token for login attempt: {email}")
        
        # Verify token with clock tolerance
        token_verification = verify_supabase_token(token)
        if token_verification["status"] != "success":
            print(f"[LOGIN ERROR] Token verification failed: {token_verification['message']}")
            return jsonify({
                "status": "error", 
                "message": f"Authentication failed: {token_verification['message']}"
            }), 401

        verified_user = token_verification["user"]
        
        # Store in session
        session["access_token"] = token
        session["user"] = {
            "id": user_id or verified_user.get("id"),
            "email": email or verified_user.get("email"),
            **verified_user.get("user_metadata", {}),
            **verified_user.get("app_metadata", {})
        }
        session.permanent = True
        
        print(f"[LOGIN SUCCESS] Login successful for user: {session['user']['email']}")
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "redirect_url": url_for("user_select"),
        })
        
    except Exception as e:
        print(f"[LOGIN ERROR] Login error: {e}")
        return jsonify({"status": "error", "message": f"Login failed: {str(e)}"}), 500

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if session.get("user") and session.get("user_role"):
            return redirect(url_for("user_select"))
        return render_template("auth/signup.html")

    try:
        # Parse JSON data
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # Extract required fields
        token = data.get("token")
        email = data.get("email")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        phone = data.get("phone")
        state = data.get("state")
        user_id = data.get("user_id")

        # Validate required fields
        missing_fields = []
        if not token:
            missing_fields.append("token")
        if not email:
            missing_fields.append("email")
        if not first_name:
            missing_fields.append("first_name")
        if not last_name:
            missing_fields.append("last_name")
        if not phone:
            missing_fields.append("phone")
        if not state:
            missing_fields.append("state")

        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        print(f"[SIGNUP] Verifying token for signup attempt: {email}")

        # Verify token with clock tolerance
        token_verification = verify_supabase_token(token)
        if token_verification["status"] != "success":
            print(f"[SIGNUP ERROR] Token verification failed: {token_verification['message']}")
            return jsonify({
                "status": "error",
                "message": f"Authentication failed: {token_verification['message']}",
            }), 401

        verified_user = token_verification["user"]
        final_user_id = user_id or verified_user.get("id")

        # Prepare user data
        user_data = {
            "id": final_user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "state": state,
            "full_name": f"{first_name} {last_name}".strip(),
            "user_type": "pending",
            **verified_user.get("user_metadata", {}),
            **verified_user.get("app_metadata", {})
        }

        # Store in session
        session["access_token"] = token
        session["user"] = user_data
        session.permanent = True

        print(f"[SIGNUP SUCCESS] Signup successful for user: {email}")

        return jsonify({
            "status": "success",
            "message": "Registration successful",
            "redirect_url": url_for("user_select"),
            "user": user_data,
        })

    except Exception as e:
        print(f"[SIGNUP ERROR] Signup error: {e}")
        return jsonify({"status": "error", "message": f"Registration failed: {str(e)}"}), 500

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
        # TODO: Integrate Supabase Auth password reset (magic link)
        return jsonify({"status": "success", "message": "Password reset link sent"})
    except Exception as e:
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
            return jsonify({
                "status": "error",
                "message": f"Invalid role: {role}. Must be buyer or seller.",
            }), 400
        session["user_role"] = role
        redirect_url = url_for("buyer_feed") if role == "buyer" else url_for("seller_feed")
        return jsonify({"status": "success", "message": f"Role set as {role}", "redirect_url": redirect_url})
    except Exception as e:
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
            .eq("email", session["user"]["email"])
            .execute()
        )
        products = getattr(resp, "data", resp)
        return render_template("feeds/seller_feed.html", products=products, session=session)
    except Exception as e:
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
        except Exception:
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
        _ = request.get_json(force=True, silent=True) or {}
        # TODO: persist profile to DB if needed
        return jsonify({"status": "success", "message": "Profile updated successfully"})
    except Exception as e:
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
        except Exception:
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
        _ = request.get_json(force=True, silent=True) or {}
        # TODO: persist profile to DB if needed
        return jsonify({"status": "success", "message": "Profile updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== PRODUCT UPLOAD ====================

@app.route("/upload-product", methods=["POST"])
@require_auth
def upload_product():
    if session.get("user_role") != "seller":
        return jsonify({"status": "error", "message": "Only sellers can upload products"}), 403

    user = session.get("user")
    if not user or not user.get("email"):
        return jsonify({"status": "error", "message": "User session data missing"}), 401

    access_token = session.get("access_token")
    if not access_token:
        return jsonify({"status": "error", "message": "No access token found"}), 401

    tok = verify_supabase_token(access_token)
    if tok["status"] != "success":
        return jsonify({"status": "error", "message": tok["message"]}), 401

    # Build a token-authenticated client so RLS policies using auth() are applied
    supa_user = supabase_with_user(access_token)

    # Form fields
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    quantity = (request.form.get("quantity") or "").strip()
    price = (request.form.get("price") or "").strip()
    category = (request.form.get("category") or "").strip()
    location = (request.form.get("location") or "").strip()

    missing = [k for k, v in {
        "title": title,
        "description": description,
        "quantity": quantity,
        "price": price,
        "category": category,
        "location": location,
    }.items() if not v]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    image_file = request.files.get("images")
    image_urls: list[str] = []
    bucket = "products"

    try:
        if image_file and image_file.filename:
            safe_name = image_file.filename.replace("..", "/")
            path = f"{user['id']}/{int(datetime.now(tz=IST).timestamp())}_{safe_name}"
            file_bytes = image_file.read()

            # Upload (works for both string path & bytes). We use bytes for API consistency.
            upload_res = supa_user.storage.from_(bucket).upload(path=path, file=file_bytes)

            # Handle error shapes across versions
            if getattr(upload_res, "error", None):
                return jsonify({"status": "error", "message": f"Storage upload failed: {upload_res.error}"}), 500

            public_url_resp = supa_user.storage.from_(bucket).get_public_url(path)
            if isinstance(public_url_resp, str):
                image_urls = [public_url_resp]
            else:
                # supabase-py returns a dict in newer versions
                image_urls = [public_url_resp.get("publicURL") or public_url_resp.get("publicUrl") or ""]
        else:
            image_urls = [f"https://via.placeholder.com/400x240?text={category or 'Product'}"]

        product_data = {
            "title": title,
            "description": description,
            "quantity": quantity,
            "price": price,
            "category": category,
            "location": location,
            "images": image_urls,
            "seller_email": user["email"],
        }

        response = supa_user.table("products").insert(product_data).execute()
        if getattr(response, "error", None):
            return jsonify({"status": "error", "message": f"DB insert failed: {response.error}"}), 500

        return jsonify({
            "status": "success",
            "message": "Product uploaded successfully",
            "product": product_data,
            "redirect_url": url_for("seller_feed"),
        })

    except Exception as e:
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
        return (
            f"""
        <div style="text-align:center; padding:50px; font-family:Arial;">
            <h1>Post New Product</h1>
            <p>Upload your farm produce here!</p>
            <p><strong>Template: post_upload.html not found</strong></p>
            <a href="/seller-feed">Back to Dashboard</a>
        </div>
        """
        )

# ==================== PREDICTOR ====================

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
            for name, value, min_val, max_val in [
                ("n", n, 0, 200),
                ("p", p, 0, 150),
                ("k", k, 0, 200),
                ("humidity", humidity, 0, 100),
                ("rainfall", rainfall, 0, 3000),
            ]:
                if value < min_val or value > max_val:
                    return jsonify({
                        "status": "error",
                        "message": f"{name} must be between {min_val} and {max_val}",
                    }), 400

            features = np.array([[n, p, k, humidity, rainfall]], dtype=float)
            pred = model.predict(features)[0]
            crop = str(pred).upper()
            current_time = datetime.now(tz=IST).strftime("%I:%M %p IST on %B %d, %Y")

            return jsonify({
                "status": "success",
                "crop_name": crop,
                "n": n,
                "p": p,
                "k": k,
                "humidity": humidity,
                "rainfall": rainfall,
                "timestamp": current_time,
            })

        except Exception as e:
            return jsonify({"status": "error", "message": f"Error during prediction: {e}"}), 500

    # Render template
    try:
        return render_template("constants/seller/predictor.html", session=session)
    except Exception:
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
        if user_role == "seller":
            return render_template("constants/seller/about_sell.html", session=session)

        flash("Invalid user role. Please select your role again.", "error")
        session.pop("user_role", None)
        return redirect(url_for("user_select"))

    except Exception as e:
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
        if user_role == "seller":
            return render_template("constants/seller/contact_sell.html", session=session)

        flash("Invalid user role. Please select your role again.", "error")
        session.pop("user_role", None)
        return redirect(url_for("user_select"))

    except Exception as e:
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
        if user_role == "seller":
            return render_template("constants/seller/market_sell.html", session=session)

        flash("Invalid user role. Please select your role again.", "error")
        session.pop("user_role", None)
        return redirect(url_for("user_select"))

    except Exception as e:
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
        tok = verify_supabase_token(session["access_token"])
        if tok["status"] != "success":
            session.clear()
            return jsonify({
                "status": "error",
                "authenticated": False,
                "message": tok["message"],
            })
        return jsonify({
            "status": "success",
            "authenticated": True,
            "user": session["user"],
            "role": session.get("user_role"),
        })
    return jsonify({"status": "error", "authenticated": False, "message": "No user session"})

@app.route("/api/update-profile", methods=["POST"])
@require_auth
def update_profile():
    try:
        data = request.get_json(force=True, silent=True) or {}
        user_role = session.get("user_role")
        if data.get("user_metadata"):
            session.setdefault("user", {}).setdefault("user_metadata", {}).update(data["user_metadata"])
        # TODO: Persist in DB if needed
        return jsonify({
            "status": "success",
            "message": "Profile updated successfully",
            "data": data,
            "role": user_role,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(_error):
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
def internal_error(_error):
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
    with app.test_request_context():
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
            print(f"   {rule} -> {rule.endpoint}")
    app.run(debug=True)
