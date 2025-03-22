"""
GPT Shell Server

Usage:
  run_server.py run [--base=<dir>] [--port=<port>] [--key=<key>]
  run_server.py (-h | --help)

Options:
  --base=<dir>     Base directory for file operations [default: /home/test/workspace]
  --port=<port>    Port to run the server on [default: 5001]
  --key=<key>      API key for authorization [default: qwe]
  -h --help        Show this screen.
"""

from docopt import docopt
from flask import Flask, request
import subprocess
import os
import xml.etree.ElementTree as ET
import logging

# === CLI args ===
args = docopt(__doc__)
BASE_DIR = args["--base"]
PORT = int(args["--port"])
SECRET_KEY = args["--key"]

# === Logging ===
LOG_FILE = "activity.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# === Flask app ===
app = Flask(__name__)

def to_xml_response(tag, data: dict):
    root = ET.Element(tag)
    for key, val in data.items():
        ET.SubElement(root, key).text = str(val)
    return ET.tostring(root, encoding='unicode')

def check_auth():
    return request.headers.get("X-Api-Key") == SECRET_KEY

@app.before_request
def require_auth():
    if not check_auth():
        logging.warning("Unauthorized request")
        return to_xml_response("AuthError", {
            "Status": "Denied",
            "Reason": "Invalid or missing API key"
        }), 403, {'Content-Type': 'application/xml'}

@app.route('/run-command', methods=['POST'])
def run_command():
    data = request.get_json()
    cmd = data.get("command", "")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        logging.info(f"Executed command: {cmd} | Code: {result.returncode}")
        return to_xml_response("CommandResult", {
            "Command": cmd,
            "ReturnCode": result.returncode,
            "Stdout": result.stdout,
            "Stderr": result.stderr
        }), 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        logging.error(f"Command failed: {cmd} | Error: {str(e)}")
        return to_xml_response("CommandResult", {
            "Command": cmd,
            "Error": str(e)
        }), 500, {'Content-Type': 'application/xml'}

@app.route('/write-file', methods=['POST'])
def write_file():
    data = request.get_json()
    path = data.get("path")
    content = data.get("content")
    try:
        if not path or content is None:
            raise ValueError("Missing 'path' or 'content'")
        abs_path = os.path.abspath(os.path.join(BASE_DIR, path))
        if not abs_path.startswith(BASE_DIR):
            raise PermissionError("Access outside of base dir denied")
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w') as f:
            f.write(content)
        logging.info(f"File written: {path}")
        return to_xml_response("FileWriteResult", {
            "Path": path,
            "Status": "Success"
        }), 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        logging.error(f"File write failed: {path} | Error: {str(e)}")
        return to_xml_response("FileWriteResult", {
            "Path": path,
            "Status": "Error",
            "Message": str(e)
        }), 500, {'Content-Type': 'application/xml'}

@app.route('/read-file', methods=['POST'])
def read_file():
    data = request.get_json()
    path = data.get("path")
    try:
        if not path:
            raise ValueError("Missing 'path'")
        abs_path = os.path.abspath(os.path.join(BASE_DIR, path))
        if not abs_path.startswith(BASE_DIR):
            raise PermissionError("Access outside of base dir denied")
        with open(abs_path, 'r') as f:
            content = f.read()
        logging.info(f"File read: {path}")
        return to_xml_response("FileReadResult", {
            "Path": path,
            "Content": content
        }), 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        logging.error(f"File read failed: {path} | Error: {str(e)}")
        return to_xml_response("FileReadResult", {
            "Path": path,
            "Status": "Error",
            "Message": str(e)
        }), 500, {'Content-Type': 'application/xml'}


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return to_xml_response("UploadResult", {
            "Status": "Error",
            "Message": "No file part"
        }), 400, {'Content-Type': 'application/xml'}

    file = request.files['file']
    if file.filename == '':
        return to_xml_response("UploadResult", {
            "Status": "Error",
            "Message": "No selected file"
        }), 400, {'Content-Type': 'application/xml'}

    try:
        save_path = os.path.join("/tmp", file.filename)
        file.save(save_path)
        logging.info(f"File uploaded: {file.filename} -> {save_path}")
        return to_xml_response("UploadResult", {
            "Status": "Success",
            "Path": save_path
        }), 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        logging.error(f"Upload failed: {str(e)}")
        return to_xml_response("UploadResult", {
            "Status": "Error",
            "Message": str(e)
        }), 500, {'Content-Type': 'application/xml'}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)