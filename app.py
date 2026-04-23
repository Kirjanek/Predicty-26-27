import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client

# ==========================================
# 1. KONFIGURACJA
# ==========================================
SUPABASE_URL = "https://edrlnpuyvpzbdlffwbim.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVkcmxucHV5dnB6YmRsZmZ3YmltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5NTA4NTksImV4cCI6MjA5MjUyNjg1OX0._dzKIbr9ZmmRfihW7WRmUK_d41RJF7DYAk5aTqjJmZI"
FOOTBALL_TOKEN = "21d27ca30b4246dd92da0c67601362ab"

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. FUNKCJE API
# ==========================================

@st.cache_data(ttl=600) # Zapamiętuje mecze na 10 minut
def get_fixtures():
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        formatted = []
        for m in matches:
            utc_date = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
            pl_date = utc_date + timedelta(hours=2) # Czas PL
            
            formatted.append({
                'id': str(m['id']),
                'display_date': pl_date.strftime("%d.%m.%Y %H:%M"),
                'raw_date': pl_date,
                'home': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                'away': m['awayTeam']['shortName'] or m['awayTeam']['name'],
                'home_id': m['homeTeam']['id'],
                'away_id': m['awayTeam']['id']
            })
        return formatted[:15]
    except:
        return []

@st.cache_data(ttl=3600) # Zapamiętuje składy na godzinę
def get_players(home_id, away_id):
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    players = []
    try:
        for team_id in [home_id, away_id]:
            url = f"https://api.football-data.org/v4/teams/{team_id}"
            res = requests.get(url, headers=headers).json()
            squad = res.get('squad', [])
            for p in squad:
                if p['position'] in ['Offence', 'Midfield', 'Defence']:
                    players.append(p['name'])
        return sorted(list(set(players)))
    except:
        return ["Błąd pobierania listy"]

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    try:
        data = {
            "user_id": str(user_id),
            "match_id": str(match_id),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "scorer_name": str(scorer)
        }
        st.session_state.supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")
        return False

# ==========================================
# 3. INTERFEJS
# ==========================================

st.set_page_config(page_title="Liga Predicty 25/26", page_icon="⚽", layout="wide")

if 'user_id' not in st.session_state:
    st.title("⚽ Witaj w Liga Predicty")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip()
        u_pw = st.text_input("Hasło", type="password").strip()
        if st.form_submit_button("Zaloguj"):
            try:
                auth = st.session_state.supabase.auth.sign_in_with_password({"email": u_email, "password": u_pw})
                st.session_state.user_id = auth.user.id
                st.session_state.user_email = auth.user.email
                st.rerun()
            except:
                st.error("Błędne dane logowania.")
else:
    st.sidebar.success(f"Gracz: {st.session_state.user_email}")
    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state['user_id']
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        st.header("Nadchodzące mecze (Czas PL)")
        fixtures = get_fixtures()
        now = datetime.now()
        
        for f in fixtures:
            is_blocked = now > f['raw_date']
            
            with st.expander(f"🗓️ {f['display_date']} | {f['home']} vs {f['away']}"):
                if is_blocked:
                    st.error("🔒 Mecz już się rozpoczął. Typowanie zablokowane.")
                else:
                    col1, col2 = st.columns(2)
                    h_val = col1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                    a_val = col2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                    
                    # Logika ładowania piłkarzy
                    st.write("---")
                    show_players = st.checkbox(f"Pobierz listę piłkarzy dla tego meczu", key=f"chk{f['id']}")
                    
                    if show_players:
                        player_list = get_players(f['home_id'], f['away_id'])
                        sc = st.selectbox("Kto strzeli gola?", ["Brak strzelca / Samobój"] + player_list, key=f"s{f['id']}")
                        
                        if st.button("Zatwierdź Predict", key=f"b{f['id']}"):
                            if save_prediction(st.session_state.user_id, f['id'], h_val, a_val, sc):
                                st.success("Zapisano!")
                    else:
                        st.info("Zaznacz powyższe pole, aby wybrać strzelca z listy.")

    with tab2:
        st.subheader("Ranking")
        try:
            res = st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute()
            if res.data:
                st.table(pd.DataFrame(res.data))
            else:
                st.write("Ranking będzie dostępny wkrótce.")
        except:
            st.write("Błąd ładowania rankingu.")

    with tab3:
        st.subheader("Twoje ostatnie wysłane typy")
        try:
            my = st.session_state.supabase.table("predictions").select("match_id, home_score, away_score, scorer_name").eq("user_id", st.session_state.user_id).execute()
            if my.data:
                st.dataframe(pd.DataFrame(my.data))
            else:
                st.write("Nie masz jeszcze zapisanych typów.")
        except:
            st.write("Błąd pobierania typów.")
