from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
import csv
import os
import pandas as pd
from datetime import datetime
from collections import defaultdict, Counter
import json
from io import BytesIO
import xlsxwriter
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Flash mesajları üçün

# --- Parametrlər və Qlobal Dəyişənlər ---
DATA_FOLDER = 'data'
CSV_FILE = os.path.join(DATA_FOLDER, 'evaluations.csv')
CSV_HEADERS = ['Tarix', 'Qrup', 'Tələbə Adı', 'Dərsə Qoşulma', 'Ev Tapşırığı', 'Dərsə Hazırlıq']
UPLOAD_FOLDER = os.path.join(DATA_FOLDER, 'uploads')

# Qovluqları yarat
for folder in [DATA_FOLDER, UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# CSV faylını hazırla
if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADERS)

def read_evaluations():
    """CSV faylından məlumatları oxuyur"""
    evaluations = []
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        try:
            with open(CSV_FILE, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Başlığı keç
                for row in reader:
                    if row and len(row) == len(CSV_HEADERS):
                        evaluations.append(row)
        except Exception as e:
            app.logger.error(f"CSV oxuma xətası: {e}")
    return evaluations

def calculate_analytics(evaluations):
    """Analitika hesablamalarını edir"""
    if not evaluations:
        return {}
    
    # DataFrame yaradırıq
    df = pd.DataFrame(evaluations, columns=CSV_HEADERS)
    
    # Rəqəmsal sütunları çeviririk
    numeric_cols = ['Dərsə Qoşulma', 'Ev Tapşırığı', 'Dərsə Hazırlıq']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Ümumi ortalama
    df['Ümumi Ortalama'] = df[numeric_cols].mean(axis=1).round(2)
    
    # Analitika hesablamaları
    analytics = {
        'total_evaluations': len(df),
        'total_students': df['Tələbə Adı'].nunique(),
        'total_groups': df['Qrup'].nunique(),
        'average_scores': {
            'ders_qosulma': df['Dərsə Qoşulma'].mean().round(2),
            'ev_tapsirigi': df['Ev Tapşırığı'].mean().round(2),
            'ders_hazirliq': df['Dərsə Hazırlıq'].mean().round(2),
            'overall': df['Ümumi Ortalama'].mean().round(2)
        },
        'group_stats': {},
        'student_stats': {},
        'top_students': [],
        'low_performers': []
    }
    
    # Qrup statistikaları
    for group in df['Qrup'].unique():
        group_data = df[df['Qrup'] == group]
        analytics['group_stats'][group] = {
            'count': len(group_data),
            'average': group_data['Ümumi Ortalama'].mean().round(2),
            'students': group_data['Tələbə Adı'].nunique()
        }
    
    # Tələbə statistikaları
    student_groups = df.groupby('Tələbə Adı')
    for student, data in student_groups:
        avg_score = data['Ümumi Ortalama'].mean()
        analytics['student_stats'][student] = {
            'evaluations_count': len(data),
            'average_score': round(avg_score, 2),
            'last_evaluation': data['Tarix'].iloc[-1],
            'group': data['Qrup'].iloc[-1]
        }
    
    # Ən yaxşı və ən aşağı performans göstərən tələbələr
    sorted_students = sorted(analytics['student_stats'].items(), 
                           key=lambda x: x[1]['average_score'], reverse=True)
    
    analytics['top_students'] = sorted_students[:5]
    analytics['low_performers'] = sorted_students[-5:] if len(sorted_students) >= 5 else []
    
    return analytics

def filter_evaluations(evaluations, filters):
    """Məlumatları filtrlər"""
    if not evaluations or not filters:
        return evaluations
    
    filtered = []
    for row in evaluations:
        include = True
        
        # Tələbə adı filtri
        if filters.get('student_name'):
            if filters['student_name'].lower() not in row[2].lower():
                include = False
        
        # Qrup filtri
        if filters.get('group'):
            if filters['group'].lower() not in row[1].lower():
                include = False
        
        # Tarix filtri
        if filters.get('date_from') or filters.get('date_to'):
            row_date = datetime.strptime(row[0], '%Y-%m-%d')
            
            if filters.get('date_from'):
                from_date = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                if row_date < from_date:
                    include = False
            
            if filters.get('date_to'):
                to_date = datetime.strptime(filters['date_to'], '%Y-%m-%d')
                if row_date > to_date:
                    include = False
        
        # Minimum bal filtri
        if filters.get('min_score'):
            try:
                scores = [float(row[3]), float(row[4]), float(row[5])]
                avg_score = sum(scores) / len(scores)
                if avg_score < float(filters['min_score']):
                    include = False
            except ValueError:
                pass
        
        if include:
            filtered.append(row)
    
    return filtered

@app.route('/', methods=['GET', 'POST'])
def index():
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    error_msg = None
    form_data_on_error = {}

    if request.method == 'POST':
        # Form məlumatlarını al
        tarix = request.form.get('tarix', today_date_str)
        qrup = request.form.get('qrup', '').strip()
        telebe_adi = request.form.get('telebe_adi', '').strip()
        ders_qosulma = request.form.get('ders_qosulma')
        ev_tapsirigi = request.form.get('ev_tapsirigi')
        ders_hazirliq = request.form.get('ders_hazirliq')

        if qrup and telebe_adi and ders_qosulma and ev_tapsirigi and ders_hazirliq:
            new_data = [tarix, qrup, telebe_adi, ders_qosulma, ev_tapsirigi, ders_hazirliq]
            
            try:
                with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(new_data)
                flash('Qiymətləndirmə uğurla əlavə edildi!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                error_msg = f"Məlumat əlavə edilərkən xəta: {e}"
        else:
            error_msg = "Bütün sahələri doldurun."
            form_data_on_error = request.form

    # Filtrlər
    filters = {
        'student_name': request.args.get('student_name', ''),
        'group': request.args.get('group', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
        'min_score': request.args.get('min_score', '')
    }

    # Məlumatları oxu və filtrlə
    all_evaluations = read_evaluations()
    filtered_evaluations = filter_evaluations(all_evaluations, filters)
    
    # Analitika hesabla
    analytics = calculate_analytics(all_evaluations)

    return render_template('index.html',
                         evaluations=filtered_evaluations,
                         headers=CSV_HEADERS,
                         today_date=today_date_str,
                         error_message=error_msg,
                         form_data=form_data_on_error,
                         analytics=analytics,
                         filters=filters)

@app.route('/analytics')
def analytics_page():
    """Ayrıca analitika səhifəsi"""
    evaluations = read_evaluations()
    analytics = calculate_analytics(evaluations)
    return render_template('analytics.html', analytics=analytics)

@app.route('/export/csv')
def export_csv():
    """CSV export"""
    try:
        return send_file(CSV_FILE, 
                        as_attachment=True, 
                        download_name=f'evaluations_{datetime.now().strftime("%Y%m%d")}.csv')
    except Exception as e:
        flash(f'Export xətası: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/export/excel')
def export_excel():
    """Excel export"""
    try:
        evaluations = read_evaluations()
        analytics = calculate_analytics(evaluations)
        
        # Excel faylı yarat
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Məlumatlar səhifəsi
        worksheet_data = workbook.add_worksheet('Qiymətləndirmələr')
        
        # Başlıqları yaz
        for col, header in enumerate(CSV_HEADERS):
            worksheet_data.write(0, col, header)
        
        # Məlumatları yaz
        for row, evaluation in enumerate(evaluations, 1):
            for col, value in enumerate(evaluation):
                worksheet_data.write(row, col, value)
        
        # Analitika səhifəsi
        worksheet_analytics = workbook.add_worksheet('Analitika')
        
        row = 0
        worksheet_analytics.write(row, 0, 'Ümumi Statistika')
        row += 1
        worksheet_analytics.write(row, 0, 'Ümumi qiymətləndirmələr:')
        worksheet_analytics.write(row, 1, analytics.get('total_evaluations', 0))
        row += 1
        worksheet_analytics.write(row, 0, 'Ümumi tələbələr:')
        worksheet_analytics.write(row, 1, analytics.get('total_students', 0))
        row += 1
        worksheet_analytics.write(row, 0, 'Ümumi qruplar:')
        worksheet_analytics.write(row, 1, analytics.get('total_groups', 0))
        
        workbook.close()
        output.seek(0)
        
        return send_file(output,
                        as_attachment=True,
                        download_name=f'evaluations_report_{datetime.now().strftime("%Y%m%d")}.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    except Exception as e:
        flash(f'Excel export xətası: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/import', methods=['POST'])
def import_data():
    """CSV faylından məlumat import et"""
    if 'file' not in request.files:
        flash('Fayl seçilməyib', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Fayl seçilməyib', 'error')
        return redirect(url_for('index'))
    
    if file and file.filename.lower().endswith('.csv'):
        try:
            # Faylı müvəqqəti olaraq saxla
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # CSV-ni oxu və yoxla
            imported_count = 0
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                # Başlığı yoxla
                if header != CSV_HEADERS:
                    flash(f'CSV başlıqları uyğun deyil. Gözlənilən: {CSV_HEADERS}', 'error')
                    os.remove(filepath)
                    return redirect(url_for('index'))
                
                # Məlumatları əlavə et
                with open(CSV_FILE, 'a', newline='', encoding='utf-8') as main_file:
                    writer = csv.writer(main_file)
                    for row in reader:
                        if row and len(row) == len(CSV_HEADERS):
                            writer.writerow(row)
                            imported_count += 1
            
            os.remove(filepath)  # Müvəqqəti faylı sil
            flash(f'{imported_count} qeyd uğurla import edildi!', 'success')
            
        except Exception as e:
            flash(f'Import xətası: {e}', 'error')
    else:
        flash('Yalnız CSV faylları dəstəklənir', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/analytics')
def api_analytics():
    """Analitika məlumatlarını JSON formatında qaytarır"""
    evaluations = read_evaluations()
    analytics = calculate_analytics(evaluations)
    return jsonify(analytics)
def analytics_page():
    # Burada analytics məlumatlarınızı yaradırsınız
    analytics = {
        "total_evaluations": 120,
        "total_students": 30,
        "total_groups": 5,
        "average_scores": {
            "ders_qosulma": 80,
            "ev_tapsirigi": 75,
            "ders_hazirliq": 70,
            "overall": 75
        },
        "student_names": ["Elvin", "Leyla", "Murad"],
        "student_averages": [85, 78, 69]
    }
if __name__ == '__main__':
    app.run(debug=True)
    