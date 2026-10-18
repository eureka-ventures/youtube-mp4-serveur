#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur YouTube → MP4 (Flask + yt-dlp + ffmpeg).
Reçoit une URL YouTube, produit un MP4 et le renvoie au navigateur.
"""

import os
import re
import shutil
import tempfile
import threading
import time

from flask import Flask, jsonify, request, send_file, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)  # autorise la page Netlify à appeler ce serveur

HAUTEURS = {"best": None, "1080": 1080, "720": 720, "480": 480}
YT_RE = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", re.I)


def options_communes():
    """Options yt-dlp communes : cookies / proxy fournis via variables d'environnement."""
    o = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # clients alternatifs : contournent souvent le blocage des IP cloud
        "extractor_args": {"youtube": {"player_client": ["android_vr", "ios", "web"]}},
    }
    cookies = os.environ.get("COOKIES_TXT", "").strip()
    if cookies:
        chemin = "/tmp/cookies.txt"
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(cookies + "\n")
        o["cookiefile"] = chemin
    proxy = os.environ.get("PROXY", "").strip()
    if proxy:
        o["proxy"] = proxy
    return o


def construire_format(h):
    sel = f"[height<={h}]" if h else ""
    return (
        f"bestvideo{sel}[ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo{sel}+bestaudio/best{sel}[ext=mp4]/best{sel}"
    )


def nettoyer_plus_tard(dossier, delai=120):
    def _run():
        time.sleep(delai)
        shutil.rmtree(dossier, ignore_errors=True)
    threading.Thread(target=_run, daemon=True).start()


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/info")
def info():
    url = request.args.get("url", "").strip()
    if not YT_RE.match(url):
        return jsonify({"erreur": "URL YouTube invalide."}), 400
    try:
        with yt_dlp.YoutubeDL({**options_communes(), "skip_download": True}) as ydl:
            i = ydl.extract_info(url, download=False)
        return jsonify({
            "titre": i.get("title"),
            "duree": i.get("duration"),
            "miniature": i.get("thumbnail"),
            "chaine": i.get("uploader"),
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"erreur": str(e)}), 500


@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    qualite = data.get("qualite", "best")
    if not YT_RE.match(url):
        return jsonify({"erreur": "URL YouTube invalide."}), 400
    if qualite not in HAUTEURS:
        qualite = "best"

    dossier = tempfile.mkdtemp(prefix="ytmp4_")
    options = {
        **options_communes(),
        "format": construire_format(HAUTEURS[qualite]),
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(dossier, "%(title).120s.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
        fichiers = [f for f in os.listdir(dossier) if f.lower().endswith(".mp4")]
        if not fichiers:
            raise RuntimeError("Aucun fichier MP4 produit.")
        chemin = os.path.join(dossier, fichiers[0])
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(dossier, ignore_errors=True)
        return jsonify({"erreur": str(e)}), 500

    nettoyer_plus_tard(dossier)
    return send_file(chemin, as_attachment=True, download_name=fichiers[0], mimetype="video/mp4")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
