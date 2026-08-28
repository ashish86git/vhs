from flask import Flask, render_template, request, redirect, url_for, make_response, session, flash, jsonify
from datetime import datetime, timedelta
import plotly.graph_objects as go
import pytz
import io
import csv
import logging
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# CONFIGURATION
# ============================================================

logging.basicConfig(level=logging.INFO)

IST = pytz.timezone("Asia/Kolkata")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")


DB_HOST = os.environ.get("DB_HOST", "c89hfa8mgg235.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "d2hc5emqstdlu5")
DB_USER = os.environ.get("DB_USER", "u5no93tf65ksha")
DB_PASSWORD = os.environ.get(
    "DB_PASSWORD",
    "p86edb19173b56140c6f59850879a1341955fa911bfcaf2f17f8ecf207bc42dad"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
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
# DATABASE MODELS
# ============================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, index=True)
    location = db.Column(db.String(150), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        # Supports both new hashed passwords and old plain passwords.
        if self.password and self.password.startswith(("pbkdf2:", "scrypt:", "argon2:")):
            return check_password_hash(self.password, password)
        return self.password == password


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id = db.Column(db.Integer, primary_key=True)

    # ============================================================
    # BASIC VEHICLE INFORMATION
    # ============================================================

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

    # ============================================================
    # VEHICLE STATUS
    # ============================================================

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

    # ============================================================
    # DRIVER INFORMATION
    # ============================================================

    driver_name = db.Column(
        db.String(150)
    )

    driver_mobile = db.Column(
        db.String(100)
    )

    # ============================================================
    # INVOICE INFORMATION
    # ============================================================

    invoice_number = db.Column(
        db.String(150)
    )

    # ============================================================
    # SECURITY ENTERED VALUES
    # ============================================================

    invoice_qty = db.Column(
        db.String(100)
    )

    number_of_boxes = db.Column(
        db.String(100)
    )

    # ============================================================
    # SUPERVISOR VERIFIED / ACTUAL VALUES
    # ============================================================

    supervisor_invoice_qty = db.Column(
        db.String(100)
    )

    supervisor_number_of_boxes = db.Column(
        db.String(100)
    )

    # ============================================================
    # DOCK INFORMATION
    # ============================================================

    dock_number = db.Column(
        db.String(20)
    )

    # ============================================================
    # INBOUND WORKFLOW
    # ============================================================

    flow_type = db.Column(
        db.String(30),
        default="INBOUND",
        nullable=False
    )

    # Security who performed Check-In
    security_checkin_by = db.Column(
        db.String(100)
    )

    # Supervisor who performed Unload
    supervisor_unload_by = db.Column(
        db.String(100)
    )

    # Actual unload date/time
    unload_time = db.Column(
        db.String(30)
    )

    # Supervisor's unload remarks
    unload_remarks = db.Column(
        db.Text
    )

    # ============================================================
    # OUTBOUND WORKFLOW
    # ============================================================

    # Supervisor who created outbound entry
    outbound_supervisor_by = db.Column(
        db.String(100)
    )

    # Outbound entry date/time
    outbound_entry_time = db.Column(
        db.String(30)
    )

    # Outbound remarks
    outbound_remarks = db.Column(
        db.Text
    )

    # ============================================================
    # CHECK-OUT SECURITY
    # ============================================================

    # Security/Admin who checked out vehicle
    checkout_by = db.Column(
        db.String(100)
    )

    # ============================================================
    # LOCATION ISOLATION
    # ============================================================

    location = db.Column(
        db.String(150),
        nullable=False,
        index=True
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():
    with app.app_context():
        db.create_all()

        # Preserve the existing admin login while moving it to DB.
        admin = User.query.filter_by(username="admin").first()

        if admin is None:
            admin = User(
                username="admin",
                role="admin",
                location="ALL",
                is_active=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()

        logging.info("Database tables initialized successfully.")


# ============================================================
# HELPERS
# ============================================================

def current_time():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def current_role():
    return session.get("role")


def current_location():
    return session.get("location")


def is_security():
    # lifelong is retained for backward compatibility.
    return current_role() in ("security", "lifelong")


def is_supervisor():
    return current_role() == "supervisor"


def is_admin():
    return current_role() == "admin"


def require_login():
    return "user" in session


def can_access_vehicle(vehicle):
    if vehicle is None:
        return False

    if is_admin():
        return True

    return (
        current_location()
        and vehicle.location
        and vehicle.location.strip().lower() == current_location().strip().lower()
    )


def get_accessible_vehicles():
    if is_admin():
        return Vehicle.query.all()

    location = current_location()

    if not location:
        return []

    return Vehicle.query.filter(
        Vehicle.location.ilike(location)
    ).all()


def get_vehicle_for_current_user(vid):
    vehicle = db.session.get(Vehicle, vid)

    if vehicle is None:
        return None

    if not can_access_vehicle(vehicle):
        return None

    return vehicle


def get_summary(vehicles):
    """Calculates summary counts based on a given list of vehicles."""
    total_in = 0
    total_out = 0
    total_status = len(vehicles)
    over_48hrs = 0

    for v in vehicles:
        if v.status == "IN":
            total_in += 1
        elif v.status == "OUT":
            total_out += 1

        if v.check_in and v.check_out:
            try:
                check_in_time = datetime.strptime(
                    v.check_in, "%Y-%m-%d %H:%M:%S"
                )
                check_out_time = datetime.strptime(
                    v.check_out, "%Y-%m-%d %H:%M:%S"
                )
                diff = check_out_time - check_in_time

                if diff > timedelta(hours=48):
                    over_48hrs += 1

            except ValueError:
                logging.error(
                    "Error parsing date for vehicle ID: %s",
                    v.id
                )

    return total_in, total_out, total_status, over_48hrs


def generate_charts(daily_in, daily_out):
    """Generates Plotly charts as HTML strings."""

    all_days = sorted(
        list(set(daily_in.keys()) | set(daily_out.keys()))
    )

    in_counts = [daily_in.get(d, 0) for d in all_days]
    out_counts = [daily_out.get(d, 0) for d in all_days]

    fig_in = go.Figure()
    fig_in.add_trace(
        go.Scatter(
            x=all_days,
            y=in_counts,
            mode="lines+markers",
            marker=dict(color="green", size=8),
            line=dict(width=2),
            hovertemplate=(
                "Date: %{x}<br>"
                "Check-Ins: %{y}<extra></extra>"
            ),
        )
    )
    fig_in.update_layout(
        title="Daily Check-Ins",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=80),
    )
    chart_in = fig_in.to_html(full_html=False)

    fig_out = go.Figure()
    fig_out.add_trace(
        go.Scatter(
            x=all_days,
            y=out_counts,
            mode="lines+markers",
            marker=dict(color="red", size=8),
            line=dict(width=2),
            hovertemplate=(
                "Date: %{x}<br>"
                "Check-Outs: %{y}<extra></extra>"
            ),
        )
    )
    fig_out.update_layout(
        title="Daily Check-Outs",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=80),
    )
    chart_out = fig_out.to_html(full_html=False)

    return chart_in, chart_out


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("index"))
    return redirect(url_for("login"))


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        userid = request.form.get("userid", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(
            username=userid,
            is_active=True
        ).first()

        if user and user.check_password(password):
            session["user"] = user.username
            session["role"] = user.role
            session["location"] = user.location

            # Transparently upgrade old plain-text password to a hash.
            if not user.password.startswith(("pbkdf2:", "scrypt:", "argon2:")):
                user.set_password(password)
                db.session.commit()

            return redirect(url_for("index"))

        flash("Invalid credentials!", "danger")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("role", None)
    session.pop("location", None)
    return redirect(url_for("login"))


# ============================================================
# ADMIN USER MANAGEMENT
# ADMIN ONLY
# ============================================================

@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not require_login():
        return redirect(url_for("login"))

    if not is_admin():
        flash("Unauthorized! Only Admin can manage users.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()
        location = request.form.get("location", "").strip()

        allowed_roles = {"admin", "supervisor", "security", "lifelong"}

        if not username or not password or not role or not location:
            flash("Username, password, role and location are required.", "danger")
            return redirect(url_for("admin_users"))

        if role not in allowed_roles:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("admin_users"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("admin_users"))

        user = User(
            username=username,
            role=role,
            location=location,
            is_active=True,
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("User created successfully.", "success")
        return redirect(url_for("admin_users"))

    users = User.query.order_by(User.id.asc()).all()

    return render_template(
        "admin_users.html",
        users=users,
        user=session.get("user"),
        role=session.get("role"),
        location=session.get("location"),
    )


@app.route("/admin/users/toggle/<int:uid>")
def toggle_user(uid):
    if not require_login():
        return redirect(url_for("login"))

    if not is_admin():
        flash("Unauthorized! Only Admin can manage users.", "warning")
        return redirect(url_for("index"))

    user = db.session.get(User, uid)

    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin_users"))

    if user.username == session.get("user"):
        flash("Current admin user cannot be disabled.", "warning")
        return redirect(url_for("admin_users"))

    user.is_active = not user.is_active
    db.session.commit()

    flash(
        f"User {'enabled' if user.is_active else 'disabled'} successfully.",
        "success"
    )
    return redirect(url_for("admin_users"))


# ============================================================
# MAIN INDEX / DASHBOARD
# ============================================================

@app.route("/index")
def index():
    if not require_login():
        return redirect(url_for("login"))

    reg_no = request.args.get("reg", "").strip().lower()
    transporter = request.args.get("transporter", "").strip().lower()
    supplier = request.args.get("supplier", "").strip().lower()
    load_unload = request.args.get("load_unload", "").strip().lower()
    status = request.args.get("status", "").strip().lower()
    from_date_str = request.args.get("from_date", "")
    to_date_str = request.args.get("to_date", "")

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    ROWS_PER_PAGE = 20

    # LOCATION FILTER:
    # Admin sees all locations; every other user sees only own location.
    if is_admin():
        vehicles_query = Vehicle.query
    else:
        vehicles_query = Vehicle.query.filter_by(
            location=current_location()
        )

    vehicles_query = vehicles_query.order_by(Vehicle.id.desc())

    if reg_no:
        vehicles_query = vehicles_query.filter(
            Vehicle.reg_no.ilike(f"%{reg_no}%")
        )

    if transporter:
        vehicles_query = vehicles_query.filter(
            Vehicle.transporter.ilike(f"%{transporter}%")
        )

    if supplier:
        vehicles_query = vehicles_query.filter(
            Vehicle.supplier.ilike(f"%{supplier}%")
        )

    if load_unload:
        vehicles_query = vehicles_query.filter(
            Vehicle.load_unload.ilike(f"%{load_unload}%")
        )

    if status:
        vehicles_query = vehicles_query.filter(
            Vehicle.status.ilike(f"%{status}%")
        )

    if from_date_str:
        try:
            start_dt = datetime.strptime(from_date_str, "%Y-%m-%d")
            vehicles_query = vehicles_query.filter(
                Vehicle.check_in >= start_dt.strftime("%Y-%m-%d %H:%M:%S")
            )
        except ValueError:
            flash("Invalid From Date.", "warning")

    if to_date_str:
        try:
            end_dt = (
                datetime.strptime(to_date_str, "%Y-%m-%d")
                + timedelta(days=1)
            )
            vehicles_query = vehicles_query.filter(
                Vehicle.check_in < end_dt.strftime("%Y-%m-%d %H:%M:%S")
            )
        except ValueError:
            flash("Invalid To Date.", "warning")

    total_filtered_vehicles = vehicles_query.count()

    total_pages = (
        total_filtered_vehicles + ROWS_PER_PAGE - 1
    ) // ROWS_PER_PAGE

    if total_pages == 0:
        total_pages = 1

    if page > total_pages:
        page = total_pages

    vehicles = vehicles_query.offset(
        (page - 1) * ROWS_PER_PAGE
    ).limit(ROWS_PER_PAGE).all()

    # Same complete filtered dataset is used for dashboard summary/charts.
    all_filtered_vehicles = vehicles_query.all()

    daily_in = {}
    daily_out = {}

    for v in all_filtered_vehicles:
        if v.check_in:
            date_str = v.check_in.split(" ")[0]

            if v.status == "IN":
                daily_in[date_str] = daily_in.get(date_str, 0) + 1
            elif v.status == "OUT":
                daily_out[date_str] = daily_out.get(date_str, 0) + 1

    chart_in, chart_out = generate_charts(daily_in, daily_out)

    total_in, total_out, total_status, over_48hrs = get_summary(
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
        user=session["user"],
        role=session["role"],
        location=session.get("location"),
        current_year=datetime.now(IST).year,
    )


# ============================================================
# INBOUND CHECK-IN
# SECURITY ONLY
# ============================================================

@app.route("/checkin", methods=["POST"])
def checkin():
    if not require_login():
        return redirect(url_for("login"))

    if not is_security():
        flash(
            "Unauthorized! Only Security can create an Inbound Check-In.",
            "warning"
        )
        return redirect(url_for("index"))

    try:
        reg_no = request.form.get("reg_no", "").strip()
        vtype = request.form.get("type", "").strip()
        transporter = request.form.get("transporter", "").strip()
        supplier = request.form.get("supplier", "").strip()
        lr_number = request.form.get("lr_number", "").strip()
        contact_no = request.form.get("contact_no", "").strip()
        load_unload = request.form.get("load_unload", "Unload").strip()
        remarks = request.form.get("remarks", "").strip()

        driver_name = request.form.get("driver_name", "").strip()
        driver_mobile = request.form.get("driver_mobile", "").strip()
        invoice_number = request.form.get("invoice_number", "").strip()
        invoice_qty = request.form.get("invoice_qty", "").strip()
        number_of_boxes = request.form.get("number_of_boxes", "").strip()
        dock_number = request.form.get("dock_number", "").strip()

        if not reg_no or not vtype:
            flash("Vehicle Reg No and Type are required.", "danger")
            return redirect(url_for("index"))

        if dock_number:
            try:
                dock_int = int(dock_number)
                if dock_int < 1 or dock_int > 16:
                    raise ValueError
            except ValueError:
                flash(
                    "Dock Assign Number must be between 1 and 16.",
                    "danger"
                )
                return redirect(url_for("index"))

        now = current_time()

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
            check_out="",
            driver_name=driver_name,
            driver_mobile=driver_mobile,
            invoice_number=invoice_number,
            invoice_qty=invoice_qty,
            number_of_boxes=number_of_boxes,
            dock_number=dock_number,
            flow_type="INBOUND",
            security_checkin_by=session.get("user"),
            location=session.get("location"),
        )

        db.session.add(vehicle)
        db.session.commit()

        flash(
            "Inbound vehicle successfully checked in by Security!",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        logging.exception("Inbound check-in error")
        flash(f"Error during check-in: {e}", "danger")

    return redirect(url_for("index"))


# ============================================================
# INBOUND UNLOAD
# SUPERVISOR ONLY
# ============================================================

@app.route("/unload/<int:vid>", methods=["GET", "POST"])
def unload(vid):

    if not require_login():
        return redirect(url_for("login"))

    if not is_supervisor():
        flash(
            "Unauthorized! Only Supervisor can complete unloading.",
            "warning"
        )
        return redirect(url_for("index"))

    vehicle = get_vehicle_for_current_user(vid)

    if vehicle is None:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("index"))

    if vehicle.status != "IN":
        flash(
            "Vehicle is already checked out.",
            "warning"
        )
        return redirect(url_for("index"))

    if vehicle.flow_type != "INBOUND":
        flash(
            "This vehicle is not an Inbound vehicle.",
            "warning"
        )
        return redirect(url_for("index"))

    if request.method == "POST":

        try:

            # ==================================================
            # EXISTING VEHICLE DETAILS
            # ==================================================

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

            vehicle.load_unload = request.form.get(
                "load_unload",
                vehicle.load_unload or "Unload"
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

            # ==================================================
            # DOCK VALIDATION
            # ==================================================

            if vehicle.dock_number:

                try:

                    dock_int = int(vehicle.dock_number)

                    if dock_int < 1 or dock_int > 16:
                        raise ValueError

                except ValueError:

                    flash(
                        "Dock Assign Number must be between 1 and 16.",
                        "danger"
                    )

                    return redirect(
                        url_for("unload", vid=vid)
                    )

            # ==================================================
            # SUPERVISOR ACTUAL VALUES
            #
            # SECURITY VALUES:
            # vehicle.invoice_qty
            # vehicle.number_of_boxes
            #
            # These are NOT displayed to supervisor.
            # ==================================================

            vehicle.supervisor_invoice_qty = request.form.get(
                "supervisor_invoice_qty",
                vehicle.supervisor_invoice_qty or ""
            ).strip()

            vehicle.supervisor_number_of_boxes = request.form.get(
                "supervisor_number_of_boxes",
                vehicle.supervisor_number_of_boxes or ""
            ).strip()

            vehicle.supervisor_damaged_qty = request.form.get(
                "supervisor_damaged_qty",
                ""
            ).strip()

            vehicle.supervisor_damaged_boxes = request.form.get(
                "supervisor_damaged_boxes",
                ""
            ).strip()

            # ==================================================
            # SUPERVISOR UNLOAD INFORMATION
            # ==================================================

            vehicle.supervisor_unload_by = session.get("user")

            vehicle.unload_time = current_time()

            vehicle.unload_remarks = request.form.get(
                "unload_remarks",
                ""
            ).strip()

            # ==================================================
            # GENERAL REMARKS
            # ==================================================

            extra_remarks = request.form.get(
                "remarks",
                ""
            ).strip()

            if extra_remarks:
                vehicle.remarks = extra_remarks

            # ==================================================
            # SAVE
            # ==================================================

            db.session.commit()

            flash(
                "Inbound unloading completed by Supervisor.",
                "success"
            )

            return redirect(url_for("index"))

        except Exception as e:

            db.session.rollback()

            logging.exception(
                "Unload error"
            )

            flash(
                f"Error during unload: {e}",
                "danger"
            )

    return render_template(
        "unload.html",
        vehicle=vehicle,
        role=session.get("role"),
        user=session.get("user"),
        location=session.get("location"),
    )


# ============================================================
# OUTBOUND ENTRY
# SUPERVISOR ONLY
# ============================================================

# ============================================================
# OUTBOUND ENTRY
# SUPERVISOR ONLY
# ============================================================

@app.route("/outbound", methods=["POST"])
def outbound():

    if not require_login():
        return redirect(url_for("login"))

    if not is_supervisor():
        flash(
            "Unauthorized! Only Supervisor can create Outbound Entry.",
            "warning"
        )
        return redirect(url_for("index"))

    try:

        reg_no = request.form.get("reg_no", "").strip()
        vtype = request.form.get("type", "").strip()
        transporter = request.form.get("transporter", "").strip()
        supplier = request.form.get("supplier", "").strip()
        lr_number = request.form.get("lr_number", "").strip()
        contact_no = request.form.get("contact_no", "").strip()

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

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not reg_no:
            flash("Vehicle Reg No is required.", "danger")
            return redirect(url_for("index"))

        if not vtype:
            flash("Vehicle Type is required.", "danger")
            return redirect(url_for("index"))

        # ----------------------------------------------------
        # DOCK VALIDATION
        # ----------------------------------------------------

        if dock_number:

            try:
                dock_int = int(dock_number)

                if dock_int < 1 or dock_int > 16:
                    raise ValueError

            except ValueError:

                flash(
                    "Dock Assign Number must be between 1 and 16.",
                    "danger"
                )

                return redirect(url_for("index"))

        # ----------------------------------------------------
        # CREATE OUTBOUND VEHICLE
        # ----------------------------------------------------

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

            dock_number=dock_number,

            remarks=remarks,

            status="IN",

            check_in=now,

            check_out="",

            flow_type="OUTBOUND",

            security_checkin_by=None,

            supervisor_unload_by=None,

            unload_time=None,

            outbound_supervisor_by=session.get("user"),

            outbound_entry_time=now,

            outbound_remarks=remarks,

            checkout_by=None,

            location=session.get("location"),
        )

        # ----------------------------------------------------
        # SAVE TO DATABASE
        # ----------------------------------------------------

        db.session.add(vehicle)

        db.session.commit()

        flash(
            "Outbound vehicle entry submitted successfully by Supervisor.",
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

    return redirect(url_for("index"))

# ============================================================
# CHECK-OUT
# SECURITY ONLY FOR NORMAL OPERATIONS
# ADMIN CAN ALSO CHECK-OUT FOR ADMIN CONTROL
# ============================================================

@app.route("/checkout/<int:vid>")
def checkout(vid):
    if not require_login():
        return redirect(url_for("login"))

    if not (is_security() or is_admin()):
        flash(
            "Unauthorized! Only Security can Check-Out.",
            "warning"
        )
        return redirect(url_for("index"))

    try:
        vehicle = get_vehicle_for_current_user(vid)

        if vehicle is None:
            flash("Vehicle not found.", "danger")
            return redirect(url_for("index"))

        if vehicle.status != "IN":
            flash("Vehicle is already checked out.", "warning")
            return redirect(url_for("index"))

        # Inbound must be unloaded by Supervisor before checkout.
        if vehicle.flow_type == "INBOUND":
            if not vehicle.supervisor_unload_by or not vehicle.unload_time:
                flash(
                    "Inbound vehicle must be unloaded by Supervisor "
                    "before Security can Check-Out.",
                    "warning"
                )
                return redirect(url_for("index"))

        vehicle.status = "OUT"
        vehicle.check_out = current_time()
        vehicle.checkout_by = session.get("user")

        db.session.commit()

        flash(
            "Vehicle successfully checked out by Security!",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        logging.exception("Check-out error")
        flash(f"Error during check-out: {e}", "danger")

    return redirect(url_for("index"))


# ============================================================
# EXPORT CSV
# ADMIN + SUPERVISOR
# ============================================================

@app.route("/export")
def export():
    if not require_login():
        return redirect(url_for("login"))

    if session.get("role") not in ["admin", "supervisor"]:
        flash(
            "Unauthorized! Access denied.",
            "warning"
        )
        return redirect(url_for("index"))

    si = io.StringIO()
    cw = csv.writer(si)

    cw.writerow([
        "Entry ID",
        "Location",
        "Flow Type",
        "Reg. Number",
        "Type",
        "Transporter",
        "Supplier",
        "LR Number",
        "Contact No",
        "Driver Name",
        "Driver Mobile",
        "Invoice Number",
        "Invoice Qty",
        "Number Of Boxes",
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
        "Check-Out Time",
        "Check-Out By",
    ])

    if is_admin():
        vehicles = Vehicle.query.order_by(Vehicle.id.asc()).all()
    else:
        vehicles = Vehicle.query.filter_by(
            location=session.get("location")
        ).order_by(Vehicle.id.asc()).all()

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
            v.check_out,
            v.checkout_by,
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = (
        "attachment; filename=vehicle_log.csv"
    )
    output.headers["Content-type"] = "text/csv"

    return output


# ============================================================
# CHATBOT
# ============================================================

@app.route("/chatbot", methods=["POST"])
def chatbot():
    if not require_login():
        return jsonify({"answer": "Please login first."}), 401

    # Location restriction is applied here too.
    if is_admin():
        vehicles = Vehicle.query.all()
    else:
        vehicles = Vehicle.query.filter_by(
            location=session.get("location")
        ).all()

    data = request.get_json(silent=True) or {}
    query = data.get("query", "").lower().strip()

    total = len(vehicles)

    answer = "Sorry, I didn’t understand your question."

    if "total" in query and "vehicle" in query:
        answer = f"There are {total} vehicles in the system."

    elif "in" in query and "vehicle" in query:
        total_in = sum(
            1 for v in vehicles if v.status == "IN"
        )
        answer = f"Currently {total_in} vehicles are IN."

    elif "out" in query and "vehicle" in query:
        total_out = sum(
            1 for v in vehicles if v.status == "OUT"
        )
        answer = f"Currently {total_out} vehicles are OUT."

    elif "oldest" in query or "sabse purana" in query:
        try:
            oldest_in = min(
                (v for v in vehicles if v.check_in),
                key=lambda v: datetime.strptime(
                    v.check_in,
                    "%Y-%m-%d %H:%M:%S"
                )
            )
            answer = (
                f"The oldest check-in is "
                f"{oldest_in.reg_no} at {oldest_in.check_in}."
            )
        except ValueError:
            answer = (
                "Could not find the oldest check-in due to "
                "a data format issue."
            )
        except Exception:
            answer = "No vehicles with a check-in time found."

    elif "latest" in query or "sabse naya" in query:
        try:
            latest_in = max(
                (v for v in vehicles if v.check_in),
                key=lambda v: datetime.strptime(
                    v.check_in,
                    "%Y-%m-%d %H:%M:%S"
                )
            )
            answer = (
                f"The latest check-in is "
                f"{latest_in.reg_no} at {latest_in.check_in}."
            )
        except ValueError:
            answer = (
                "Could not find the latest check-in due to "
                "a data format issue."
            )
        except Exception:
            answer = "No vehicles with a check-in time found."

    else:
        for v in vehicles:
            if v.reg_no and v.reg_no.lower() in query:
                in_time = v.check_in or "N/A"
                out_time = v.check_out or "N/A"

                answer = (
                    f"Details for {v.reg_no}: "
                    f"Status = {v.status}, "
                    f"Check-in = {in_time}, "
                    f"Check-out = {out_time}, "
                    f"Type = {v.type or 'Unknown'}."
                )
                break

    return jsonify({"answer": answer})




# ============================================================
# START APPLICATION
# ============================================================

# Tables are created automatically when the application starts.
init_database()


if __name__ == "__main__":
    app.run(debug=True)
