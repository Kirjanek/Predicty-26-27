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
ADMIN_EMAIL = "k1rj4nek@gmail.com"  # Twój mail - tylko Ty zobaczysz przycisk przeliczania

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. LOGIKA BIZNESOWA (BACKEND)
# ==========================================

def login_user(email, password):
    """Loguje użytkownika i odświeża sesję."""
    try:
        auth = st.session_state.supabase.auth.sign_in_with_password({"email": email, "password": password})
        if auth.user:
            st.session_state.user_id = auth.user.id
            st.session_state.user_email = auth.user.email
            return True
    except:
        return False
    return False

@st.cache_data(ttl=600)
def get_fixtures():
    """Pobiera nadchodzące mecze PL."""
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    try:
        res = requests.get(url, headers=headers).json()
        matches = res.get('matches', [])
        formatted = []
        for m in matches:
            utc_date = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
            pl_date = utc_date + timedelta(hours=2) # Czas polski
            formatted.append({
                'id': str(m['id']),
                'display_date': pl_date.strftime("%d.%m.%Y %H:%M"),
                'raw_date': pl_date,
                'home': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                'away': m['awayTeam']['shortName'] or m['awayTeam']['name']
            })
        return formatted[:15]
    except:
        return []

def save_prediction(user_id, match_id, h_score, a_score, scorer):
    """Zapisuje lub aktualizuje typ w bazie."""
    try:
        data = {
            "user_id": user_id, 
            "match_id": match_id, 
            "home_score": h_score, 
            "away_score": a_score, 
            "scorer_name": scorer.strip()
        }
        st.session_state.supabase.table("predictions").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd bazy: {e}")
        return False

def update_ranking():
    """ADMIN: Pobiera wyniki i przelicza punkty wszystkich graczy."""
    st.info("🔄 Łączenie z API i przeliczanie punktów...")
    url = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
    headers = {'X-Auth-Token': FOOTBALL_TOKEN}
    
    try:
        res = requests.get(url, headers=headers).json()
        finished = res.get('matches', [])
        preds = st.session_state.supabase.table("predictions").select("*").execute().data
        
        user_points = {} # u_id -> punkty

        for m in finished:
            m_id = str(m['id'])
            real_h = m['score']['fullTime']['home']
            real_a = m['score']['fullTime']['away']
            
            # Lista strzelców (małe litery dla łatwego porównania)
            goals = [g['player']['name'].lower() for g in m.get('goals', []) if g.get('player')]
            first_scorer = goals[0] if goals else None

            # Sprawdzamy typy dla tego meczu
            match_preds = [p for p in preds if p['match_id'] == m_id]
            
            for p in match_preds:
                pts = 0
                ph, pa = p['home_score'], p['away_score']
                ps = p['scorer_name'].lower().strip()

                # 1. PUNKTY ZA WYNIK
                if ph == real_h and pa == real_a:
                    pts += 3 # Dokładny wynik
                elif (ph > pa and real_h > real_a) or (ph < pa and real_h < real_a) or (ph == pa and real_h == real_a):
                    pts += 1 # Tendencja (kto wygrał/remis)

                # 2. PUNKTY ZA STRZELCA (5 pkt za 1., 2 pkt za pozostałych)
                if first_scorer and ps in first_scorer:
                    pts += 5
                elif any(ps in s for s in goals):
                    pts += 2
                
                user_points[p['user_id']] = user_points.get(p['user_id'], 0) + pts

        # Aktualizacja tabeli profiles
        for u_id, total in user_points.items():
            st.session_state.supabase.table("profiles").update({"points": total}).eq("id", u_id).execute()
        
        st.success("✅ Ranking zaktualizowany!")
        st.rerun()
    except Exception as e:
        st.error(f"Błąd rozliczania: {e}")

# ==========================================
# 3. INTERFEJS UŻYTKOWNIKA (FRONTEND)
# ==========================================

st.set_page_config(page_title="Liga Predicty", page_icon="⚽", layout="wide")

