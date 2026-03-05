import json
import os
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, 'dashboard_data.json')

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(
            f"Error: '{data_path}' not found. Run update_data.py first."
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: '{data_path}' contains invalid JSON: {exc}")

    templates_dir = os.path.join(base_dir, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))

    # Expose Python built-ins used in templates
    env.globals['abs'] = abs
    env.globals['min'] = min

    # Provide a mock request object so layout.html active-link logic renders cleanly
    env.globals['request'] = SimpleNamespace(path='/')

    momentum_periods = {
        '단기': ['1주', '2주', '3주', '4주'],
        '중기': ['1개월', '2개월', '3개월', '4개월', '5개월', '6개월'],
        '장기': ['1년', '3년', '5년'],
    }

    sp500_heatmap = data.get('sp500_heatmap_html', '<p>S&P 500 히트맵 데이터를 찾을 수 없습니다.</p>')
    alerts_data = data.get('alerts_data', {})

    template = env.get_template('index.html')
    rendered = template.render(
        last_updated=data['last_updated'],
        sp500_heatmap=sp500_heatmap,
        alerts_data=alerts_data,
        momentum_data=data['momentum_data'],
        correlation_plots=data['correlation_plots'],
        momentum_periods=momentum_periods,
    )

    public_dir = os.path.join(base_dir, 'public')
    os.makedirs(public_dir, exist_ok=True)

    output_path = os.path.join(public_dir, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered)

    # Prevent GitHub Pages from processing files with Jekyll
    nojekyll_path = os.path.join(public_dir, '.nojekyll')
    open(nojekyll_path, 'w').close()

    # Generate a 404 fallback page
    not_found_html = """\
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>404 – 페이지를 찾을 수 없습니다</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh;">
  <div class="text-center">
    <h1 class="display-1 fw-bold text-muted">404</h1>
    <p class="fs-4">요청하신 페이지를 찾을 수 없습니다.</p>
    <a href="/" class="btn btn-primary mt-3">대시보드 홈으로 돌아가기</a>
  </div>
</body>
</html>
"""
    not_found_path = os.path.join(public_dir, '404.html')
    with open(not_found_path, 'w', encoding='utf-8') as f:
        f.write(not_found_html)

    print(f"Static site built successfully: {output_path}")


if __name__ == '__main__':
    build()
