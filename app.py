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
    return render_template('index.html')

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
def spotify_callback():
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
        
    playlists = []
    while True:
        playlist_items = playlist_data.get("items", [])
        for p in playlist_items:
            playlists.append({
                "id": p["id"],
                "name": p["name"],
                "image": p["images"][0]["url"] if p.get("images") and len(p["images"]) > 0 else "https://via.placeholder.com/150"
            })

        if not playlist_data.get("next"):
            break

        res = requests.get(playlist_data["next"], headers=headers)
        playlist_data = res.json()

    return render_template("profile.html",
                           display_name=profile_data.get("display_name"),
                           display_image=(profile_data["images"][0]["url"] if profile_data.get("images") and len(profile_data["images"]) > 0 else "https://via.placeholder.com/150"),
                           playlists=playlists)

@app.route('/loading/<id_playlist>')
def loading(id_playlist):
    return render_template("loading.html", id_playlist=id_playlist)

@app.route('/playlist/<id_playlist>')
def playlist(id_playlist):
    access_token = session.get("access_token")
    
    if not access_token:
        return redirect("/login")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    #Info do Get playlists
    res = requests.get(f"https://api.spotify.com/v1/playlists/{id_playlist}", headers=headers)
    playlist_data = res.json()
    playlist_tracks = []
    playlist_tracks_info = playlist_data["tracks"]

    artist_cache = {}
    track_id_list = []

    #Coleta dados de todas as tracks da playlist
    while True:
        for item in playlist_tracks_info["items"]:
            track = item.get("track")

            if not track:
                continue

            #Info Track
            track_id = track.get("id") #ID Track
            track_name = track.get("name", "Desconhecida") #Nome Track
            track_popularity = track.get("popularity", "-") #Popularidade Track
            track_duration_ms = track.get("duration_ms", 0) #Duração Track MS
            duration_sec = track_duration_ms // 1000 #Duração Track Segundos
            duration_min_min = duration_sec // 60 #Duração Track Minutos (Min)
            duration_min_sec = duration_sec % 60 #Duração Track Minutos (Sec)

            #Artistas da Track
            artists = []
            for artist in track.get("artists", []):
                artist_id = artist.get("id") #ID Artista
                artist_name = artist.get("name", "Desconhecido") #Nome Artista

                if artist_id in artist_cache:
                    genres = artist_cache[artist_id] #Generos do Artista (Segundo Cache)

                else:
                    genres = []

                    if artist_id:
                        artist_res = requests.get(f"https://api.spotify.com/v1/artists/{artist_id}", headers=headers)

                        if artist_res.status_code == 200:
                            artist_info = artist_res.json()
                            genres = artist_info.get("genres", []) #Generos do Artista

                    artist_cache[artist_id] = genres #Salva Artista em Cache
                
                artists.append({"name": artist_name, "genres": genres}) #Salva Info Artista

            #Adiciona o ID na lista para requisição futura de audio features
            if track_id:
                track_id_list.append(track_id)

            #Lista final
            playlist_tracks.append({
                "id": track_id,
                "name": track_name,
                "artists": artists,
                "popularity": track_popularity,
                "duration_ms": track_duration_ms,
                "duration_sec": duration_sec,
                "duration_min_min": duration_min_min,
                "duration_min_sec": duration_min_sec
            })

        if not playlist_tracks_info.get("next"):
            break

        res = requests.get(playlist_tracks_info["next"], headers=headers)
        playlist_tracks_info = res.json()

    #Audio Features
    features = {}
    for i in range(0, len(track_id_list), 100):
        batch = track_id_list[i:i+100]
        res = requests.get(f"https://api.spotify.com/v1/audio-features?ids={','.join(batch)}", headers=headers)

        if res.status_code == 200:
            feautres_info = res.json()
            for af in feautres_info.get("audio_features", []):
                if af:
                    features[af["id"]] = af

    #Anexar audio features aos tracks
    for track in playlist_tracks:
        af = features.get(track["id"], {})
        track.update({
            "acousticness": af.get("acousticness"),
            "danceability": af.get("danceability"),
            "energy": af.get("energy"),
            "instrumentalness": af.get("instrumentalness"),
            "liveness": af.get("liveness"),
            "loudness": af.get("loudness"),
            "speechiness": af.get("speechiness"),
            "bps": af.get("tempo"),
            "valence": af.get("valence")
        })


    #Análise da Playlist

    #Duração Média
    durations = [t["duration_ms"] for t in playlist_tracks if isinstance(t["duration_ms"], int)]
    if durations:
        playlist_duration_ms = sum(durations)/len(durations)
        playlist_duration_sec = playlist_duration_ms // 1000
        playlist_duration_min_min = playlist_duration_sec // 60
        playlist_duration_min_sec = playlist_duration_sec % 60
    else:
        playlist_duration_ms = playlist_duration_sec = playlist_duration_min_min = playlist_duration_min_sec = "-"
    
    #Lista Final Playlist
    playlist_analysis = [{
        "playlist_duration_ms": playlist_duration_ms,
        "playlist_duration_sec": playlist_duration_sec,
        "playlist_duration_min_min": playlist_duration_min_min,
        "playlist_duration_min_sec": playlist_duration_min_sec
    }]
    
    return render_template("playlist.html", tracks=playlist_tracks, playlist=playlist_analysis[0])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')