from flask import Flask, render_template, request, redirect, url_for
import csv
import os
from datetime import datetime

app = Flask(__name__)

# CSV faylının yolu
DATA_FOLDER = 'data'
CSV_FILE = os.path.join(DATA_FOLDER, 'evaluations.csv')
CSV_HEADERS = ['Tarix', 'Qrup', 'Tələbə Adı', 'Dərsə Qoşulma', 'Ev Tapşırığı', 'Dərsə Hazırlıq']

# Məlumat qovluğunu yarat (əgər yoxdursa)
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# CSV faylını yarat və başlıqları yaz (əgər yoxdursa)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADERS)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Qiymətləndirmə şkalasını burada təyin edək (məsələn, 1-5)
        # İstifadəçidən bu barədə soruşduqdan sonra dəqiqləşdirəcəyik.
        # Hələlik fərz edək ki, istifadəçi düzgün rəqəm daxil edir.
        
        tarix = request.form.get('tarix', datetime.now().strftime('%Y-%m-%d'))
        qrup = request.form.get('qrup')
        telebe_adi = request.form.get('telebe_adi')
        ders_qosulma = request.form.get('ders_qosulma')
        ev_tapsirigi = request.form.get('ev_tapsirigi')
        ders_hazirliq = request.form.get('ders_hazirliq')

        if qrup and telebe_adi and ders_qosulma and ev_tapsirigi and ders_hazirliq:
            new_data = [tarix, qrup, telebe_adi, ders_qosulma, ev_tapsirigi, ders_hazirliq]
            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(new_data)
            return redirect(url_for('index')) # Səhifəni yeniləyərək formu təmizlə

    # CSV-dən məlumatları oxu və göstər
    evaluations = []
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        header = next(reader) # Başlığı ötür
        for row in reader:
            evaluations.append(row)
    
    return render_template('index.html', evaluations=evaluations, headers=CSV_HEADERS)

if __name__ == '__main__':
    app.run(debug=True)