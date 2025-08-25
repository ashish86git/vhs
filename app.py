from flask import Flask, render_template, request, redirect, url_for, make_response, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import matplotlib
import pytz
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import io
import csv

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
app.secret_key = "supersecret"

# ✅ Database Config (PostgreSQL)
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


# 🚚 Vehicle Table
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reg_no = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    transporter = db.Column(db.String(100))
    supplier = db.Column(db.String(100))
    lr_number = db.Column(db.String(100))
    contact_no = db.Column(db.String(15))   # ✅ NEW COLUMN

    load_unload = db.Column(db.String(50))  # Load / Unload
    remarks = db.Column(db.String(255))     # Remarks

    status = db.Column(db.String(10), default="IN")
    check_in = db.Column(db.String(50))
    check_out = db.Column(db.String(50))


# ✅ Hardcoded Users
USERS = {
    "admin": "admin123",
    "super": "test123"
}


# ---------- Helper Functions ----------
def filter_by_date_range(data, start_date, end_date):
    if not start_date or not end_date:
        return data
    filtered = []
    for v in data:
        if v.check_in:
            check_in = datetime.strptime(v.check_in, "%Y-%m-%d %H:%M:%S")
            if start_date <= check_in.date() <= end_date:
                filtered.append(v)
    return filtered


def get_summary():
    total_in = Vehicle.query.filter_by(status="IN").count()
    total_out = Vehicle.query.filter_by(status="OUT").count()
    total_status = Vehicle.query.count()
    return total_in, total_out, total_status


def generate_charts(daily_in, daily_out):
    all_days = sorted(set(daily_in.keys()) | set(daily_out.keys()))
    in_counts = [daily_in.get(d, 0) for d in all_days]
    out_counts = [daily_out.get(d, 0) for d in all_days]

    # ---- IN VEHICLES CHART ----
    fig1, ax1 = plt.subplots(figsize=(5, 3))
    ax1.plot(all_days, in_counts, marker='o', linestyle='-', color='green', linewidth=2)
    ax1.set_title("Daily Check-Ins")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Count")
    ax1.grid(True, linestyle="--", alpha=0.6)

    buf1 = io.BytesIO()
    plt.tight_layout()
    fig1.savefig(buf1, format="png")
    buf1.seek(0)
    chart_in = base64.b64encode(buf1.getvalue()).decode("utf-8")
    plt.close(fig1)

    # ---- OUT VEHICLES CHART ----
    fig2, ax2 = plt.subplots(figsize=(5, 3))
    ax2.plot(all_days, out_counts, marker='o', linestyle='-', color='red', linewidth=2)
    ax2.set_title("Daily Check-Outs")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Count")
    ax2.grid(True, linestyle="--", alpha=0.6)

    buf2 = io.BytesIO()
    plt.tight_layout()
    fig2.savefig(buf2, format="png")
    buf2.seek(0)
    chart_out = base64.b64encode(buf2.getvalue()).decode("utf-8")
    plt.close(fig2)

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
        if userid in USERS and USERS[userid] == password:
            session['user'] = userid
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/index')
def index():
    if "user" not in session:
        return redirect(url_for('login'))

    search_query = request.args.get('search', '').strip()
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    # ✅ Order by ID
    vehicles = Vehicle.query.order_by(Vehicle.id.asc()).all()
    filtered = filter_by_date_range(vehicles, start_date, end_date)

    if search_query:
        filtered = [v for v in filtered if search_query in v.reg_no]

    daily_in, daily_out = {}, {}
    for v in filtered:
        date_str = v.check_in.split(" ")[0] if v.check_in else None
        if date_str:
            if v.status == "IN":
                daily_in[date_str] = daily_in.get(date_str, 0) + 1
            elif v.status == "OUT":
                daily_out[date_str] = daily_out.get(date_str, 0) + 1

    chart_in, chart_out = generate_charts(daily_in, daily_out) if filtered else (None, None)
    total_in, total_out, total_status = get_summary()

    return render_template(
        'index.html',
        vehicles=filtered,
        total_in=total_in,
        total_out=total_out,
        total_status=total_status,
        chart_in=chart_in,
        chart_out=chart_out,
        start_date=start_date_str,
        end_date=end_date_str,
        user=session['user']
    )


@app.route('/checkin', methods=['POST'])
def checkin():
    if "user" not in session:
        return redirect(url_for('login'))

    reg_no = request.form['reg_no']
    vtype = request.form['type']
    transporter = request.form['transporter']
    supplier = request.form['supplier']
    lr_number = request.form['lr_number']
    contact_no = request.form['contact_no']  # ✅ new
    load_unload = request.form.get('load_unload', '')
    remarks = request.form.get('remarks', '')

    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    vehicle = Vehicle(
        reg_no=reg_no,
        type=vtype,
        transporter=transporter,
        supplier=supplier,
        lr_number=lr_number,
        contact_no=contact_no,   # ✅ save contact
        load_unload=load_unload,
        remarks=remarks,
        status="IN",
        check_in=now,
        check_out=""
    )
    db.session.add(vehicle)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/checkout/<int:vid>')
def checkout(vid):
    if "user" not in session:
        return redirect(url_for('login'))

    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    vehicle = Vehicle.query.get(vid)
    if vehicle and vehicle.status == "IN":
        vehicle.status = "OUT"
        vehicle.check_out = now
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/export')
def export():
    if "user" not in session:
        return redirect(url_for('login'))

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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
