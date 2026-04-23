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

# TUTAJ WKLEJ SWÓJ TOKEN Z FOOTBALL-DATA.ORG
FOOTBALL_DATA_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE API
# ==========================================

def get_fixtures():
    """Pobiera mecze Premier League z Football-Data.org."""
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        formatted = []
        for m in matches:
            formatted.append({
                'fixture_id': m['id'],
                'date': m['utcDate'],
                'home_team': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                'away_team': m['awayTeam']['shortName'] or m['awayTeam']['name'],
                'home_id': m['homeTeam']['id'],
                'away_id': m['awayTeam']['id']
            })
        return formatted[:15]
    except:
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje typ do bazy."""
    data = {
        "user_id": user_id,
        "match_id": str(match_id),
        "home_score": h_score,
        "away_score": a_score,
        "scorer_name": scorer,
        "created_at": datetime.now().isoformat()
    }
    # Używamy rpc lub bezpośredniego insertu z obsługą błędów
    try:
        supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd bazy: {e}")
        return False

# ==========================================
# 3. INTERFEJS
# ==========================================

st.set_page_config(page_title="Predicty 25/26", page_icon="⚽", layout="wide")
st.title("⚽ Liga Predicty - Sezon 2025/2026")

if 'user_id' not in st.session_state:
    st.subheader("Zaloguj się")
    with st.form("login"):
        email = st.text_input("Email")
        pw = st.text_input("Hasło", type="password")
        if st.form_submit_button("Graj"):
            try:
                auth = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state['user_id'] = auth.user.id
                st.session_state['user_email'] = auth.user.email
                st.rerun()
            except:
                st.error("Błąd logowania")
else:
    st.sidebar.write(f"Konto: {st.session_state['user_email']}")
    if st.sidebar.button("Wyloguj"):
        del st.session_state['user_id']
        st.rerun()

    t1, t2, t3 = st.tabs(["📝 Typuj", "🏆 Ranking", "📋 Moje Typy"])

    with t1:
        matches = get_fixtures()
        if not matches:
            st.warning("Podaj poprawny TOKEN w kodzie!")
        
        for m in matches:
            with st.expander(f"{m['home_team']} vs {m['away_team']} ({m['date'][:10]})"):
                c1, c2 = st.columns(2)
                h_s = c1.number_input("Gole Dom", 0, 10, key=f"h{m['fixture_id']}")
                a_s = c2.number_input("Gole Wyjazd", 0, 10, key=f"a{m['fixture_id']}")
                
                # Rozwiązanie problemu strzelca: 
                # Zostawiamy wpisywanie, ale dodajemy instrukcję, by unikać błędów.
                st.markdown("**Strzelec:** (Wpisz nazwisko, np. Haaland, Salah)")
                scorer = st.text_input("Nazwisko piłkarza", key=f"s{m['fixture_id']}")
                
                if st.button("Zapisz", key=f"b{m['fixture_id']}"):
                    if not scorer:
                        st.error("Musisz podać strzelca!")
                    else:
                        success = save_prediction(st.session_state['user_id'], m['fixture_id'], h_s, a_s, scorer)
                        if success:
                            st.success("Typ zapisany!")

    with t2:
        res = supabase.table("profiles").select("username, points").order("points", desc=True).execute()
        if res.data:
            st.table(pd.DataFrame(res.data))

    with t3:
        my = supabase.table("predictions").select("*").eq("user_id", st.session_state['user_id']).execute()
        if my.data:
            st.write(pd.DataFrame(my.data))
