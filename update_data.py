import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import json
from datetime import datetime, timedelta
import io
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import requests
from scipy.signal import find_peaks # 새로 추가

# --- 다이버전스 탐지 함수 (새로 추가) ---
def detect_rsi_divergence(df, lookback=14):
    """
    최근 lookback 기간 동안 4가지 유형의 RSI 다이버전스를 탐지합니다.
    (일반 강세/약세, 히든 강세/약세)
    """
    recent_df = df.iloc[-lookback:].copy()
    price = recent_df['Close']
    rsi = recent_df['RSI_14']

    # 가격과 RSI의 고점(peaks)과 저점(troughs) 인덱스를 찾음
    price_peaks, _ = find_peaks(price)
    price_troughs, _ = find_peaks(-price)
    rsi_peaks, _ = find_peaks(rsi)
    rsi_troughs, _ = find_peaks(-rsi)

    # 1. 일반 약세 다이버전스: 가격은 고점 갱신, RSI는 고점 하락
    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        last_price_peak = price.iloc[price_peaks[-1]]
        prev_price_peak = price.iloc[price_peaks[-2]]
        last_rsi_peak = rsi.iloc[rsi_peaks[-1]]
        prev_rsi_peak = rsi.iloc[rsi_peaks[-2]]
        if last_price_peak > prev_price_peak and last_rsi_peak < prev_rsi_peak:
            return "일반 약세"

    # 2. 일반 강세 다이버전스: 가격은 저점 갱신, RSI는 저점 상승
    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        last_price_trough = price.iloc[price_troughs[-1]]
        prev_price_trough = price.iloc[price_troughs[-2]]
        last_rsi_trough = rsi.iloc[rsi_troughs[-1]]
        prev_rsi_trough = rsi.iloc[rsi_troughs[-2]]
        if last_price_trough < prev_price_trough and last_rsi_trough > prev_rsi_trough:
            return "일반 강세"

    # 3. 히든 약세 다이버전스: 가격은 고점 하락, RSI는 고점 갱신
    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        last_price_peak = price.iloc[price_peaks[-1]]
        prev_price_peak = price.iloc[price_peaks[-2]]
        last_rsi_peak = rsi.iloc[rsi_peaks[-1]]
        prev_rsi_peak = rsi.iloc[rsi_peaks[-2]]
        if last_price_peak < prev_price_peak and last_rsi_peak > prev_rsi_peak:
            return "히든 약세"

    # 4. 히든 강세 다이버전스: 가격은 저점 상승, RSI는 저점 갱신
    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        last_price_trough = price.iloc[price_troughs[-1]]
        prev_price_trough = price.iloc[price_troughs[-2]]
        last_rsi_trough = rsi.iloc[rsi_troughs[-1]]
        prev_rsi_trough = rsi.iloc[rsi_troughs[-2]]
        if last_price_trough > prev_price_trough and last_rsi_trough < prev_rsi_trough:
            return "히든 강세"

    return "없음"


# --- 기존 텔레그램 및 기술적 분석 함수 ---

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("경고: config.json 파일이 없습니다. 텔레그램 알림이 비활성화됩니다.")
        return None

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"텔레그램 메시지 발송 성공: {message.splitlines()[0]}")
    except requests.exceptions.RequestException as e:
        print(f"텔레그램 메시지 발송 실패: {e}")

def calculate_alerts(tickers=['TSLA', 'QQQ']):
    """(수정) 지정된 티커에 대한 상세 기술적 지표를 계산합니다."""
    print("알림 지표 계산 시작...")
    alerts = {}

    # 다이버전스 분석을 위해 200일 데이터 다운로드
    data = yf.download(tickers, period='280d', progress=False, threads=False)

    for ticker in tickers:
        df = data.loc[:, (slice(None), ticker)].copy()
        df.columns = [col[0] for col in df.columns]

        # 1. 기술적 지표 계산
        df.ta.rsi(length=14, append=True)
        df.ta.sma(length=120, append=True)
        df.ta.sma(length=240, append=True) # 240일선은 더 긴 데이터가 필요할 수 있음
        df.ta.macd(append=True)

        latest = df.iloc[-1]

        # 2. RSI 다이버전스 확인 (핵심 수정 부분)
        # 2주(10거래일)가 아닌 3주(15거래일) 기간으로 좀 더 여유있게 확인
        divergence = detect_rsi_divergence(df, lookback=15)

        # 3. MACD 상세 정보 및 크로스 확인
        macd_line = latest['MACD_12_26_9']
        signal_line = latest['MACDs_12_26_9']
        hist = latest['MACDh_12_26_9']
        prev_hist = df.iloc[-2]['MACDh_12_26_9']
        macd_status = f"MACD: {macd_line:.2f}, Signal: {signal_line:.2f}"
        if hist > 0 and prev_hist < 0:
            macd_status += " (골든 크로스, 양수 전환)"
        elif hist < 0 and prev_hist > 0:
            macd_status += " (데드 크로스, 음수 전환)"

        # 4. 결과 저장
        alerts[ticker] = {
            'Close':f"{latest['Close']:.2f}",
            'RSI': f"{latest['RSI_14']:.2f} ({divergence})",
            '120SMA': f"{latest['SMA_120']:.2f} ({'UP' if latest['Close'] > latest['SMA_120'] else 'DOWN'})",
            '240SMA': f"{latest['SMA_240']:.2f} ({'UP' if latest['Close'] > latest['SMA_240'] else 'DOWN'})",
            'MACD_Status': macd_status
        }
        print(f"  - {ticker} 지표 계산 완료. 다이버전스: {divergence}")

    return alerts

