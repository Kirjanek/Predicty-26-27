import streamlit as st
import requests
from datetime import datetime
import pandas as pd
from supabase import create_client

# ==========================================
# 1. KONFIGURACJA
# ==========================================
# Dane Supabase (zostają te same, bo baza działa)
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"

# NOWE API (Football-Data.org) - Wklej tutaj swój token z maila!
FOOTBALL_DATA_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE API I LOGIKA
# ==========================================

def get_fixtures():
    """Pobiera nadchodzące mecze Premier League z Football-Data.org."""
    # PL to kod Premier League w tym API
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        
        # Przerabiamy dane, żeby pasowały do reszty Twojego interfejsu
        formatted = []
        for m in matches:
            formatted.append({
                'fixture': {
                    'id': m['id'],
                    'date': m['utcDate']
                },
                'teams': {
                    'home': {'name': m['homeTeam']['shortName'], 'id': m['homeTeam']['id']},
                    'away': {'name': m['awayTeam']['shortName'], 'id': m['awayTeam']['id']}
                }
            })
        return formatted[:15] # Pokazujemy najbliższe 15 meczów
    except Exception as e:
        st.error(f"Błąd nowego API: {e}")
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje lub aktualizuje typ w Supabase."""
    data = {
        "user_id": user_id,
        "match_id": str(match_id), # ID meczu jako tekst
        "home_score": h_score,
        "away_score": a_score,
        "scorer_name": scorer,
        "created_at": datetime.now().isoformat()
    }
    try:
        supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu do bazy: {e}")
        return False

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
    st.sidebar.info(f"Zalogowany jako: {st.session_state['user_email']}")
    if st.sidebar.button("Wyloguj się"):
        del st.session_state['user_id']
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    # --- TAB 1: TYPOWANIE ---
    with tab1:
        st.header("Nadchodzące mecze Premier League")
        fixtures = get_fixtures()
        
        if not fixtures:
            st.info("Brak nadchodzących meczów (Sprawdź czy Token API jest poprawny).")
        
        for f in fixtures:
            fid = f['fixture']['id']
            home = f['teams']['home']
            away = f['teams']['away']
            # Parsowanie daty z formatu UTC
            match_date = datetime.strptime(f['fixture']['date'], "%Y-%m-%dT%H:%M:%SZ")
            
            with st.expander(f"🗓️ {match_date.strftime('%d.%m %H:%M')} | {home['name']} vs {away['name']}"):
                c1, c2 = st.columns(2)
                h_score = c1.number_input(f"Gole: {home['name']}", 0, 15, key=f"h_{fid}")
                a_score = c2.number_input(f"Gole: {away['name']}", 0, 15, key=f"a_{fid}")
                
                # Uproszczony wybór strzelca (bez pobierania składów, żeby nie marnować limitów API)
                scorer = st.text_input("Kto strzeli gola? (Wpisz nazwisko)", key=f"s_{fid}")
                
                if st.button("Wyślij Predict", key=f"btn_{fid}"):
                    if save_prediction(st.session_state['user_id'], fid, h_score, a_score, scorer):
                        st.success(f"Zapisano typ na mecz {home['name']} vs {away['name']}!")

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
                st.write("Ranking jest pusty. Dodaj użytkowników w Supabase!")
        except Exception as e:
            st.error(f"Błąd rankingu: {e}")

    # --- TAB 3: MOJE TYPY ---
    with tab3:
        st.header("Twoje ostatnie typy")
        try:
            my_preds = supabase.table("predictions").select("match_id, home_score, away_score, scorer_name, created_at").eq("user_id", st.session_state['user_id']).execute()
            if my_preds.data:
                st.write(pd.DataFrame(my_preds.data))
            else:
                st.write("Jeszcze nic nie wytypowałeś.")
        except Exception as e:
            st.error(f"Błąd pobierania typów: {e}")
