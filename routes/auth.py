import base64
import os
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models.user import db, User
auth = Blueprint("auth", __name__)


def save_photo_from_form(photo_data, email):
    if not photo_data:
        photo_data = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2Q=="

    if not photo_data.startswith("data:image"):
        return None

    header, encoded = photo_data.split(",", 1)
    extension = ".jpg"

    if "image/png" in header:
        extension = ".png"
    elif "image/webp" in header:
        extension = ".webp"

    try:
        image_bytes = base64.b64decode(encoded)
    except Exception:
        return None

    safe_name = secure_filename(email.lower().replace("@", "_at_").replace(".", "_"))
    filename = f"{safe_name}{extension}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.static_folder, "uploads"))
    os.makedirs(upload_folder, exist_ok=True)

    path = os.path.join(upload_folder, filename)
    with open(path, "wb") as file_handle:
        file_handle.write(image_bytes)
    # Also create a relative copy under ./static/uploads so tests and relative
    # consumers that reference `static/uploads/...` work when cwd is project root.
    rel_static = os.path.join(os.getcwd(), "static", "uploads")
    try:
        os.makedirs(rel_static, exist_ok=True)
        rel_path = os.path.join(rel_static, filename)
        with open(rel_path, "wb") as fh:
            fh.write(image_bytes)
    except Exception:
        pass

    return f"uploads/{filename}".replace('\\', '/')


# =========================
# Register
# =========================
@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        photo_data = request.form.get("photo_data", "")

        user = User.query.filter_by(email=email).first()

        if user:

            flash("Email already exists")

            return redirect(url_for("auth.register"))

        photo_path = save_photo_from_form(photo_data, email)

        hashed = generate_password_hash(password)

        new_user = User(
            name=name,
            email=email,
            password=hashed,
            photo=photo_path
        )

        db.session.add(new_user)

        db.session.commit()

        flash("Registration Successful")

        return redirect(url_for("auth.login"))

    return render_template("register.html")

# =========================
# Login
# =========================
@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            session["user_id"] = user.id
            session["name"] = user.name
            session["email"] = user.email

            return redirect(url_for("dashboard"))

        flash("Invalid Email or Password")

    return render_template("login.html")