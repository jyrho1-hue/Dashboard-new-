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

    print(f"Static site built successfully: {output_path}")


if __name__ == '__main__':
    build()
