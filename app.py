from flask import Flask, render_template, request, redirect, url_for, send_file, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import csv
import io
import pdfkit
import datetime
import matplotlib.pyplot as plt
import os
import uuid
import smtplib
from email.message import EmailMessage
import qrcode

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
db = SQLAlchemy(app)

# MODELS
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    group = db.Column(db.String(50))
    date = db.Column(db.Date, default=datetime.date.today)
    ders_qosulma = db.Column(db.Integer)
    ev_tapsirigi = db.Column(db.Integer)
    ders_hazirliq = db.Column(db.Integer)

    @property
    def average_score(self):
        return round((self.ders_qosulma + self.ev_tapsirigi + self.ders_hazirliq) / 3, 2)

# LOGIN SYSTEM
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# INDEX & CRUD
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = Evaluation.query
    student_name = request.args.get('student_name')
    group = request.args.get('group')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_score = request.args.get('min_score')

    if student_name:
        query = query.filter(Evaluation.student_name.contains(student_name))
    if group:
        query = query.filter_by(group=group)
    if date_from:
        query = query.filter(Evaluation.date >= datetime.datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Evaluation.date <= datetime.datetime.strptime(date_to, '%Y-%m-%d'))
    if min_score:
        query = query.filter((Evaluation.ders_qosulma + Evaluation.ev_tapsirigi + Evaluation.ders_hazirliq)/3 >= float(min_score))

    evaluations = query.all()
    return render_template('index.html', evaluations=evaluations)

@app.route('/add', methods=['POST'])
def add():
    name = request.form['student_name']
    group = request.form['group']
    date = request.form['date']
    ders_qosulma = int(request.form['ders_qosulma'])
    ev_tapsirigi = int(request.form['ev_tapsirigi'])
    ders_hazirliq = int(request.form['ders_hazirliq'])

    existing = Evaluation.query.filter_by(student_name=name, date=date).first()
    if existing:
        return redirect(url_for('index'))

    eval = Evaluation(student_name=name, group=group, date=date, ders_qosulma=ders_qosulma,
                      ev_tapsirigi=ev_tapsirigi, ders_hazirliq=ders_hazirliq)
    db.session.add(eval)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    eval = Evaluation.query.get_or_404(id)
    db.session.delete(eval)
    db.session.commit()
    return redirect(url_for('index'))

# EXPORTS
@app.route('/export/excel')
def export_excel():
    evaluations = Evaluation.query.all()
    df = pd.DataFrame([{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in evaluations])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, download_name='evaluations.xlsx', as_attachment=True)

@app.route('/export/csv')
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Group', 'Date', 'Ders Qosulma', 'Ev Tapsirigi', 'Ders Hazirliq'])
    for e in Evaluation.query.all():
        writer.writerow([e.id, e.student_name, e.group, e.date, e.ders_qosulma, e.ev_tapsirigi, e.ders_hazirliq])
    output.seek(0)
    return send_file(io.BytesIO(output.read().encode()), download_name="evaluations.csv", as_attachment=True)

@app.route('/export/pdf')
def export_pdf():
    evaluations = Evaluation.query.all()
    rendered = render_template('pdf_template.html', evaluations=evaluations)
    pdf = pdfkit.from_string(rendered, False)
    return send_file(io.BytesIO(pdf), download_name='evaluations.pdf', as_attachment=True)

# ANALYTICS & CHARTS
@app.route('/analytics')
def analytics():
    evaluations = Evaluation.query.all()
    student_names = list(set([e.student_name for e in evaluations]))
    student_averages = [
        round(sum(e.average_score for e in Evaluation.query.filter_by(student_name=name)) /
              Evaluation.query.filter_by(student_name=name).count(), 2)
        for name in student_names
    ]
    average_scores = {
        "ders_qosulma": round(sum(e.ders_qosulma for e in evaluations) / len(evaluations), 2),
        "ev_tapsirigi": round(sum(e.ev_tapsirigi for e in evaluations) / len(evaluations), 2),
        "ders_hazirliq": round(sum(e.ders_hazirliq for e in evaluations) / len(evaluations), 2),
        "overall": round(sum(e.average_score for e in evaluations) / len(evaluations), 2)
    }
    return render_template('analytics.html', analytics={
        "average_scores": average_scores,
        "student_names": student_names,
        "student_averages": student_averages
    })

# BACKUP
@app.route('/backup')
def backup():
    backup_name = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    db.session.commit()
    db.engine.execute(f"VACUUM INTO '{backup_name}'")
    return send_file(backup_name, as_attachment=True)

# EMAIL NOTIFY
def notify_low_performance(student, score):
    msg = EmailMessage()
    msg['Subject'] = 'Aşağı Performans Bildirişi'
    msg['From'] = 'admin@example.com'
    msg['To'] = 'teacher@example.com'
    msg.set_content(f"{student} tələbəsinin performansı aşağıdır: {score}")

    with smtplib.SMTP('smtp.example.com', 587) as smtp:
        smtp.starttls()
        smtp.login('admin@example.com', 'password')
        smtp.send_message(msg)

# QR CODE
@app.route('/qr/<int:id>')
def generate_qr(id):
    data = f"Tələbə ID: {id}"
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
