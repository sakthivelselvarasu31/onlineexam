import os
from flask import Flask, render_template, session, redirect, url_for
from config import Config
from models.user import db, User
import models.proctor  # Ensure all proctoring models are registered with SQLAlchemy
from routes.auth import auth
from routes.exam import exam
from routes.proctor import proctor_bp

# Create Flask App
app = Flask(__name__)

# Load Configuration
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize Database
db.init_app(app)

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(exam)
app.register_blueprint(proctor_bp)



# --------------------------------
# Home Page
# --------------------------------
@app.route("/")
def home():
    return redirect(url_for("auth.login"))


# --------------------------------
# Student Dashboard
# --------------------------------
@app.route("/dashboard")
def dashboard():

    # Check whether student is logged in
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Get student details from database
    user = User.query.get(session["user_id"])

    if user is None:
        session.clear()
        return redirect(url_for("auth.login"))

    photo_url = None
    if user.photo:
        normalized_photo = user.photo.replace('\\', '/')
        photo_url = url_for("static", filename=normalized_photo)

    return render_template(
        "dashboard.html",
        name=user.name,
        email=user.email,
        photo=user.photo,
        photo_url=photo_url
    )


# --------------------------------
# Logout
# --------------------------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("auth.login"))


# --------------------------------
# Create Database
# --------------------------------
with app.app_context():
    db.create_all()


# --------------------------------
# Run Application
# --------------------------------
if __name__ == "__main__":
    app.run(debug=True)