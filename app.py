from flask import Flask, render_template, request, redirect, url_for, make_response, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from datetime import timedelta
import plotly.graph_objects as go
import pytz
import io
import csv
import logging

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
app.secret_key = "supersecret"

# Database Config (PostgreSQL)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user='u7tqojjihbpn7s',
        password='p1b1897f6356bab4e52b727ee100290a84e4bf71d02e064e90c2c705bfd26f4a5',
        host='c7s7ncbk19n97r.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com',
        port=5432,
        database='d8lp4hr6fmvb9m'
    )
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Vehicle Table
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reg_no = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    transporter = db.Column(db.String(100))
    supplier = db.Column(db.String(100))
    lr_number = db.Column(db.String(100))
    contact_no = db.Column(db.String(15))
    load_unload = db.Column(db.String(50))
    remarks = db.Column(db.String(255))
    status = db.Column(db.String(10), default="IN")
    check_in = db.Column(db.String(50))
    check_out = db.Column(db.String(50))


# Hardcoded Users with Roles
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "super": {"password": "test123", "role": "supervisor"},
    "lifelong": {"password": "lifelong123", "role": "lifelong"}
}


# ---------- Helper Functions ----------
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
                check_in_time = datetime.strptime(v.check_in, "%Y-%m-%d %H:%M:%S")
                check_out_time = datetime.strptime(v.check_out, "%Y-%m-%d %H:%M:%S")
                diff = check_out_time - check_in_time
                if diff > timedelta(hours=48):
                    over_48hrs += 1
            except ValueError:
                logging.error(f"Error parsing date for vehicle ID: {v.id}")

    return total_in, total_out, total_status, over_48hrs


def generate_charts(daily_in, daily_out):
    """Generates Plotly charts as HTML strings."""
    all_days = sorted(list(set(daily_in.keys()) | set(daily_out.keys())))
    in_counts = [daily_in.get(d, 0) for d in all_days]
    out_counts = [daily_out.get(d, 0) for d in all_days]

    fig_in = go.Figure()
    fig_in.add_trace(go.Scatter(
        x=all_days,
        y=in_counts,
        mode='lines+markers',
        marker=dict(color='green', size=8),
        line=dict(width=2),
        hovertemplate="Date: %{x}<br>Check-Ins: %{y}<extra></extra>"
    ))
    fig_in.update_layout(title="Daily Check-Ins", xaxis_title="Date", yaxis_title="Count", template="plotly_white",
                         margin=dict(l=40, r=40, t=40, b=80))
    chart_in = fig_in.to_html(full_html=False)

    fig_out = go.Figure()
    fig_out.add_trace(go.Scatter(
        x=all_days,
        y=out_counts,
        mode='lines+markers',
        marker=dict(color='red', size=8),
        line=dict(width=2),
        hovertemplate="Date: %{x}<br>Check-Outs: %{y}<extra></extra>"
    ))
    fig_out.update_layout(title="Daily Check-Outs", xaxis_title="Date", yaxis_title="Count", template="plotly_white",
                          margin=dict(l=40, r=40, t=40, b=80))
    chart_out = fig_out.to_html(full_html=False)

    return chart_in, chart_out