if 'user_id' not in st.session_state:
    st.title("⚽ Liga Predicty 25/26")
    st.write("Zaloguj się, aby zacząć typowanie.")
    
    with st.form("login_form"):
        email = st.text_input("Email").strip()
        password = st.text_input("Hasło", type="password")
        if st.form_submit_button("Zaloguj do gry"):
            if login_user(email, password):
                st.rerun()
            else:
                st.error("Błędne dane logowania.")
else:
    # Sidebar
    st.sidebar.title(f"Witaj, {st.session_state.user_email.split('@')[0]}!")
    
    if st.session_state.user_email == ADMIN_EMAIL:
        st.sidebar.divider()
        st.sidebar.subheader("👑 Panel Admina")
        if st.sidebar.button("🔄 Przelicz Ranking"):
            update_ranking()
            
    if st.sidebar.button("Wyloguj"):
        st.session_state.supabase.auth.sign_out()
        del st.session_state['user_id']
        st.rerun()

    # Zakładki
    tab1, tab2, tab3 = st.tabs(["📝 Typuj Mecze", "🏆 Ranking", "📋 Moje Typy"])

    with tab1:
        st.header("Nadchodzące mecze")
        fixtures = get_fixtures()
        now = datetime.now()
        
        if not fixtures:
            st.info("Obecnie brak meczów do typowania.")
            
        for f in fixtures:
            is_blocked = now > f['raw_date']
            with st.expander(f"🗓️ {f['display_date']} | {f['home']} - {f['away']}"):
                if is_blocked:
                    st.error("🔒 Mecz już trwa lub się zakończył.")
                else:
                    col1, col2 = st.columns(2)
                    h = col1.number_input(f"Gole {f['home']}", 0, 15, key=f"h{f['id']}")
                    a = col2.number_input(f"Gole {f['away']}", 0, 15, key=f"a{f['id']}")
                    s = st.text_input("Nazwisko strzelca", key=f"s{f['id']}")
                    
                    if st.button("Zatwierdź Predict", key=f"b{f['id']}"):
                        if not s:
                            st.warning("Podaj nazwisko strzelca!")
                        elif save_prediction(st.session_state.user_id, f['id'], h, a, s):
                            st.success(f"Zapisano: {f['home']} {h}:{a} {f['away']} (Strzelec: {s})")

    with tab2:
        st.header("Tabela Ligi")
        try:
            rank_data = st.session_state.supabase.table("profiles").select("username, points").order("points", desc=True).execute().data
            if rank_data:
                df_rank = pd.DataFrame(rank_data)
                df_rank.columns = ["Gracz", "Punkty"]
                st.table(df_rank)
            else:
                st.write("Ranking jest jeszcze pusty.")
        except:
            st.error("Nie udało się załadować rankingu.")

    with tab3:
        st.header("Twoje ostatnie typy")
        try:
            raw_data = st.session_state.supabase.table("predictions").select("match_id, home_score, away_score, scorer_name, created_at").eq("user_id", st.session_state.user_id).execute().data
            
            if raw_data:
                df = pd.DataFrame(raw_data)
                # Mapowanie ID na nazwy drużyn dla czytelności
                fix = {f['id']: f"{f['home']} - {f['away']}" for f in get_fixtures()}
                df['Mecz'] = df['match_id'].map(fix).fillna(df['match_id'])
                
                # Formatowanie tabeli
                df_view = df[['Mecz', 'home_score', 'away_score', 'scorer_name', 'created_at']].copy()
                df_view.columns = ["Mecz", "Dom", "Wyjazd", "Strzelec", "Wysłano"]
                df_view['Wysłano'] = pd.to_datetime(df_view['Wysłano']).dt.strftime('%d.%m %H:%M')
                
                st.dataframe(df_view, use_container_width=True, hide_index=True)
            else:
                st.info("Nie masz jeszcze żadnych typów.")
        except Exception as e:
            st.error(f"Błąd ładowania Twoich typów: {e}")
