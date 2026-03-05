import base64
import io
from datetime import datetime, timedelta
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import yfinance as yf
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Add this block to make Python functions available in templates
app.jinja_env.globals['abs'] = abs
app.jinja_env.globals['min'] = min

# --- 메인 대시보드 페이지 ---
@app.route('/')
def index():
    """메인 페이지. 미리 생성된 JSON 데이터를 읽어와 보여줍니다."""
    try:
        with open('/home/jyrho95/dashboard_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return "데이터 파일(dashboard_data.json)을 찾을 수 없습니다. 먼저 update_data.py를 실행해주세요.", 404

    # 모멘텀 데이터를 템플릿에 맞게 재구성
    momentum_periods = {
        '단기': ['1주', '2주', '3주', '4주'],
        '중기': ['1개월', '2개월', '3개월', '4개월', '5개월', '6개월'],
        '장기': ['1년', '3년', '5년']
    }

    # .get()을 사용하여 히트맵 데이터가 없는 경우에도 오류가 나지 않도록 처리
    sp500_heatmap = data.get('sp500_heatmap_html', '<p>S&P 500 히트맵 데이터를 찾을 수 없습니다.</p>')

    alerts_data = data.get('alerts_data', {})

    return render_template('index.html',
                           last_updated=data['last_updated'],
                           sp500_heatmap=sp500_heatmap,
                           alerts_data=alerts_data, # 이 줄 추가
                           momentum_data=data['momentum_data'],
                           correlation_plots=data['correlation_plots'],
                           momentum_periods=momentum_periods)

# --- 맞춤 분석 페이지 ---
@app.route('/custom', methods=['GET', 'POST'])
def custom_analysis():
    """사용자가 직접 티커를 입력하여 모멘텀과 상관관계를 분석하는 페이지."""
    if request.method == 'POST':
        submitted_tickers = request.form.get('tickers', '').strip()
        if submitted_tickers:
            tickers_list = [ticker.strip().upper() for ticker in submitted_tickers.replace(',', ' ').replace('\n', ' ').split() if ticker.strip()]

            # 여기서 모멘텀과 상관관계를 실시간으로 계산
            # 실제 서비스에서는 이 부분을 비동기 처리(Celery 등)하는 것이 좋습니다.
            # 지금은 간단하게 직접 호출합니다.
            momentum_data = calculate_custom_momentum(tickers_list)
            corr_plots, error_msg = generate_correlation_plots(tickers_list)

            momentum_periods = {
                '단기': ['1주', '2주', '3주', '4주'],
                '중기': ['1개월', '2개월', '3개월', '4개월', '5개월', '6개월'],
                '장기': ['1년', '3년', '5년']
            }

            return render_template('custom.html',
                                   submitted_tickers=submitted_tickers,
                                   momentum_data=momentum_data,
                                   correlation_plots=corr_plots,
                                   momentum_periods=momentum_periods,
                                   error_message=error_msg)

    return render_template('custom.html', submitted_tickers='')

# --- 맞춤 분석용 헬퍼 함수들 ---
# 이 함수들은 `update_data.py`의 함수들과 거의 동일하지만, 실시간 요청을 위해 여기에 포함됩니다.

def calculate_custom_momentum(tickers):
    """맞춤 분석 페이지를 위한 모멘텀 계산 함수."""
    # update_data.py의 get_momentum_data 함수와 로직이 거의 동일합니다.
    # 여기서는 간략화된 버전을 사용합니다.
    MOMENTUM_PERIODS = {
        '1주': 5, '2주': 10, '3주': 15, '4주': 20,
        '1개월': 21, '2개월': 42, '3개월': 63, '4개월': 84, '5개월': 105, '6개월': 126,
        '1년': 252, '3년': 252 * 3, '5년': 252 * 5
    }
    data = yf.download(tickers, period='6y', progress=False)['Close']
    if data.empty: return []
    if isinstance(data, pd.Series): # 티커가 하나일 경우 DataFrame으로 변환
        data = data.to_frame(tickers[0])

    momentum_results = []
    for ticker in tickers:
        ticker_data = {'ticker': ticker}
        momentum_values = {}
        for label, days in MOMENTUM_PERIODS.items():
            if ticker in data and len(data[ticker].dropna()) > days:
                past_price = data[ticker].dropna().iloc[-days-1]
                current_price = data[ticker].dropna().iloc[-1]
                momentum = ((current_price - past_price) / past_price) * 100 if past_price != 0 else 0
                momentum_values[label] = round(momentum, 2)
            else:
                momentum_values[label] = None
        ticker_data['momentum'] = momentum_values
        status = '혼조'
        m_1m = momentum_values.get('1개월', 0)
        m_6m = momentum_values.get('6개월', 0)
        if m_1m is not None and m_6m is not None:
            if m_1m > 0 and m_6m > 0: status = '상승'
            elif m_1m < 0 and m_6m < 0: status = '하락'
        ticker_data['status'] = status
        momentum_results.append(ticker_data)
    return momentum_results

def generate_correlation_plots(tickers):
    """맞춤 분석 페이지를 위한 상관관계 플롯 생성 함수."""
    if not tickers or len(tickers) < 2:
        return None, "최소 2개 이상의 유효한 티커를 입력해야 합니다."

    plots_data = []
    end_date = datetime.now()
    TIME_PERIODS = {
        '1 Week': timedelta(weeks=1), '1 Month': timedelta(days=30), '1 Year': timedelta(days=365)
    }

    for label, delta in TIME_PERIODS.items():
        start_date = end_date - delta
        plot_url, message = None, None
        try:
            data = yf.download(tickers, start=start_date, end=end_date, progress=False)['Close']
            if data.empty or data.shape[1] < 2 or len(data.dropna()) < 5:
                message = f"데이터 부족 ({label})"
                plots_data.append({'label': label, 'plot_url': None, 'message': message})
                continue
            returns = data.pct_change().dropna()
            corr_matrix = returns.corr()
            plt.figure(figsize=(12, 10))
            sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
            plt.title(f'Stock Correlation Matrix ({label})', fontsize=16)
            plt.xticks(rotation=45, ha='right'); plt.yticks(rotation=0); plt.tight_layout()
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png'); img_buffer.seek(0)
            plot_url = base64.b64encode(img_buffer.getvalue()).decode('utf8')
            plt.close()
        except Exception as e:
            message = f"오류 발생 ({label}): {e}"
        plots_data.append({'label': label, 'plot_url': plot_url, 'message': message})
    return plots_data, None

if __name__ == '__main__':
    app.run(debug=True)
