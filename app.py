import pandas as pd
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# 파일 업로드를 위한 디렉토리 설정
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# CSV 파일 정제 함수

def clean_amount(amount):
    if isinstance(amount, str):
        amount = amount.replace(',', '').strip()
    return amount

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'spo_file' not in request.files or 'fin_file' not in request.files:
        return jsonify({"error": "Both 'spo_file' and 'fin_file' are required."}), 400

    spo_file = request.files['spo_file']
    fin_file = request.files['fin_file']

    # 파일 저장
    spo_filename = secure_filename(spo_file.filename)
    fin_filename = secure_filename(fin_file.filename)

    spo_path = os.path.join(app.config['UPLOAD_FOLDER'], spo_filename)
    fin_path = os.path.join(app.config['UPLOAD_FOLDER'], fin_filename)

    spo_file.save(spo_path)
    fin_file.save(fin_path)

    try:
        # CSV 읽기
        df_spo = pd.read_csv(spo_path, encoding='utf-8')
        df_fin = pd.read_csv(fin_path, encoding='utf-8')

        # 정제 및 숫자 변환
        df_spo['amount_cleaned'] = df_spo['amount'].apply(clean_amount)
        df_fin['amount_cleaned'] = df_fin['amount'].apply(clean_amount)

        df_spo['amount_numeric'] = pd.to_numeric(df_spo['amount_cleaned'], errors='coerce')
        df_fin['amount_numeric'] = pd.to_numeric(df_fin['amount_cleaned'], errors='coerce')

        # 유효 데이터 필터링
        df_spo_clean = df_spo.dropna(subset=['amount_numeric'])
        df_fin_clean = df_fin.dropna(subset=['amount_numeric'])

        # 고객별 합계 계산
        spo_grouped = df_spo_clean.groupby('name')['amount_numeric'].sum().reset_index()
        fin_grouped = df_fin_clean.groupby('name')['amount_numeric'].sum().reset_index()

        # 병합 및 차이 계산
        comparison = pd.merge(fin_grouped, spo_grouped, on='name', how='outer', suffixes=('_fin', '_spo'))
        comparison['amount_numeric_spo'].fillna(0, inplace=True)
        comparison['amount_numeric_fin'].fillna(0, inplace=True)
        comparison['difference'] = comparison['amount_numeric_fin'] - comparison['amount_numeric_spo']

        # 차액 있는 데이터만 반환
        discrepancies = comparison[comparison['difference'] != 0]
        total_difference = discrepancies['difference'].sum()

        result = {
            "discrepancies": discrepancies.to_dict(orient='records'),
            "total_difference": total_difference
        }

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