# ---------- Routes ----------
@app.route('/')
def home():
    if "user" in session:
        return redirect(url_for('index'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        userid = request.form['userid']
        password = request.form['password']
        if userid in USERS and USERS[userid]["password"] == password:
            session['user'] = userid
            session['role'] = USERS[userid]["role"]
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('login'))


@app.route('/index')
def index():
    if "user" not in session:
        return redirect(url_for('login'))

    # Get all filter parameters from the request
    reg_no = request.args.get('reg', '').strip().lower()
    transporter = request.args.get('transporter', '').strip().lower()
    supplier = request.args.get('supplier', '').strip().lower()
    load_unload = request.args.get('load_unload', '').strip().lower()
    status = request.args.get('status', '').strip().lower()
    from_date_str = request.args.get('from_date', '')
    to_date_str = request.args.get('to_date', '')

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    ROWS_PER_PAGE = 20

    # Build the base query
    vehicles_query = Vehicle.query.order_by(Vehicle.id.desc())

    # Apply filters dynamically
    if reg_no:
        vehicles_query = vehicles_query.filter(Vehicle.reg_no.ilike(f"%{reg_no}%"))
    if transporter:
        vehicles_query = vehicles_query.filter(Vehicle.transporter.ilike(f"%{transporter}%"))
    if supplier:
        vehicles_query = vehicles_query.filter(Vehicle.supplier.ilike(f"%{supplier}%"))
    if load_unload:
        vehicles_query = vehicles_query.filter(Vehicle.load_unload.ilike(f"%{load_unload}%"))
    if status:
        vehicles_query = vehicles_query.filter(Vehicle.status.ilike(f"%{status}%"))

    # Date filter
    if from_date_str:
        start_dt = datetime.strptime(from_date_str, '%Y-%m-%d')
        vehicles_query = vehicles_query.filter(Vehicle.check_in >= start_dt.strftime('%Y-%m-%d %H:%M:%S'))
    if to_date_str:
        end_dt = datetime.strptime(to_date_str, '%Y-%m-%d') + timedelta(days=1)
        vehicles_query = vehicles_query.filter(Vehicle.check_in <= end_dt.strftime('%Y-%m-%d %H:%M:%S'))

    # Get the total count of filtered results for pagination and summary
    total_filtered_vehicles = vehicles_query.count()
    total_pages = (total_filtered_vehicles + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE

    # Apply pagination to the query
    vehicles = vehicles_query.limit(ROWS_PER_PAGE).offset((page - 1) * ROWS_PER_PAGE).all()

    # Get all filtered vehicles for summary and charts
    all_filtered_vehicles = vehicles_query.all()

    # Calculate daily trends for charts from the all filtered data
    daily_in, daily_out = {}, {}
    for v in all_filtered_vehicles:
        if v.check_in:
            date_str = v.check_in.split(" ")[0]
            if v.status == "IN":
                daily_in[date_str] = daily_in.get(date_str, 0) + 1
            elif v.status == "OUT":
                daily_out[date_str] = daily_out.get(date_str, 0) + 1

    chart_in, chart_out = generate_charts(daily_in, daily_out)

    # Calculate summary based on the all filtered data
    total_in, total_out, total_status, over_48hrs = get_summary(all_filtered_vehicles)

    return render_template(
        'index.html',
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
        user=session['user'],
        role=session['role'],
        current_year=datetime.now(IST).year
    )


# ---------- Restricted Routes for Admin Only ----------
@app.route('/checkin', methods=['POST'])
def checkin():
    if "user" not in session:
        return redirect(url_for('login'))
    if session.get("role") != "admin":
        flash("Unauthorized! Read-only access.", "warning")
        return redirect(url_for('index'))

    try:
        reg_no = request.form['reg_no']
        vtype = request.form['type']
        transporter = request.form['transporter']
        supplier = request.form['supplier']
        lr_number = request.form['lr_number']
        contact_no = request.form['contact_no']
        load_unload = request.form.get('load_unload', '')
        remarks = request.form.get('remarks', '')

        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
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
            check_out=""
        )
        db.session.add(vehicle)
        db.session.commit()
        flash("Vehicle successfully checked in!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error during check-in: {e}", "danger")

    return redirect(url_for('index'))


@app.route('/checkout/<int:vid>')
def checkout(vid):
    if "user" not in session:
        return redirect(url_for('login'))
    if session.get("role") != "admin":
        flash("Unauthorized! Read-only access.", "warning")
        return redirect(url_for('index'))

    try:
        vehicle = Vehicle.query.get_or_404(vid)
        if vehicle.status == "IN":
            vehicle.status = "OUT"
            vehicle.check_out = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            db.session.commit()
            flash("Vehicle successfully checked out!", "success")
        else:
            flash("Vehicle is already checked out.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error during check-out: {e}", "danger")
    return redirect(url_for('index'))


@app.route('/export')
def export():
    if "user" not in session:
        return redirect(url_for('login'))
    if session.get("role") not in ["admin", "supervisor"]:
        flash("Unauthorized! Access denied.", "warning")
        return redirect(url_for('index'))

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Entry ID", "Reg. Number", "Type", "Transporter", "Supplier",
        "LR Number", "Contact No", "Load/Unload", "Status", "Remarks",
        "Check-In Time", "Check-Out Time"
    ])

    for v in Vehicle.query.order_by(Vehicle.id.asc()).all():
        cw.writerow([
            v.id, v.reg_no, v.type, v.transporter, v.supplier,
            v.lr_number, v.contact_no, v.load_unload, v.status,
            v.remarks, v.check_in, v.check_out
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=vehicle_log.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    query = data.get("query", "").lower().strip()

    vehicles = Vehicle.query.all()
    total = len(vehicles)

    answer = "Sorry, I didn’t understand your question."

    # Generic Queries
    if "total" in query and "vehicle" in query:
        answer = f"There are {total} vehicles in the system."
    elif "in" in query and "vehicle" in query:
        total_in = sum(1 for v in vehicles if v.status == "IN")
        answer = f"Currently {total_in} vehicles are IN."
    elif "out" in query and "vehicle" in query:
        total_out = sum(1 for v in vehicles if v.status == "OUT")
        answer = f"Currently {total_out} vehicles are OUT."
    elif "oldest" in query or "sabse purana" in query:
        try:
            oldest_in = min((v for v in vehicles if v.check_in),
                            key=lambda v: datetime.strptime(v.check_in, "%Y-%m-%d %H:%M:%S"))
            answer = f"The oldest check-in is {oldest_in.reg_no} at {oldest_in.check_in}."
        except ValueError:
            answer = "Could not find the oldest check-in due to a data format issue."
        except Exception:
            answer = "No vehicles with a check-in time found."
    elif "latest" in query or "sabse naya" in query:
        try:
            latest_in = max((v for v in vehicles if v.check_in),
                            key=lambda v: datetime.strptime(v.check_in, "%Y-%m-%d %H:%M:%S"))
            answer = f"The latest check-in is {latest_in.reg_no} at {latest_in.check_in}."
        except ValueError:
            answer = "Could not find the latest check-in due to a data format issue."
        except Exception:
            answer = "No vehicles with a check-in time found."

    # Specific Vehicle Queries (by registration number)
    else:
        for v in vehicles:
            if v.reg_no and v.reg_no.lower() in query:
                in_time = v.check_in if v.check_in else "N/A"
                out_time = v.check_out if v.check_out else "N/A"
                answer = (
                    f"Details for {v.reg_no}: "
                    f"Status = {v.status}, "
                    f"Check-in = {in_time}, "
                    f"Check-out = {out_time}, "
                    f"Type = {v.type or 'Unknown'}."
                )
                break
    return jsonify({"answer": answer})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
