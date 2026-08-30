from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response,
    session,
    flash,
    jsonify,
)

from datetime import datetime, timedelta

import plotly.graph_objects as go
import pytz
import io
import csv
import logging
import os

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect


# ============================================================
# CONFIGURATION
# ============================================================

logging.basicConfig(level=logging.INFO)

IST = pytz.timezone("Asia/Kolkata")

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.environ.get(
    "DB_HOST",
    "c89hfa8mgg235.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com"
)

DB_PORT = os.environ.get(
    "DB_PORT",
    "5432"
)

DB_NAME = os.environ.get(
    "DB_NAME",
    "d2hc5emqstdlu5"
)

DB_USER = os.environ.get(
    "DB_USER",
    "u5no93tf65ksha"
)

DB_PASSWORD = os.environ.get(
    "DB_PASSWORD",
    "p86edb19173b56140c6f59850879a1341955fa911bfcaf2f17f8ecf207bc42dad"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

# ============================================================
# HEROKU / POSTGRES DATABASE URL
# ============================================================

if DATABASE_URL:

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

else:

    DATABASE_URL = (
        f"postgresql+psycopg2://"
        f"{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )


app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
}

db = SQLAlchemy(app)


# ============================================================
# USER MODEL
# ============================================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        nullable=False,
        index=True
    )

    location = db.Column(
        db.String(150),
        nullable=False,
        index=True
    )

    phone_number = db.Column(
        db.String(50)
    )

    email = db.Column(
        db.String(150)
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    def set_password(self, password):

        self.password = generate_password_hash(password)

    def check_password(self, password):

        if self.password and self.password.startswith(
            (
                "pbkdf2:",
                "scrypt:",
                "argon2:"
            )
        ):

            return check_password_hash(
                self.password,
                password
            )

        return self.password == password


# ============================================================
# VEHICLE MODEL
# ============================================================

class Vehicle(db.Model):

    __tablename__ = "vehicles"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ========================================================
    # BASIC INFORMATION
    # ========================================================

    reg_no = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )

    type = db.Column(
        db.String(100),
        nullable=False
    )

    transporter = db.Column(
        db.String(150)
    )

    supplier = db.Column(
        db.String(150)
    )

    # ========================================================
    # GENERAL / UNLOAD LR
    # ========================================================

    lr_number = db.Column(
        db.String(150)
    )

    contact_no = db.Column(
        db.String(100)
    )

    load_unload = db.Column(
        db.String(50)
    )

    remarks = db.Column(
        db.Text
    )

    # ========================================================
    # STATUS
    # ========================================================

    status = db.Column(
        db.String(20),
        default="IN",
        nullable=False,
        index=True
    )

    check_in = db.Column(
        db.String(30),
        index=True
    )

    check_out = db.Column(
        db.String(30)
    )

    # ========================================================
    # DRIVER
    # ========================================================

    driver_name = db.Column(
        db.String(150)
    )

    driver_mobile = db.Column(
        db.String(100)
    )

    # ========================================================
    # GENERAL / UNLOAD INVOICE
    # ========================================================

    invoice_number = db.Column(
        db.String(150)
    )

    invoice_qty = db.Column(
        db.String(100)
    )

    number_of_boxes = db.Column(
        db.String(100)
    )

    # ========================================================
    # UNLOAD SUPERVISOR VERIFIED VALUES
    # ========================================================

    supervisor_invoice_qty = db.Column(
        db.String(100)
    )

    supervisor_number_of_boxes = db.Column(
        db.String(100)
    )

    # ========================================================
    # UNLOAD DAMAGED VALUES
    # ========================================================

    supervisor_damaged_qty = db.Column(
        db.String(100)
    )

    supervisor_damaged_boxes = db.Column(
        db.String(100)
    )

    # ========================================================
    # DOCK
    # ========================================================

    dock_number = db.Column(
        db.String(20)
    )

    # ========================================================
    # FLOW
    # ========================================================

    flow_type = db.Column(
        db.String(30),
        default="INBOUND",
        nullable=False,
        index=True
    )

    # ========================================================
    # SECURITY CHECK-IN
    # ========================================================

    security_checkin_by = db.Column(
        db.String(100)
    )

    # ========================================================
    # SUPERVISOR UNLOAD
    # ========================================================

    supervisor_unload_by = db.Column(
        db.String(100)
    )

    unload_time = db.Column(
        db.String(30)
    )

    unload_remarks = db.Column(
        db.Text
    )

    # ========================================================
    # SUPERVISOR LOAD
    #
    # IMPORTANT:
    # LOAD vehicle ke liye ye fields Supervisor fill karega.
    # Security Gate Check-In par ye blank rahenge.
    # ========================================================

    load_lr_number = db.Column(
        db.String(150)
    )

    load_invoice_number = db.Column(
        db.String(150)
    )

    load_invoice_qty = db.Column(
        db.String(100)
    )

    load_number_of_boxes = db.Column(
        db.String(100)
    )

    actual_qty = db.Column(
        db.String(100)
    )

    actual_boxes = db.Column(
        db.String(100)
    )

    supervisor_load_by = db.Column(
        db.String(100)
    )

    load_completed_time = db.Column(
        db.String(30)
    )

    load_remarks = db.Column(
        db.Text
    )

    # ========================================================
    # SECURITY CHECKOUT VERIFICATION FOR LOAD
    # ========================================================

    security_checkout_invoice_qty = db.Column(
        db.String(100)
    )

    security_checkout_number_of_boxes = db.Column(
        db.String(100)
    )

    # ========================================================
    # DIRECT OUTBOUND WORKFLOW
    # ========================================================

    outbound_supervisor_by = db.Column(
        db.String(100)
    )

    outbound_entry_time = db.Column(
        db.String(30)
    )

    outbound_remarks = db.Column(
        db.Text
    )

    # ========================================================
    # CHECKOUT SECURITY
    # ========================================================

    checkout_by = db.Column(
        db.String(100)
    )

    # ========================================================
    # LOCATION
    # ========================================================

    location = db.Column(
        db.String(150),
        nullable=False,
        index=True
    )


# ============================================================
# DATABASE SCHEMA PATCH
# ============================================================