# --- S&P 500 히트맵 생성 함수 (이 함수만 교체) ---
def generate_sp500_heatmap():
    """
    S&P 500 기업 목록을 가져와 일일 성과를 기준으로 Plotly 트리맵을 생성합니다.
    (수정) NaN 값 처리 및 GOOG 티커 제거.
    """
    print("S&P 500 히트맵 데이터 생성 시작 (순차 모드)...")
    try:
        # 1. 위키피디아에서 S&P 500 티커 목록 가져오기
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        table = pd.read_html(response.text)[0]
        tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()]

        # --- 새로 추가된 부분 (1): GOOG 티커 제거 ---
        if 'GOOG' in tickers:
            tickers.remove('GOOG')
            print("GOOG 티커 제거 완료. GOOGL만 사용합니다.")
        # -----------------------------------------

        print(f"S&P 500 티커 {len(tickers)}개 로드 완료.")

        # 2. 모든 티커의 일일 데이터 다운로드
        data = yf.download(tickers, period='2d', progress=False, threads=False)
        if data.empty:
            return "<p>S&P 500 데이터를 다운로드할 수 없습니다.</p>"

        # 3. 수익률 및 기업 정보 수집
        df_list = []
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info
                close_yesterday = data['Close'][ticker].iloc[-2]
                close_today = data['Close'][ticker].iloc[-1]
                performance = ((close_today - close_yesterday) / close_yesterday) * 100

                # --- 새로 추가된 부분 (2): NaN 값 처리 ---
                if pd.isna(performance):
                    performance = 0.0  # NaN 값을 0으로 대체하여 오류 방지
                # ----------------------------------------

                sector = info.get('sector', 'N/A')
                market_cap = info.get('marketCap', 0)
                short_name = info.get('shortName', ticker)

                if sector != 'N/A' and market_cap > 0:
                    df_list.append({
                        'Ticker': ticker, 'Name': short_name, 'Sector': sector,
                        'MarketCap': market_cap, 'Performance': performance
                    })
            except Exception:
                continue

        if not df_list:
            return "<p>S&P 500 히트맵을 생성할 데이터가 부족합니다.</p>"

        df = pd.DataFrame(df_list)
        print(f"유효한 기업 데이터 {len(df)}개 처리 완료.")

        # 4. Plotly 트리맵 생성 (이전과 동일)
        fig = px.treemap(
            df, path=[px.Constant("S&P 500"), 'Sector', 'Ticker'], values='MarketCap',
            color='Performance', color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
            hover_data={'Name': True, 'Performance': ':.2f%'},
            custom_data=['Performance']
        )
        fig.data[0].texttemplate = "<b>%{label}</b><br>%{customdata[0]:.2f}%"
        fig.data[0].textfont = {'size': 20}
        fig.data[0].textposition = 'middle center'
        fig.data[0].marker.pad = {'t': 25, 'b': 10, 'l': 10, 'r': 10}
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), font_color="white", coloraxis_showscale=False)

        # 5. HTML 조각으로 변환
        chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
        print("S&P 500 히트맵 생성 완료.")
        return chart_html

    except Exception as e:
        print(f"S&P 500 히트맵 생성 중 오류 발생: {e}")
        return f"<p>S&P 500 히트맵 생성 중 오류가 발생했습니다: {e}</p>"

