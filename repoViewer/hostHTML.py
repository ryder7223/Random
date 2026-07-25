from flask import Flask, request, send_from_directory, jsonify, Response
import requests
from urllib.parse import urlparse
import mimetypes
import urllib3

urllib3.disable_warnings()

app = Flask(__name__, static_folder=".")

@app.route("/")
def index():
    return send_from_directory(".", "repoViewer.html")

@app.route("/proxy")
def proxy():
    targetUrl = request.args.get("url")
    if not targetUrl:
        return jsonify({"error":"Missing URL"}),400
    try:
        response=requests.get(
            targetUrl,
            timeout=30,
            headers={
                "User-Agent":"Mozilla/5.0 iOSRepoViewer"
            }
        )
        contentType=response.headers.get(
            "Content-Type",
            mimetypes.guess_type(targetUrl)[0] or "application/octet-stream"
        )
        return Response(
            response.content,
            status=response.status_code,
            content_type=contentType
        )
    except Exception as error:
        return jsonify({
            "error":str(error)
        }),500

@app.route("/repo")
def repo():
    targetUrl=request.args.get("url")
    if not targetUrl:
        return jsonify({
            "error":"Missing URL parameter"
        }),400
    try:
        response=requests.get(
            targetUrl,
            timeout=30,
            allow_redirects=True,
            headers={
                "User-Agent":"Mozilla/5.0 (iOS Repository Browser)"
            }
            ,verify=False
        )
        if response.status_code != 200:
            return jsonify({
                "error":"Remote server returned HTTP error",
                "status":response.status_code,
                "url":targetUrl,
                "headers":dict(response.headers),
                "body":response.text[:1000]
            }),response.status_code
        try:
            data=response.json()
        except Exception as jsonError:
            return jsonify({
                "error":"Remote response was not valid JSON",
                "jsonError":str(jsonError),
                "contentType":response.headers.get("Content-Type"),
                "body":response.text[:1000]
            }),500
        return jsonify(data)
    except requests.exceptions.Timeout:
        return jsonify({
            "error":"Request timed out",
            "url":targetUrl
        }),500
    except requests.exceptions.RequestException as requestError:
        return jsonify({
            "error":"Request failed",
            "details":str(requestError),
            "url":targetUrl
        }),500
    except Exception as error:
        return jsonify({
            "error":"Unknown server error",
            "details":str(error)
        }),500

if __name__=="__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )