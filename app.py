import streamlit as st
import requests
from datetime import datetime

st.title("🏆 Liga Predict - MS 2026")

# klucz API 
API_KEY = "7d0575164002aad2416ed0759bc40950"

def get_fixtures():
    url = "https://v3.football.api-sports.io/fixtures?league=1&season=2026" # League 1 to World Cup
    headers = {'x-apisports-key': API_KEY}
    response = requests.get(url, headers=headers)
    return response.json()['response']

# Logowanie
if 'user' not in st.session_state:
    with st.form("login_form"):
        username = st.text_input("Login")
        password = st.text_input("Hasło", type="password")
        if st.form_submit_button("Zaloguj"):
            # Tutaj dodamy potem weryfikację z Supabase
            st.session_state['user'] = username
            st.rerun()
else:
    st.write(f"Witaj {st.session_state['user']}!")
    
    # Wyświetlanie meczów
    st.header("Nadchodzące mecze")
    fixtures = get_fixtures()
    for f in fixtures[:5]: # Na razie tylko 5 pierwszych
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        match_time = datetime.fromisoformat(f['fixture']['date'].replace('Z', ''))
        
        col1, col2 = st.columns([3, 1])
        col1.write(f"{home} vs {away} ({match_time.strftime('%d.%m %H:%M')})")
        
        # BLOKADA CZASOWA
        if datetime.now() < match_time:
            if col2.button("Typuj", key=f['fixture']['id']):
                st.info("Tu otworzy się okno typowania")
        else:
            col2.write("🔒 Zablokowane")
