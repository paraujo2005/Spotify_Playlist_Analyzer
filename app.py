from flask import Flask, redirect, request, session, render_template
import requests
import os
from dotenv import load_dotenv
import base64

#Carrega variáveis do .env
load_dotenv()

#Define App
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

#Carrega variáveis do Spotify
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-private"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

#App
@app.route('/')
def index():
    return render_template('index_tailwind.html')

#Página de logijn
@app.route('/login')
def login():
    auth_query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    # Monta a URL de login
    query_str = "&".join([f"{k}={v}" for k, v in auth_query.items()])
    return redirect(f"{AUTH_URL}?{query_str}")

#Retorno do Spotify
@app.route('/callback')
def callback():
    code = request.args.get("code")

    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    res = requests.post(TOKEN_URL, data=payload, headers=headers)
    res_data = res.json()

    access_token = res_data.get("access_token")
    refresh_token = res_data.get("refresh_token")

    session["access_token"] = access_token
    session["refresh_token"] = refresh_token

    return redirect("/profile")

@app.route('/profile')
def profile():
    access_token = session.get("access_token")
    
    if not access_token:
        return redirect("/login")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    res = requests.get("https://api.spotify.com/v1/me", headers=headers)

    if res.status_code == 401:
        return redirect("/login")
    elif res.status_code != 200:
        return f"Erro ao obter perfil: {res.text}", res.status_code

    profile_data = res.json()

    res = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)

    if res.status_code != 200:
        return f"Erro ao obter playlists: {res.text}", res.status_code
    
    playlist_data = res.json()
    playlist_items = playlist_data.get("items", [])
        
    playlists = []
    for p in playlist_items:
        playlists.append({
            "id": p["id"],
            "name": p["name"],
            "image": p["images"][0]["url"] if p.get("images") and len(p["images"]) > 0 else "https://via.placeholder.com/150"
        })


    return render_template("profile_tailwind.html",
                           display_name=profile_data.get("display_name"),
                           display_image=(profile_data["images"][0]["url"]),
                           playlists=playlists)


@app.route('/playlist/<id>')
def playlist(id):
    return f"Testando e Funcionando para a playlist {id}"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')