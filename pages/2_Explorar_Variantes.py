
import json
import os
import sys
from pathlib import Path
from io import StringIO
from datetime import datetime
from urllib.parse import unquote

import chess
import chess.pgn
import chess.svg
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

st.set_page_config(
    page_title="Explorador de Variantes — Metrificador 64 Casas",
    page_icon="🔎",
    layout="wide"
)

st.markdown(
    """
    <style>
    :root {
        --bg-main: #2C2520;
        --bg-main-2: #241E1A;
        --bg-main-3: #332B25;
        --bg-card: #3E352F;
        --bg-card-2: #4A4038;
        --accent: #C9A063;
        --accent-soft: #E0BE7C;
        --text-main: #F5EBE0;
        --text-soft: #E6D6C3;
        --text-muted: #CBB8A3;
        --border-soft: rgba(201, 160, 99, 0.30);
        --shadow-soft: rgba(0, 0, 0, 0.28);
        --success-text: #9EE6A4;
        --danger-text: #F2A6A0;
    }
    .stApp {
        background: linear-gradient(135deg, #2C2520 0%, #241E1A 52%, #332B25 100%);
        color: var(--text-main);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        color: var(--text-main);
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #211B17 0%, #2C2520 58%, #241E1A 100%);
        border-right: 1px solid var(--border-soft);
    }
    section[data-testid="stSidebar"] * { color: var(--text-main) !important; }
    h1, h2, h3, h4, h5, h6 { color: var(--text-main) !important; }
    p, li, span, label, div { color: var(--text-main); }
    .stCaption, [data-testid="stCaptionContainer"], small { color: var(--text-muted) !important; }
    a { color: var(--accent-soft) !important; text-decoration-color: rgba(201,160,99,0.45) !important; }
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #3E352F 0%, #4A4038 100%);
        border: 1px solid var(--border-soft);
        padding: 1rem;
        border-radius: 16px;
        box-shadow: 0 6px 18px var(--shadow-soft);
    }
    div[data-testid="stMetric"] label { color: var(--text-soft) !important; font-weight: 650; }
    div[data-testid="stMetricValue"] { color: var(--accent) !important; font-weight: 800; }
    .variant-card {
        background: rgba(62,53,47,0.92);
        border: 1px solid var(--border-soft);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 6px 18px var(--shadow-soft);
        margin-bottom: 1rem;
    }
    .board-card {
        background: rgba(62,53,47,0.92);
        border: 1px solid var(--border-soft);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 6px 18px var(--shadow-soft);
        display: flex;
        justify-content: center;
    }
    .stButton > button {
        background: linear-gradient(135deg, #4A3C33 0%, #5A493D 100%) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
    }
    .stButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: #3A312B !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] > div {
        background: #3A312B !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] span, div[data-baseweb="select"] div { color: var(--text-main) !important; }
    div[role="radiogroup"] label, div[data-testid="stCheckbox"] label { color: var(--text-main) !important; }
    div[data-testid="stDataFrame"], [data-testid="stTable"] {
        background: var(--bg-card);
        border-radius: 14px;
        border: 1px solid var(--border-soft);
        box-shadow: 0 6px 18px var(--shadow-soft);
    }
    details {
        background: rgba(62,53,47,0.86) !important;
        border-radius: 12px;
        border: 1px solid var(--border-soft) !important;
        color: var(--text-main) !important;
    }
    details summary, details summary * { color: var(--accent-soft) !important; font-weight: 700; }
    div[data-testid="stAlert"] {
        background: #4A4038;
        border: 1px solid var(--border-soft);
        color: var(--text-main);
        border-radius: 12px;
    }
    div[data-testid="stAlert"] * { color: var(--text-main) !important; }
    hr { border-color: var(--border-soft); }
    code {
        background: #2C2520 !important;
        color: var(--accent-soft) !important;
        border: 1px solid rgba(201,160,99,0.18);
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def clean_eco_url(eco_url):
    if not eco_url:
        return None
    last_part = eco_url.rstrip("/").split("/")[-1]
    last_part = unquote(last_part)
    return last_part.replace("-", " ")


def detect_opening(game):
    moves = []
    board = game.board()
    for i, move in enumerate(game.mainline_moves()):
        moves.append(board.san(move))
        board.push(move)
        if i >= 11:
            break
    sequence = " ".join(moves)

    if sequence.startswith("e4 e5 Bc4"):
        return "Abertura do Bispo"
    if sequence.startswith("e4 e5 Nc3"):
        return "Abertura Viena"
    if sequence.startswith("e4 e5 Nf3 Nc6 Nc3 Nf6"):
        return "Abertura dos Quatro Cavalos"
    if sequence.startswith("e4 e5 Nf3 Nc6 Nc3"):
        return "Abertura dos Três Cavalos"
    if sequence.startswith("e4 e5 f4"):
        return "Gambito do Rei"
    if sequence.startswith("e4 e5 Nf3 Nc6 d4 exd4 c3"):
        return "Gambito Dinamarquês"
    if sequence.startswith("e4 e5 Nf3 Nc6 d4 exd4 Bc4"):
        return "Gambito Escocês"
    if sequence.startswith("e4 e5 Nf3 Nc6 d4"):
        return "Escocesa"
    if sequence.startswith("e4 e5 Nf3 d6"):
        return "Defesa Philidor"
    if sequence.startswith("e4 e5 Nf3 Nc6 c3"):
        return "Abertura Ponziani"
    if sequence.startswith("e4 e5 Nf3 Nf6"):
        return "Defesa Petroff"
    if sequence.startswith("e4 e5 Nf3 Nc6 Bb5"):
        return "Ruy Lopez"
    if sequence.startswith("e4 e5 Nf3 Nc6 Bc4"):
        return "Italiana"
    if sequence.startswith("e4 Nf6"):
        return "Defesa Alekhine"
    if sequence.startswith("e4 c5"):
        return "Defesa Siciliana"
    if sequence.startswith("e4 e6"):
        return "Defesa Francesa"
    if sequence.startswith("e4 c6"):
        return "Caro-Kann"
    if sequence.startswith("e4 d5"):
        return "Defesa Escandinava"
    if sequence.startswith("e4 b6"):
        return "Defesa Owen"
    if sequence.startswith("e4 d6"):
        return "Defesa Pirc"
    if sequence.startswith("e4 g6"):
        return "Defesa Moderna"
    if sequence.startswith("d4 e5"):
        return "Gambito Englund"
    if sequence.startswith("d4 f5"):
        return "Defesa Holandesa"
    if sequence.startswith("d4 Nf6 c4 e6 Nc3 Bb4"):
        return "Defesa Nimzoíndia"
    if sequence.startswith("d4 Nf6 c4 e6 Nf3 b6"):
        return "Defesa Índia da Dama"
    if sequence.startswith("d4 Nf6 c4 c5 d5 b5"):
        return "Gambito Benko"
    if sequence.startswith("d4 Nf6 c4 c5 d5"):
        return "Defesa Benoni"
    if sequence.startswith("d4 Nf6 c4 g6 Nc3 d5"):
        return "Defesa Grünfeld"
    if sequence.startswith("d4 Nf6 c4 g6"):
        return "Defesa Índia do Rei"
    if sequence.startswith("d4 d5 c4 c6"):
        return "Defesa Eslava"
    if sequence.startswith("d4 d5 c4"):
        return "Gambito da Dama"
    if sequence.startswith("d4 d5 Bf4") or sequence.startswith("d4 Nf6 Bf4"):
        return "Sistema London"
    if sequence.startswith("c4"):
        return "Inglesa"
    if sequence.startswith("Nf3"):
        return "Réti"
    return "Outras"


def get_opening_from_headers_or_moves(game):
    eco = game.headers.get("ECO")
    eco_url = game.headers.get("ECOUrl")
    opening = game.headers.get("Opening")
    if opening and eco:
        return f"{eco} - {opening}"
    if eco_url and eco:
        return f"{eco} - {clean_eco_url(eco_url)}"
    if opening:
        return opening
    if eco_url:
        return clean_eco_url(eco_url)
    if eco:
        return f"{eco} - Abertura não identificada"
    return detect_opening(game)


def get_opening_family(game):
    eco_url = game.headers.get("ECOUrl")
    if eco_url:
        name = clean_eco_url(eco_url).lower()
        mapping = [
            ("sicilian defense", "Defesa Siciliana"), ("french defense", "Defesa Francesa"),
            ("caro kann", "Caro-Kann"), ("scandinavian defense", "Defesa Escandinava"),
            ("petrov", "Defesa Petroff"), ("petroff", "Defesa Petroff"),
            ("philidor", "Defesa Philidor"), ("ponziani", "Abertura Ponziani"),
            ("owen", "Defesa Owen"), ("pirc", "Defesa Pirc"), ("modern defense", "Defesa Moderna"),
            ("four knights", "Quatro Cavalos"), ("three knights", "Três Cavalos"),
            ("scotch gambit", "Gambito Escocês"), ("scotch game", "Escocesa"),
            ("king's gambit", "Gambito do Rei"), ("kings gambit", "Gambito do Rei"),
            ("ruy lopez", "Ruy Lopez"), ("italian game", "Italiana"),
            ("queen's pawn opening", "Abertura do Peão da Dama"), ("queens pawn opening", "Abertura do Peão da Dama"),
            ("queen's gambit", "Gambito da Dama"), ("queens gambit", "Gambito da Dama"),
            ("catalan", "Abertura Catalã"), ("semi slav", "Defesa Semieslava"), ("semi-slav", "Defesa Semieslava"),
            ("slav defense", "Defesa Eslava"), ("bogo indian", "Defesa Bogoíndia"), ("bogo-indian", "Defesa Bogoíndia"),
            ("budapest", "Gambito Budapeste"), ("nimzo indian", "Defesa Nimzoíndia"),
            ("queen's indian", "Defesa Índia da Dama"), ("queens indian", "Defesa Índia da Dama"),
            ("grunfeld", "Defesa Grünfeld"), ("grünfeld", "Defesa Grünfeld"),
            ("king's indian", "Defesa Índia do Rei"), ("kings indian", "Defesa Índia do Rei"),
            ("benko gambit", "Gambito Benko"), ("benoni", "Defesa Benoni"),
            ("dutch defense", "Defesa Holandesa"), ("englund gambit", "Gambito Englund"),
            ("alekhine", "Defesa Alekhine"), ("london system", "Sistema London"),
            ("colle", "Sistema Colle"), ("stonewall", "Stonewall"),
            ("trompowsky", "Ataque Trompowsky"), ("torre attack", "Ataque Torre"),
            ("english opening", "Inglesa"), ("reti opening", "Réti"),
            ("bird", "Bird"), ("grob", "Grob"), ("polish", "Abertura Polaca"), ("sokolsky", "Abertura Polaca"),
            ("danish gambit", "Gambito Dinamarquês"), ("vienna", "Abertura Viena"), ("bishop", "Abertura do Bispo"),
        ]
        for needle, family in mapping:
            if needle in name:
                return family
    return detect_opening(game)


def classify_side(opening, color):
    black_defenses = {
        "Defesa Siciliana", "Defesa Francesa", "Caro-Kann", "Defesa Escandinava", "Defesa Petroff",
        "Defesa Philidor", "Defesa Owen", "Defesa Pirc", "Defesa Moderna", "Defesa Eslava",
        "Defesa Semieslava", "Defesa Grünfeld", "Defesa Índia do Rei", "Defesa Nimzoíndia",
        "Defesa Bogoíndia", "Gambito Benko", "Gambito Budapeste", "Defesa Benoni",
        "Defesa Alekhine", "Defesa Holandesa", "Defesa Índia da Dama", "Gambito Englund"
    }
    white_openings = {
        "Ruy Lopez", "Italiana", "Escocesa", "Abertura Ponziani", "Gambito do Rei",
        "Gambito Escocês", "Gambito da Dama", "Abertura Catalã", "Sistema London", "Sistema Colle",
        "Ataque Trompowsky", "Ataque Torre", "Inglesa", "Réti", "Abertura do Bispo", "Abertura Viena",
        "Abertura dos Quatro Cavalos", "Abertura dos Três Cavalos", "Quatro Cavalos", "Três Cavalos",
        "Stonewall", "Bird", "Grob", "Abertura Polaca", "Gambito Dinamarquês", "Abertura do Peão da Dama"
    }
    if opening in black_defenses:
        return f"Joguei: {opening}" if color == "Pretas" else f"Enfrentei: {opening}"
    if opening in white_openings:
        return f"Joguei: {opening}" if color == "Brancas" else f"Enfrentei: {opening}"
    return f"Indefinido: {opening}"


def get_opening_sequence(game, max_plies=6):
    board = game.board()
    san_moves = []
    fens = [board.fen()]
    for move in game.mainline_moves():
        san = board.san(move)
        san_moves.append(san)
        board.push(move)
        fens.append(board.fen())
        if len(san_moves) >= max_plies:
            break
    return san_moves, fens


def san_to_pt(san):
    if not isinstance(san, str):
        return san
    if san.startswith("O-O"):
        return san
    piece_map = {"N": "C", "Q": "D", "R": "T", "K": "R", "B": "B"}
    return piece_map.get(san[0], san[0]) + san[1:] if san else san


def format_san_sequence_pt(moves, max_plies=6):
    if not isinstance(moves, list):
        return ""
    return " ".join(san_to_pt(move) for move in moves[:max_plies])


def result_to_pt(result_label):
    return {"win": "Vitória", "draw": "Empate", "loss": "Derrota"}.get(result_label, "")


def game_row_style(result_label):
    if result_label == "win":
        return "color: #9EE6A4; font-weight: 700;"
    if result_label == "loss":
        return "color: #F2A6A0; font-weight: 700;"
    return "color: #F5EBE0;"


def html_escape(value):
    if pd.isna(value):
        return ""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#x27;"))


@st.cache_data(show_spinner="Processando partidas para o explorador de variantes...")
def load_variant_games(games_filename, username, file_mtime):
    with open(games_filename, "r", encoding="utf-8") as f:
        games = json.load(f)

    rows = []
    for game_data in games:
        pgn_text = game_data.get("pgn")
        if not pgn_text:
            continue
        game = chess.pgn.read_game(StringIO(pgn_text))
        if game is None:
            continue

        white = game.headers.get("White", "")
        black = game.headers.get("Black", "")
        result = game.headers.get("Result", "*")

        if username.lower() == white.lower():
            color = "Brancas"
            opponent = black
            score = 1 if result == "1-0" else 0 if result == "0-1" else 0.5
            rating = game_data.get("white", {}).get("rating")
            opponent_rating = game_data.get("black", {}).get("rating")
        elif username.lower() == black.lower():
            color = "Pretas"
            opponent = white
            score = 1 if result == "0-1" else 0 if result == "1-0" else 0.5
            rating = game_data.get("black", {}).get("rating")
            opponent_rating = game_data.get("white", {}).get("rating")
        else:
            continue

        if score == 1:
            result_label = "win"
        elif score == 0:
            result_label = "loss"
        else:
            result_label = "draw"

        timestamp = game_data.get("end_time")
        game_date = datetime.fromtimestamp(timestamp) if timestamp else None
        opening = get_opening_from_headers_or_moves(game)
        opening_family = get_opening_family(game)
        perspective = classify_side(opening_family, color)
        opening_san_moves, opening_fens = get_opening_sequence(game, max_plies=6)

        rows.append({
            "opening": opening,
            "opening_family": opening_family,
            "color": color,
            "perspective": perspective,
            "score": score,
            "result_label": result_label,
            "rating": rating,
            "opponent": opponent,
            "opponent_rating": opponent_rating,
            "date": game_date,
            "time_class": game_data.get("time_class", "unknown"),
            "url": game_data.get("url"),
            "opening_san_moves": opening_san_moves,
            "opening_fens": opening_fens,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.dropna(subset=["date"]).sort_values(by="date").reset_index(drop=True)
    return df


def build_variant_stats(base_df):
    variant_df = base_df[base_df["perspective"].astype(str).str.startswith("Joguei:")].copy()
    if len(variant_df) == 0:
        return pd.DataFrame(), variant_df

    stats = variant_df.groupby(["color", "opening_family", "opening"]).agg(
        games=("opening", "count"),
        score=("score", "sum")
    ).reset_index()
    stats["winrate"] = (stats["score"] / stats["games"] * 100).round(1)
    stats = stats.sort_values(by=["color", "games", "winrate"], ascending=[True, False, False])
    stats["variant_key"] = stats.apply(
        lambda row: f"{row['color']}||{row['opening_family']}||{row['opening']}",
        axis=1
    )
    return stats, variant_df


def display_variant_table(stats):
    display = stats.rename(columns={
        "color": "Cor",
        "opening_family": "Família",
        "opening": "Variante ECO/Chess.com",
        "games": "Partidas",
        "score": "Pontuação",
        "winrate": "Aproveitamento (%)",
    })[["Cor", "Família", "Variante ECO/Chess.com", "Partidas", "Pontuação", "Aproveitamento (%)"]]
    st.dataframe(display, use_container_width=True, hide_index=True)


def show_games_table(games_df):
    if len(games_df) == 0:
        st.info("Nenhuma partida encontrada para esta variante.")
        return

    games_display = games_df[["date", "color", "result_label", "opponent", "opponent_rating", "rating", "url"]].copy()
    games_display["date"] = pd.to_datetime(games_display["date"]).dt.strftime("%d/%m/%Y")
    html = """
    <style>
    .variant-games-table-wrapper { overflow-x: auto; margin-top: .5rem; margin-bottom: 1rem; border-radius: 14px; box-shadow: 0 6px 18px rgba(0,0,0,.28); border: 1px solid rgba(201,160,99,.30); }
    table.variant-games-table { width: 100%; border-collapse: collapse; background: rgba(62,53,47,.92); border-radius: 14px; overflow: hidden; font-size: .92rem; color: #F5EBE0; }
    table.variant-games-table th { background: rgba(74,64,56,.98); color: #C9A063; text-align: left; padding: .65rem .75rem; border-bottom: 1px solid rgba(201,160,99,.30); white-space: nowrap; }
    table.variant-games-table td { padding: .55rem .75rem; border-bottom: 1px solid rgba(201,160,99,.18); vertical-align: top; color: #F5EBE0; }
    table.variant-games-table tr:last-child td { border-bottom: none; }
    table.variant-games-table tr:hover td { background: rgba(201,160,99,.08); }
    table.variant-games-table a { color: #E0BE7C; font-weight: 700; text-decoration: none; }
    table.variant-games-table a:hover { color: #C9A063; text-decoration: underline; }
    </style>
    <div class="variant-games-table-wrapper"><table class="variant-games-table"><thead><tr>
    """
    headers = ["Data", "Cor", "Resultado", "Adversário", "Rating adversário", "Seu rating", "Partida"]
    for header in headers:
        html += f"<th>{html_escape(header)}</th>"
    html += "</tr></thead><tbody>"

    for _, row in games_display.iterrows():
        style = game_row_style(row.get("result_label"))
        html += f'<tr style="{style}">'
        html += f"<td>{html_escape(row.get('date'))}</td>"
        html += f"<td>{html_escape(row.get('color'))}</td>"
        html += f"<td>{html_escape(result_to_pt(row.get('result_label')))}</td>"
        html += f"<td>{html_escape(row.get('opponent'))}</td>"
        html += f"<td>{html_escape(row.get('opponent_rating'))}</td>"
        html += f"<td>{html_escape(row.get('rating'))}</td>"
        url = row.get("url")
        if isinstance(url, str) and url.strip():
            html += f'<td><a href="{html_escape(url.strip())}" target="_blank">Abrir partida</a></td>'
        else:
            html += "<td></td>"
        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


st.title("🔎 Explorador de Variantes")
st.caption("Investigue as variantes mais frequentes, veja a posição inicial representativa e acesse as partidas jogadas nessa linha.")

try:
    st.page_link("dashboard.py", label="← Voltar ao dashboard", icon="♟")
except Exception:
    pass

st.sidebar.header("Usuário do Chess.com")
username_default = st.session_state.get("chess_username", "") or ""
username = st.sidebar.text_input("Digite o username", value=username_default, placeholder="Exemplo: fabiorr87").strip()
st.session_state["chess_username"] = username

if not username:
    st.info("Digite um username na barra lateral para carregar as variantes.")
    st.stop()

games_filename = f"games_{username.lower()}.json"
if not os.path.exists(games_filename):
    st.warning(
        f"Nenhum arquivo de partidas encontrado para {username}. "
        "Volte ao dashboard principal e use o botão para baixar as partidas desse usuário."
    )
    st.stop()

file_mtime = os.path.getmtime(games_filename)
df = load_variant_games(games_filename, username, file_mtime)
if len(df) == 0:
    st.warning("Nenhuma partida processável foi encontrada para este usuário.")
    st.stop()

st.sidebar.header("Filtros")
time_class_labels = {
    "rapid": "Rápidas",
    "blitz": "Blitz",
    "bullet": "Bullet",
    "daily": "Diárias",
}
available_time_classes = [tc for tc in ["rapid", "blitz", "bullet", "daily"] if tc in set(df["time_class"].dropna())]
if available_time_classes:
    selected_time_class = st.sidebar.selectbox(
        "Ritmo",
        options=available_time_classes,
        format_func=lambda x: time_class_labels.get(x, x)
    )
    filtered_df = df[df["time_class"] == selected_time_class].copy()
else:
    filtered_df = df.copy()

color_filter = st.sidebar.selectbox("Cor", ["Todas", "Brancas", "Pretas"])
if color_filter != "Todas":
    filtered_df = filtered_df[filtered_df["color"] == color_filter].copy()

variant_stats, variant_df = build_variant_stats(filtered_df)
if len(variant_stats) == 0:
    st.info("Nenhuma variante jogada encontrada para os filtros atuais.")
    st.stop()

st.markdown("### 🔍 Variantes mais frequentes")
display_variant_table(variant_stats)

st.markdown("### Escolha uma variante para investigar")
option_map = {
    row["variant_key"]: (
        f"{row['color']} — {row['opening_family']} — {row['opening']} "
        f"({int(row['games'])} partida(s), {row['winrate']}%)"
    )
    for _, row in variant_stats.iterrows()
}

selected_key = st.selectbox(
    "Variante",
    options=list(option_map.keys()),
    format_func=lambda key: option_map.get(key, key)
)

selected_color, selected_family, selected_opening = selected_key.split("||", 2)
selected_games = variant_df[
    (variant_df["color"] == selected_color) &
    (variant_df["opening_family"] == selected_family) &
    (variant_df["opening"] == selected_opening)
].copy()

selected_stat = variant_stats[variant_stats["variant_key"] == selected_key].iloc[0]

st.markdown('<div class="variant-card">', unsafe_allow_html=True)
st.markdown(f"### {selected_family}")
st.markdown(f"**Variante:** {selected_opening}")
st.markdown(f"**Cor:** {selected_color}")
st.markdown('</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)
col_a.metric("Partidas", int(selected_stat["games"]))
col_b.metric("Pontuação", selected_stat["score"])
col_c.metric("Aproveitamento", f"{selected_stat['winrate']}%")

example = selected_games.iloc[0]
opening_moves = example.get("opening_san_moves")
fens = example.get("opening_fens")
position_fen = None
if isinstance(fens, list) and len(fens) > 1:
    # Usa a última posição da sequência inicial armazenada, até 6 meio-lances.
    position_fen = fens[-1]
else:
    position_fen = chess.STARTING_FEN

st.markdown("### Posição representativa da variante")
st.caption(
    "O tabuleiro usa a sequência inicial armazenada para esta variante, normalmente até os 6 primeiros meio-lances."
)

col_board, col_moves = st.columns([1, 1.2])
with col_board:
    board = chess.Board(position_fen)
    orientation = chess.WHITE if selected_color == "Brancas" else chess.BLACK
    board_svg = chess.svg.board(board=board, size=440, orientation=orientation)
    st.markdown('<div class="board-card">', unsafe_allow_html=True)
    components.html(board_svg, height=460)
    st.markdown('</div>', unsafe_allow_html=True)

with col_moves:
    st.markdown('<div class="variant-card">', unsafe_allow_html=True)
    st.markdown("#### Linha inicial")
    sequence_text = format_san_sequence_pt(opening_moves, max_plies=6)
    st.write(sequence_text if sequence_text else "Sequência não disponível.")
    st.markdown("#### Interpretação")
    st.write(
        "A lista abaixo reúne todas as partidas do usuário que caem nesta mesma família e variante ECO/Chess.com. "
        "Use os links para revisar os planos recorrentes e comparar como a posição evoluiu em partidas reais."
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("### Partidas nesta variante")
selected_games = selected_games.dropna(subset=["date"]).sort_values("date", ascending=False)
show_games_table(selected_games)
