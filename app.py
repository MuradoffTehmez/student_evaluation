from flask import Flask, render_template, request, redirect, url_for
import csv
import os
from datetime import datetime

app = Flask(__name__)

# --- Parametrlər və Qlobal Dəyişənlər ---
DATA_FOLDER = 'data'  # Məlumatların saxlanacağı qovluğun adı
CSV_FILE = os.path.join(DATA_FOLDER, 'evaluations.csv') # CSV faylının tam yolu
CSV_HEADERS = ['Tarix', 'Qrup', 'Tələbə Adı', 'Dərsə Qoşulma', 'Ev Tapşırığı', 'Dərsə Hazırlıq']

# --- Başlanğıcda Qovluq və CSV Faylının Hazırlanması ---
# Məlumat qovluğunu yarat (əgər yoxdursa)
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# CSV faylını yarat və başlıqları yaz (əgər fayl yoxdursa və ya tamamilə boşdursa)
# Bu, proqramın hər dəfə işə düşdüyündə faylın düzgün formatda olmasını təmin edir.
if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADERS)
# --- Başlanğıc Hazırlığı Bitdi ---

@app.route('/', methods=['GET', 'POST'])
def index():
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    error_msg = None
    form_data_on_error = {} # Xəta zamanı formu yenidən doldurmaq üçün

    if request.method == 'POST':
        # Formdan məlumatları al
        tarix = request.form.get('tarix', today_date_str)
        qrup = request.form.get('qrup', '').strip()
        telebe_adi = request.form.get('telebe_adi', '').strip()
        ders_qosulma = request.form.get('ders_qosulma')
        ev_tapsirigi = request.form.get('ev_tapsirigi')
        ders_hazirliq = request.form.get('ders_hazirliq')

        # Sadə yoxlama (bütün sahələr doldurulubmu?)
        if qrup and telebe_adi and ders_qosulma and ev_tapsirigi and ders_hazirliq:
            new_data = [tarix, qrup, telebe_adi, ders_qosulma, ev_tapsirigi, ders_hazirliq]
            
            # Məlumat qovluğunun mövcudluğunu bir daha yoxla (əgər manual silinibsə)
            if not os.path.exists(DATA_FOLDER):
                os.makedirs(DATA_FOLDER)

            # CSV faylına yazma (əgər fayl yoxdursa/boşdursa başlıqla, əks halda əlavə et)
            is_new_or_empty_file = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0
            
            if is_new_or_empty_file:
                # Fayl yoxdur və ya boşdur, 'w' (write) ilə açaraq başlıqları və məlumatı yaz
                with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(CSV_HEADERS)
                    writer.writerow(new_data)
            else:
                # Fayl mövcuddur və içində məlumat var, 'a' (append) ilə açaraq yeni məlumatı əlavə et
                with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(new_data)
            
            return redirect(url_for('index')) # Uğurlu əlavədən sonra ana səhifəyə yönləndir
        else:
            error_msg = "Zəhmət olmasa, bütün sahələri düzgün doldurun."
            form_data_on_error = request.form # Xəta zamanı daxil edilmiş məlumatları saxla

    # ----- GET Sorğusu və ya POST Xətası Zamanı Məlumatların Oxunması və Göstərilməsi -----
    evaluations = []
    # CSV faylının mövcudluğunu və boş olmadığını yoxla
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            try:
                actual_header = next(reader) # Başlığı oxu
                # Başlığın düzgünlüyünü yoxla (istəyə bağlı)
                if actual_header != CSV_HEADERS:
                    app.logger.warning(
                        f"CSV başlığı uyğun deyil! Fayldakı başlıq: {actual_header}. Gözlənilən: {CSV_HEADERS}"
                    )
                    # Bu halda, ya məlumatları göstərmə, ya da xəta mesajı ver.
                    # Hələlik, fərz edirik ki, sütun sayı eynidirsə, məlumatlar oxuna bilər.
                    # Əgər sütun sayı fərqlidirsə, problem yarana bilər.

                for row in reader:
                    # Sətirin boş olmadığını və gözlənilən sayda sütuna malik olduğunu yoxla
                    if row and len(row) == len(CSV_HEADERS):
                        evaluations.append(row)
                    elif row: # Əgər sətir var amma formatı düzgün deyilsə (məsələn, sütun sayı fərqlidirsə)
                        app.logger.warning(f"Yanlış formatlı sətir ötürülür (sütun sayı uyğun deyil): {row}")
            except StopIteration:
                # Fayl yalnız başlıqdan ibarətdir və ya tamamilə boşdur (başlanğıc yoxlamasına baxmayaraq).
                app.logger.info("CSV faylında başlıqdan başqa məlumat tapılmadı və ya fayl boşdur.")
            except Exception as e:
                app.logger.error(f"CSV faylını oxuyarkən xəta baş verdi: {e}")
                error_msg = f"Məlumatları fayldan oxuyarkən xəta baş verdi: {e}"
    elif os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) == 0 and not error_msg:
        # Fayl var amma tamamilə boşdur (başlanğıcda başlıq yazılmayıbsa - bu olmamalıdır)
        error_msg = "Məlumat faylı boşdur. Başlıqlar yazılmayıb."
        app.logger.error("Məlumat faylı (evaluations.csv) mövcuddur amma tamamilə boşdur.")


    # Şablona ötürüləcək məlumatlar
    template_context = {
        'evaluations': evaluations,
        'headers': CSV_HEADERS,
        'today_date': today_date_str,
        'error_message': error_msg,
        'form_data': form_data_on_error # Xəta zamanı form məlumatlarını da ötür
    }
    
    return render_template('index.html', **template_context)

if __name__ == '__main__':
    app.run(debug=True) # debug=True test üçün yaxşıdır, amma real mühitdə False olmalıdır