def patch_database_schema():

    try:

        with app.app_context():

            inspector = inspect(db.engine)

            # =================================================
            # USERS
            # =================================================

            if inspector.has_table("users"):

                user_columns = {
                    column["name"]
                    for column in inspector.get_columns("users")
                }

                user_missing_columns = {

                    "phone_number":
                        "VARCHAR(50)",

                    "email":
                        "VARCHAR(150)",
                }

                for column_name, column_type in user_missing_columns.items():

                    if column_name not in user_columns:

                        db.session.execute(
                            text(
                                f"""
                                ALTER TABLE users
                                ADD COLUMN IF NOT EXISTS
                                {column_name}
                                {column_type}
                                """
                            )
                        )

                        logging.info(
                            "Added users.%s",
                            column_name
                        )

            # =================================================
            # VEHICLES
            # =================================================

            if inspector.has_table("vehicles"):

                vehicle_columns = {
                    column["name"]
                    for column in inspector.get_columns("vehicles")
                }

                vehicle_missing_columns = {

                    "supervisor_damaged_qty":
                        "VARCHAR(100)",

                    "supervisor_damaged_boxes":
                        "VARCHAR(100)",

                    "load_lr_number":
                        "VARCHAR(150)",

                    "load_invoice_number":
                        "VARCHAR(150)",

                    "load_invoice_qty":
                        "VARCHAR(100)",

                    "load_number_of_boxes":
                        "VARCHAR(100)",

                    "actual_qty":
                        "VARCHAR(100)",

                    "actual_boxes":
                        "VARCHAR(100)",

                    "supervisor_load_by":
                        "VARCHAR(100)",

                    "load_completed_time":
                        "VARCHAR(30)",

                    "load_remarks":
                        "TEXT",

                    "security_checkout_invoice_qty":
                        "VARCHAR(100)",

                    "security_checkout_number_of_boxes":
                        "VARCHAR(100)",
                }

                for column_name, column_type in vehicle_missing_columns.items():

                    if column_name not in vehicle_columns:

                        db.session.execute(
                            text(
                                f"""
                                ALTER TABLE vehicles
                                ADD COLUMN IF NOT EXISTS
                                {column_name}
                                {column_type}
                                """
                            )
                        )

                        logging.info(
                            "Added vehicles.%s",
                            column_name
                        )

            db.session.commit()

            logging.info(
                "Database schema patch completed."
            )

    except Exception:

        db.session.rollback()

        logging.exception(
            "Database schema patch failed."
        )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():

    try:

        with app.app_context():

            db.create_all()

            patch_database_schema()

            admin = User.query.filter_by(
                username="admin"
            ).first()

            if admin is None:

                admin = User(
                    username="admin",
                    role="admin",
                    location="ALL",
                    is_active=True
                )

                admin.set_password(
                    "admin123"
                )

                db.session.add(admin)

                db.session.commit()

                logging.warning(
                    "Default admin created. "
                    "Please change the password immediately."
                )

            logging.info(
                "Database initialized."
            )

    except Exception:

        logging.exception(
            "Database initialization failed."
        )


# ============================================================
# HELPERS
# ============================================================

