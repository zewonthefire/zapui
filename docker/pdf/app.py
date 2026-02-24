import json
import subprocess
import tempfile
from flask import Flask, jsonify, request, Response

app = Flask(__name__)


@app.post('/render')
def render_pdf():
    payload = request.get_json(silent=True) or {}
    html = payload.get('html', '')
    options = payload.get('options', {}) or {}

    if not isinstance(html, str) or not html.strip():
        return jsonify({'error': 'html must be a non-empty string'}), 400
    if not isinstance(options, dict):
        return jsonify({'error': 'options must be an object'}), 400

    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as html_file:
        html_file.write(html)
        html_path = html_file.name

    cmd = ['wkhtmltopdf']
    for key, value in options.items():
        flag = f"--{str(key).strip('-')}"
        if isinstance(value, bool):
            if value:
                cmd.append(flag)
        elif value is not None:
            cmd.extend([flag, str(value)])

    cmd.extend([html_path, '-'])

    try:
        proc = subprocess.run(cmd, check=False, capture_output=True)
    finally:
        subprocess.run(['rm', '-f', html_path], check=False)

    if proc.returncode != 0:
        return jsonify({'error': 'wkhtmltopdf failed', 'stderr': proc.stderr.decode('utf-8', errors='ignore')}), 500

    return Response(proc.stdout, mimetype='application/pdf')


@app.get('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8092)