# --- 기존 설정 및 함수들 (이전 코드와 동일, threads=False 유지) ---
TICKERS = [
    '^GSPC', '^DJI', '^IXIC', '^RUT', '^GDAXI', '^FTSE', '^N225', '^HSI',
    '^KS11', 'SHY', 'IEF', 'TLT', 'DX-Y.NYB', 'GC=F', 'CL=F', 'BTC-USD',
    'ETH-USD', '^VIX', '^MOVE', '^SKEW'
]
MOMENTUM_PERIODS = {
    '1주': 5, '2주': 10, '3주': 15, '4주': 20, '1개월': 21, '2개월': 42, '3개월': 63,
    '4개월': 84, '5개월': 105, '6개월': 126, '1년': 252, '3년': 252 * 3, '5년': 252 * 5
}
CORR_PERIODS = {
    '1 Week': timedelta(weeks=1), '1 Month': timedelta(days=30), '3 Months': timedelta(days=91),
    '6 Months': timedelta(days=182), '1 Year': timedelta(days=365),
    '5 Years': timedelta(days=365 * 5), '10 Years': timedelta(days=365 * 10)
}

def get_momentum_data(tickers):
    print("모멘텀 데이터 다운로드 및 계산 시작...")
    ticker_names = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            name = info.get('longName', info.get('shortName', ticker))
            ticker_names[ticker] = name
        except Exception:
            ticker_names[ticker] = ticker

    data = yf.download(tickers, period='11y', progress=False, threads=False)['Close']
    if data.empty: return []
    momentum_results = []
    for ticker in tickers:
        ticker_data = {'ticker': ticker, 'name': ticker_names.get(ticker, ticker)}
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
        try:
            m_1m, m_6m, m_1y = momentum_values.get('1개월'), momentum_values.get('6개월'), momentum_values.get('1년')
            if all(v is not None for v in [m_1m, m_6m, m_1y]):
                if m_1m > 0 and m_6m > 0 and m_1y > 0: status = '상승'
                elif m_1m < 0 and m_6m < 0: status = '하락'
        except Exception: pass
        ticker_data['status'] = status
        momentum_results.append(ticker_data)
    print("모멘텀 데이터 계산 완료.")
    return momentum_results

def generate_correlation_plots(tickers):
    print("상관관계 데이터 계산 시작...")
    plots_data = []
    end_date = datetime.now()
    for label, delta in CORR_PERIODS.items():
        start_date = end_date - delta
        plot_url, message = None, None
        try:
            data = yf.download(tickers, start=start_date, end=end_date, progress=False, threads=False)['Close']
            if data.empty or data.shape[1] < 2 or len(data.dropna()) < 5:
                message = f"데이터 부족 ({label})"
                plots_data.append({'label': label, 'plot_url': None, 'message': message})
                continue
            returns = data.pct_change().dropna()
            corr_matrix = returns.corr()
            plt.figure(figsize=(14, 12)); sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5, annot_kws={"size": 8}); plt.title(f'Asset Correlation Matrix ({label})', fontsize=16)
            plt.xticks(rotation=45, ha='right'); plt.yticks(rotation=0); plt.tight_layout()
            img_buffer = io.BytesIO(); plt.savefig(img_buffer, format='png'); img_buffer.seek(0)
            plot_url = base64.b64encode(img_buffer.getvalue()).decode('utf8'); plt.close()
        except Exception as e:
            message = f"오류 발생 ({label}): {e}"
        plots_data.append({'label': label, 'plot_url': plot_url, 'message': message})
    print("상관관계 데이터 계산 완료.")
    return plots_data

# --- 메인 실행 로직 (이전과 거의 동일) ---
if __name__ == "__main__":
    print(f"데이터 업데이트 시작: {datetime.now()}")

    config = load_config()

    if config:
        alerts_data = calculate_alerts(['TSLA', 'QQQ'])
        for ticker, data in alerts_data.items():
            message = (
                f"*{ticker} 일일 브리핑*\n"
                f"--------------------------\n"
                f"Close: *{data['Close']}*\n"
                f"RSI(14): *{data['RSI']}*\n"
                f"120SMA: *{data['120SMA']}*\n"
                f"240SMA: *{data['240SMA']}*\n"
                f"MACD: *{data['MACD_Status']}*"
            )
            send_telegram_message(config['telegram_token'], config['telegram_chat_id'], message)
    else:
        alerts_data = {}

    sp500_heatmap_html = generate_sp500_heatmap()
    momentum_data = get_momentum_data(TICKERS)
    correlation_plots = generate_correlation_plots(TICKERS)

    final_data = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'alerts_data': alerts_data,
        'sp500_heatmap_html': sp500_heatmap_html,
        'momentum_data': momentum_data,
        'correlation_plots': correlation_plots
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    print("dashboard_data.json 파일 저장 완료.")