def current_time():

    return datetime.now(
        IST
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def current_role():

    return session.get("role")


def current_location():

    return session.get("location")


def current_user():

    return session.get("user")


def require_login():

    return "user" in session


def is_admin():

    return current_role() == "admin"


def is_security():

    return current_role() in (
        "security",
        "lifelong"
    )


def is_supervisor():

    return current_role() == "supervisor"


# ============================================================
# LOCATION ACCESS
# ============================================================

def can_access_vehicle(vehicle):

    if vehicle is None:

        return False

    if is_admin():

        return True

    user_location = current_location()

    if not user_location:

        return False

    if not vehicle.location:

        return False

    return (
        vehicle.location.strip().lower()
        ==
        user_location.strip().lower()
    )


def get_vehicle_for_current_user(vid):

    vehicle = db.session.get(
        Vehicle,
        vid
    )

    if vehicle is None:

        return None

    if not can_access_vehicle(vehicle):

        return None

    return vehicle


# ============================================================
# DOCK VALIDATION
# ============================================================

def validate_dock(dock_number):

    if not dock_number:

        return True

    try:

        dock = int(dock_number)

        return 1 <= dock <= 16

    except (ValueError, TypeError):

        return False


# ============================================================
# SUMMARY
# ============================================================

def get_summary(vehicles):

    total_in = 0

    total_out = 0

    total_status = len(
        vehicles
    )

    over_48hrs = 0

    now = datetime.now(
        IST
    ).replace(
        tzinfo=None
    )

    for vehicle in vehicles:

        if vehicle.status == "IN":

            total_in += 1

        elif vehicle.status == "OUT":

            total_out += 1

        if vehicle.check_in:

            try:

                check_in_time = datetime.strptime(
                    vehicle.check_in,
                    "%Y-%m-%d %H:%M:%S"
                )

                if vehicle.check_out:

                    check_out_time = datetime.strptime(
                        vehicle.check_out,
                        "%Y-%m-%d %H:%M:%S"
                    )

                else:

                    check_out_time = now

                diff = (
                    check_out_time
                    - check_in_time
                )

                if diff > timedelta(hours=48):

                    over_48hrs += 1

            except ValueError:

                logging.warning(
                    "Invalid check-in date for vehicle %s",
                    vehicle.id
                )

    return (
        total_in,
        total_out,
        total_status,
        over_48hrs
    )


# ============================================================
# CHARTS
# ============================================================

def generate_charts(
    daily_in,
    daily_out
):

    all_days = sorted(
        set(daily_in.keys())
        |
        set(daily_out.keys())
    )

    in_counts = [
        daily_in.get(
            day,
            0
        )
        for day in all_days
    ]

    out_counts = [
        daily_out.get(
            day,
            0
        )
        for day in all_days
    ]

    # ========================================================
    # CHECK-IN
    # ========================================================

    fig_in = go.Figure()

    fig_in.add_trace(
        go.Scatter(
            x=all_days,
            y=in_counts,
            mode="lines+markers",
            marker=dict(
                color="green",
                size=8
            ),
            line=dict(
                width=2
            ),
            hovertemplate=(
                "Date: %{x}<br>"
                "Check-Ins: %{y}"
                "<extra></extra>"
            )
        )
    )

    fig_in.update_layout(
        title="Daily Check-Ins",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
        margin=dict(
            l=40,
            r=40,
            t=40,
            b=80
        )
    )

    chart_in = fig_in.to_html(
        full_html=False
    )

    # ========================================================
    # CHECK-OUT
    # ========================================================

    fig_out = go.Figure()

    fig_out.add_trace(
        go.Scatter(
            x=all_days,
            y=out_counts,
            mode="lines+markers",
            marker=dict(
                color="red",
                size=8
            ),
            line=dict(
                width=2
            ),
            hovertemplate=(
                "Date: %{x}<br>"
                "Check-Outs: %{y}"
                "<extra></extra>"
            )
        )
    )

    fig_out.update_layout(
        title="Daily Check-Outs",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
        margin=dict(
            l=40,
            r=40,
            t=40,
            b=80
        )
    )

    chart_out = fig_out.to_html(
        full_html=False
    )

    return (
        chart_in,
        chart_out
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if require_login():

        return redirect(
            url_for("index")
        )

    return redirect(
        url_for("login")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        userid = request.form.get(
            "userid",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        try:

            user = User.query.filter_by(
                username=userid,
                is_active=True
            ).first()

            if user and user.check_password(password):

                session["user"] = user.username

                session["role"] = user.role

                session["location"] = user.location

                # Upgrade old plain-text password

                if not user.password.startswith(
                    (
                        "pbkdf2:",
                        "scrypt:",
                        "argon2:"
                    )
                ):

                    user.set_password(
                        password
                    )

                    db.session.commit()

                return redirect(
                    url_for("index")
                )

            flash(
                "Invalid credentials!",
                "danger"
            )

        except Exception:

            db.session.rollback()

            logging.exception(
                "Login error"
            )

            flash(
                "Database error during login.",
                "danger"
            )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# ADMIN USERS
# ============================================================

@app.route(
    "/admin/users",
    methods=["GET", "POST"]
)
def admin_users():

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_admin():

        flash(
            "Only Admin can manage users.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    # ============================================================
    # POST
    # CREATE / UPDATE USER
    # ============================================================

    if request.method == "POST":

        action = request.form.get(
            "action",
            ""
        ).strip()

        # ========================================================
        # UPDATE EXISTING USER
        # ========================================================

        if action == "update_user":

            user_id = request.form.get(
                "user_id",
                "",
                type=int
            )

            user = db.session.get(
                User,
                user_id
            )

            if user is None:

                flash(
                    "User not found.",
                    "danger"
                )

                return redirect(
                    url_for("admin_users")
                )

            role = request.form.get(
                "role",
                ""
            ).strip().lower()

            location = request.form.get(
                "location",
                ""
            ).strip()

            phone_number = request.form.get(
                "phone_number",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            allowed_roles = {
                "admin",
                "supervisor",
                "security",
                "lifelong",
                "wm"
            }

            # ----------------------------------------------------
            # VALIDATION
            # ----------------------------------------------------

            if not role or not location:

                flash(
                    "Role and location are required.",
                    "danger"
                )

                return redirect(
                    url_for("admin_users")
                )

            if role not in allowed_roles:

                flash(
                    "Invalid role.",
                    "danger"
                )

                return redirect(
                    url_for("admin_users")
                )

            # ----------------------------------------------------
            # UPDATE USER DETAILS
            # ----------------------------------------------------

            user.role = role

            user.location = location

            user.phone_number = phone_number

            user.email = email

            # ----------------------------------------------------
            # PASSWORD
            # Only change password if admin entered a new one
            # ----------------------------------------------------

            if password.strip():

                user.set_password(
                    password
                )

            db.session.commit()

            flash(
                "User updated successfully.",
                "success"
            )

            return redirect(
                url_for("admin_users")
            )

        # ========================================================
        # CREATE NEW USER
        # ========================================================

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role",
            ""
        ).strip().lower()

        location = request.form.get(
            "location",
            ""
        ).strip()

        phone_number = request.form.get(
            "phone_number",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        allowed_roles = {
            "admin",
            "supervisor",
            "security",
            "lifelong",
            "wm"
        }

        if not all([
            username,
            password,
            role,
            location
        ]):

            flash(
                "Username, password, role and location are required.",
                "danger"
            )

            return redirect(
                url_for("admin_users")
            )

        if role not in allowed_roles:

            flash(
                "Invalid role.",
                "danger"
            )

            return redirect(
                url_for("admin_users")
            )

        if User.query.filter_by(
            username=username
        ).first():

            flash(
                "Username already exists.",
                "danger"
            )

            return redirect(
                url_for("admin_users")
            )

        user = User(
            username=username,
            role=role,
            location=location,
            phone_number=phone_number,
            email=email,
            is_active=True
        )

        user.set_password(
            password
        )

        db.session.add(user)

        db.session.commit()

        flash(
            "User created successfully.",
            "success"
        )

        return redirect(
            url_for("admin_users")
        )

    # ============================================================
    # GET USERS
    # ============================================================

    users = User.query.order_by(
        User.id.asc()
    ).all()

    return render_template(
        "admin_users.html",
        users=users,
        user=current_user(),
        role=current_role(),
        location=current_location()
    )


# ============================================================
# TOGGLE USER
# ============================================================

@app.route(
    "/admin/users/toggle/<int:uid>"
)
def toggle_user(uid):

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_admin():

        flash(
            "Only Admin can manage users.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    user = db.session.get(
        User,
        uid
    )

    if user is None:

        flash(
            "User not found.",
            "danger"
        )

        return redirect(
            url_for("admin_users")
        )

    if user.username == current_user():

        flash(
            "Current admin cannot be disabled.",
            "warning"
        )

        return redirect(
            url_for("admin_users")
        )

    user.is_active = not user.is_active

    db.session.commit()

    flash(
        f"User {'enabled' if user.is_active else 'disabled'} successfully.",
        "success"
    )

    return redirect(
        url_for("admin_users")
    )


# ============================================================
# MAIN DASHBOARD
# ============================================================

@app.route("/index")
def index():

    if not require_login():

        return redirect(
            url_for("login")
        )

    reg_no = request.args.get(
        "reg",
        ""
    ).strip()

    transporter = request.args.get(
        "transporter",
        ""
    ).strip()

    supplier = request.args.get(
        "supplier",
        ""
    ).strip()

    load_unload = request.args.get(
        "load_unload",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    from_date_str = request.args.get(
        "from_date",
        ""
    )

    to_date_str = request.args.get(
        "to_date",
        ""
    )

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    ROWS_PER_PAGE = 20

    # ========================================================
    # BASE QUERY
    # ========================================================

    if is_admin():

        vehicles_query = Vehicle.query

    else:

        vehicles_query = Vehicle.query.filter_by(
            location=current_location()
        )

    # ========================================================
    # FILTERS
    # ========================================================

    if reg_no:

        vehicles_query = vehicles_query.filter(
            Vehicle.reg_no.ilike(
                f"%{reg_no}%"
            )
        )

    if transporter:

        vehicles_query = vehicles_query.filter(
            Vehicle.transporter.ilike(
                f"%{transporter}%"
            )
        )

    if supplier:

        vehicles_query = vehicles_query.filter(
            Vehicle.supplier.ilike(
                f"%{supplier}%"
            )
        )

    if load_unload:
        vehicles_query = vehicles_query.filter(
            Vehicle.load_unload.ilike(
                f"%{load_unload}%"
            )
        )

    if status:

        vehicles_query = vehicles_query.filter(
            Vehicle.status.ilike(
                f"%{status}%"
            )
        )

    # ========================================================
    # DATE FILTER
    # ========================================================

    if from_date_str:

        try:

            start_dt = datetime.strptime(
                from_date_str,
                "%Y-%m-%d"
            )

            vehicles_query = vehicles_query.filter(
                Vehicle.check_in >=
                start_dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

        except ValueError:

            flash(
                "Invalid From Date.",
                "warning"
            )

    if to_date_str:

        try:

            end_dt = (
                datetime.strptime(
                    to_date_str,
                    "%Y-%m-%d"
                )
                +
                timedelta(days=1)
            )

            vehicles_query = vehicles_query.filter(
                Vehicle.check_in <
                end_dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

        except ValueError:

            flash(
                "Invalid To Date.",
                "warning"
            )

    # ========================================================
    # ORDER
    # ========================================================

    vehicles_query = vehicles_query.order_by(
        Vehicle.id.desc()
    )

    # ========================================================
    # PAGINATION
    # ========================================================

    total_filtered_vehicles = (
        vehicles_query.count()
    )

    total_pages = (
        total_filtered_vehicles
        + ROWS_PER_PAGE
        - 1
    ) // ROWS_PER_PAGE

    if total_pages < 1:

        total_pages = 1

    if page > total_pages:

        page = total_pages

    vehicles = vehicles_query.offset(
        (page - 1)
        * ROWS_PER_PAGE
    ).limit(
        ROWS_PER_PAGE
    ).all()

    # ========================================================
    # ALL FILTERED DATA
    # ========================================================

    all_filtered_vehicles = (
        vehicles_query.all()
    )

    daily_in = {}

    daily_out = {}

    for vehicle in all_filtered_vehicles:

        if not vehicle.check_in:

            continue

        date_str = vehicle.check_in.split(
            " "
        )[0]

        if vehicle.status == "IN":

            daily_in[date_str] = (
                daily_in.get(
                    date_str,
                    0
                )
                + 1
            )

        elif vehicle.status == "OUT":

            daily_out[date_str] = (
                daily_out.get(
                    date_str,
                    0
                )
                + 1
            )

    chart_in, chart_out = generate_charts(
        daily_in,
        daily_out
    )

    (
        total_in,
        total_out,
        total_status,
        over_48hrs
    ) = get_summary(
        all_filtered_vehicles
    )

    return render_template(
        "index.html",
        vehicles=vehicles,
        total_in=total_in,
        total_out=total_out,
        total_status=total_status,
        over_48hrs=over_48hrs,
        chart_in=chart_in,
        chart_out=chart_out,
        current_page=page,
        total_pages=total_pages,
        from_date=from_date_str,
        to_date=to_date_str,
        user=current_user(),
        role=current_role(),
        location=current_location(),
        current_year=datetime.now(
            IST
        ).year
    )


# ============================================================
# SECURITY GATE CHECK-IN
# ============================================================

@app.route(
    "/checkin",
    methods=["POST"]
)
def checkin():

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_security():

        flash(
            "Only Security can create Gate Check-In.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    try:

        # ====================================================
        # BASIC DETAILS
        # ====================================================

        reg_no = request.form.get(
            "reg_no",
            ""
        ).strip()

        vtype = request.form.get(
            "type",
            ""
        ).strip()

        transporter = request.form.get(
            "transporter",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        contact_no = request.form.get(
            "contact_no",
            ""
        ).strip()

        load_unload = request.form.get(
            "load_unload",
            "Unload"
        ).strip()

        remarks = request.form.get(
            "remarks",
            ""
        ).strip()

        driver_name = request.form.get(
            "driver_name",
            ""
        ).strip()

        driver_mobile = request.form.get(
            "driver_mobile",
            ""
        ).strip()

        # ====================================================
        # SECURITY UNLOAD FIELDS
        # ====================================================

        lr_number = request.form.get(
            "lr_number",
            ""
        ).strip()

        invoice_number = request.form.get(
            "invoice_number",
            ""
        ).strip()

        invoice_qty = request.form.get(
            "invoice_qty",
            ""
        ).strip()

        number_of_boxes = request.form.get(
            "number_of_boxes",
            ""
        ).strip()

        dock_number = request.form.get(
            "dock_number",
            ""
        ).strip()

        # ====================================================
        # VALIDATION
        # ====================================================

        if not reg_no or not vtype:

            flash(
                "Vehicle Reg No and Type are required.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        if load_unload.lower() not in (
            "load",
            "unload"
        ):

            flash(
                "Load/Unload must be Load or Unload.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        if not validate_dock(dock_number):

            flash(
                "Dock Assign Number must be between 1 and 16.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        # ====================================================
        # LOAD LOGIC
        #
        # VERY IMPORTANT:
        #
        # LOAD:
        # Security does not know LR / Invoice / Qty / Boxes.
        #
        # Therefore all those fields are forcibly blank.
        # ====================================================

        if load_unload.lower() == "load":

            lr_number = ""

            invoice_number = ""

            invoice_qty = ""

            number_of_boxes = ""

        # ====================================================
        # TIME
        # ====================================================

        now = current_time()

        # ====================================================
        # CREATE VEHICLE
        # ====================================================

        vehicle = Vehicle(

            reg_no=reg_no,

            type=vtype,

            transporter=transporter,

            supplier=supplier,

            lr_number=lr_number,

            contact_no=contact_no,

            load_unload=load_unload,

            remarks=remarks,

            status="IN",

            check_in=now,

            check_out=None,

            driver_name=driver_name,

            driver_mobile=driver_mobile,

            invoice_number=invoice_number,

            invoice_qty=invoice_qty,

            number_of_boxes=number_of_boxes,

            supervisor_invoice_qty="",

            supervisor_number_of_boxes="",

            supervisor_damaged_qty="",

            supervisor_damaged_boxes="",

            dock_number=dock_number,

            flow_type="INBOUND",

            security_checkin_by=current_user(),

            supervisor_unload_by=None,

            unload_time=None,

            unload_remarks=None,

            # LOAD FIELDS ALWAYS BLANK AT GATE CHECK-IN

            load_lr_number="",

            load_invoice_number="",

            load_invoice_qty="",

            load_number_of_boxes="",

            actual_qty="",

            actual_boxes="",

            supervisor_load_by=None,

            load_completed_time=None,

            load_remarks=None,

            # SECURITY CHECKOUT VALUES

            security_checkout_invoice_qty="",

            security_checkout_number_of_boxes="",

            # DIRECT OUTBOUND

            outbound_supervisor_by=None,

            outbound_entry_time=None,

            outbound_remarks=None,

            checkout_by=None,

            location=current_location()
        )

        db.session.add(
            vehicle
        )

        db.session.commit()

        flash(
            f"Gate Check-In successful for {reg_no}.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        logging.exception(
            "Gate Check-In error"
        )

        flash(
            f"Error during Gate Check-In: {e}",
            "danger"
        )

    return redirect(
        url_for("index")
    )


# ============================================================
# SUPERVISOR LOAD
# ============================================================

@app.route(
    "/load/<int:vid>",
    methods=["GET", "POST"]
)
def load_vehicle(vid):

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_supervisor():

        flash(
            "Only Supervisor can complete loading.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    vehicle = get_vehicle_for_current_user(
        vid
    )

    if vehicle is None:

        flash(
            "Vehicle not found.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.status != "IN":

        flash(
            "Vehicle is already checked out.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.flow_type != "INBOUND":

        flash(
            "This is not an Inbound vehicle.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    if not vehicle.load_unload:

        flash(
            "Load/Unload type is missing.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.load_unload.strip().lower() != "load":

        flash(
            "This vehicle is not marked for Load.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        try:

            load_lr_number = request.form.get(
                "load_lr_number",
                ""
            ).strip()

            load_invoice_number = request.form.get(
                "load_invoice_number",
                ""
            ).strip()

            load_invoice_qty = request.form.get(
                "load_invoice_qty",
                ""
            ).strip()

            load_number_of_boxes = request.form.get(
                "load_number_of_boxes",
                ""
            ).strip()

            actual_qty = request.form.get(
                "actual_qty",
                ""
            ).strip()

            actual_boxes = request.form.get(
                "actual_boxes",
                ""
            ).strip()

            load_remarks = request.form.get(
                "load_remarks",
                ""
            ).strip()

            # =================================================
            # REQUIRED LOAD FIELDS
            # =================================================

            if not load_lr_number:

                flash(
                    "LR Number is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "load_vehicle",
                        vid=vid
                    )
                )

            if not load_invoice_number:

                flash(
                    "Invoice Number is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "load_vehicle",
                        vid=vid
                    )
                )

            if not load_invoice_qty:

                flash(
                    "Invoice Quantity is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "load_vehicle",
                        vid=vid
                    )
                )

            if not load_number_of_boxes:

                flash(
                    "Number of Boxes is required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "load_vehicle",
                        vid=vid
                    )
                )

            # =================================================
            # SAVE LOAD DATA
            # =================================================

            vehicle.load_lr_number = (
                load_lr_number
            )

            vehicle.load_invoice_number = (
                load_invoice_number
            )

            vehicle.load_invoice_qty = (
                load_invoice_qty
            )

            vehicle.load_number_of_boxes = (
                load_number_of_boxes
            )

            vehicle.actual_qty = (
                actual_qty
            )

            vehicle.actual_boxes = (
                actual_boxes
            )

            vehicle.supervisor_load_by = (
                current_user()
            )

            vehicle.load_completed_time = (
                current_time()
            )

            vehicle.load_remarks = (
                load_remarks
            )

            # =================================================
            # DO NOT PUT LOAD DATA INTO GENERAL UNLOAD FIELDS
            #
            # LR / Invoice / Qty / Boxes remain in their
            # dedicated LOAD fields.
            # =================================================

            db.session.commit()

            flash(
                "Loading completed successfully by Supervisor.",
                "success"
            )

            return redirect(
                url_for("index")
            )

        except Exception as e:

            db.session.rollback()

            logging.exception(
                "Supervisor Load error"
            )

            flash(
                f"Error during loading: {e}",
                "danger"
            )

    return render_template(
        "load.html",
        vehicle=vehicle,
        user=current_user(),
        role=current_role(),
        location=current_location()
    )


# ============================================================
# SUPERVISOR UNLOAD
# ============================================================

@app.route(
    "/unload/<int:vid>",
    methods=["GET", "POST"]
)
def unload(vid):

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_supervisor():

        flash(
            "Only Supervisor can complete unloading.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    vehicle = get_vehicle_for_current_user(
        vid
    )

    if vehicle is None:

        flash(
            "Vehicle not found.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.status != "IN":

        flash(
            "Vehicle is already checked out.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.flow_type != "INBOUND":

        flash(
            "This vehicle is not Inbound.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    if (
        vehicle.load_unload
        and
        vehicle.load_unload.strip().lower()
        == "load"
    ):

        flash(
            "This vehicle is marked as Load, not Unload.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        try:

            # =================================================
            # VEHICLE DETAILS
            # =================================================

            vehicle.reg_no = request.form.get(
                "reg_no",
                vehicle.reg_no
            ).strip()

            vehicle.type = request.form.get(
                "type",
                vehicle.type
            ).strip()

            vehicle.transporter = request.form.get(
                "transporter",
                vehicle.transporter or ""
            ).strip()

            vehicle.supplier = request.form.get(
                "supplier",
                vehicle.supplier or ""
            ).strip()

            vehicle.lr_number = request.form.get(
                "lr_number",
                vehicle.lr_number or ""
            ).strip()

            vehicle.contact_no = request.form.get(
                "contact_no",
                vehicle.contact_no or ""
            ).strip()

            vehicle.driver_name = request.form.get(
                "driver_name",
                vehicle.driver_name or ""
            ).strip()

            vehicle.driver_mobile = request.form.get(
                "driver_mobile",
                vehicle.driver_mobile or ""
            ).strip()

            vehicle.dock_number = request.form.get(
                "dock_number",
                vehicle.dock_number or ""
            ).strip()

            if not validate_dock(
                vehicle.dock_number
            ):

                flash(
                    "Dock Assign Number must be between 1 and 16.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "unload",
                        vid=vid
                    )
                )

            # =================================================
            # SUPERVISOR ACTUAL VALUES
            # =================================================

            vehicle.supervisor_invoice_qty = request.form.get(
                "supervisor_invoice_qty",
                ""
            ).strip()

            vehicle.supervisor_number_of_boxes = request.form.get(
                "supervisor_number_of_boxes",
                ""
            ).strip()

            # =================================================
            # DAMAGED
            # =================================================

            vehicle.supervisor_damaged_qty = request.form.get(
                "supervisor_damaged_qty",
                ""
            ).strip()

            vehicle.supervisor_damaged_boxes = request.form.get(
                "supervisor_damaged_boxes",
                ""
            ).strip()

            # =================================================
            # SUPERVISOR UNLOAD
            # =================================================

            vehicle.supervisor_unload_by = (
                current_user()
            )

            vehicle.unload_time = (
                current_time()
            )

            vehicle.unload_remarks = request.form.get(
                "unload_remarks",
                ""
            ).strip()

            extra_remarks = request.form.get(
                "remarks",
                ""
            ).strip()

            if extra_remarks:

                vehicle.remarks = extra_remarks

            db.session.commit()

            flash(
                "Inbound unloading completed by Supervisor.",
                "success"
            )

            return redirect(
                url_for("index")
            )

        except Exception as e:

            db.session.rollback()

            logging.exception(
                "Supervisor Unload error"
            )

            flash(
                f"Error during unload: {e}",
                "danger"
            )

    return render_template(
        "unload.html",
        vehicle=vehicle,
        user=current_user(),
        role=current_role(),
        location=current_location()
    )


# ============================================================
# DIRECT OUTBOUND ENTRY
# SUPERVISOR
# ============================================================

@app.route(
    "/outbound",
    methods=["POST"]
)
def outbound():

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not is_supervisor():

        flash(
            "Only Supervisor can create Outbound Entry.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    try:

        reg_no = request.form.get(
            "reg_no",
            ""
        ).strip()

        vtype = request.form.get(
            "type",
            ""
        ).strip()

        transporter = request.form.get(
            "transporter",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        lr_number = request.form.get(
            "lr_number",
            ""
        ).strip()

        contact_no = request.form.get(
            "contact_no",
            ""
        ).strip()

        load_unload = request.form.get(
            "load_unload",
            "Load"
        ).strip()

        driver_name = request.form.get(
            "driver_name",
            ""
        ).strip()

        driver_mobile = request.form.get(
            "driver_mobile",
            ""
        ).strip()

        invoice_number = request.form.get(
            "invoice_number",
            ""
        ).strip()

        invoice_qty = request.form.get(
            "invoice_qty",
            ""
        ).strip()

        number_of_boxes = request.form.get(
            "number_of_boxes",
            ""
        ).strip()

        dock_number = request.form.get(
            "dock_number",
            ""
        ).strip()

        remarks = request.form.get(
            "remarks",
            ""
        ).strip()

        if not reg_no or not vtype:

            flash(
                "Vehicle Reg No and Type are required.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        if not validate_dock(dock_number):

            flash(
                "Dock Assign Number must be between 1 and 16.",
                "danger"
            )

            return redirect(
                url_for("index")
            )

        now = current_time()

        vehicle = Vehicle(

            reg_no=reg_no,

            type=vtype,

            transporter=transporter,

            supplier=supplier,

            lr_number=lr_number,

            contact_no=contact_no,

            load_unload=load_unload,

            driver_name=driver_name,

            driver_mobile=driver_mobile,

            invoice_number=invoice_number,

            invoice_qty=invoice_qty,

            number_of_boxes=number_of_boxes,

            supervisor_invoice_qty="",

            supervisor_number_of_boxes="",

            supervisor_damaged_qty="",

            supervisor_damaged_boxes="",

            dock_number=dock_number,

            remarks=remarks,

            flow_type="OUTBOUND",

            status="IN",

            check_in=now,

            check_out=None,

            security_checkin_by=None,

            supervisor_unload_by=None,

            unload_time=None,

            unload_remarks=None,

            # LOAD fields blank

            load_lr_number="",

            load_invoice_number="",

            load_invoice_qty="",

            load_number_of_boxes="",

            actual_qty="",

            actual_boxes="",

            supervisor_load_by=None,

            load_completed_time=None,

            load_remarks=None,

            security_checkout_invoice_qty="",

            security_checkout_number_of_boxes="",

            # DIRECT OUTBOUND

            outbound_supervisor_by=current_user(),

            outbound_entry_time=now,

            outbound_remarks=remarks,

            checkout_by=None,

            location=current_location()
        )

        db.session.add(
            vehicle
        )

        db.session.commit()

        flash(
            "Outbound vehicle entry submitted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        logging.exception(
            "Outbound entry error"
        )

        flash(
            f"Error during outbound entry: {e}",
            "danger"
        )

    return redirect(
        url_for("index")
    )


# ============================================================
# SECURITY CHECKOUT
# ============================================================

@app.route(
    "/checkout/<int:vid>",
    methods=["GET", "POST"]
)
def checkout(vid):

    if not require_login():

        return redirect(
            url_for("login")
        )

    if not (
        is_security()
        or is_admin()
    ):

        flash(
            "Only Security can Check-Out.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    vehicle = get_vehicle_for_current_user(
        vid
    )

    if vehicle is None:

        flash(
            "Vehicle not found.",
            "danger"
        )

        return redirect(
            url_for("index")
        )

    if vehicle.status != "IN":

        flash(
            "Vehicle is already checked out.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    # ========================================================
    # INBOUND
    # ========================================================

    if vehicle.flow_type == "INBOUND":

        is_load = (
            vehicle.load_unload
            and
            vehicle.load_unload.strip().lower()
            == "load"
        )

        # ====================================================
        # LOAD CHECKOUT
        # ====================================================

        if is_load:

            # -----------------------------------------------
            # Supervisor must complete LOAD first
            # -----------------------------------------------

            if not vehicle.supervisor_load_by:

                flash(
                    "Supervisor must complete loading before Security Check-Out.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            if not vehicle.load_completed_time:

                flash(
                    "Loading completion time is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            # -----------------------------------------------
            # Required Supervisor Load Details
            # -----------------------------------------------

            if not vehicle.load_lr_number:

                flash(
                    "Supervisor LR Number is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            if not vehicle.load_invoice_number:

                flash(
                    "Supervisor Invoice Number is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            if not vehicle.load_invoice_qty:

                flash(
                    "Supervisor Invoice Quantity is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            if not vehicle.load_number_of_boxes:

                flash(
                    "Supervisor Number of Boxes is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            # -----------------------------------------------
            # SECURITY POST
            # -----------------------------------------------

            if request.method == "POST":

                security_invoice_qty = request.form.get(
                    "security_checkout_invoice_qty",
                    ""
                ).strip()

                security_boxes = request.form.get(
                    "security_checkout_number_of_boxes",
                    ""
                ).strip()

                if not security_invoice_qty:

                    flash(
                        "Security Invoice Quantity is required.",
                        "danger"
                    )

                    return redirect(
                        url_for(
                            "checkout",
                            vid=vid
                        )
                    )

                if not security_boxes:

                    flash(
                        "Security Number Of Boxes is required.",
                        "danger"
                    )

                    return redirect(
                        url_for(
                            "checkout",
                            vid=vid
                        )
                    )

                vehicle.security_checkout_invoice_qty = (
                    security_invoice_qty
                )

                vehicle.security_checkout_number_of_boxes = (
                    security_boxes
                )

        # ====================================================
        # UNLOAD CHECKOUT
        # ====================================================

        else:

            if not vehicle.supervisor_unload_by:

                flash(
                    "Supervisor must complete unloading before Security Check-Out.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

            if not vehicle.unload_time:

                flash(
                    "Unload completion time is missing.",
                    "warning"
                )

                return redirect(
                    url_for("index")
                )

    # ========================================================
    # DIRECT OUTBOUND
    # ========================================================

    elif vehicle.flow_type == "OUTBOUND":

        if not vehicle.outbound_supervisor_by:

            flash(
                "Outbound Supervisor entry is incomplete.",
                "warning"
            )

            return redirect(
                url_for("index")
            )

    # ========================================================
    # CHECKOUT
    # ========================================================

    if request.method == "POST":

        try:

            vehicle.status = "OUT"

            vehicle.check_out = (
                current_time()
            )

            vehicle.checkout_by = (
                current_user()
            )

            db.session.commit()

            flash(
                f"Vehicle {vehicle.reg_no} successfully checked out.",
                "success"
            )

            return redirect(
                url_for("index")
            )

        except Exception as e:

            db.session.rollback()

            logging.exception(
                "Checkout error"
            )

            flash(
                f"Error during Check-Out: {e}",
                "danger"
            )

            return redirect(
                url_for("index")
            )

    # ========================================================
    # GET CHECKOUT PAGE
    # ========================================================

    return render_template(
        "checkout.html",
        vehicle=vehicle,
        user=current_user(),
        role=current_role(),
        location=current_location()
    )


# ============================================================
# CSV EXPORT
# ============================================================

@app.route("/export")
def export():

    if not require_login():

        return redirect(
            url_for("login")
        )

    if current_role() not in (
        "admin",
        "supervisor"
    ):

        flash(
            "Unauthorized! Access denied.",
            "warning"
        )

        return redirect(
            url_for("index")
        )

    si = io.StringIO()

    cw = csv.writer(si)

    cw.writerow([

        "Entry ID",
        "Location",
        "Flow Type",
        "Reg Number",
        "Type",
        "Transporter",
        "Supplier",

        "General LR Number",
        "Contact No",

        "Driver Name",
        "Driver Mobile",

        "General Invoice Number",
        "General Invoice Qty",
        "General Number Of Boxes",

        "Load LR Number",
        "Load Invoice Number",
        "Load Invoice Qty",
        "Load Number Of Boxes",
        "Load Actual Qty",
        "Load Actual Boxes",
        "Supervisor Load By",
        "Load Completed Time",
        "Load Remarks",

        "Unload Supervisor Qty",
        "Unload Supervisor Boxes",
        "Damaged Qty",
        "Damaged Boxes",

        "Dock Number",
        "Load/Unload",
        "Status",
        "Remarks",

        "Check-In Time",
        "Security Check-In By",

        "Supervisor Unload By",
        "Unload Time",
        "Unload Remarks",

        "Outbound Supervisor By",
        "Outbound Entry Time",
        "Outbound Remarks",

        "Security Checkout Qty",
        "Security Checkout Boxes",

        "Check-Out Time",
        "Check-Out By",
    ])

    # ========================================================
    # LOCATION
    # ========================================================

    if is_admin():

        vehicles = Vehicle.query.order_by(
            Vehicle.id.asc()
        ).all()

    else:

        vehicles = Vehicle.query.filter_by(
            location=current_location()
        ).order_by(
            Vehicle.id.asc()
        ).all()

    # ========================================================
    # ROWS
    # ========================================================

    for v in vehicles:

        cw.writerow([

            v.id,
            v.location,
            v.flow_type,
            v.reg_no,
            v.type,
            v.transporter,
            v.supplier,

            v.lr_number,
            v.contact_no,

            v.driver_name,
            v.driver_mobile,

            v.invoice_number,
            v.invoice_qty,
            v.number_of_boxes,

            v.load_lr_number,
            v.load_invoice_number,
            v.load_invoice_qty,
            v.load_number_of_boxes,
            v.actual_qty,
            v.actual_boxes,
            v.supervisor_load_by,
            v.load_completed_time,
            v.load_remarks,

            v.supervisor_invoice_qty,
            v.supervisor_number_of_boxes,
            v.supervisor_damaged_qty,
            v.supervisor_damaged_boxes,

            v.dock_number,
            v.load_unload,
            v.status,
            v.remarks,

            v.check_in,
            v.security_checkin_by,

            v.supervisor_unload_by,
            v.unload_time,
            v.unload_remarks,

            v.outbound_supervisor_by,
            v.outbound_entry_time,
            v.outbound_remarks,

            v.security_checkout_invoice_qty,
            v.security_checkout_number_of_boxes,

            v.check_out,
            v.checkout_by,
        ])

    output = make_response(
        si.getvalue()
    )

    output.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        "filename=vehicle_log.csv"
    )

    output.headers[
        "Content-Type"
    ] = "text/csv"

    return output


# ============================================================
# CHATBOT
# ============================================================

@app.route(
    "/chatbot",
    methods=["POST"]
)
def chatbot():

    if not require_login():

        return jsonify({
            "answer": "Please login first."
        }), 401

    try:

        if is_admin():

            vehicles = Vehicle.query.all()

        else:

            vehicles = Vehicle.query.filter_by(
                location=current_location()
            ).all()

        data = request.get_json(
            silent=True
        ) or {}

        query = data.get(
            "query",
            ""
        ).lower().strip()

        total = len(
            vehicles
        )

        answer = (
            "Sorry, I didn't understand your question."
        )

        # ====================================================
        # TOTAL
        # ====================================================

        if (
            "total" in query
            and
            "vehicle" in query
        ):

            answer = (
                f"There are {total} vehicles "
                f"in the system."
            )

        # ====================================================
        # IN
        # ====================================================

        elif (
            "in" in query
            and
            "vehicle" in query
        ):

            total_in = sum(
                1
                for v in vehicles
                if v.status == "IN"
            )

            answer = (
                f"Currently {total_in} "
                f"vehicles are IN."
            )

        # ====================================================
        # OUT
        # ====================================================

        elif (
            "out" in query
            and
            "vehicle" in query
        ):

            total_out = sum(
                1
                for v in vehicles
                if v.status == "OUT"
            )

            answer = (
                f"Currently {total_out} "
                f"vehicles are OUT."
            )

        # ====================================================
        # LOAD
        # ====================================================

        elif "load" in query:

            load_vehicles = [
                v
                for v in vehicles
                if (
                    v.load_unload
                    and
                    v.load_unload.lower() == "load"
                    and
                    v.status == "IN"
                )
            ]

            answer = (
                f"There are {len(load_vehicles)} "
                f"Load vehicles currently IN."
            )

        # ====================================================
        # UNLOAD
        # ====================================================

        elif "unload" in query:

            unload_vehicles = [
                v
                for v in vehicles
                if (
                    v.load_unload
                    and
                    v.load_unload.lower() == "unload"
                    and
                    v.status == "IN"
                )
            ]

            answer = (
                f"There are {len(unload_vehicles)} "
                f"Unload vehicles currently IN."
            )

        # ====================================================
        # OLDEST
        # ====================================================

        elif (
            "oldest" in query
            or
            "sabse purana" in query
        ):

            try:

                oldest = min(
                    (
                        v
                        for v in vehicles
                        if v.check_in
                    ),
                    key=lambda v:
                    datetime.strptime(
                        v.check_in,
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                answer = (
                    f"The oldest check-in is "
                    f"{oldest.reg_no} "
                    f"at {oldest.check_in}."
                )

            except Exception:

                answer = (
                    "No valid check-in data found."
                )

        # ====================================================
        # LATEST
        # ====================================================

        elif (
            "latest" in query
            or
            "sabse naya" in query
        ):

            try:

                latest = max(
                    (
                        v
                        for v in vehicles
                        if v.check_in
                    ),
                    key=lambda v:
                    datetime.strptime(
                        v.check_in,
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                answer = (
                    f"The latest check-in is "
                    f"{latest.reg_no} "
                    f"at {latest.check_in}."
                )

            except Exception:

                answer = (
                    "No valid check-in data found."
                )

        # ====================================================
        # VEHICLE SEARCH
        # ====================================================

        else:

            for v in vehicles:

                if (
                    v.reg_no
                    and
                    v.reg_no.lower() in query
                ):

                    answer = (
                        f"Details for {v.reg_no}: "
                        f"Status = {v.status}, "
                        f"Flow = {v.flow_type}, "
                        f"Load/Unload = {v.load_unload}, "
                        f"Check-in = {v.check_in or 'N/A'}, "
                        f"Check-out = {v.check_out or 'N/A'}, "
                        f"Type = {v.type or 'Unknown'}."
                    )

                    break

        return jsonify({
            "answer": answer
        })

    except Exception:

        logging.exception(
            "Chatbot error"
        )

        return jsonify({
            "answer": (
                "Unable to process the request."
            )
        }), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "application": "Vehicle Tracking System"
    })


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_database()


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )