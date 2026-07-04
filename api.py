from flask import Flask, request, jsonify
import json
import hashlib
from datetime import datetime


app = Flask(__name__)


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/chaxunData', methods=['GET'])
def chaxunData():
    req_md5 = request.args.get("key")
    if not req_md5:
        return jsonify({})

    today_str = datetime.now().strftime("%Y%m%d")
    raw_str = f"s_t_o_c_k_{today_str}"
    calc_md5 = hashlib.md5(raw_str.encode("utf-8")).hexdigest()

    if req_md5.lower() != calc_md5:
        return jsonify({})

    try:
        with open(r"C:\stock.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=43958, debug=False)
