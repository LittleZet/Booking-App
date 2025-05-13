from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()
db_url = os.environ.get('DATABASE_URL')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url  # Supabase DB URL here
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    email = db.Column(db.String, primary_key=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, db.ForeignKey('user.email'))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.String)
    color = db.Column(db.String)

@app.route('/')
def index():
    user = request.args.get("user")
    if not user:
        return redirect(url_for('login'))
    bookings = Booking.query.order_by(Booking.start_time).all()
    return render_template("index.html", bookings=bookings)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        if User.query.get(email):
            return redirect(url_for('index', user=email))
        return "Unauthorized email", 403
    return render_template("login.html")

@app.route('/book', methods=['POST'])
def book():
    email = request.form['email']
    start = datetime.fromisoformat(request.form['start'])
    end = datetime.fromisoformat(request.form['end'])
    purpose = request.form['usage']
    color = request.form['color']


    # Rule 1: Overlap Check
    overlaps = Booking.query.filter(
        Booking.end_time > start,
        Booking.start_time < end
    ).count()
    if overlaps > 0:
        return "Booking overlaps with existing session", 400

    # Rule 2: 3-day limit & cooldown
    existing = Booking.query.order_by(Booking.start_time).all()
    total_session = timedelta(0)
    last_end = None

    for b in existing:
        if b.end_time <= start:
            total_session = timedelta(0)
            continue
        if b.start_time >= end:
            break
        # Session contributes to continuous use
        if last_end and (b.start_time - last_end > timedelta(hours=12)):
            total_session = timedelta(0)
        total_session += b.end_time - b.start_time
        last_end = b.end_time
        if total_session >= timedelta(hours=72):
            cooldown_end = b.end_time + timedelta(hours=12)
            if start < cooldown_end:
                return "Cooldown in progress. Try later.", 400

    booking = Booking(email=email, 
                      start_time=start, 
                      end_time=end,
                      purpose=purpose,
                      color=color)
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for('index', user=email))

@app.route('/remove/<int:booking_id>', methods=['POST'])
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    email = request.args.get('user_email') or request.form.get('email')  # depends on frontend

    if booking.email != email:
        return "Unauthorized", 403

    db.session.delete(booking)
    db.session.commit()
    return '', 204  # No Content

