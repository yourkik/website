import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
from datetime import datetime
import json

# .env 파일의 내용을 환경변수로 불러옵니다.
load_dotenv()

# 데이터베이스 연결 함수
def get_db_connection():
    # 디버깅: 연결 전에 값이 제대로 들어왔는지 눈으로 확인 (확인 후 삭제하세요)
    print("----- DB 접속 정보 확인 -----")
    print(f"Host: {os.getenv('DB_HOST')}")
    print(f"User: {os.getenv('DB_USER')}")
    # print(f"PW: {os.getenv('DB_PASSWORD')}") # 비밀번호는 보안상 주석처리
    print("----------------------------")

    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require' 
        )
        conn.autocommit = True
        print("✅ DB 연결 성공!")
        return conn
    except Exception as e:
        print("❌ DB 연결 실패:", e)
        return None

app = Flask(__name__)

# # 로컬 환경에서는 .env를 읽고, Azure에서는 패스.
# if os.path.exists('.env'):
#     load_dotenv()
# app.secret_key = os.urandom(24)

# # 데이터베이스 연결 함수
# def get_db_connection():
#     conn = psycopg2.connect(
#         host=os.getenv('DB_HOST'),
#         port=os.getenv('DB_PORT'),
#         dbname=os.getenv('DB_NAME'),
#         user=os.getenv('DB_USER'),
#         password=os.getenv('DB_PASSWORD'),
#         sslmode='require' #Azure를 위해 반드시 추가
#     )
#     print('get_db_connection', conn)
#     conn.autocommit = True
#     return conn

@app.route('/')
def index():
    # 1. 데이터 베이스에 접속
    conn = get_db_connection()
    print('get_db_connection', conn)
    cursor = conn.cursor(cursor_factory=DictCursor)
    # 2. SELECT
    cursor.execute("SELECT id, title, author, created_at, view_count, like_count FROM board.posts ORDER BY created_at DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    # 3. index.html 파일에 변수로 넘겨주기
    return render_template('index.html', posts = posts)

@app.route('/create/', methods=['GET'] )
def create_form():
    return render_template('create.html')

@app.route('/create/',methods=['POST']  )
def create_post():
    #1. 폼에 있는 정보들을 get
    title = request.form.get('title')
    author = request.form.get('author')
    content = request.form.get('content')

    if not title or not author or not content:
        flash('모든 필드를 똑바로 채워주세요!!!!')
        return redirect(url_for('create_form'))
    
    # 1. 데이터 베이스에 접속
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    # 2. INSERT
    cursor.execute("INSERT INTO board.posts (title, author, content) VALUES (%s, %s, %s) RETURNING id", (title,author,content ))
    post_id = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    flash('게시글이 성공적으로 등록되었음')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/<int:post_id>')
def view_post(post_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute('UPDATE board.posts SET view_count = view_count + 1 WHERE id = %s', (post_id,))
    
    cursor.execute('SELECT * FROM board.posts WHERE id = %s', (post_id,))
    post = cursor.fetchone()
    
    if post is None:
        cursor.close()
        conn.close()
        flash('게시글을 찾을 수 없습니다.')
        return redirect(url_for('index'))
    
    cursor.execute('SELECT * FROM board.comments WHERE post_id = %s ORDER BY created_at', (post_id,))
    comments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    user_ip = request.remote_addr
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))
    liked = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    
    return render_template('view.html', post=post, comments=comments, liked=liked)

@app.route('/edit/<int:post_id>', methods=['GET'])
def edit_form(post_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM board.posts WHERE id = %s', (post_id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if post is None:
        flash('게시글을 찾을 수 없습니다.')
        return redirect(url_for('index'))
    
    return render_template('edit.html', post=post)

@app.route('/edit/<int:post_id>', methods=['POST'])
def edit_post(post_id):
    title = request.form.get('title')
    content = request.form.get('content')
    
    if not title or not content:
        flash('제목과 내용을 모두 입력해주세요.')
        return redirect(url_for('edit_form', post_id=post_id))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE board.posts SET title = %s, content = %s, updated_at = %s WHERE id = %s',
        (title, content, datetime.now(), post_id)
    )
    cursor.close()
    conn.close()
    
    flash('게시글이 성공적으로 수정되었습니다.')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM board.posts WHERE id = %s', (post_id,))
    cursor.close()
    conn.close()
    
    flash('게시글이 성공적으로 삭제되었습니다.')
    return redirect(url_for('index'))

