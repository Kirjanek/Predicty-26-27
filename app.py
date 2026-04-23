import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from supabase import create_client

# ==========================================
# 1. KONFIGURACJA
# ==========================================
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
API_KEY = "7d0575164002aad2416ed0759bc40950"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
HEADERS = {'x-apisports-key': API_KEY}

# ==========================================
# 2. FUNKCJE API I LOGIKA
# ==========================================

def get_fixtures(league_id=39, season=2024):
    """Pobiera mecze od dziś do końca sezonu 25/26."""
    # Definiujemy zakres dat (od dziś do końca maja 2026)
    today = datetime.now().strftime('%Y-%m-%d')
    end_season = "2026-05-31"
    
    # Używamy filtrów daty, co jest skuteczniejsze w końcówce sezonu
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={season}&from={today}&to={end_season}"
    
    try:
        res = requests.get(url, headers=HEADERS).json()
        fixtures = res.get('response', [])
        # Sortujemy chronologicznie
        fixtures.sort(key=lambda x: x['fixture']['date'])
        return fixtures
    except Exception as e:
        st.error(f"Błąd pobierania meczów: {e}")
        return []

@st.cache_data(ttl=3600)
def get_players_list(team_id):
    """Pobiera skład drużyny do listy strzelców."""
    url = f"https://v3.football.api-sports.io/players/squads?team={team_id}"
    res = requests.get(url, headers=HEADERS).json()
    if res.get('response'):
        return [p['name'] for p in res['response'][0]['players']]
    return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje lub aktualizuje typ w Supabase."""
    data = {
        "user_id": user_id,
        "match_id": match_id,
        "home_score": h_score,
        "away_score": a_score,
        "scorer_name": scorer,
        "created_at": datetime.now().isoformat()
    }
    # .upsert wymaga klucza UNIQUE (user_id, match_id) w bazie, który już dodałeś
    supabase.table("predictions").upsert(data).execute()

# ==========================================
# 3. INTERFEJS STREAMLIT
# ==========================================

st.set_page_config(page_title="Predicty 25/26", page_icon="⚽", layout="wide")
st.title("⚽ Liga Predicty - Sezon 2025/2026")

# --- LOGOWANIE ---
if 'user_id' not in st.session_state:
    st.subheader("Zaloguj się, aby typować")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Hasło", type="password")
        if st.form_submit_button("Wejdź do gry"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user_id'] = res.user.id
                st.session_state['user_email'] = res.user.email
                st.rerun()
            except Exception:
                st.error("Nieprawidłowy email lub hasło.")
else:
    # --- PASEK BOCZNY ---
    st.sidebar.info(f"Zalogowany jako: {st.session_state['user_email']}")
    if st.sidebar.button("Wyloguj się"):
        del st.session_state['user_id']
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    # --- TAB 1: TYPOWANIE ---
    with tab1:
        st.header("Nadchodzące mecze Premier League 25/26")
        fixtures = get_fixtures(league_id=39, season=2025)
        
        if not fixtures:
            st.info("Nie znaleziono nadchodzących meczów na ten okres.")
        
        for f in fixtures:
            fid = f['fixture']['id']
            home = f['teams']['home']
            away = f['teams']['away']
            match_date = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00'))
            
            with st.expander(f"🗓️ {match_date.strftime('%d.%m %H:%M')} | {home['name']} vs {away['name']}"):
                # Blokada czasowa (nie można typować po rozpoczęciu meczu)
                if datetime.now().astimezone() < match_date:
                    c1, c2 = st.columns(2)
                    h_score = c1.number_input(f"Gole: {home['name']}", 0, 15, key=f"h_{fid}")
                    a_score = c2.number_input(f"Gole: {away['name']}", 0, 15, key=f"a_{fid}")
                    
                    with st.spinner('Ładowanie listy strzelców...'):
                        players = get_players_list(home['id']) + get_players_list(away['id'])
                        players = sorted(list(set(players)))
                    
                    scorer = st.selectbox("Kto strzeli gola?", ["Brak"] + players, key=f"s_{fid}")
                    
                    if st.button("Wyślij Predict", key=f"btn_{fid}"):
                        save_prediction(st.session_state['user_id'], fid, h_score, a_score, scorer)
                        st.success("Typ zapisany!")
                else:
                    st.error("🔒 Mecz już trwa lub się zakończył.")

    # --- TAB 2: RANKING ---
    with tab2:
        st.header("Ranking Graczy")
        try:
            res = supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df.columns = ["Gracz", "Punkty"]
                df.index += 1
                st.table(df)
            else:
                st.write("Ranking jest jeszcze pusty.")
        except Exception as e:
            st.error(f"Błąd bazy danych: {e}")

    # --- TAB 3: MOJE TYPY ---
    with tab3:
        st.header("Twoje ostatnie typy")
        try:
            my_preds = supabase.table("predictions").select("*").eq("user_id", st.session_state['user_id']).execute()
            if my_preds.data:
                st.write(pd.DataFrame(my_preds.data))
            else:
                st.write("Jeszcze nic nie wytypowałeś.")
        except Exception as e:
            st.error(f"Błąd pobierania typów: {e}")