@app.route('/post/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    author = request.form.get('author')
    content = request.form.get('content')
    
    if not author or not content:
        flash('작성자와 내용을 모두 입력해주세요.')
        return redirect(url_for('view_post', post_id=post_id))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO board.comments (post_id, author, content) VALUES (%s, %s, %s)',
        (post_id, author, content)
    )
    cursor.close()
    conn.close()
    
    flash('댓글이 등록되었습니다.')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    user_ip = request.remote_addr
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))
    already_liked = cursor.fetchone()[0] > 0
    
    if already_liked:
        cursor.execute('DELETE FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))
        cursor.execute('UPDATE board.posts SET like_count = like_count - 1 WHERE id = %s', (post_id,))
        message = '좋아요가 취소되었습니다.'
    else:
        cursor.execute('INSERT INTO board.likes (post_id, user_ip) VALUES (%s, %s)', (post_id, user_ip))
        cursor.execute('UPDATE board.posts SET like_count = like_count + 1 WHERE id = %s', (post_id,))
        message = '좋아요가 등록되었습니다.'
    
    cursor.close()
    conn.close()   
    flash(message)
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/fms_result')
def fms_result():
    # 1. 데이터 베이스에 접속
    conn = get_db_connection()
    print('get_db_connection', conn)
    cursor = conn.cursor(cursor_factory=DictCursor)
    # 2. SELECT
    cursor.execute("SELECT * FROM fms.v_chick_report ORDER BY 육계번호 DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    # 3. fms_result.html 파일에 변수로 넘겨주기
    return render_template('fms_result.html', results = posts)


#################################################################################
# 통계 페이지 추가
#################################################################################
import matplotlib
matplotlib.use('Agg')  # [중요] 서버에서 GUI 창이 뜨지 않도록 백엔드 설정

import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import pandas as pd
import re
from flask import Flask, render_template


import numpy as np
from scipy.stats import norm # 정규분포 곡선 계산용

def create_plot(df):
    # 1. 한글 폰트 설정 (Windows 기준)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    
    # 2. 그래프 그리기 (예: 품종별 무게 Boxplot)
    plt.figure(figsize=(10, 6))
    sns.boxplot(x='breed_name', y='raw_weight_num', data=df, palette='Set3')
    plt.title('품종별 무게 분포 (Box Plot)')
    plt.grid(True, alpha=0.3)
    
    # 3. 이미지를 메모리에 저장 (파일로 저장 X)
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    
    # 4. Base64 문자열로 변환
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close() # 메모리 해제
    
    return plot_url

# @app.route('/statistics')
# def statistics():
#     conn = get_db_connection()
    
#     # --- [기존] 1. 품종별 무게 데이터 조회 ---
#     query_weight = """
#     SELECT C.code_desc AS breed_name, B.raw_weight
#     FROM fms.chick_info A
#     JOIN fms.prod_result B ON A.chick_no = B.chick_no
#     JOIN fms.master_code C ON A.breeds = C.code
#     """
#     df_weight = pd.read_sql(query_weight, conn)

#     # --- [신규] 2. 체온 데이터 조회 (health_cond 테이블) ---
#     query_temp = "SELECT body_temp FROM fms.health_cond"
#     df_temp = pd.read_sql(query_temp, conn)
    
#     conn.close()

#     # --- 3. 데이터 전처리 (공통 함수 사용) ---
#     def clean_numeric(val):
#         if isinstance(val, str):
#             return float(re.sub(r'[^\d\.]', '', val))
#         return float(val)
    
#     # 무게 전처리
#     df_weight['raw_weight_num'] = df_weight['raw_weight'].apply(clean_numeric)
    
#     # 체온 전처리 (결측치 제거 포함)
#     df_temp['body_temp_num'] = df_temp['body_temp'].apply(clean_numeric)
#     df_temp = df_temp.dropna(subset=['body_temp_num']) # NaN 제거

#     # --- 4. 통계표 생성 (기존 코드) ---
#     stats_df = df_weight.groupby('breed_name')['raw_weight_num'].agg(['count', 'mean', 'min', 'max']).round(2)
#     stats_df = stats_df.reset_index()
#     stats_data = stats_df.to_dict('records')

#     # --- 5. 그래프 생성 함수들 ---
    
#     # (A) 품종별 무게 Box Plot (기존)
#     img1 = io.BytesIO()
#     plt.figure(figsize=(10, 6))
#     plt.rcParams['font.family'] = 'Malgun Gothic'
#     plt.rcParams['axes.unicode_minus'] = False
    
#     sns.boxplot(x='breed_name', y='raw_weight_num', data=df_weight, palette='Set3')
#     plt.title('품종별 무게 분포')
#     plt.savefig(img1, format='png', bbox_inches='tight')
#     img1.seek(0)
#     weight_plot_url = base64.b64encode(img1.getvalue()).decode()
#     plt.close()

# # (B) [수정] 체온 정규분포 그래프 (Winter Palette 적용)
#     img2 = io.BytesIO()
    
#     # 그래프 객체 생성
#     fig, ax = plt.subplots(figsize=(10, 6))
    
#     # 데이터 정의
#     data = df_temp['body_temp_num']
    
#     # 1. 히스토그램 그리기 (matplotlib의 hist 사용 -> patches 제어)
#     # density=True: 빈도수가 아닌 밀도(확률)로 표시
#     n, bins, patches = ax.hist(data, bins=20, density=True, alpha=0.8)
    
#     # [핵심] Winter Colormap 적용
#     # 'winter' 컬러맵 가져오기
#     cmap = plt.get_cmap('winter')
    
#     # X축(체온) 위치에 따라 색상 매핑 (0.0 ~ 1.0 사이 값으로 변환)
#     bin_centers = 0.5 * (bins[:-1] + bins[1:])
#     col = (bin_centers - min(bin_centers)) / (max(bin_centers) - min(bin_centers))
    
#     # 각 막대(patch)에 색상 입히기
#     for c, p in zip(col, patches):
#         plt.setp(p, 'facecolor', cmap(c))
    
#     # 2. KDE (커널 밀도 추정) - 부드러운 실선
#     # 배경이 진할 수 있으므로 흰색이나 밝은 색으로 라인을 그림
#     sns.kdeplot(data, color='pink', linewidth=2, linestyle='-', ax=ax, label='Actual Distribution')
    
#     # 3. 이론적 정규분포 곡선 (빨간 점선)
#     # Winter 색상과 대비되도록 빨간색(red) 또는 오렌지색 사용
#     mu, std = data.mean(), data.std()
#     x = np.linspace(data.min(), data.max(), 100)
#     p = norm.pdf(x, mu, std)
#     ax.plot(x, p, 'r--', linewidth=2.5, label=f'Normal Dist (μ={mu:.1f})')
    
#     # 디자인 다듬기
#     ax.set_title('체온 데이터 정규분포 (Winter Theme)', fontsize=14, fontweight='bold')
#     ax.set_xlabel('체온 (℃)')
#     ax.set_ylabel('밀도 (Density)')
#     ax.legend()
#     ax.grid(True, alpha=0.3, linestyle='--')
    
#     # 저장
#     plt.savefig(img2, format='png', bbox_inches='tight')
#     img2.seek(0)
#     temp_plot_url = base64.b64encode(img2.getvalue()).decode()
#     plt.close()

#     # --- 6. 템플릿 반환 ---
#     return render_template('statistics.html', 
#                            table_data=stats_data, 
#                            weight_graph=weight_plot_url,
#                            temp_graph=temp_plot_url) # 체온 그래프 추가

# app.py

@app.route('/statistics')
def statistics():
    conn = get_db_connection()
    
    # --- [데이터 조회] ---
    # 1. 품종별 무게
    query_weight = """
    SELECT C.code_desc AS breed_name, B.raw_weight
    FROM fms.chick_info A
    JOIN fms.prod_result B ON A.chick_no = B.chick_no
    JOIN fms.master_code C ON A.breeds = C.code
    """
    df_weight = pd.read_sql(query_weight, conn)

    # 2. 체온
    query_temp = "SELECT body_temp FROM fms.health_cond"
    df_temp = pd.read_sql(query_temp, conn)

    # 3. 성장 데이터
    query_growth = """
    SELECT C.code_desc as breed_name, H.check_date, H.weight
    FROM fms.health_cond H
    JOIN fms.chick_info I ON H.chick_no = I.chick_no
    JOIN fms.master_code C ON I.breeds = C.code
    ORDER BY H.check_date
    """
    df_growth = pd.read_sql(query_growth, conn)
    
    conn.close()

    # --- [데이터 전처리] ---
    def clean_numeric(val):
        if isinstance(val, str):
            return float(re.sub(r'[^\d\.]', '', val))
        return float(val)
    
    df_weight['raw_weight_num'] = df_weight['raw_weight'].apply(clean_numeric)
    
    df_temp['body_temp_num'] = df_temp['body_temp'].apply(clean_numeric)
    df_temp = df_temp.dropna(subset=['body_temp_num'])
    
    df_growth['weight'] = df_growth['weight'].apply(clean_numeric)
    df_growth['check_date'] = pd.to_datetime(df_growth['check_date'])

    # --- [통계표 생성] ---
    stats_df = df_weight.groupby('breed_name')['raw_weight_num'].agg(['count', 'mean', 'min', 'max']).round(2)
    stats_df = stats_df.reset_index()
    stats_data = stats_df.to_dict('records')

    # --- [그래프 생성] ---
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

    # (A) 품종별 무게 Box Plot
    img1 = io.BytesIO()
    plt.figure(figsize=(10, 6))
    sns.boxplot(x='breed_name', y='raw_weight_num', hue='breed_name', data=df_weight, palette='Set3', legend=False)
    plt.title('품종별 무게 분포')
    plt.savefig(img1, format='png', bbox_inches='tight')
    img1.seek(0)
    weight_plot_url = base64.b64encode(img1.getvalue()).decode()
    plt.close()

    # (B) 체온 정규분포
    img2 = io.BytesIO()
    fig, ax = plt.subplots(figsize=(10, 6))
    data = df_temp['body_temp_num']
    if len(data) > 0: # 데이터가 있을 때만 그림
        n, bins, patches = ax.hist(data, bins=20, density=True, alpha=0.8)
        cmap = plt.get_cmap('winter')
        bin_centers = 0.5 * (bins[:-1] + bins[1:])
        col = (bin_centers - min(bin_centers)) / (max(bin_centers) - min(bin_centers))
        for c, p in zip(col, patches):
            plt.setp(p, 'facecolor', cmap(c))
        sns.kdeplot(data, color='pink', linewidth=2, linestyle='-', ax=ax, label='Actual Distribution')
        mu, std = data.mean(), data.std()
        x = np.linspace(data.min(), data.max(), 100)
        p = norm.pdf(x, mu, std)
        ax.plot(x, p, 'r--', linewidth=2.5, label=f'Normal Dist (μ={mu:.1f})')
        ax.legend()
    ax.set_title('체온 데이터 정규분포 (Winter Theme)')
    plt.savefig(img2, format='png', bbox_inches='tight')
    img2.seek(0)
    temp_plot_url = base64.b64encode(img2.getvalue()).decode()
    plt.close()

    # (C) 성장 곡선
    img3 = io.BytesIO()
    plt.figure(figsize=(10, 6))
    if not df_growth.empty:
        growth_summary = df_growth.groupby(['breed_name', 'check_date'])['weight'].mean().reset_index()
        sns.lineplot(x='check_date', y='weight', hue='breed_name', data=growth_summary, marker='o', linewidth=2.5)
    plt.title('일별 품종별 성장 곡선 (평균 증체량)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(img3, format='png', bbox_inches='tight')
    img3.seek(0)
    growth_plot_url = base64.b64encode(img3.getvalue()).decode()
    plt.close()

    return render_template('statistics.html', 
                           table_data=stats_data, 
                           weight_graph=weight_plot_url,
                           temp_graph=temp_plot_url,
                           growth_graph=growth_plot_url,
                           )

if __name__ == '__main__':
    app.run(debug=True)

