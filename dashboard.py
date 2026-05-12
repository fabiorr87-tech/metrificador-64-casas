import json
import os
import chess.pgn
import chess.svg
import chess.engine
import requests
from io import StringIO
from datetime import datetime, timedelta
from urllib.parse import unquote, quote_plus

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit.components.v1 as components

from chess_training_utils import (
    classify_exercise_difficulty,
    classify_exercise_theme,
    generate_exercise_id,
)


DEFAULT_USERNAME = ""
DEFAULT_ENGINE_PATH = os.environ.get(
    "STOCKFISH_PATH",
    "stockfish" if os.name != "nt" else os.path.join("engines", "stockfish.exe")
)
ENGINE_ANALYSIS_VERSION = "stockfish_v2"


# =========================
# DETECÇÃO DE ABERTURAS
# =========================

def detect_opening(game):
    moves = []
    board = game.board()

    for i, move in enumerate(game.mainline_moves()):
        moves.append(board.san(move))
        board.push(move)

        if i >= 11:
            break

    sequence = " ".join(moves)

    # Jogos abertos, aberturas de 1.e4 e gambitos
    if sequence.startswith("e4 e5 Bc4"):
        return "Abertura do Bispo"

    elif sequence.startswith("e4 e5 Nc3"):
        return "Abertura Viena"

    elif sequence.startswith("e4 e5 Nf3 Nc6 Nc3 Nf6"):
        return "Abertura dos Quatro Cavalos"

    elif sequence.startswith("e4 e5 Nf3 Nc6 Nc3"):
        return "Abertura dos Três Cavalos"

    elif sequence.startswith("e4 e5 f4"):
        return "Gambito do Rei"

    elif sequence.startswith("e4 e5 Nf3 Nc6 d4 exd4 c3"):
        return "Gambito Dinamarquês"

    elif sequence.startswith("e4 e5 Nf3 Nc6 d4 exd4 Bc4"):
        return "Gambito Escocês"

    elif sequence.startswith("e4 e5 Nf3 Nc6 d4"):
        return "Escocesa"

    elif sequence.startswith("e4 e5 Nf3 d6"):
        return "Defesa Philidor"

    elif sequence.startswith("e4 e5 Nf3 Nc6 c3"):
        return "Abertura Ponziani"

    elif sequence.startswith("e4 e5 Nf3 Nf6"):
        return "Defesa Petroff"

    elif sequence.startswith("e4 e5 Nf3 Nc6 Bb5"):
        return "Ruy Lopez"

    elif sequence.startswith("e4 e5 Nf3 Nc6 Bc4"):
        return "Italiana"

    # Defesas contra 1.e4
    elif sequence.startswith("e4 Nf6"):
        return "Defesa Alekhine"
    elif sequence.startswith("e4 c5"):
        return "Defesa Siciliana"
    elif sequence.startswith("e4 e6"):
        return "Defesa Francesa"
    elif sequence.startswith("e4 c6"):
        return "Caro-Kann"
    elif sequence.startswith("e4 d5"):
        return "Defesa Escandinava"
    elif sequence.startswith("e4 b6"):
        return "Defesa Owen"
    elif sequence.startswith("e4 d6"):
        return "Defesa Pirc"
    elif sequence.startswith("e4 g6"):
        return "Defesa Moderna"

    # Gambitos e defesas irregulares contra 1.d4
    elif sequence.startswith("d4 e5"):
        return "Gambito Englund"

    elif sequence.startswith("d4 f5"):
        return "Defesa Holandesa"

    # Stonewall pode surgir por várias ordens
    elif (
        sequence.startswith("d4 d5 e3 Nf6 Bd3")
        or sequence.startswith("d4 f5 e3 Nf6 Bd3")
        or sequence.startswith("d4 d5 e3 e6 Bd3")
    ):
        return "Stonewall"

    # Catalã, Bogoíndia, Budapeste e Semieslava
    elif (
        sequence.startswith("d4 Nf6 c4 e6 g3")
        or sequence.startswith("d4 d5 c4 e6 Nf3 Nf6 g3")
        or sequence.startswith("d4 Nf6 c4 e6 Nf3 d5 g3")
    ):
        return "Abertura Catalã"

    elif sequence.startswith("d4 Nf6 c4 e5"):
        return "Gambito Budapeste"

    elif sequence.startswith("d4 Nf6 c4 e6 Nf3 Bb4+"):
        return "Defesa Bogoíndia"

    elif (
        sequence.startswith("d4 d5 c4 e6 Nf3 Nf6 Nc3 c6")
        or sequence.startswith("d4 d5 c4 c6 Nf3 Nf6 Nc3 e6")
    ):
        return "Defesa Semieslava"

    # Índias, Benoni, Benko, Grünfeld
    elif sequence.startswith("d4 Nf6 c4 e6 Nc3 Bb4"):
        return "Defesa Nimzoíndia"
    elif sequence.startswith("d4 Nf6 c4 e6 Nf3 b6"):
        return "Defesa Índia da Dama"
    elif sequence.startswith("d4 Nf6 c4 c5 d5 b5"):
        return "Gambito Benko"
    elif sequence.startswith("d4 Nf6 c4 c5 d5"):
        return "Defesa Benoni"
    elif sequence.startswith("d4 Nf6 c4 g6 Nc3 d5"):
        return "Defesa Grünfeld"
    elif sequence.startswith("d4 Nf6 c4 g6"):
        return "Defesa Índia do Rei"

    # Gambito da Dama e Eslava
    elif sequence.startswith("d4 d5 c4 c6"):
        return "Defesa Eslava"
    elif sequence.startswith("d4 d5 c4"):
        return "Gambito da Dama"

    # Sistemas de peão dama
    elif (
        sequence.startswith("d4 d5 Nf3 Nf6 e3")
        or sequence.startswith("d4 Nf6 Nf3 d5 e3")
        or sequence.startswith("d4 d5 e3 Nf6 Nf3")
    ):
        return "Sistema Colle"

    elif (
        sequence.startswith("d4 Nf6 Bg5")
        or sequence.startswith("d4 d5 Bg5")
    ):
        return "Ataque Trompowsky"

    elif (
        sequence.startswith("d4 Nf6 Nf3 e6 Bg5")
        or sequence.startswith("d4 Nf6 Nf3 d5 Bg5")
        or sequence.startswith("d4 d5 Nf3 Nf6 Bg5")
    ):
        return "Ataque Torre"

    elif (
        sequence.startswith("d4 d5 Bf4")
        or sequence.startswith("d4 Nf6 Bf4")
        or sequence.startswith("d4 Nf6 Nf3 d5 Bf4")
        or sequence.startswith("d4 d5 Nf3 Nf6 Bf4")
    ):
        return "Sistema London"

    # Flancos e aberturas irregulares
    elif sequence.startswith("f4"):
        return "Bird"

    elif sequence.startswith("g4"):
        return "Grob"

    elif sequence.startswith("b4"):
        return "Abertura Polaca"

    elif sequence.startswith("c4"):
        return "Inglesa"

    elif sequence.startswith("Nf3"):
        return "Réti"

    return "Outras"


def clean_eco_url(eco_url):
    if not eco_url:
        return None

    last_part = eco_url.rstrip("/").split("/")[-1]
    last_part = unquote(last_part)
    last_part = last_part.replace("-", " ")

    return last_part


def get_opening_from_headers_or_moves(game):
    eco = game.headers.get("ECO")
    eco_url = game.headers.get("ECOUrl")
    opening = game.headers.get("Opening")

    if opening and eco:
        return f"{eco} - {opening}"

    if eco_url and eco:
        eco_name = clean_eco_url(eco_url)
        return f"{eco} - {eco_name}"

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

        if "sicilian defense" in name:
            return "Defesa Siciliana"
        if "french defense" in name:
            return "Defesa Francesa"
        if "caro kann" in name:
            return "Caro-Kann"
        if "scandinavian defense" in name:
            return "Defesa Escandinava"
        if "petrov" in name or "petroff" in name:
            return "Defesa Petroff"
        if "philidor" in name:
            return "Defesa Philidor"
        if "ponziani" in name:
            return "Abertura Ponziani"
        if "owen" in name:
            return "Defesa Owen"
        if "pirc" in name:
            return "Defesa Pirc"
        if "modern defense" in name:
            return "Defesa Moderna"
        if "four knights" in name:
            return "Quatro Cavalos"
        if "three knights" in name:
            return "Três Cavalos"
        if "scotch gambit" in name:
            return "Gambito Escocês"
        if "scotch game" in name:
            return "Escocesa"
        if "king's gambit" in name or "kings gambit" in name:
            return "Gambito do Rei"
        if "ruy lopez" in name:
            return "Ruy Lopez"
        if "italian game" in name:
            return "Italiana"
        if "queen's pawn opening" in name or "queens pawn opening" in name:
            return "Abertura do Peão da Dama"
        if "queen's gambit" in name or "queens gambit" in name:
            return "Gambito da Dama"
        if "catalan" in name:
            return "Abertura Catalã"
        if "semi slav" in name or "semi-slav" in name:
            return "Defesa Semieslava"
        if "slav defense" in name:
            return "Defesa Eslava"
        if "bogo indian" in name or "bogo-indian" in name:
            return "Defesa Bogoíndia"
        if "budapest" in name:
            return "Gambito Budapeste"
        if "nimzo indian" in name:
            return "Defesa Nimzoíndia"
        if "queen's indian" in name or "queens indian" in name:
            return "Defesa Índia da Dama"
        if "grunfeld" in name or "grünfeld" in name:
            return "Defesa Grünfeld"
        if "king's indian" in name or "kings indian" in name:
            return "Defesa Índia do Rei"
        if "benko gambit" in name:
            return "Gambito Benko"
        if "benoni" in name:
            return "Defesa Benoni"
        if "dutch defense" in name:
            return "Defesa Holandesa"
        if "englund gambit" in name:
            return "Gambito Englund"
        if "alekhine" in name:
            return "Defesa Alekhine"
        if "london system" in name:
            return "Sistema London"
        if "colle" in name:
            return "Sistema Colle"
        if "stonewall" in name:
            return "Stonewall"
        if "trompowsky" in name:
            return "Ataque Trompowsky"
        if "torre attack" in name:
            return "Ataque Torre"
        if "english opening" in name:
            return "Inglesa"
        if "reti opening" in name:
            return "Réti"
        if "bird" in name:
            return "Bird"
        if "grob" in name:
            return "Grob"
        if "polish" in name or "sokolsky" in name:
            return "Abertura Polaca"
        if "danish gambit" in name:
            return "Gambito Dinamarquês"
        if "vienna" in name:
            return "Abertura Viena"
        if "bishop" in name:
            return "Abertura do Bispo"

    return detect_opening(game)


# =========================
# CLASSIFICAÇÃO DE PERSPECTIVA
# =========================

def classify_side(opening, color):
    black_defenses = {
        "Defesa Siciliana",
        "Defesa Francesa",
        "Caro-Kann",
        "Defesa Escandinava",
        "Defesa Petroff",
        "Defesa Philidor",
        "Defesa Owen",
        "Defesa Pirc",
        "Defesa Moderna",
        "Defesa Eslava",
        "Defesa Semieslava",
        "Defesa Grünfeld",
        "Defesa Índia do Rei",
        "Defesa Nimzoíndia",
        "Defesa Bogoíndia",
        "Gambito Benko",
        "Gambito Budapeste",
        "Defesa Benoni",
        "Defesa Alekhine",
        "Defesa Holandesa",
        "Defesa Índia da Dama",
        "Gambito Englund",
    }

    white_openings = {
        "Ruy Lopez",
        "Italiana",
        "Escocesa",
        "Abertura Ponziani",
        "Gambito do Rei",
        "Gambito Escocês",
        "Gambito da Dama",
        "Abertura Catalã",
        "Sistema London",
        "Sistema Colle",
        "Ataque Trompowsky",
        "Ataque Torre",
        "Inglesa",
        "Réti",
        "Abertura do Bispo",
        "Abertura Viena",
        "Abertura dos Quatro Cavalos",
        "Abertura dos Três Cavalos",
        "Quatro Cavalos",
        "Três Cavalos",
        "Stonewall",
        "Bird",
        "Grob",
        "Abertura Polaca",
        "Gambito Dinamarquês",
        "Abertura do Peão da Dama",
    }

    if opening in black_defenses:
        if color == "Pretas":
            return f"Joguei: {opening}"
        return f"Enfrentei: {opening}"

    if opening in white_openings:
        if color == "Brancas":
            return f"Joguei: {opening}"
        return f"Enfrentei: {opening}"

    return f"Indefinido: {opening}"


def make_recommendation(games, winrate):
    if games < 3:
        return "Amostra pequena"
    if winrate >= 60:
        return "Ponto forte"
    if winrate >= 50:
        return "Repertório viável"
    if winrate >= 40:
        return "Atenção"
    return "Fraqueza crítica"


def calculate_streaks(results):
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for result in results:
        if result == "win":
            current_wins += 1
            current_losses = 0
        elif result == "loss":
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0

        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)

    return max_wins, max_losses


def result_to_pt(result_label):
    result_map = {
        "win": "Vitória",
        "draw": "Empate",
        "loss": "Derrota"
    }
    return result_map.get(result_label, "")


def game_row_style(result_label):
    if result_label == "win":
        return "color: #9EE6A4; font-weight: 700;"
    if result_label == "loss":
        return "color: #F2A6A0; font-weight: 700;"
    return "color: #F5EBE0;"


def html_escape(value):
    if pd.isna(value):
        return ""

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def show_games_table(games_df):
    if len(games_df) == 0:
        st.info("Nenhuma partida encontrada.")
        return

    games_display = games_df[[
        "date",
        "color",
        "result_label",
        "opponent",
        "opponent_rating",
        "rating",
        "perspective",
        "url"
    ]].copy()

    games_display["date"] = pd.to_datetime(games_display["date"]).dt.strftime("%d/%m/%Y")

    headers = [
        "Data",
        "Cor",
        "Resultado",
        "Adversário",
        "Rating adversário",
        "Seu rating",
        "Abertura/Perspectiva",
        "Partida"
    ]

    html = """
    <style>
    .games-table-wrapper {
        overflow-x: auto;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
        border-radius: 14px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
        border: 1px solid rgba(201, 160, 99, 0.30);
    }
    table.games-table {
        width: 100%;
        border-collapse: collapse;
        background: rgba(62, 53, 47, 0.92);
        border-radius: 14px;
        overflow: hidden;
        font-size: 0.92rem;
        color: #F5EBE0;
    }
    table.games-table th {
        background: rgba(74, 64, 56, 0.98);
        color: #C9A063;
        text-align: left;
        padding: 0.65rem 0.75rem;
        border-bottom: 1px solid rgba(201, 160, 99, 0.30);
        white-space: nowrap;
    }
    table.games-table td {
        padding: 0.55rem 0.75rem;
        border-bottom: 1px solid rgba(201, 160, 99, 0.18);
        vertical-align: top;
        color: #F5EBE0;
    }
    table.games-table tr:last-child td {
        border-bottom: none;
    }
    table.games-table tr:hover td {
        background: rgba(201, 160, 99, 0.08);
    }
    table.games-table a {
        color: #E0BE7C;
        font-weight: 700;
        text-decoration: none;
    }
    table.games-table a:hover {
        color: #C9A063;
        text-decoration: underline;
    }
    </style>
    <div class="games-table-wrapper">
    <table class="games-table">
        <thead>
            <tr>
    """

    for header in headers:
        html += f"<th>{html_escape(header)}</th>"

    html += """
            </tr>
        </thead>
        <tbody>
    """

    for _, row in games_display.iterrows():
        result_label = row.get("result_label")
        style = game_row_style(result_label)
        result_text = result_to_pt(result_label)
        url = row.get("url")

        html += f'<tr style="{style}">'
        html += f"<td>{html_escape(row.get('date'))}</td>"
        html += f"<td>{html_escape(row.get('color'))}</td>"
        html += f"<td>{html_escape(result_text)}</td>"
        html += f"<td>{html_escape(row.get('opponent'))}</td>"
        html += f"<td>{html_escape(row.get('opponent_rating'))}</td>"
        html += f"<td>{html_escape(row.get('rating'))}</td>"
        html += f"<td>{html_escape(row.get('perspective'))}</td>"

        if isinstance(url, str) and url.strip():
            safe_url = html_escape(url.strip())
            html += f'<td><a href="{safe_url}" target="_blank">Abrir partida</a></td>'
        else:
            html += "<td></td>"

        html += "</tr>"

    html += """
        </tbody>
    </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


# =========================
# PERFIL DE DESEMPENHO SEM ENGINE
# =========================

def clamp_score(value, minimum=0, maximum=100):
    if value is None or pd.isna(value):
        return None
    return max(minimum, min(maximum, float(value)))


def score_from_dataframe(base_df):
    if base_df is None or len(base_df) == 0:
        return None
    return clamp_score(base_df["score"].mean() * 100)


def score_label(score):
    if score is None or pd.isna(score):
        return "Sem dados"
    if score >= 75:
        return "Ponto forte"
    if score >= 60:
        return "Bom"
    if score >= 50:
        return "Regular"
    if score >= 40:
        return "Atenção"
    return "Crítico"


def get_game_ply_count(game):
    return sum(1 for _ in game.mainline_moves())


def get_timeout_flag(user_result_reason, termination):
    text = f"{user_result_reason or ''} {termination or ''}".lower()
    timeout_terms = [
        "timeout",
        "time forfeit",
        "time",
        "tempo",
        "flagged"
    ]
    return any(term in text for term in timeout_terms)


def score_position_cp_for_user(cp_value):
    """Transforma avaliação em centipawns, do ponto de vista do usuário, em nota 0-100."""
    if cp_value is None or pd.isna(cp_value):
        return None
    # -300 cp = 0, 0 cp = 50, +300 cp = 100.
    return clamp_score(50 + (float(cp_value) / 6))


def accuracy_from_avg_cp_loss(avg_cp_loss):
    """Converte perda média em centipawns para uma precisão aproximada 0-100."""
    if avg_cp_loss is None or pd.isna(avg_cp_loss):
        return None
    # Curva suave inspirada em métricas de perda média: 0 cp ≈ 100, 50 cp ≈ 79, 100 cp ≈ 62.
    value = 103.1668 * (2.718281828 ** (-0.0047 * float(avg_cp_loss))) - 3.1669
    return clamp_score(value)


def calculate_performance_profile(base_df):
    rows = []

    if base_df is None or len(base_df) == 0:
        return pd.DataFrame(columns=[
            "Aspecto", "Nota", "Amostra", "Diagnóstico", "Interpretação", "Observação técnica"
        ])

    overall_score = score_from_dataframe(base_df) or 50
    has_engine = "engine_accuracy" in base_df.columns and base_df["engine_accuracy"].notna().any()

    # Abertura: com engine, usa avaliação após 15 lances completos; sem engine, usa proxy por repertório.
    if has_engine and "opening_eval_15_cp" in base_df.columns:
        opening_engine_df = base_df.dropna(subset=["opening_eval_15_cp"]).copy()
        if len(opening_engine_df) > 0:
            opening_scores = opening_engine_df["opening_eval_15_cp"].apply(score_position_cp_for_user)
            opening_score = clamp_score(opening_scores.mean())
            opening_sample = len(opening_engine_df)
            opening_interpretation = "Avaliação média da posição do usuário após 15 lances completos, segundo Stockfish."
            opening_observation = "Com engine: 50 é posição equilibrada; acima de 50 indica posições mais confortáveis após a abertura."
        else:
            opening_score = None
            opening_sample = 0
            opening_interpretation = "Ainda não há partidas analisadas até 15 lances completos."
            opening_observation = "Execute análise Stockfish em partidas suficientes para medir abertura."
    else:
        opening_df = base_df[
            base_df["perspective"].astype(str).str.startswith("Joguei:")
        ].copy()
        if len(opening_df) == 0:
            opening_df = base_df.copy()
        opening_score = score_from_dataframe(opening_df)
        opening_sample = len(opening_df)
        opening_interpretation = "Desempenho nas linhas classificadas como parte do repertório do usuário."
        opening_observation = "Provisório sem engine: use Stockfish para avaliar a posição após 15 lances."

    rows.append({
        "Aspecto": "Abertura",
        "Nota": opening_score,
        "Amostra": opening_sample,
        "Diagnóstico": score_label(opening_score),
        "Interpretação": opening_interpretation,
        "Observação técnica": opening_observation
    })

    # Táticas: com engine usa precisão média e penaliza blunders; sem engine usa proxy.
    if has_engine:
        engine_df = base_df.dropna(subset=["engine_accuracy"]).copy()
        if len(engine_df) > 0:
            avg_accuracy = engine_df["engine_accuracy"].mean()
            blunder_penalty = min(25, engine_df.get("engine_blunders", pd.Series([0] * len(engine_df))).mean() * 4)
            tactics_score = clamp_score(avg_accuracy - blunder_penalty)
            tactics_sample = len(engine_df)
            tactics_interpretation = "Precisão média aproximada com penalização por lances de grande perda de avaliação."
            tactics_observation = "Com engine: baseada em perda média em centipawns e blunders detectados pelo Stockfish."
        else:
            tactics_score = None
            tactics_sample = 0
            tactics_interpretation = "Sem partidas analisadas por engine."
            tactics_observation = "Execute análise Stockfish para medir tática."
    else:
        if "fullmove_count" in base_df.columns:
            short_loss_rate = (
                (base_df["result_label"] == "loss") &
                (base_df["fullmove_count"] <= 25)
            ).mean() * 100
        else:
            short_loss_rate = 0
        tactics_score = clamp_score((overall_score * 0.70) + ((100 - short_loss_rate) * 0.30))
        tactics_sample = len(base_df)
        tactics_interpretation = "Estimativa baseada em resultado geral e frequência de derrotas curtas."
        tactics_observation = "Proxy sem engine: tática real exige perda de avaliação por lance."

    rows.append({
        "Aspecto": "Táticas",
        "Nota": tactics_score,
        "Amostra": tactics_sample,
        "Diagnóstico": score_label(tactics_score),
        "Interpretação": tactics_interpretation,
        "Observação técnica": tactics_observation
    })

    # Finais: com engine usa precisão média no final; sem engine usa partidas longas/material.
    if has_engine and "accuracy_endgame" in base_df.columns:
        endgame_engine_df = base_df.dropna(subset=["accuracy_endgame"]).copy()
        if len(endgame_engine_df) > 0:
            endgame_score = clamp_score(endgame_engine_df["accuracy_endgame"].mean())
            endgame_sample = len(endgame_engine_df)
            endgame_interpretation = "Precisão média aproximada nas jogadas feitas após o lance 30."
            endgame_observation = "Com engine: usa perda média em centipawns na fase final."
        else:
            endgame_score = None
            endgame_sample = 0
            endgame_interpretation = "Ainda não há jogadas de final analisadas pela engine."
            endgame_observation = "Partidas curtas podem não gerar amostra de final."
    else:
        if "fullmove_count" in base_df.columns:
            endgame_df = base_df[
                (base_df["fullmove_count"] >= 40) |
                (base_df["rook_ending"] == True) |
                (base_df["opposite_colored_bishops"] == True)
            ].copy()
        else:
            endgame_df = base_df[
                (base_df["rook_ending"] == True) |
                (base_df["opposite_colored_bishops"] == True)
            ].copy()
        endgame_score = score_from_dataframe(endgame_df)
        endgame_sample = len(endgame_df)
        endgame_interpretation = "Desempenho em partidas longas ou com material típico de final."
        endgame_observation = "Sem engine, não mede se o final estava ganho, empatado ou perdido."

    rows.append({
        "Aspecto": "Finais",
        "Nota": endgame_score,
        "Amostra": endgame_sample,
        "Diagnóstico": score_label(endgame_score),
        "Interpretação": endgame_interpretation,
        "Observação técnica": endgame_observation
    })

    # Conversão: com engine mede resultado quando houve vantagem objetiva; sem engine usa favoritismo por rating.
    if has_engine and "engine_conversion_opportunity" in base_df.columns:
        conversion_df = base_df[base_df["engine_conversion_opportunity"] == True].copy()
        conversion_score = score_from_dataframe(conversion_df)
        conversion_sample = len(conversion_df)
        conversion_interpretation = "Aproveitamento quando Stockfish indicou vantagem objetiva relevante em algum momento."
        conversion_observation = "Com engine: considera oportunidade quando a avaliação chegou a pelo menos +3.00 para o usuário."
    else:
        rating_df = base_df.dropna(subset=["rating", "opponent_rating"]).copy()
        conversion_df = rating_df[
            rating_df["rating"] - rating_df["opponent_rating"] >= 100
        ].copy()
        conversion_score = score_from_dataframe(conversion_df)
        conversion_sample = len(conversion_df)
        conversion_interpretation = "Aproveitamento quando o usuário era favorito por rating de pelo menos 100 pontos."
        conversion_observation = "Proxy sem engine: conversão real exige detectar vantagem objetiva durante a partida."

    rows.append({
        "Aspecto": "Conversão",
        "Nota": conversion_score,
        "Amostra": conversion_sample,
        "Diagnóstico": score_label(conversion_score),
        "Interpretação": conversion_interpretation,
        "Observação técnica": conversion_observation
    })

    # Resiliência: com engine mede resultado quando esteve perdido; sem engine usa underdog por rating.
    if has_engine and "engine_resilience_opportunity" in base_df.columns:
        resilience_df = base_df[base_df["engine_resilience_opportunity"] == True].copy()
        resilience_score = score_from_dataframe(resilience_df)
        resilience_sample = len(resilience_df)
        resilience_interpretation = "Aproveitamento quando Stockfish indicou posição objetivamente perdida em algum momento."
        resilience_observation = "Com engine: considera oportunidade quando a avaliação chegou a pelo menos -3.00 para o usuário."
    else:
        rating_df = base_df.dropna(subset=["rating", "opponent_rating"]).copy()
        resilience_df = rating_df[
            rating_df["opponent_rating"] - rating_df["rating"] >= 100
        ].copy()
        resilience_score = score_from_dataframe(resilience_df)
        resilience_sample = len(resilience_df)
        resilience_interpretation = "Aproveitamento contra adversários pelo menos 100 pontos mais fortes."
        resilience_observation = "Proxy sem engine: resiliência real exige detectar posições objetivamente perdidas salvas."

    rows.append({
        "Aspecto": "Resiliência",
        "Nota": resilience_score,
        "Amostra": resilience_sample,
        "Diagnóstico": score_label(resilience_score),
        "Interpretação": resilience_interpretation,
        "Observação técnica": resilience_observation
    })

    # Tempo: permanece parcialmente independente de engine.
    if "user_result_reason" in base_df.columns:
        timeout_losses = base_df.apply(
            lambda row: row.get("result_label") == "loss" and get_timeout_flag(
                row.get("user_result_reason"), row.get("termination")
            ),
            axis=1
        )
        timeout_loss_rate = timeout_losses.mean() * 100 if len(base_df) > 0 else 0
    else:
        timeout_loss_rate = 0
    time_score = clamp_score((overall_score * 0.70) + ((100 - timeout_loss_rate) * 0.30))
    rows.append({
        "Aspecto": "Tempo",
        "Nota": time_score,
        "Amostra": len(base_df),
        "Diagnóstico": score_label(time_score),
        "Interpretação": "Resultado geral com penalização por derrotas associadas ao tempo.",
        "Observação técnica": "A análise de engine não mede tempo; será mais precisa se os PGNs tiverem relógio [%clk] por lance."
    })

    profile_df = pd.DataFrame(rows)
    profile_df["Nota"] = profile_df["Nota"].apply(lambda x: round(x, 1) if x is not None and not pd.isna(x) else None)

    return profile_df


# =========================
# ANÁLISE COM STOCKFISH
# =========================

def load_engine_analysis(filename):
    if not os.path.exists(filename):
        return {
            "version": ENGINE_ANALYSIS_VERSION,
            "games": {}
        }

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {
            "version": ENGINE_ANALYSIS_VERSION,
            "games": {}
        }

    if not isinstance(data, dict):
        return {
            "version": ENGINE_ANALYSIS_VERSION,
            "games": {}
        }

    data.setdefault("version", ENGINE_ANALYSIS_VERSION)
    data.setdefault("games", {})
    return data


def save_engine_analysis(filename, analysis_data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)


def engine_score_cp(engine, board, limit):
    info = engine.analyse(board, limit)
    pov_score = info["score"].pov(chess.WHITE)
    return pov_score.score(mate_score=100000)


def engine_position_info(engine, board, limit):
    """Retorna avaliação em cp do ponto de vista das brancas e o melhor lance sugerido."""
    info = engine.analyse(board, limit)
    pov_score = info["score"].pov(chess.WHITE)
    score_cp = pov_score.score(mate_score=100000)

    best_move = None
    pv = info.get("pv")
    if pv and len(pv) > 0:
        best_move = pv[0]

    return score_cp, best_move


def phase_from_fullmove(fullmove_number):
    if fullmove_number <= 10:
        return "opening"
    if fullmove_number <= 30:
        return "middlegame"
    return "endgame"


def phase_label_pt(phase):
    labels = {
        "opening": "Abertura",
        "middlegame": "Meio-jogo",
        "endgame": "Final"
    }
    return labels.get(phase, phase)


def average(values):
    values = [v for v in values if v is not None and not pd.isna(v)]
    if not values:
        return None
    return sum(values) / len(values)


def should_create_training_position(before_user, after_user, cp_loss, phase):
    """Seleciona blunders úteis para treino, priorizando abertura e meio-jogo."""
    if phase not in ["opening", "middlegame"]:
        return False

    if before_user is None or after_user is None or cp_loss is None:
        return False

    if abs(before_user) > 50000 or abs(after_user) > 50000:
        return False

    # Blunder mínimo para virar exercício.
    if cp_loss < 200:
        return False

    wasted_advantage = before_user >= 100 and after_user <= 30
    became_lost = before_user > -250 and after_user <= -250
    severe_loss = cp_loss >= 300

    return wasted_advantage or became_lost or severe_loss


def training_position_reason(before_user, after_user, cp_loss):
    if before_user >= 100 and after_user <= 30:
        return "Vantagem desperdiçada"
    if before_user > -250 and after_user <= -250:
        return "Posição ficou perdida"
    if cp_loss >= 300:
        return "Blunder grave"
    return "Blunder relevante"


def analyze_game_with_stockfish(
    engine,
    pgn_text,
    user_color_name,
    result_label,
    engine_time=None,
    engine_depth=8,
    game_url=None,
    game_date=None,
    opening=None,
    opening_family=None,
    opponent=None,
    opponent_rating=None
):
    game = chess.pgn.read_game(StringIO(pgn_text))
    if game is None:
        return None

    user_color = chess.WHITE if user_color_name == "Brancas" else chess.BLACK
    board = game.board()

    if engine_time is not None:
        limit = chess.engine.Limit(time=float(engine_time))
    else:
        limit = chess.engine.Limit(depth=int(engine_depth))

    cp_losses = []
    opponent_cp_losses = []
    phase_losses = {
        "opening": [],
        "middlegame": [],
        "endgame": []
    }

    mistakes = 0
    blunders = 0
    opponent_mistakes = 0
    opponent_blunders = 0
    ply_index = 0
    opening_eval_15_cp = None
    training_positions = []

    eval_white, best_move = engine_position_info(engine, board, limit)
    eval_user_initial = eval_white if user_color == chess.WHITE else -eval_white
    max_eval_user = eval_user_initial
    min_eval_user = eval_user_initial

    for move in game.mainline_moves():
        moving_color = board.turn
        fullmove_number = board.fullmove_number
        phase = phase_from_fullmove(fullmove_number)

        before_user = eval_white if user_color == chess.WHITE else -eval_white
        before_mover = eval_white if moving_color == chess.WHITE else -eval_white

        board_before_fen = board.fen()
        played_move_uci = move.uci()
        played_move_san = board.san(move)

        best_move_uci = None
        best_move_san = None
        if best_move is not None and best_move in board.legal_moves:
            best_move_uci = best_move.uci()
            best_move_san = board.san(best_move)

        board.push(move)
        ply_index += 1

        eval_white_after, best_move_after = engine_position_info(engine, board, limit)
        after_user = eval_white_after if user_color == chess.WHITE else -eval_white_after
        after_mover = eval_white_after if moving_color == chess.WHITE else -eval_white_after

        max_eval_user = max(max_eval_user, after_user)
        min_eval_user = min(min_eval_user, after_user)

        if ply_index == 30:
            opening_eval_15_cp = after_user

        cp_loss = max(0, before_mover - after_mover)
        # Limita mates/colapsos extremos para não distorcer a média.
        cp_loss = min(cp_loss, 1000)

        if moving_color == user_color:
            cp_losses.append(cp_loss)
            phase_losses[phase].append(cp_loss)

            if cp_loss >= 300:
                blunders += 1
            elif cp_loss >= 100:
                mistakes += 1

            if should_create_training_position(before_user, after_user, cp_loss, phase):
                exercise_item = {
                    "game_url": game_url,
                    "date": game_date.isoformat() if hasattr(game_date, "isoformat") else str(game_date) if game_date is not None else None,
                    "color": user_color_name,
                    "user_color": "white" if user_color == chess.WHITE else "black",
                    "opponent": opponent,
                    "opponent_rating": int(opponent_rating) if opponent_rating is not None and not pd.isna(opponent_rating) else None,
                    "opening": opening,
                    "opening_family": opening_family,
                    "phase": phase,
                    "phase_label": phase_label_pt(phase),
                    "fullmove_number": int(fullmove_number),
                    "fen_before": board_before_fen,
                    "played_move_uci": played_move_uci,
                    "played_move_san": played_move_san,
                    "best_move_uci": best_move_uci,
                    "best_move_san": best_move_san,
                    "eval_before_cp": round(before_user, 0),
                    "eval_after_cp": round(after_user, 0),
                    "loss_cp": round(cp_loss, 0),
                    "reason": training_position_reason(before_user, after_user, cp_loss)
                }
                exercise_item["exercise_id"] = generate_exercise_id(exercise_item)
                exercise_item["difficulty"] = classify_exercise_difficulty(exercise_item)
                exercise_item["theme"] = classify_exercise_theme(exercise_item)
                training_positions.append(exercise_item)
        else:
            opponent_cp_losses.append(cp_loss)

            if cp_loss >= 300:
                opponent_blunders += 1
            elif cp_loss >= 100:
                opponent_mistakes += 1

        eval_white = eval_white_after
        best_move = best_move_after

    avg_cp_loss = average(cp_losses)
    opponent_avg_cp_loss = average(opponent_cp_losses)
    engine_accuracy = accuracy_from_avg_cp_loss(avg_cp_loss)
    opponent_accuracy = accuracy_from_avg_cp_loss(opponent_avg_cp_loss)

    opening_avg_loss = average(phase_losses["opening"])
    middlegame_avg_loss = average(phase_losses["middlegame"])
    endgame_avg_loss = average(phase_losses["endgame"])

    conversion_opportunity = max_eval_user >= 300
    resilience_opportunity = min_eval_user <= -300

    return {
        "engine_avg_cp_loss": round(avg_cp_loss, 1) if avg_cp_loss is not None else None,
        "engine_accuracy": round(engine_accuracy, 1) if engine_accuracy is not None else None,
        "engine_mistakes": int(mistakes),
        "engine_blunders": int(blunders),
        "engine_opponent_avg_cp_loss": round(opponent_avg_cp_loss, 1) if opponent_avg_cp_loss is not None else None,
        "engine_opponent_accuracy": round(opponent_accuracy, 1) if opponent_accuracy is not None else None,
        "engine_opponent_mistakes": int(opponent_mistakes),
        "engine_opponent_blunders": int(opponent_blunders),
        "opening_eval_15_cp": round(opening_eval_15_cp, 0) if opening_eval_15_cp is not None else None,
        "accuracy_opening": round(accuracy_from_avg_cp_loss(opening_avg_loss), 1) if opening_avg_loss is not None else None,
        "accuracy_middlegame": round(accuracy_from_avg_cp_loss(middlegame_avg_loss), 1) if middlegame_avg_loss is not None else None,
        "accuracy_endgame": round(accuracy_from_avg_cp_loss(endgame_avg_loss), 1) if endgame_avg_loss is not None else None,
        "engine_conversion_opportunity": bool(conversion_opportunity),
        "engine_resilience_opportunity": bool(resilience_opportunity),
        "engine_max_eval_user_cp": round(max_eval_user, 0),
        "engine_min_eval_user_cp": round(min_eval_user, 0),
        "engine_user_moves_analyzed": len(cp_losses),
        "engine_opponent_moves_analyzed": len(opponent_cp_losses),
        "engine_result_label": result_label,
        "training_positions": training_positions[:12]
    }

def run_stockfish_analysis_for_dataframe(base_df, engine_path, analysis_filename, engine_time, engine_depth, max_games):
    if not os.path.exists(engine_path):
        st.error(
            "Stockfish não encontrado. Confira o caminho informado. "
            "Exemplo esperado: engines/stockfish.exe"
        )
        return load_engine_analysis(analysis_filename)

    analysis_data = load_engine_analysis(analysis_filename)
    games_cache = analysis_data.setdefault("games", {})

    required_engine_fields = [
        "engine_accuracy",
        "engine_avg_cp_loss",
        "engine_opponent_mistakes",
        "engine_opponent_blunders",
        "opening_eval_15_cp",
        "accuracy_opening",
        "accuracy_middlegame",
        "accuracy_endgame",
        "training_positions"
    ]

    def needs_engine_analysis(url):
        cached = games_cache.get(str(url))
        if not isinstance(cached, dict):
            return True
        if cached.get("engine_error"):
            return False
        if any(field not in cached for field in required_engine_fields):
            return True
        positions = cached.get("training_positions")
        if not isinstance(positions, list):
            return True
        for item in positions:
            if isinstance(item, dict) and (
                not item.get("exercise_id")
                or not item.get("difficulty")
                or not item.get("theme")
            ):
                return True
        return False

    pending_df = base_df[
        base_df["url"].notna() &
        base_df["pgn"].notna() &
        base_df["url"].apply(needs_engine_analysis)
    ].copy()

    if max_games is not None and max_games > 0:
        pending_df = pending_df.head(int(max_games))

    if len(pending_df) == 0:
        st.info("Todas as partidas filtradas já têm análise Stockfish salva e atualizada.")
        return analysis_data

    progress = st.progress(0, text="Iniciando Stockfish...")

    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        progress.empty()
        st.error(f"Não foi possível iniciar o Stockfish: {e}")
        return analysis_data

    try:
        total = len(pending_df)
        for index, (_, row) in enumerate(pending_df.iterrows(), start=1):
            progress.progress(
                index / total,
                text=f"Analisando partida {index}/{total} com Stockfish..."
            )

            try:
                result = analyze_game_with_stockfish(
                    engine=engine,
                    pgn_text=row["pgn"],
                    user_color_name=row["color"],
                    result_label=row["result_label"],
                    engine_time=engine_time,
                    engine_depth=engine_depth,
                    game_url=row.get("url"),
                    game_date=row.get("date"),
                    opening=row.get("opening"),
                    opening_family=row.get("opening_family"),
                    opponent=row.get("opponent"),
                    opponent_rating=row.get("opponent_rating")
                )

                if result is not None:
                    games_cache[str(row["url"])] = result
                    if index % 3 == 0:
                        save_engine_analysis(analysis_filename, analysis_data)

            except Exception as e:
                games_cache[str(row["url"])] = {
                    "engine_error": str(e)
                }

        save_engine_analysis(analysis_filename, analysis_data)
        st.success(f"Análise Stockfish concluída para {total} nova(s) partida(s).")

    finally:
        try:
            engine.quit()
        except Exception:
            pass
        progress.empty()

    return analysis_data


def attach_engine_analysis(base_df, analysis_data):
    if base_df is None or len(base_df) == 0:
        return base_df

    games_cache = analysis_data.get("games", {}) if isinstance(analysis_data, dict) else {}
    df_with_engine = base_df.copy()

    engine_columns = [
        "engine_avg_cp_loss",
        "engine_accuracy",
        "engine_mistakes",
        "engine_blunders",
        "engine_opponent_avg_cp_loss",
        "engine_opponent_accuracy",
        "engine_opponent_mistakes",
        "engine_opponent_blunders",
        "opening_eval_15_cp",
        "accuracy_opening",
        "accuracy_middlegame",
        "accuracy_endgame",
        "engine_conversion_opportunity",
        "engine_resilience_opportunity",
        "engine_max_eval_user_cp",
        "engine_min_eval_user_cp",
        "engine_user_moves_analyzed",
        "engine_opponent_moves_analyzed"
    ]

    for column in engine_columns:
        df_with_engine[column] = None

    for idx, row in df_with_engine.iterrows():
        url = row.get("url")
        if not isinstance(url, str):
            continue

        analysis = games_cache.get(url)
        if not isinstance(analysis, dict):
            continue

        for column in engine_columns:
            if column in analysis:
                df_with_engine.at[idx, column] = analysis[column]

    numeric_columns = [
        "engine_avg_cp_loss",
        "engine_accuracy",
        "engine_mistakes",
        "engine_blunders",
        "engine_opponent_avg_cp_loss",
        "engine_opponent_accuracy",
        "engine_opponent_mistakes",
        "engine_opponent_blunders",
        "opening_eval_15_cp",
        "accuracy_opening",
        "accuracy_middlegame",
        "accuracy_endgame",
        "engine_max_eval_user_cp",
        "engine_min_eval_user_cp",
        "engine_user_moves_analyzed",
        "engine_opponent_moves_analyzed"
    ]

    for column in numeric_columns:
        df_with_engine[column] = pd.to_numeric(df_with_engine[column], errors="coerce")

    return df_with_engine


# =========================
# RELATÓRIO DETALHADO DO PERFIL
# =========================

def format_cp(cp_value):
    if cp_value is None or pd.isna(cp_value):
        return "sem dados"
    cp_value = float(cp_value)
    sign = "+" if cp_value > 0 else ""
    return f"{sign}{cp_value:.0f} cp"


def format_engine_points_from_cp(cp_value):
    """Mostra centipeões como a avaliação comum da engine: +0,35, -1,20 etc."""
    if cp_value is None or pd.isna(cp_value):
        return "sem dados"
    points = float(cp_value) / 100
    sign = "+" if points > 0 else ""
    text = f"{sign}{points:.2f}"
    return text.replace(".", ",")


def format_engine_points_sentence_from_cp(cp_value):
    if cp_value is None or pd.isna(cp_value):
        return "sem dados"
    points = float(cp_value) / 100
    abs_text = f"{abs(points):.2f}".replace(".", ",")
    if points > 0:
        return f"{abs_text} ponto(s) de vantagem"
    if points < 0:
        return f"{abs_text} ponto(s) de desvantagem"
    return "posição igualada"


def opening_eval_summary_text(cp_value):
    if cp_value is None or pd.isna(cp_value):
        return "Ainda não há dados suficientes para interpretar essa avaliação."

    points = float(cp_value) / 100
    formatted = format_engine_points_from_cp(cp_value)

    if points >= 1.5:
        return f"Ótimo trabalho. Você tende a sair da abertura com vantagem clara ({formatted} pontos)."
    if points >= 0.5:
        return f"Bom sinal. Você tende a terminar a fase de abertura com leve vantagem ({formatted} pontos)."
    if points > -0.5:
        return f"Nada mal. Você tende a terminar a fase de abertura em pé de igualdade com seu oponente ({formatted} pontos)."
    if points > -1.5:
        return f"Ponto de atenção. Você tende a sair da abertura um pouco pior que seu oponente ({formatted} pontos)."
    return f"Hora de estudar. Você tende a sair da abertura em posição desconfortável ({formatted} pontos)."


def format_san_sequence_pt(moves, max_plies=6):
    if not isinstance(moves, list) or len(moves) == 0:
        return ""

    converted = []
    piece_map = {
        "N": "C",
        "Q": "D",
        "R": "T",
        "K": "R",
        "B": "B"
    }

    for move in moves[:max_plies]:
        if not isinstance(move, str):
            continue
        if move.startswith("O-O"):
            converted.append(move)
        elif move and move[0] in piece_map:
            converted.append(piece_map[move[0]] + move[1:])
        else:
            converted.append(move)

    return " ".join(converted)


def google_search_link(term):
    if term is None or pd.isna(term):
        term = "chess opening plans"
    query = quote_plus(f"{term} chess opening plans")
    return f"https://www.google.com/search?q={query}"


def opening_popular_rows(engine_df, limit_per_color=2):
    if engine_df is None or len(engine_df) == 0 or "opening_eval_15_cp" not in engine_df.columns:
        return []

    opening_eval_df = engine_df.dropna(subset=["opening_eval_15_cp"]).copy()
    opening_eval_df = opening_eval_df[
        opening_eval_df["perspective"].astype(str).str.startswith("Joguei:")
    ].copy()

    if len(opening_eval_df) == 0:
        return []

    rows = []
    for color_name in ["Brancas", "Pretas"]:
        color_df = opening_eval_df[opening_eval_df["color"] == color_name].copy()
        if len(color_df) == 0:
            continue

        grouped = color_df.groupby(["color", "opening_family", "opening"]).agg(
            games=("opening", "count"),
            avg_eval=("opening_eval_15_cp", "mean"),
            winrate=("score", "mean"),
            avg_accuracy=("engine_accuracy", "mean")
        ).reset_index()

        grouped = grouped.sort_values(["games", "avg_eval"], ascending=[False, False]).head(limit_per_color)

        for _, item in grouped.iterrows():
            subset = color_df[
                (color_df["opening_family"] == item["opening_family"]) &
                (color_df["opening"] == item["opening"])
            ].copy()

            sequence = ""
            if "opening_san_moves" in subset.columns and len(subset) > 0:
                sequence = format_san_sequence_pt(subset.iloc[0].get("opening_san_moves"), max_plies=6)

            record = item.to_dict()
            record["sequence"] = sequence
            rows.append(record)

    return rows


def opening_popular_comment(row, overall_winrate):
    avg_eval = row.get("avg_eval")
    winrate = row.get("winrate")
    opening_name = row.get("opening") or row.get("opening_family")
    sequence = row.get("sequence")

    eval_text = format_engine_points_from_cp(avg_eval)
    winrate_pct = float(winrate) * 100 if winrate is not None and not pd.isna(winrate) else None
    overall_pct = float(overall_winrate) * 100 if overall_winrate is not None and not pd.isna(overall_winrate) else None

    title = f"**{opening_name}**"
    if sequence:
        title += f" ({sequence})"

    points = float(avg_eval) / 100 if avg_eval is not None and not pd.isna(avg_eval) else None

    if points is None:
        return f"ℹ️ {title}\n\nAinda não há avaliação suficiente após 15 lances para interpretar esta linha."

    if points >= 0.5 and (winrate_pct is None or overall_pct is None or winrate_pct >= overall_pct):
        return (
            f"✅ {title}\n\n"
            f"Esta é uma linha forte para você. Em média, você chega ao meio-jogo com **{eval_text} pontos**, "
            "e os resultados acompanham essa boa saída de abertura."
        )

    if points >= 0.5:
        return (
            f"🚨 {title}\n\n"
            f"Você costuma sair da abertura bem, com **{eval_text} pontos**, mas essa vantagem ainda não está se convertendo em resultados na mesma proporção. "
            "Vale estudar os planos típicos de meio-jogo dessa estrutura."
        )

    if points <= -0.5:
        return (
            f"🚨 {title}\n\n"
            f"Esta linha pode precisar de ajustes. Em média, você chega ao meio-jogo com **{eval_text} pontos**, "
            "o que indica posições um pouco desconfortáveis após a abertura."
        )

    return (
        f"ℹ️ {title}\n\n"
        f"Esta linha tem produzido posições equilibradas após a abertura (**{eval_text} pontos**). "
        "Pode ser uma boa candidata para aprofundar planos típicos e melhorar a conversão prática."
    )


def format_percent(value):
    if value is None or pd.isna(value):
        return "sem dados"
    return f"{float(value):.1f}%"


def result_rate_label(score_value):
    if score_value is None or pd.isna(score_value):
        return "sem dados"
    return f"{float(score_value) * 100:.1f}%"


def opening_highlights(engine_df, ascending=False, limit=2):
    if engine_df is None or len(engine_df) == 0 or "opening_eval_15_cp" not in engine_df.columns:
        return []

    opening_eval_df = engine_df.dropna(subset=["opening_eval_15_cp"]).copy()
    if len(opening_eval_df) == 0:
        return []

    grouped = opening_eval_df.groupby("opening_family").agg(
        games=("opening_family", "count"),
        avg_eval=("opening_eval_15_cp", "mean"),
        avg_accuracy=("engine_accuracy", "mean"),
        score=("score", "mean")
    ).reset_index()

    # Exige amostra mínima quando possível; se o filtro for pequeno, aceita 1 partida.
    min_games = 2 if grouped["games"].max() >= 2 else 1
    grouped = grouped[grouped["games"] >= min_games].copy()

    if len(grouped) == 0:
        return []

    if ascending:
        grouped = grouped.sort_values(by=["avg_eval", "games"], ascending=[True, False])
    else:
        grouped = grouped.sort_values(by=["avg_eval", "games"], ascending=[False, False])

    return grouped.head(limit).to_dict("records")


def material_endgame_highlights(engine_df):
    if engine_df is None or len(engine_df) == 0 or "accuracy_endgame" not in engine_df.columns:
        return pd.DataFrame()

    rows = []
    material_groups = [
        ("Finais de torres", "rook_ending"),
        ("Bispos de cores opostas", "opposite_colored_bishops"),
        ("Partidas em que terminou com par de bispos", "bishop_pair"),
    ]

    for label, column in material_groups:
        if column not in engine_df.columns:
            continue
        subset = engine_df[(engine_df[column] == True) & engine_df["accuracy_endgame"].notna()].copy()
        if len(subset) == 0:
            continue
        rows.append({
            "Tipo de final": label,
            "Partidas": len(subset),
            "Precisão média no final (%)": round(subset["accuracy_endgame"].mean(), 1),
            "Aproveitamento (%)": round(subset["score"].mean() * 100, 1)
        })

    return pd.DataFrame(rows)


def render_performance_detailed_report(base_df, profile_df):
    st.markdown("### 🧭 Relatório detalhado do perfil")

    if base_df is None or len(base_df) == 0:
        st.info("Não há partidas suficientes para gerar o relatório detalhado.")
        return

    has_engine = "engine_accuracy" in base_df.columns and base_df["engine_accuracy"].notna().any()

    if not has_engine:
        st.info(
            "O relatório detalhado fica mais preciso depois que algumas partidas forem analisadas com Stockfish. "
            "No momento, apenas as métricas sem engine estão disponíveis."
        )
        return

    engine_df = base_df.dropna(subset=["engine_accuracy"]).copy()

    # -------------------------
    # Abertura
    # -------------------------
    st.markdown("#### 1. Abertura")

    opening_available = "opening_eval_15_cp" in engine_df.columns and engine_df["opening_eval_15_cp"].notna().any()
    if opening_available:
        opening_eval_df = engine_df.dropna(subset=["opening_eval_15_cp"]).copy()
        avg_opening_eval = opening_eval_df["opening_eval_15_cp"].mean()
        white_opening_eval = opening_eval_df[opening_eval_df["color"] == "Brancas"]["opening_eval_15_cp"].mean()
        black_opening_eval = opening_eval_df[opening_eval_df["color"] == "Pretas"]["opening_eval_15_cp"].mean()

        st.markdown("**Interpretação**")

        st.markdown("**Sua pontuação média geral após os primeiros 15 lances de uma partida**")
        st.markdown(
            f"{opening_eval_summary_text(avg_opening_eval)} "
            f"A avaliação média geral foi de **{format_engine_points_from_cp(avg_opening_eval)} pontos** "
            f"em **{len(opening_eval_df)}** partida(s) analisada(s)."
        )

        st.markdown("**Com as peças brancas**")
        if not pd.isna(white_opening_eval):
            white_count = len(opening_eval_df[opening_eval_df["color"] == "Brancas"])
            st.markdown(
                f"{opening_eval_summary_text(white_opening_eval)} "
                f"A média com brancas foi de **{format_engine_points_from_cp(white_opening_eval)} pontos** "
                f"em **{white_count}** partida(s)."
            )
        else:
            st.markdown("Ainda não há partidas de brancas com avaliação Stockfish após 15 lances.")

        st.markdown("**Com as peças pretas**")
        if not pd.isna(black_opening_eval):
            black_count = len(opening_eval_df[opening_eval_df["color"] == "Pretas"])
            st.markdown(
                f"{opening_eval_summary_text(black_opening_eval)} "
                f"A média com pretas foi de **{format_engine_points_from_cp(black_opening_eval)} pontos** "
                f"em **{black_count}** partida(s)."
            )
        else:
            st.markdown("Ainda não há partidas de pretas com avaliação Stockfish após 15 lances.")

        popular_rows = opening_popular_rows(engine_df, limit_per_color=2)

        st.markdown("**Suas aberturas e defesas populares**")
        if popular_rows:
            overall_winrate_for_openings = opening_eval_df["score"].mean()
            for row in popular_rows:
                st.markdown(opening_popular_comment(row, overall_winrate_for_openings))

            study_targets = [
                row for row in popular_rows
                if (not pd.isna(row.get("avg_eval")) and float(row.get("avg_eval")) / 100 <= -0.5)
                or (not pd.isna(row.get("avg_eval")) and float(row.get("avg_eval")) / 100 >= 0.5 and row.get("winrate") < overall_winrate_for_openings)
            ]

            st.markdown("**Como melhorar**")
            st.markdown(
                "É sempre uma boa ideia seguir os princípios de abertura: desenvolvimento, segurança do rei, controle do centro "
                "e evitar mover muitas vezes a mesma peça sem necessidade. Além disso, vale se aprofundar nos planos e temas das linhas que aparecem com frequência no seu repertório."
            )

            if study_targets:
                st.markdown("Aqui estão alguns links do Google para começar:")
                for item in study_targets[:3]:
                    opening_name = item.get("opening") or item.get("opening_family")
                    st.markdown(f"- [{opening_name}]({google_search_link(opening_name)})")
        else:
            st.caption("Ainda não há amostra suficiente para destacar aberturas ou defesas populares com avaliação após 15 lances.")

        with st.expander("Destaques técnicos por família de abertura"):
            positive = opening_highlights(engine_df, ascending=False, limit=2)
            negative = opening_highlights(engine_df, ascending=True, limit=2)

            col_open_pos, col_open_neg = st.columns(2)
            with col_open_pos:
                st.markdown("**Destaques positivos**")
                if positive:
                    for item in positive:
                        st.markdown(
                            f"- **{item['opening_family']}**: média de **{format_engine_points_from_cp(item['avg_eval'])} pontos** "
                            f"após 15 lances em {int(item['games'])} partida(s)."
                        )
                else:
                    st.write("Sem amostra suficiente.")

            with col_open_neg:
                st.markdown("**Pontos de atenção**")
                if negative:
                    for item in negative:
                        st.markdown(
                            f"- **{item['opening_family']}**: média de **{format_engine_points_from_cp(item['avg_eval'])} pontos** "
                            f"após 15 lances em {int(item['games'])} partida(s)."
                        )
                else:
                    st.write("Sem amostra suficiente.")
    else:
        st.info("Ainda não há partidas analisadas com avaliação após 15 lances completos.")

    # -------------------------
    # Táticas
    # -------------------------
    st.markdown("#### 2. Táticas")

    user_mistakes = engine_df["engine_mistakes"].mean() if "engine_mistakes" in engine_df.columns else None
    user_blunders = engine_df["engine_blunders"].mean() if "engine_blunders" in engine_df.columns else None
    opp_mistakes = engine_df["engine_opponent_mistakes"].mean() if "engine_opponent_mistakes" in engine_df.columns else None
    opp_blunders = engine_df["engine_opponent_blunders"].mean() if "engine_opponent_blunders" in engine_df.columns else None
    user_cp_loss = engine_df["engine_avg_cp_loss"].mean() if "engine_avg_cp_loss" in engine_df.columns else None
    opp_cp_loss = engine_df["engine_opponent_avg_cp_loss"].mean() if "engine_opponent_avg_cp_loss" in engine_df.columns else None

    st.markdown(
        f"Nas partidas analisadas, o usuário tem média de **{user_mistakes:.2f} erro(s)** e "
        f"**{user_blunders:.2f} blunder(s)** por partida, com perda média de **{user_cp_loss:.1f} cp por lance analisado**. "
        if all(v is not None and not pd.isna(v) for v in [user_mistakes, user_blunders, user_cp_loss])
        else "Ainda não há dados suficientes para detalhar erros táticos do usuário."
    )

    if all(v is not None and not pd.isna(v) for v in [opp_mistakes, opp_blunders, opp_cp_loss]):
        st.markdown(
            f"Os adversários, no mesmo conjunto de partidas, tiveram média de **{opp_mistakes:.2f} erro(s)** e "
            f"**{opp_blunders:.2f} blunder(s)** por partida, com perda média de **{opp_cp_loss:.1f} cp**. "
            "Essa comparação ajuda a perceber se o desempenho tático está acima ou abaixo do nível dos oponentes enfrentados."
        )
    else:
        st.caption(
            "Comparação com adversários indisponível para partidas antigas já analisadas. "
            "Reanalise algumas partidas com Stockfish para gerar também erros e blunders dos adversários."
        )

    tactic_rows = []
    if user_mistakes is not None and not pd.isna(user_mistakes):
        tactic_rows.append({"Tipo": "Erros do usuário", "Média por partida": round(user_mistakes, 2)})
    if user_blunders is not None and not pd.isna(user_blunders):
        tactic_rows.append({"Tipo": "Blunders do usuário", "Média por partida": round(user_blunders, 2)})
    if opp_mistakes is not None and not pd.isna(opp_mistakes):
        tactic_rows.append({"Tipo": "Erros dos adversários", "Média por partida": round(opp_mistakes, 2)})
    if opp_blunders is not None and not pd.isna(opp_blunders):
        tactic_rows.append({"Tipo": "Blunders dos adversários", "Média por partida": round(opp_blunders, 2)})
    if tactic_rows:
        st.dataframe(pd.DataFrame(tactic_rows), use_container_width=True, hide_index=True)

    # -------------------------
    # Finais
    # -------------------------
    st.markdown("#### 3. Finais")

    endgame_df = engine_df.dropna(subset=["accuracy_endgame"]).copy() if "accuracy_endgame" in engine_df.columns else pd.DataFrame()
    if len(endgame_df) > 0:
        avg_endgame_accuracy = endgame_df["accuracy_endgame"].mean()
        st.markdown(
            f"A precisão média do usuário em finais é de **{avg_endgame_accuracy:.1f}%**, "
            f"considerando **{len(endgame_df)}** partida(s) com amostra de final."
        )

        material_df = material_endgame_highlights(engine_df)
        if len(material_df) > 0:
            best_material = material_df.sort_values("Precisão média no final (%)", ascending=False).head(1)
            worst_material = material_df.sort_values("Precisão média no final (%)", ascending=True).head(1)

            best_label = best_material.iloc[0]["Tipo de final"]
            best_acc = best_material.iloc[0]["Precisão média no final (%)"]
            worst_label = worst_material.iloc[0]["Tipo de final"]
            worst_acc = worst_material.iloc[0]["Precisão média no final (%)"]

            st.markdown(
                f"Entre os tipos de finais detectados, o melhor desempenho aparece em **{best_label}** "
                f"({best_acc:.1f}% de precisão média). O ponto de maior dificuldade aparece em **{worst_label}** "
                f"({worst_acc:.1f}% de precisão média)."
            )
            st.dataframe(material_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Ainda há pouca amostra para diferenciar tipos específicos de finais.")
    else:
        st.info("Ainda não há amostra suficiente de finais analisados pela engine.")

    # -------------------------
    # Conversão
    # -------------------------
    st.markdown("#### 4. Conversão de vantagem")

    if "engine_conversion_opportunity" in engine_df.columns:
        conversion_df = engine_df[engine_df["engine_conversion_opportunity"] == True].copy()
    else:
        conversion_df = pd.DataFrame()

    if len(conversion_df) > 0:
        converted_wins = int((conversion_df["result_label"] == "win").sum())
        conversion_rate = converted_wins / len(conversion_df) * 100
        conversion_score = conversion_df["score"].mean() * 100
        st.markdown(
            f"O Stockfish detectou vantagem objetiva relevante em **{len(conversion_df)}** partida(s). "
            f"O usuário converteu em vitória **{converted_wins}** delas, uma taxa de conversão estrita de **{conversion_rate:.1f}%**. "
            f"Considerando empates como meio ponto, o aproveitamento nessas posições foi de **{conversion_score:.1f}%**."
        )
    else:
        st.info("Nenhuma oportunidade clara de conversão foi detectada nas partidas analisadas pelo Stockfish.")

    # -------------------------
    # Resiliência
    # -------------------------
    st.markdown("#### 5. Resiliência")

    if "engine_resilience_opportunity" in engine_df.columns:
        resilience_df = engine_df[engine_df["engine_resilience_opportunity"] == True].copy()
    else:
        resilience_df = pd.DataFrame()

    if len(resilience_df) > 0:
        saved_games = int((resilience_df["result_label"].isin(["win", "draw"])).sum())
        resilience_rate = saved_games / len(resilience_df) * 100
        resilience_score = resilience_df["score"].mean() * 100
        st.markdown(
            f"O usuário esteve objetivamente perdido em **{len(resilience_df)}** partida(s), segundo o limite de -3.00. "
            f"Conseguiu salvar **{saved_games}** delas com empate ou vitória, uma taxa de resistência de **{resilience_rate:.1f}%**. "
            f"O aproveitamento total nessas partidas foi de **{resilience_score:.1f}%**."
        )
    else:
        st.info("Nenhuma posição objetivamente perdida foi detectada nas partidas analisadas pelo Stockfish.")

    # -------------------------
    # Tempo
    # -------------------------
    st.markdown("#### 6. Tempo")

    if "user_result_reason" in base_df.columns:
        timeout_losses = base_df.apply(
            lambda row: row.get("result_label") == "loss" and get_timeout_flag(
                row.get("user_result_reason"), row.get("termination")
            ),
            axis=1
        )
        timeout_loss_count = int(timeout_losses.sum())
        timeout_loss_rate = timeout_loss_count / len(base_df) * 100 if len(base_df) > 0 else 0
    else:
        timeout_loss_count = 0
        timeout_loss_rate = 0

    if timeout_loss_count > 0:
        st.markdown(
            f"Foram detectadas **{timeout_loss_count}** derrota(s) associadas ao tempo, "
            f"equivalentes a **{timeout_loss_rate:.1f}%** das partidas filtradas. "
            "Essa é a principal penalização usada na nota de gerenciamento de tempo."
        )
    else:
        st.markdown(
            "Não foram detectadas derrotas claramente associadas ao tempo nas partidas filtradas. "
            "Nesse caso, a nota de tempo é influenciada principalmente pelo aproveitamento geral."
        )


# =========================
# COACH DO JOGADOR
# =========================

def safe_mean(series):
    if series is None:
        return None
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) == 0:
        return None
    return clean.mean()


def safe_rate(mask, denominator):
    if denominator is None or denominator == 0:
        return None
    return float(mask) / float(denominator) * 100


def get_profile_note(profile_df, aspecto):
    if profile_df is None or len(profile_df) == 0:
        return None
    row = profile_df[profile_df["Aspecto"] == aspecto]
    if len(row) == 0:
        return None
    value = row.iloc[0].get("Nota")
    if value is None or pd.isna(value):
        return None
    return float(value)


def describe_rating_trend(all_df):
    rating_df = all_df.dropna(subset=["rating", "date"]).copy() if all_df is not None else pd.DataFrame()
    if len(rating_df) < 4:
        return {
            "label": "histórico ainda curto",
            "text": "Ainda há poucas partidas com rating para afirmar uma tendência estatística forte. Mesmo assim, cada nova partida baixada vai melhorar essa leitura.",
            "change": None
        }

    rating_df["rating"] = pd.to_numeric(rating_df["rating"], errors="coerce")
    rating_df = rating_df.dropna(subset=["rating"]).sort_values("date")

    if len(rating_df) < 4:
        return {
            "label": "histórico ainda curto",
            "text": "Ainda há poucas partidas com rating válido para medir tendência. O painel já está preparado para acompanhar a evolução conforme novas partidas forem incluídas.",
            "change": None
        }

    recent_count = min(20, len(rating_df))
    recent = rating_df.tail(recent_count)
    recent_change = int(recent.iloc[-1]["rating"] - recent.iloc[0]["rating"])

    if recent_change >= 30:
        label = "ascensão"
        text = f"A curva recente sugere ascensão: nas últimas {recent_count} partidas com rating, houve variação de {recent_change:+d} pontos. Isso é um bom sinal de adaptação prática."
    elif recent_change <= -30:
        label = "oscilação negativa"
        text = f"A curva recente mostra uma oscilação de {recent_change:+d} pontos nas últimas {recent_count} partidas. Isso não é um diagnóstico ruim: costuma indicar uma fase boa para revisar padrões recorrentes e estabilizar o repertório."
    else:
        label = "estabilização"
        text = f"A curva recente está relativamente estável, com variação de {recent_change:+d} pontos nas últimas {recent_count} partidas. Isso sugere uma base consolidada, pronta para pequenos ajustes técnicos produzirem ganho de rating."

    return {
        "label": label,
        "text": text,
        "change": recent_change
    }


def get_top_repertoire_lines(base_df, color_name, limit=3):
    if base_df is None or len(base_df) == 0:
        return []

    repertoire_df = base_df[
        (base_df["color"] == color_name) &
        (base_df["perspective"].astype(str).str.startswith("Joguei:"))
    ].copy()

    if len(repertoire_df) == 0:
        return []

    grouped = repertoire_df.groupby("opening_family").agg(
        games=("opening_family", "count"),
        score=("score", "mean")
    ).reset_index()

    grouped["winrate"] = (grouped["score"] * 100).round(1)
    grouped = grouped.sort_values(["games", "winrate"], ascending=[False, False])

    return grouped.head(limit).to_dict("records")


def infer_player_style(base_df, profile_df):
    white_lines = get_top_repertoire_lines(base_df, "Brancas", limit=4)
    black_lines = get_top_repertoire_lines(base_df, "Pretas", limit=4)
    main_openings = {item["opening_family"] for item in white_lines + black_lines}

    solid_openings = {
        "Caro-Kann", "Defesa Francesa", "Defesa Eslava", "Defesa Semieslava",
        "Sistema London", "Abertura Catalã", "Defesa Nimzoíndia", "Defesa Bogoíndia",
        "Defesa Índia da Dama", "Defesa Philidor", "Defesa Petroff"
    }
    dynamic_openings = {
        "Defesa Siciliana", "Gambito do Rei", "Gambito Escocês", "Escocesa",
        "Gambito Benko", "Defesa Benoni", "Defesa Grünfeld", "Gambito Budapeste",
        "Ataque Trompowsky", "Bird", "Grob", "Gambito Dinamarquês"
    }

    solid_count = len(main_openings & solid_openings)
    dynamic_count = len(main_openings & dynamic_openings)

    tactics_note = get_profile_note(profile_df, "Táticas")
    endgame_note = get_profile_note(profile_df, "Finais")
    conversion_note = get_profile_note(profile_df, "Conversão")
    resilience_note = get_profile_note(profile_df, "Resiliência")
    opening_note = get_profile_note(profile_df, "Abertura")

    evidence = []

    if solid_count > dynamic_count:
        base_style = "sólido e estrutural"
        evidence.append("o repertório principal contém várias escolhas associadas a estruturas sólidas e planos recorrentes")
    elif dynamic_count > solid_count:
        base_style = "dinâmico e combativo"
        evidence.append("o repertório principal inclui linhas que tendem a criar desequilíbrios e posições táticas")
    else:
        base_style = "prático e flexível"
        evidence.append("o repertório mostra uma mistura de estruturas sólidas e posições com desequilíbrio")

    if conversion_note is not None and conversion_note >= 65:
        evidence.append("a conversão de vantagem aparece como um sinal positivo de força prática")
    if resilience_note is not None and resilience_note >= 45:
        evidence.append("há indícios de capacidade de resistência quando a posição fica difícil")
    if endgame_note is not None and endgame_note >= 60:
        evidence.append("os finais aparecem como uma área com sinais de competência técnica")
    if tactics_note is not None and tactics_note < 55:
        evidence.append("a redução de erros táticos pode gerar ganho rápido de desempenho")
    if opening_note is not None and opening_note >= 60:
        evidence.append("a fase de abertura já oferece uma base útil para construir posições jogáveis")

    if not evidence:
        evidence.append("os dados ainda estão formando uma amostra, mas já permitem orientar o treino de forma mais objetiva")

    return {
        "style": base_style,
        "evidence": evidence[:4]
    }


def get_strengths_and_improvements(base_df, profile_df):
    strengths = []
    improvements = []

    if profile_df is not None and len(profile_df) > 0:
        notes = profile_df.dropna(subset=["Nota"]).copy()
        if len(notes) > 0:
            top_notes = notes.sort_values("Nota", ascending=False).head(3)
            low_notes = notes.sort_values("Nota", ascending=True).head(3)

            for _, row in top_notes.iterrows():
                aspecto = row["Aspecto"]
                nota = float(row["Nota"])
                if aspecto == "Abertura":
                    strengths.append(f"A fase de abertura tem nota {nota:.1f}, indicando que o repertório já oferece uma base concreta para trabalhar planos típicos.")
                elif aspecto == "Táticas":
                    strengths.append(f"A métrica de táticas aparece com nota {nota:.1f}; isso sugere boa capacidade de manter a posição sob controle quando evita grandes perdas de avaliação.")
                elif aspecto == "Finais":
                    strengths.append(f"A nota de finais é {nota:.1f}, um sinal importante porque técnica de final costuma converter pequenas vantagens em pontos reais.")
                elif aspecto == "Conversão":
                    strengths.append(f"A conversão aparece com nota {nota:.1f}; quando obtém vantagem, há sinais de boa força prática para transformar isso em resultado.")
                elif aspecto == "Resiliência":
                    strengths.append(f"A resiliência tem nota {nota:.1f}; isso aponta capacidade de continuar criando problemas mesmo em posições difíceis.")
                elif aspecto == "Tempo":
                    strengths.append(f"O gerenciamento de tempo aparece com nota {nota:.1f}, sugerindo que o relógio não tem sido o principal obstáculo no recorte atual.")

            for _, row in low_notes.iterrows():
                aspecto = row["Aspecto"]
                nota = float(row["Nota"])
                if aspecto == "Abertura":
                    improvements.append(f"Revisar as linhas em que a avaliação após 15 lances fica pior. Melhorar a saída da abertura pode elevar todo o restante da partida.")
                elif aspecto == "Táticas":
                    improvements.append(f"Reduzir erros e blunders deve ser uma prioridade de alto retorno. Esse tipo de ajuste costuma produzir melhora rápida no rating.")
                elif aspecto == "Finais":
                    improvements.append(f"Treinar finais recorrentes do próprio banco de partidas pode transformar posições equilibradas em pontos adicionais.")
                elif aspecto == "Conversão":
                    improvements.append(f"Quando conseguir vantagem, priorizar simplificação favorável, segurança do rei e cálculo de lances forçados para converter com mais estabilidade.")
                elif aspecto == "Resiliência":
                    improvements.append(f"Em posições inferiores, buscar recursos práticos: atividade de peças, ameaças diretas, finais defensáveis e complicações quando a posição está objetivamente ruim.")
                elif aspecto == "Tempo":
                    improvements.append(f"Ajustar o uso do relógio: jogar mais automaticamente posições conhecidas de abertura e reservar tempo para momentos críticos do meio-jogo.")

    # Complementos objetivos com engine, quando existirem.
    if base_df is not None and "engine_accuracy" in base_df.columns and base_df["engine_accuracy"].notna().any():
        engine_df = base_df.dropna(subset=["engine_accuracy"]).copy()
        avg_accuracy = safe_mean(engine_df["engine_accuracy"])
        avg_blunders = safe_mean(engine_df["engine_blunders"]) if "engine_blunders" in engine_df.columns else None
        avg_opening_eval = safe_mean(engine_df["opening_eval_15_cp"]) if "opening_eval_15_cp" in engine_df.columns else None

        if avg_accuracy is not None and avg_accuracy >= 75:
            strengths.append(f"A precisão média com Stockfish está em {avg_accuracy:.1f}%, um bom indício de consistência técnica nas partidas analisadas.")
        if avg_blunders is not None and avg_blunders <= 1:
            strengths.append(f"A média de blunders está em {avg_blunders:.2f} por partida, um sinal positivo de controle dos maiores riscos táticos.")
        if avg_opening_eval is not None and avg_opening_eval > 0:
            strengths.append(f"Após 15 lances, a avaliação média é {format_cp(avg_opening_eval)}, sugerindo que há linhas em que você sai da abertura com posições promissoras.")
        elif avg_opening_eval is not None and avg_opening_eval < 0:
            improvements.append(f"A avaliação média após 15 lances está em {format_cp(avg_opening_eval)}. Isso é uma oportunidade clara: revisar poucas linhas críticas pode melhorar muito o conforto das posições.")

    if not strengths:
        strengths.append("Você já tem uma base estatística rica para orientar o treino. Isso por si só é uma vantagem: poucos jogadores estudam a partir dos próprios padrões reais de jogo.")
    if not improvements:
        improvements.append("O próximo passo é aumentar a amostra analisada com Stockfish e acompanhar quais métricas se movem primeiro. Esse acompanhamento tende a revelar ganhos pequenos, mas consistentes.")

    # Remove duplicatas preservando ordem.
    strengths = list(dict.fromkeys(strengths))[:4]
    improvements = list(dict.fromkeys(improvements))[:4]

    return strengths, improvements


def build_training_plan(base_df, profile_df):
    plan = []

    opening_note = get_profile_note(profile_df, "Abertura")
    tactics_note = get_profile_note(profile_df, "Táticas")
    endgame_note = get_profile_note(profile_df, "Finais")
    conversion_note = get_profile_note(profile_df, "Conversão")
    resilience_note = get_profile_note(profile_df, "Resiliência")
    time_note = get_profile_note(profile_df, "Tempo")

    if opening_note is None or opening_note < 60:
        plan.append("Escolha 1 ou 2 aberturas com pior avaliação após 15 lances e revise os planos típicos, não apenas a ordem exata dos lances.")
    else:
        plan.append("Mantenha o repertório principal e aprofunde as posições mais frequentes da árvore de aberturas, buscando planos de meio-jogo claros.")

    if tactics_note is None or tactics_note < 65:
        plan.append("Faça blocos curtos de tática com foco em cálculo antes de capturas, ameaças e lances forçados. O objetivo principal é reduzir blunders, não resolver problemas impossíveis.")
    else:
        plan.append("Use o bom controle tático como base para estudar posições críticas das suas próprias partidas, especialmente momentos em que a avaliação mudou muito.")

    if endgame_note is not None and endgame_note < 60:
        plan.append("Treine finais práticos que aparecem no seu banco de partidas: torres, bispos de cores opostas e finais com material reduzido.")
    elif conversion_note is not None and conversion_note < 60:
        plan.append("Ao obter vantagem, pratique técnica de conversão: trocar peças certas, evitar contrajogo e transformar vantagem dinâmica em vantagem material ou final favorável.")
    elif resilience_note is not None and resilience_note < 45:
        plan.append("Em posições inferiores, treine defesa ativa: criar ameaças, buscar simplificações defensáveis e dificultar decisões do adversário.")
    elif time_note is not None and time_note < 60:
        plan.append("Crie uma regra simples de tempo: jogar rápido posições conhecidas e reservar mais tempo para decisões irreversíveis no meio-jogo.")
    else:
        plan.append("Continue acumulando partidas analisadas e acompanhe mensalmente se precisão, abertura e conversão caminham juntas.")

    return plan[:4]


def render_rule_based_coach(base_df, all_df, profile_df, highest_rating_all_time):
    st.subheader("🧠 Coach do Jogador")

    if base_df is None or len(base_df) == 0:
        st.info("Não há partidas suficientes no filtro atual para gerar o coach do jogador.")
        return

    total_games = len(base_df)
    total_score = base_df["score"].sum() if "score" in base_df.columns else 0
    winrate = (total_score / total_games * 100) if total_games > 0 else 0

    rating_df = base_df.dropna(subset=["rating"]).copy() if "rating" in base_df.columns else pd.DataFrame()
    if len(rating_df) > 0:
        rating_df["rating"] = pd.to_numeric(rating_df["rating"], errors="coerce")
        rating_df = rating_df.dropna(subset=["rating"]).sort_values("date")
        current_rating = int(rating_df.iloc[-1]["rating"]) if len(rating_df) > 0 else "N/A"
    else:
        current_rating = "N/A"

    trend = describe_rating_trend(all_df)
    style = infer_player_style(base_df, profile_df)
    strengths, improvements = get_strengths_and_improvements(base_df, profile_df)
    training_plan = build_training_plan(base_df, profile_df)

    white_lines = get_top_repertoire_lines(base_df, "Brancas", limit=2)
    black_lines = get_top_repertoire_lines(base_df, "Pretas", limit=2)

    stronger_df = pd.DataFrame()
    if "rating" in base_df.columns and "opponent_rating" in base_df.columns:
        rating_compare_df = base_df.dropna(subset=["rating", "opponent_rating"]).copy()
        rating_compare_df["rating"] = pd.to_numeric(rating_compare_df["rating"], errors="coerce")
        rating_compare_df["opponent_rating"] = pd.to_numeric(rating_compare_df["opponent_rating"], errors="coerce")
        stronger_df = rating_compare_df[rating_compare_df["opponent_rating"] - rating_compare_df["rating"] >= 100].copy()

    stronger_text = "Ainda não há amostra suficiente contra adversários 100+ pontos mais fortes no filtro atual."
    if len(stronger_df) > 0:
        stronger_score = stronger_df["score"].mean() * 100
        stronger_text = (
            f"Contra adversários pelo menos 100 pontos mais fortes, o aproveitamento no recorte atual é de "
            f"**{stronger_score:.1f}%** em **{len(stronger_df)}** partida(s). Esse recorte é valioso porque mede força prática sob pressão."
        )

    engine_text = "Aumentar a amostra com Stockfish deixará o diagnóstico ainda mais preciso."
    if "engine_accuracy" in base_df.columns and base_df["engine_accuracy"].notna().any():
        engine_df = base_df.dropna(subset=["engine_accuracy"]).copy()
        avg_accuracy = safe_mean(engine_df["engine_accuracy"])
        avg_cp_loss = safe_mean(engine_df["engine_avg_cp_loss"]) if "engine_avg_cp_loss" in engine_df.columns else None
        avg_opening_eval = safe_mean(engine_df["opening_eval_15_cp"]) if "opening_eval_15_cp" in engine_df.columns else None
        engine_parts = []
        if avg_accuracy is not None:
            engine_parts.append(f"precisão média de **{avg_accuracy:.1f}%**")
        if avg_cp_loss is not None:
            engine_parts.append(f"perda média de **{avg_cp_loss:.1f} cp**")
        if avg_opening_eval is not None:
            engine_parts.append(f"avaliação média após 15 lances de **{format_cp(avg_opening_eval)}**")
        if engine_parts:
            engine_text = "Nas partidas já analisadas com Stockfish, o painel mostra " + ", ".join(engine_parts) + "."

    with st.container():
        st.markdown("#### 📌 Leitura geral")
        st.markdown(
            f"No recorte atual, foram analisadas **{total_games}** partida(s), com aproveitamento de **{winrate:.1f}%**. "
            f"O rating atual exibido no filtro é **{current_rating}** e o maior rating registrado no histórico baixado é **{highest_rating_all_time}**. "
            f"{trend['text']} {engine_text}"
        )

    col_style, col_rep = st.columns([1.1, 1])

    with col_style:
        st.markdown("#### ♟ Estilo provável")
        st.markdown(
            f"Os dados sugerem um estilo **{style['style']}**. Essa leitura não é um rótulo fixo; é uma hipótese prática baseada no repertório, nos resultados e nas métricas disponíveis."
        )
        for item in style["evidence"]:
            st.markdown(f"- {item}.")

    with col_rep:
        st.markdown("#### 📚 Repertório que molda o estilo")
        if white_lines:
            st.markdown("**Com Brancas**")
            for item in white_lines:
                st.markdown(f"- {item['opening_family']}: {int(item['games'])} partida(s), {item['winrate']:.1f}%")
        if black_lines:
            st.markdown("**Com Pretas**")
            for item in black_lines:
                st.markdown(f"- {item['opening_family']}: {int(item['games'])} partida(s), {item['winrate']:.1f}%")
        if not white_lines and not black_lines:
            st.write("Ainda não há repertório classificado suficiente no filtro atual.")

    col_strengths, col_improvements = st.columns(2)

    with col_strengths:
        st.markdown("#### ✅ Pontos fortes")
        for item in strengths:
            st.markdown(f"- {item}")

    with col_improvements:
        st.markdown("#### 🎯 Pontos a melhorar")
        for item in improvements:
            st.markdown(f"- {item}")

    st.markdown("#### 🧩 Força prática")
    st.markdown(
        f"{stronger_text} A força prática não aparece apenas na precisão: ela também aparece em converter vantagens, resistir em posições inferiores e escolher planos simples em posições complexas."
    )

    st.markdown("#### 📈 Plano recomendado")
    for i, item in enumerate(training_plan, start=1):
        st.markdown(f"**{i}.** {item}")

    st.success(
        "Mensagem do coach: o quadro é promissor. Você já transformou suas partidas em dados concretos, "
        "e isso muda a qualidade do treino. O próximo salto tende a vir de ajustes específicos, não de estudar tudo ao mesmo tempo: "
        "corrigir poucas linhas críticas, reduzir blunders recorrentes e acompanhar a evolução com consistência."
    )


# =========================
# BAIXAR PARTIDAS DO CHESS.COM
# =========================

def chesscom_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_profile(username):
    url = f"https://api.chess.com/pub/player/{username}"

    try:
        response = requests.get(url, headers=chesscom_headers(), timeout=30)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    return response.json()


def get_available_archives(username):
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url, headers=chesscom_headers(), timeout=30)

    if response.status_code != 200:
        raise Exception(f"Erro ao buscar arquivos. Status code: {response.status_code}")

    data = response.json()
    return data.get("archives", [])


def download_games_from_chesscom(username):
    archives = get_available_archives(username)
    all_games = []

    progress = st.progress(0, text="Baixando arquivos mensais...")

    for i, archive_url in enumerate(archives):
        response = requests.get(archive_url, headers=chesscom_headers(), timeout=30)

        if response.status_code == 200:
            month_data = response.json()
            all_games.extend(month_data.get("games", []))

        progress.progress((i + 1) / max(len(archives), 1), text="Baixando arquivos mensais...")

    progress.empty()
    return all_games


def save_games_to_json(games, filename="games.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2, ensure_ascii=False)


def get_file_mtime(filename):
    if os.path.exists(filename):
        return os.path.getmtime(filename)
    return None


# =========================
# CARACTERÍSTICAS MATERIAIS DA PARTIDA
# =========================

def get_final_board(game):
    board = game.board()

    for move in game.mainline_moves():
        board.push(move)

    return board


def square_color(square):
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    return (file_index + rank_index) % 2


def count_piece(board, color, piece_type):
    return len(board.pieces(piece_type, color))


def has_rook_ending(board):
    white_rooks = count_piece(board, chess.WHITE, chess.ROOK)
    black_rooks = count_piece(board, chess.BLACK, chess.ROOK)

    white_queens = count_piece(board, chess.WHITE, chess.QUEEN)
    black_queens = count_piece(board, chess.BLACK, chess.QUEEN)

    white_knights = count_piece(board, chess.WHITE, chess.KNIGHT)
    black_knights = count_piece(board, chess.BLACK, chess.KNIGHT)

    white_bishops = count_piece(board, chess.WHITE, chess.BISHOP)
    black_bishops = count_piece(board, chess.BLACK, chess.BISHOP)

    has_rooks = white_rooks >= 1 and black_rooks >= 1
    no_queens = white_queens == 0 and black_queens == 0
    no_minor_pieces = (
        white_knights == 0 and
        black_knights == 0 and
        white_bishops == 0 and
        black_bishops == 0
    )

    return has_rooks and no_queens and no_minor_pieces


def has_opposite_colored_bishops(board):
    white_bishops = list(board.pieces(chess.BISHOP, chess.WHITE))
    black_bishops = list(board.pieces(chess.BISHOP, chess.BLACK))

    white_knights = count_piece(board, chess.WHITE, chess.KNIGHT)
    black_knights = count_piece(board, chess.BLACK, chess.KNIGHT)

    white_queens = count_piece(board, chess.WHITE, chess.QUEEN)
    black_queens = count_piece(board, chess.BLACK, chess.QUEEN)

    # Versão conservadora: exatamente um bispo para cada lado,
    # em casas de cores opostas, sem cavalos e sem damas.
    if len(white_bishops) == 1 and len(black_bishops) == 1:
        white_bishop_color = square_color(white_bishops[0])
        black_bishop_color = square_color(black_bishops[0])

        return (
            white_bishop_color != black_bishop_color and
            white_knights == 0 and
            black_knights == 0 and
            white_queens == 0 and
            black_queens == 0
        )

    return False


def user_has_bishop_pair(board, color):
    return count_piece(board, color, chess.BISHOP) >= 2


def analyze_material_features(game, user_color):
    board = get_final_board(game)

    return {
        "rook_ending": has_rook_ending(board),
        "opposite_colored_bishops": has_opposite_colored_bishops(board),
        "bishop_pair": user_has_bishop_pair(board, user_color)
    }


# =========================
# EVENTOS DA PARTIDA
# =========================

def analyze_game_events(game, user_color):
    board = game.board()

    early_queen_trade = False
    early_queen_trade_limit = 15

    white_castled = None
    black_castled = None

    for move in game.mainline_moves():
        moving_color = board.turn
        fullmove_number = board.fullmove_number

        if board.is_castling(move):
            from_square = move.from_square
            to_square = move.to_square

            if chess.square_file(to_square) > chess.square_file(from_square):
                castle_side = "curto"
            else:
                castle_side = "longo"

            if moving_color == chess.WHITE:
                white_castled = castle_side
            else:
                black_castled = castle_side

        board.push(move)

        white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
        black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))

        if (
            white_queens == 0 and
            black_queens == 0 and
            fullmove_number <= early_queen_trade_limit
        ):
            early_queen_trade = True

    opposite_castling = (
        white_castled is not None and
        black_castled is not None and
        white_castled != black_castled
    )

    if user_color == chess.WHITE:
        user_castled = white_castled is not None
    else:
        user_castled = black_castled is not None

    user_did_not_castle = not user_castled

    return {
        "early_queen_trade": early_queen_trade,
        "opposite_castling": opposite_castling,
        "user_did_not_castle": user_did_not_castle
    }


# =========================
# CONFIGURAÇÃO DO APP E DO USUÁRIO
# =========================

st.set_page_config(
    page_title="Metrificador 64 Casas",
    page_icon="♟",
    layout="wide"
)

# Tema visual global dos gráficos Plotly: paleta Café e Madeira.
COFFEE_BG = "#2C2520"
COFFEE_CARD = "#3E352F"
COFFEE_ACCENT = "#C9A063"
COFFEE_TEXT = "#F5EBE0"
COFFEE_GRID = "rgba(201, 160, 99, 0.18)"

pio.templates["coffee_wood"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=COFFEE_CARD,
        plot_bgcolor=COFFEE_CARD,
        font=dict(color=COFFEE_TEXT),
        colorway=[COFFEE_ACCENT, "#E0BE7C", "#8A6E4C", "#CBB8A3", "#9EE6A4", "#F2A6A0"],
        xaxis=dict(gridcolor=COFFEE_GRID, zerolinecolor=COFFEE_GRID),
        yaxis=dict(gridcolor=COFFEE_GRID, zerolinecolor=COFFEE_GRID),
        polar=dict(
            bgcolor=COFFEE_CARD,
            radialaxis=dict(gridcolor=COFFEE_GRID, linecolor=COFFEE_GRID, tickfont=dict(color=COFFEE_TEXT)),
            angularaxis=dict(gridcolor=COFFEE_GRID, linecolor=COFFEE_GRID, tickfont=dict(color=COFFEE_TEXT)),
        ),
        legend=dict(font=dict(color=COFFEE_TEXT)),
        title=dict(font=dict(color=COFFEE_TEXT)),
    )
)
pio.templates.default = "coffee_wood"
px.defaults.template = "coffee_wood"

st.markdown(
    """
    <style>
    /* =========================
       PALETA CAFÉ E MADEIRA
       ========================= */

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

    /* Fundo geral com degradê discreto */
    .stApp {
        background: linear-gradient(135deg, #2C2520 0%, #241E1A 52%, #332B25 100%);
        color: var(--text-main);
    }

    /* Área principal */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        color: var(--text-main);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #211B17 0%, #2C2520 58%, #241E1A 100%);
        border-right: 1px solid var(--border-soft);
    }

    section[data-testid="stSidebar"] * {
        color: var(--text-main) !important;
    }

    /* Títulos e textos */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-main) !important;
        letter-spacing: -0.01em;
    }

    p, li, span, label, div {
        color: var(--text-main);
    }

    .stCaption, [data-testid="stCaptionContainer"], small {
        color: var(--text-muted) !important;
    }

    a {
        color: var(--accent-soft) !important;
        text-decoration-color: rgba(201, 160, 99, 0.45) !important;
    }

    a:hover {
        color: var(--accent) !important;
    }

    /* Cards de métricas */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #3E352F 0%, #4A4038 100%);
        border: 1px solid var(--border-soft);
        padding: 1rem;
        border-radius: 16px;
        box-shadow: 0 6px 18px var(--shadow-soft);
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] div,
    div[data-testid="stMetric"] span {
        color: var(--text-soft) !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--accent) !important;
        font-weight: 800;
    }

    div[data-testid="stMetricDelta"] {
        color: var(--accent-soft) !important;
    }

    /* Containers de gráficos e tabelas */
    div[data-testid="stDataFrame"],
    div[data-testid="stPlotlyChart"],
    div[data-testid="stTable"] {
        background: rgba(62, 53, 47, 0.82);
        border: 1px solid var(--border-soft);
        border-radius: 16px;
        padding: 0.5rem;
        box-shadow: 0 6px 18px var(--shadow-soft);
    }

    /* Dataframe: tenta harmonizar área interna */
    div[data-testid="stDataFrame"] * {
        color: var(--text-main);
    }

    /* Cards/caixas markdown customizadas usadas no app */
    .trainer-card,
    .custom-card,
    .neutral-box {
        background: rgba(62, 53, 47, 0.92) !important;
        border: 1px solid var(--border-soft) !important;
        color: var(--text-main) !important;
        box-shadow: 0 6px 18px var(--shadow-soft) !important;
    }

    /* Botões */
    .stButton > button {
        background: linear-gradient(135deg, #5A493D 0%, #7A6044 100%);
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft);
        border-radius: 12px;
        padding: 0.55rem 1rem;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #6B5748 0%, #8A6E4C 100%);
        color: var(--accent) !important;
        border-color: var(--accent);
    }

    /* Inputs e selects */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    input {
        background: #3A312B !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 10px !important;
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: var(--text-muted) !important;
        opacity: 0.8;
    }

    div[data-baseweb="select"] > div {
        background: #3A312B !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-soft) !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div {
        color: var(--text-main) !important;
    }

    /* Radio, checkbox, sliders */
    div[role="radiogroup"] label,
    div[data-testid="stCheckbox"] label,
    div[data-testid="stSlider"] label {
        color: var(--text-main) !important;
    }

    /* Expanders */
    details {
        background: rgba(62, 53, 47, 0.86) !important;
        border-radius: 12px;
        border: 1px solid var(--border-soft) !important;
        color: var(--text-main) !important;
        box-shadow: 0 4px 14px var(--shadow-soft);
    }

    details summary,
    details summary * {
        color: var(--accent-soft) !important;
        font-weight: 700;
    }

    /* Alertas */
    div[data-testid="stAlert"] {
        background: #4A4038;
        border: 1px solid var(--border-soft);
        color: var(--text-main);
        border-radius: 12px;
    }

    div[data-testid="stAlert"] * {
        color: var(--text-main) !important;
    }

    /* Separadores */
    hr {
        border-color: var(--border-soft);
    }

    /* Tabs / navegação */
    button[data-baseweb="tab"] {
        color: var(--text-soft) !important;
        background: transparent !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }

    /* Código inline */
    code {
        background: #2C2520 !important;
        color: var(--accent-soft) !important;
        border: 1px solid rgba(201, 160, 99, 0.18);
        border-radius: 6px;
    }

    /* Destaques */
    .highlight,
    .accent-text {
        color: var(--accent) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("♟ Metrificador 64 Casas")

try:
    st.page_link("pages/1_Blunder_Trainer.py", label="🧩 Abrir treinador de blunders", icon="🧩")
except Exception:
    pass

st.sidebar.header("Usuário do Chess.com")

USERNAME = st.sidebar.text_input(
    "Digite o username",
    value=DEFAULT_USERNAME,
    placeholder="Exemplo: fabiorr87"
).strip()

st.session_state["chess_username"] = USERNAME
st.session_state["engine_path"] = DEFAULT_ENGINE_PATH

if not USERNAME:
    st.info("Digite um username do Chess.com na barra lateral para iniciar a análise.")
    st.stop()

games_filename = f"games_{USERNAME.lower()}.json"

player_profile = get_player_profile(USERNAME)

if player_profile:
    avatar_url = player_profile.get("avatar")
    player_name = player_profile.get("name")
    player_title = player_profile.get("title")
    player_country = player_profile.get("country")

    if avatar_url:
        st.sidebar.image(avatar_url, width=120)

    st.sidebar.markdown(f"### {USERNAME}")

    if player_name:
        st.sidebar.write(player_name)

    if player_title:
        st.sidebar.write(f"Título: {player_title}")

    if player_country:
        country_code = player_country.rstrip("/").split("/")[-1]
        st.sidebar.write(f"País: {country_code}")
else:
    st.sidebar.info("Perfil público do usuário não encontrado.")

st.caption(f"Análise das partidas de {USERNAME} no Chess.com")


# =========================
# ATUALIZAÇÃO DE DADOS
# =========================

st.sidebar.header("Atualização de dados")

if st.sidebar.button("Baixar partidas do Chess.com", key="download_games_button"):
    with st.spinner(f"Baixando partidas de {USERNAME} no Chess.com..."):
        try:
            new_games = download_games_from_chesscom(USERNAME)
            save_games_to_json(new_games, filename=games_filename)

            st.cache_data.clear()

            st.sidebar.success(f"{len(new_games)} partidas baixadas com sucesso para {USERNAME}.")
            st.rerun()

        except Exception as e:
            st.sidebar.error(f"Erro ao baixar partidas: {e}")


# =========================
# ÁRVORE DE ABERTURAS
# =========================

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


def make_move_label(move, games, score):
    if games == 0:
        return f"{move} — 0 partidas"

    winrate = round((score / games) * 100, 1)
    return f"{move} — {games} partidas — {winrate}%"


# =========================
# CARREGAR E PROCESSAR JOGOS COM CACHE
# =========================

@st.cache_data(show_spinner="Processando partidas...")
def load_and_process_games(games_filename, username, file_mtime):
    with open(games_filename, "r", encoding="utf-8") as f:
        games = json.load(f)

    data = []
    skipped_games = 0

    for game_data in games:
        pgn_text = game_data.get("pgn")

        if not pgn_text:
            skipped_games += 1
            continue

        game = chess.pgn.read_game(StringIO(pgn_text))

        if game is None:
            skipped_games += 1
            continue

        white = game.headers.get("White", "")
        black = game.headers.get("Black", "")
        result = game.headers.get("Result", "*")

        opening = get_opening_from_headers_or_moves(game)
        opening_family = get_opening_family(game)

        if username.lower() == white.lower():
            color = "Brancas"
            user_color = chess.WHITE
            opponent = black
            score = 1 if result == "1-0" else 0 if result == "0-1" else 0.5
            user_rating = game_data.get("white", {}).get("rating")
            opponent_rating = game_data.get("black", {}).get("rating")
            user_result_reason = game_data.get("white", {}).get("result")

        elif username.lower() == black.lower():
            color = "Pretas"
            user_color = chess.BLACK
            opponent = white
            score = 1 if result == "0-1" else 0 if result == "1-0" else 0.5
            user_rating = game_data.get("black", {}).get("rating")
            opponent_rating = game_data.get("white", {}).get("rating")
            user_result_reason = game_data.get("black", {}).get("result")

        else:
            skipped_games += 1
            continue

        timestamp = game_data.get("end_time")

        if timestamp:
            game_date = datetime.fromtimestamp(timestamp)
        else:
            game_date = None

        if score == 1:
            result_label = "win"
        elif score == 0:
            result_label = "loss"
        else:
            result_label = "draw"

        perspective = classify_side(opening_family, color)
        material_features = analyze_material_features(game, user_color)
        game_events = analyze_game_events(game, user_color)
        opening_san_moves, opening_fens = get_opening_sequence(game, max_plies=6)
        ply_count = get_game_ply_count(game)
        fullmove_count = (ply_count + 1) // 2
        termination = game.headers.get("Termination", "")

        data.append({
            "opening": opening,
            "opening_family": opening_family,
            "color": color,
            "perspective": perspective,
            "score": score,
            "result_label": result_label,
            "rating": user_rating,
            "opponent": opponent,
            "opponent_rating": opponent_rating,
            "date": game_date,
            "time_class": game_data.get("time_class", "unknown"),
            "url": game_data.get("url"),
            "pgn": pgn_text,
            "termination": termination,
            "user_result_reason": user_result_reason,
            "ply_count": ply_count,
            "fullmove_count": fullmove_count,
            "rook_ending": material_features["rook_ending"],
            "opposite_colored_bishops": material_features["opposite_colored_bishops"],
            "bishop_pair": material_features["bishop_pair"],
            "early_queen_trade": game_events["early_queen_trade"],
            "opposite_castling": game_events["opposite_castling"],
            "user_did_not_castle": game_events["user_did_not_castle"],
            "opening_san_moves": opening_san_moves,
            "opening_fens": opening_fens
        })

    df = pd.DataFrame(data)

    if not df.empty:
        df = df.dropna(subset=["date"]).sort_values(by="date").reset_index(drop=True)

    return df, skipped_games


if not os.path.exists(games_filename):
    st.warning(
        f"Nenhum arquivo de partidas encontrado para {USERNAME}. "
        "Use o botão 'Baixar partidas do Chess.com' na barra lateral para baixar as partidas desse usuário."
    )
    st.stop()

file_mtime = get_file_mtime(games_filename)

df, skipped_games = load_and_process_games(
    games_filename,
    USERNAME,
    file_mtime
)

if skipped_games > 0:
    st.warning(
        f"{skipped_games} partidas foram ignoradas porque não tinham PGN válido "
        "ou não pertenciam ao usuário analisado."
    )

if df.empty:
    st.error("Nenhuma partida válida foi encontrada para análise.")
    st.stop()


# =========================
# FILTROS
# =========================

side_filter = st.sidebar.selectbox(
    "Filtrar por cor",
    ["Todas", "Brancas", "Pretas"]
)

time_class_filter = st.sidebar.selectbox(
    "Filtrar por ritmo",
    ["Rápidas", "Blitz", "Bullet", "Diárias"]
)

period_filter = st.sidebar.selectbox(
    "Filtrar por período",
    [
        "Últimos 7 dias",
        "Últimos 30 dias",
        "Últimos 90 dias",
        "Ano atual",
        "Período personalizado",
        "Todas"
    ]
)

st.sidebar.subheader("Características da posição final")

filter_rook_ending = st.sidebar.checkbox("Somente finais de torres")
filter_opposite_bishops = st.sidebar.checkbox("Somente bispos de cores opostas")
filter_bishop_pair = st.sidebar.checkbox("Somente partidas em que terminei com par de bispos")

filtered_df = df.copy()

if side_filter != "Todas":
    filtered_df = filtered_df[filtered_df["color"] == side_filter]

time_class_map = {
    "Rápidas": "rapid",
    "Blitz": "blitz",
    "Bullet": "bullet",
    "Diárias": "daily"
}

selected_time_class = time_class_map[time_class_filter]
filtered_df = filtered_df[filtered_df["time_class"] == selected_time_class]

# Filtro por período
today = datetime.today()

if period_filter == "Últimos 7 dias":
    start_date = today - timedelta(days=7)
    filtered_df = filtered_df[filtered_df["date"] >= start_date]

elif period_filter == "Últimos 30 dias":
    start_date = today - timedelta(days=30)
    filtered_df = filtered_df[filtered_df["date"] >= start_date]

elif period_filter == "Últimos 90 dias":
    start_date = today - timedelta(days=90)
    filtered_df = filtered_df[filtered_df["date"] >= start_date]

elif period_filter == "Ano atual":
    start_date = datetime(today.year, 1, 1)
    filtered_df = filtered_df[filtered_df["date"] >= start_date]

elif period_filter == "Período personalizado":
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    custom_range = st.sidebar.date_input(
        "Escolha o intervalo",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if isinstance(custom_range, tuple) and len(custom_range) == 2:
        custom_start, custom_end = custom_range

        custom_start = datetime.combine(custom_start, datetime.min.time())
        custom_end = datetime.combine(custom_end, datetime.max.time())

        filtered_df = filtered_df[
            (filtered_df["date"] >= custom_start) &
            (filtered_df["date"] <= custom_end)
        ]

if filter_rook_ending:
    filtered_df = filtered_df[filtered_df["rook_ending"] == True]

if filter_opposite_bishops:
    filtered_df = filtered_df[filtered_df["opposite_colored_bishops"] == True]

if filter_bishop_pair:
    filtered_df = filtered_df[filtered_df["bishop_pair"] == True]


# =========================
# ANÁLISE STOCKFISH
# =========================

engine_analysis_filename = f"engine_analysis_{USERNAME.lower()}.json"
engine_analysis_data = load_engine_analysis(engine_analysis_filename)

st.sidebar.header("Stockfish")
engine_path = st.sidebar.text_input(
    "Caminho do Stockfish",
    value=DEFAULT_ENGINE_PATH
)
st.session_state["engine_path"] = engine_path
engine_speed = st.sidebar.selectbox(
    "Tipo de análise",
    ["Rápida", "Normal", "Por profundidade"],
    index=0
)
max_engine_games = st.sidebar.number_input(
    "Máximo de partidas novas por vez",
    min_value=1,
    max_value=200,
    value=10,
    step=1
)

if engine_speed == "Rápida":
    engine_time = 0.05
    engine_depth = 8
elif engine_speed == "Normal":
    engine_time = 0.12
    engine_depth = 10
else:
    engine_time = None
    engine_depth = st.sidebar.slider("Profundidade", min_value=6, max_value=16, value=8)

if st.sidebar.button("Analisar partidas filtradas com Stockfish", key="stockfish_analysis_button"):
    engine_analysis_data = run_stockfish_analysis_for_dataframe(
        base_df=filtered_df,
        engine_path=engine_path,
        analysis_filename=engine_analysis_filename,
        engine_time=engine_time,
        engine_depth=engine_depth,
        max_games=max_engine_games
    )
    st.rerun()

filtered_df = attach_engine_analysis(filtered_df, engine_analysis_data)
engine_analyzed_count = int(filtered_df["engine_accuracy"].notna().sum()) if "engine_accuracy" in filtered_df.columns else 0


# =========================
# KPIs
# =========================

total_games = len(filtered_df)

if total_games > 0:
    total_score = filtered_df["score"].sum()
    winrate = round((total_score / total_games) * 100, 1)
else:
    total_score = 0
    winrate = 0

rating_df = filtered_df.dropna(subset=["rating"]).copy()
rating_df["rating"] = pd.to_numeric(rating_df["rating"], errors="coerce")
rating_df = rating_df.dropna(subset=["rating"])

if len(rating_df) > 0:
    latest_rating = int(rating_df.iloc[-1]["rating"])
    first_rating = int(rating_df.iloc[0]["rating"])
    rating_change = latest_rating - first_rating
else:
    latest_rating = "N/A"
    rating_change = "N/A"

# Maior rating histórico apenas no ritmo selecionado.
# Não aplica filtros de período, cor ou características finais,
# pois a ideia é mostrar o pico de rating de todos os tempos naquele ritmo.
rating_by_selected_time_class_df = df[
    df["time_class"] == selected_time_class
].dropna(subset=["rating"]).copy()

rating_by_selected_time_class_df["rating"] = pd.to_numeric(
    rating_by_selected_time_class_df["rating"],
    errors="coerce"
)
rating_by_selected_time_class_df = rating_by_selected_time_class_df.dropna(subset=["rating"])

if len(rating_by_selected_time_class_df) > 0:
    highest_rating_all_time = int(rating_by_selected_time_class_df["rating"].max())
else:
    highest_rating_all_time = "N/A"

max_wins, max_losses = calculate_streaks(filtered_df["result_label"])

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric("Partidas", total_games)
col2.metric("Pontuação", total_score)
col3.metric("Aproveitamento", f"{winrate}%")
col4.metric("Rating atual", latest_rating, delta=rating_change if rating_change != "N/A" else None)
col5.metric(f"Maior rating ({time_class_filter})", highest_rating_all_time)
col6.metric("Maior sequência", f"{max_wins}V / {max_losses}D")


# =========================
# PERFIL DE DESEMPENHO
# =========================

st.subheader("📊 Perfil de desempenho")

if "engine_accuracy" in filtered_df.columns:
    total_filtered_for_engine = len(filtered_df)
    st.caption(
        f"Stockfish: {engine_analyzed_count}/{total_filtered_for_engine} partida(s) filtrada(s) com análise salva. "
        "As notas usam engine quando há dados disponíveis e voltam para estimativas quando não há."
    )

if len(filtered_df) > 0:
    profile_df = calculate_performance_profile(filtered_df)
    radar_df = profile_df.dropna(subset=["Nota"]).copy()

    if len(radar_df) > 0:
        radar_categories = radar_df["Aspecto"].tolist()
        radar_values = radar_df["Nota"].tolist()

        # Fecha o polígono do radar.
        radar_categories_closed = radar_categories + [radar_categories[0]]
        radar_values_closed = radar_values + [radar_values[0]]

        fig_profile = go.Figure()
        fig_profile.add_trace(go.Scatterpolar(
            r=radar_values_closed,
            theta=radar_categories_closed,
            fill="toself",
            name="Perfil",
            line=dict(color=COFFEE_ACCENT, width=3),
            fillcolor="rgba(201, 160, 99, 0.34)",
            marker=dict(color=COFFEE_ACCENT, size=7)
        ))
        fig_profile.update_layout(
            polar=dict(
                bgcolor=COFFEE_CARD,
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    gridcolor=COFFEE_GRID,
                    linecolor=COFFEE_GRID,
                    tickfont=dict(color=COFFEE_TEXT)
                ),
                angularaxis=dict(
                    gridcolor=COFFEE_GRID,
                    linecolor=COFFEE_GRID,
                    tickfont=dict(color=COFFEE_TEXT)
                )
            ),
            paper_bgcolor=COFFEE_CARD,
            plot_bgcolor=COFFEE_CARD,
            font=dict(color=COFFEE_TEXT),
            showlegend=False,
            title="Notas aproximadas por aspecto do jogo"
        )

        col_profile_chart, col_profile_table = st.columns([1, 1.3])

        with col_profile_chart:
            st.plotly_chart(fig_profile, use_container_width=True)

        with col_profile_table:
            display_profile = profile_df.copy()
            display_profile["Nota"] = display_profile["Nota"].apply(
                lambda x: "Sem dados" if pd.isna(x) else f"{x:.1f}"
            )
            st.dataframe(
                display_profile[[
                    "Aspecto",
                    "Nota",
                    "Amostra",
                    "Diagnóstico",
                    "Interpretação"
                ]],
                use_container_width=True,
                hide_index=True
            )

        with st.expander("Como interpretar estas notas"):
            st.markdown(
                """
                O perfil usa **Stockfish quando há partidas analisadas** e, quando não há dados de engine suficientes, volta para estimativas estatísticas.

                - **Abertura**: com Stockfish, mede a avaliação média após 15 lances completos. Sem engine, usa desempenho nas linhas do repertório.
                - **Táticas**: com Stockfish, usa perda média em centipawns, erros e blunders. Sem engine, usa resultado geral e derrotas curtas.
                - **Finais**: com Stockfish, usa precisão aproximada após o lance 30. Sem engine, usa partidas longas e finais materiais detectados.
                - **Conversão**: com Stockfish, mede aproveitamento quando houve vantagem objetiva de pelo menos +3.00.
                - **Resiliência**: com Stockfish, mede partidas em que o usuário esteve perdido por -3.00 ou pior e conseguiu salvar.
                - **Tempo**: não depende da engine; combina resultado geral e penalização por derrotas associadas ao tempo.
                """
            )

        st.markdown("### Detalhes técnicos das métricas")
        st.dataframe(
            profile_df[[
                "Aspecto",
                "Observação técnica"
            ]],
            use_container_width=True,
            hide_index=True
        )

        render_performance_detailed_report(filtered_df, profile_df)

        render_rule_based_coach(filtered_df, df, profile_df, highest_rating_all_time)
    else:
        st.info("Não há dados suficientes para montar o perfil de desempenho com os filtros atuais.")
else:
    st.info("Nenhuma partida encontrada para montar o perfil de desempenho.")


# =========================
# DETALHES DA ANÁLISE STOCKFISH
# =========================

st.subheader("♟️ Análise com Stockfish")

if "engine_accuracy" in filtered_df.columns and filtered_df["engine_accuracy"].notna().any():
    engine_df = filtered_df.dropna(subset=["engine_accuracy"]).copy()

    col_eng1, col_eng2, col_eng3, col_eng4 = st.columns(4)
    col_eng1.metric("Partidas analisadas", len(engine_df))
    col_eng2.metric("Precisão média", f"{engine_df['engine_accuracy'].mean():.1f}%")
    col_eng3.metric("Perda média", f"{engine_df['engine_avg_cp_loss'].mean():.1f} cp")
    col_eng4.metric("Blunders médios", f"{engine_df['engine_blunders'].mean():.2f}")

    phase_rows = []
    for label, column in [
        ("Abertura", "accuracy_opening"),
        ("Meio-jogo", "accuracy_middlegame"),
        ("Final", "accuracy_endgame")
    ]:
        phase_df = engine_df.dropna(subset=[column]).copy()
        phase_rows.append({
            "Fase": label,
            "Precisão média (%)": round(phase_df[column].mean(), 1) if len(phase_df) > 0 else None,
            "Partidas com amostra": len(phase_df)
        })

    phase_stats = pd.DataFrame(phase_rows)

    col_phase, col_best_technical = st.columns([1, 1.4])

    with col_phase:
        st.markdown("### Precisão por fase")
        st.dataframe(
            phase_stats,
            use_container_width=True,
            hide_index=True
        )

    with col_best_technical:
        st.markdown("### Melhor vitória técnica")
        technical_wins = engine_df[engine_df["result_label"] == "win"].copy()
        if len(technical_wins) > 0:
            technical_wins = technical_wins.sort_values(
                by=["engine_accuracy", "opponent_rating"],
                ascending=[False, False]
            ).head(5)
            show_games_table(technical_wins)
        else:
            st.info("Nenhuma vitória analisada com Stockfish no filtro atual.")

    st.markdown("### Partidas analisadas pela engine")
    engine_display = engine_df[[
        "date",
        "color",
        "opponent",
        "opponent_rating",
        "opening_family",
        "engine_accuracy",
        "engine_avg_cp_loss",
        "engine_mistakes",
        "engine_blunders",
        "engine_opponent_mistakes",
        "engine_opponent_blunders",
        "opening_eval_15_cp",
        "accuracy_opening",
        "accuracy_middlegame",
        "accuracy_endgame",
        "url"
    ]].copy()

    engine_display["date"] = pd.to_datetime(engine_display["date"]).dt.strftime("%d/%m/%Y")
    engine_display = engine_display.rename(columns={
        "date": "Data",
        "color": "Cor",
        "opponent": "Adversário",
        "opponent_rating": "Rating adversário",
        "opening_family": "Abertura",
        "engine_accuracy": "Precisão (%)",
        "engine_avg_cp_loss": "Perda média (cp)",
        "engine_mistakes": "Erros",
        "engine_blunders": "Blunders",
        "engine_opponent_mistakes": "Erros adversário",
        "engine_opponent_blunders": "Blunders adversário",
        "opening_eval_15_cp": "Avaliação após 15 lances (cp)",
        "accuracy_opening": "Precisão abertura (%)",
        "accuracy_middlegame": "Precisão meio-jogo (%)",
        "accuracy_endgame": "Precisão final (%)",
        "url": "Partida"
    })

    st.dataframe(
        engine_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Partida": st.column_config.LinkColumn(
                "Partida no Chess.com",
                display_text="Abrir partida"
            )
        }
    )

else:
    st.info(
        "Nenhuma partida filtrada possui análise Stockfish ainda. "
        "Informe o caminho do Stockfish na barra lateral e clique em 'Analisar partidas filtradas com Stockfish'."
    )


# =========================
# PERFORMANCE MENSAL
# =========================

st.subheader("📅 Performance mensal")

if len(filtered_df) > 0:
    monthly_df = filtered_df.copy()
    monthly_df["month"] = monthly_df["date"].dt.to_period("M").astype(str)

    monthly_stats = monthly_df.groupby("month").agg(
        games=("month", "count"),
        score=("score", "sum")
    ).reset_index()

    monthly_stats["winrate"] = (
        monthly_stats["score"] / monthly_stats["games"] * 100
    ).round(1)

    col_month1, col_month2 = st.columns(2)

    with col_month1:
        fig_month_games = px.bar(
            monthly_stats,
            x="month",
            y="games",
            text="games",
            title="Partidas por mês"
        )

        st.plotly_chart(fig_month_games, use_container_width=True)

    with col_month2:
        fig_month_winrate = px.line(
            monthly_stats,
            x="month",
            y="winrate",
            markers=True,
            title="Aproveitamento mensal (%)"
        )

        st.plotly_chart(fig_month_winrate, use_container_width=True)

    st.dataframe(
        monthly_stats,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Nenhuma partida encontrada para o período selecionado.")


# =========================
# EVOLUÇÃO DE RATING
# =========================

st.subheader("📈 Evolução de rating")

if len(rating_df) > 0:
    fig_rating = px.line(
        rating_df,
        x="date",
        y="rating",
        markers=True,
        title="Rating por partida"
    )

    st.plotly_chart(fig_rating, use_container_width=True)
else:
    st.info("Não há dados de rating disponíveis para o filtro selecionado.")


# =========================
# RESULTADOS POR RATING DO ADVERSÁRIO
# =========================

st.subheader("🎯 Resultados por rating do adversário")

rating_bucket_df = filtered_df.dropna(subset=["opponent_rating"]).copy()

if len(rating_bucket_df) > 0:
    rating_bucket_df["faixa_rating_adversario"] = pd.cut(
        rating_bucket_df["opponent_rating"],
        bins=[0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 3000],
        labels=[
            "Até 1000",
            "1001-1200",
            "1201-1400",
            "1401-1600",
            "1601-1800",
            "1801-2000",
            "2001-2200",
            "2201-2400",
            "2401+"
        ],
        include_lowest=True
    )

    bucket_stats = rating_bucket_df.groupby("faixa_rating_adversario", observed=False).agg(
        games=("faixa_rating_adversario", "count"),
        wins=("result_label", lambda x: (x == "win").sum()),
        draws=("result_label", lambda x: (x == "draw").sum()),
        losses=("result_label", lambda x: (x == "loss").sum()),
        avg_opponent_rating=("opponent_rating", "mean")
    ).reset_index()

    bucket_stats = bucket_stats[bucket_stats["games"] > 0].copy()

    bucket_stats["score"] = (
        bucket_stats["wins"] +
        bucket_stats["draws"] * 0.5
    )

    bucket_stats["winrate"] = (
        bucket_stats["score"] / bucket_stats["games"] * 100
    ).round(1)

    bucket_stats["avg_opponent_rating"] = (
        bucket_stats["avg_opponent_rating"].round(0).astype(int)
    )

    bucket_display = bucket_stats.rename(columns={
        "faixa_rating_adversario": "Faixa de rating",
        "games": "Partidas",
        "wins": "Vitórias",
        "draws": "Empates",
        "losses": "Derrotas",
        "avg_opponent_rating": "Rating médio adversário",
        "winrate": "Aproveitamento (%)"
    })

    st.dataframe(
        bucket_display[[
            "Faixa de rating",
            "Partidas",
            "Vitórias",
            "Empates",
            "Derrotas",
            "Rating médio adversário",
            "Aproveitamento (%)"
        ]],
        use_container_width=True,
        hide_index=True
    )

    fig_bucket = px.bar(
        bucket_stats,
        x="faixa_rating_adversario",
        y="winrate",
        text="winrate",
        title="Aproveitamento por faixa de rating do adversário"
    )

    st.plotly_chart(fig_bucket, use_container_width=True)

else:
    st.info("Não há dados de rating dos adversários para o filtro selecionado.")


# =========================
# MELHORES VITÓRIAS
# =========================

st.subheader("🏅 Melhores 3 vitórias")

wins_df = filtered_df[
    (filtered_df["result_label"] == "win") &
    (filtered_df["opponent_rating"].notna())
].copy()

if len(wins_df) > 0:
    top_wins = wins_df.sort_values(
        by="opponent_rating",
        ascending=False
    ).head(3)

    show_games_table(top_wins)

else:
    st.info("Nenhuma vitória com rating de adversário encontrada para o filtro selecionado.")


# =========================
# ÚLTIMAS 10 PARTIDAS
# =========================

st.subheader("🕘 Últimas 10 partidas")

recent_games_df = filtered_df.dropna(subset=["date"]).copy()

if len(recent_games_df) > 0:
    recent_games = recent_games_df.sort_values(
        by="date",
        ascending=False
    ).head(10)

    show_games_table(recent_games)

else:
    st.info("Nenhuma partida encontrada para os filtros selecionados.")


# =========================
# ÁRVORE DE ABERTURAS
# =========================

st.subheader("🌳 Árvore de aberturas")

st.caption(
    "Selecione os lances em sequência. A árvore agora vai até o 3º lance das pretas. "
    "Cada meio-lance só fica disponível depois da escolha do meio-lance anterior."
)

tree_color = st.radio(
    "Ver árvore quando o usuário jogou com:",
    ["Brancas", "Pretas"],
    horizontal=True
)

tree_df = filtered_df[filtered_df["color"] == tree_color].copy()

if len(tree_df) == 0:
    st.info("Nenhuma partida encontrada para montar a árvore com os filtros atuais.")
else:
    ply_labels = [
        "1º lance das brancas",
        "1º lance das pretas",
        "2º lance das brancas",
        "2º lance das pretas",
        "3º lance das brancas",
        "3º lance das pretas"
    ]

    current_branch = tree_df.copy()
    selected_moves = []
    selection_locked = False
    placeholder = "— selecione um lance —"

    st.markdown("### Navegação pelos lances iniciais")

    for ply_index, ply_label in enumerate(ply_labels):
        select_key = f"opening_tree_ply_{ply_index}_{tree_color}_sequencial"

        if selection_locked:
            st.selectbox(
                ply_label,
                ["Selecione o lance anterior primeiro"],
                index=0,
                disabled=True,
                key=select_key
            )
            continue

        available_df = current_branch[
            current_branch["opening_san_moves"].apply(
                lambda moves: isinstance(moves, list) and len(moves) > ply_index
            )
        ].copy()

        if len(available_df) == 0:
            st.selectbox(
                ply_label,
                ["Não há dados para este meio-lance"],
                index=0,
                disabled=True,
                key=select_key
            )
            selection_locked = True
            continue

        available_df["move_at_ply"] = available_df["opening_san_moves"].apply(
            lambda moves: moves[ply_index]
        )

        move_stats = available_df.groupby("move_at_ply").agg(
            games=("move_at_ply", "count"),
            score=("score", "sum")
        ).reset_index()

        move_stats = move_stats.sort_values(
            by=["games", "score"],
            ascending=[False, False]
        )

        move_options = move_stats["move_at_ply"].tolist()

        label_map = {
            placeholder: placeholder,
            **{
                row["move_at_ply"]: make_move_label(
                    row["move_at_ply"],
                    int(row["games"]),
                    row["score"]
                )
                for _, row in move_stats.iterrows()
            }
        }

        selected_move = st.selectbox(
            ply_label,
            [placeholder] + move_options,
            index=0,
            format_func=lambda move: label_map.get(move, move),
            key=select_key
        )

        if selected_move == placeholder:
            selection_locked = True
            continue

        selected_moves.append(selected_move)

        current_branch = current_branch[
            current_branch["opening_san_moves"].apply(
                lambda moves: (
                    isinstance(moves, list)
                    and len(moves) > ply_index
                    and moves[ply_index] == selected_move
                )
            )
        ].copy()

    st.markdown("### Posição selecionada")

    orientation = chess.WHITE if tree_color == "Brancas" else chess.BLACK

    if len(selected_moves) == 0:
        st.info("Selecione o primeiro lance para começar a navegar pela árvore.")

        initial_board = chess.Board()
        board_svg = chess.svg.board(
            board=initial_board,
            size=420,
            orientation=orientation
        )
        components.html(board_svg, height=440)

    elif len(current_branch) > 0:
        example_row = current_branch.iloc[0]
        fens = example_row["opening_fens"]

        if isinstance(fens, list) and len(fens) > len(selected_moves):
            selected_fen = fens[len(selected_moves)]
            board = chess.Board(selected_fen)

            board_svg = chess.svg.board(
                board=board,
                size=420,
                orientation=orientation
            )

            components.html(board_svg, height=440)

        st.markdown("### Resumo do ramo selecionado")

        branch_games = len(current_branch)
        branch_score = current_branch["score"].sum()
        branch_winrate = round((branch_score / branch_games) * 100, 1) if branch_games > 0 else 0

        col_tree1, col_tree2, col_tree3 = st.columns(3)

        col_tree1.metric("Partidas no ramo", branch_games)
        col_tree2.metric("Pontuação", branch_score)
        col_tree3.metric("Aproveitamento", f"{branch_winrate}%")

        st.markdown("### Partidas neste ramo")

        show_games_table(current_branch)
    else:
        st.info("Nenhuma partida encontrada para o ramo selecionado.")


# =========================
# RESULTADOS POR EVENTOS DA PARTIDA
# =========================

st.subheader("⚔️ Resultados por eventos da partida")

if len(filtered_df) > 0:
    event_rows = []

    events = [
        {
            "label": "Troca de damas cedo",
            "column": "early_queen_trade"
        },
        {
            "label": "Roques em lados opostos",
            "column": "opposite_castling"
        },
        {
            "label": "Você não rocou",
            "column": "user_did_not_castle"
        }
    ]

    for event in events:
        event_df = filtered_df[filtered_df[event["column"]] == True]

        games_count = len(event_df)

        if games_count > 0:
            score = event_df["score"].sum()
            wins = (event_df["result_label"] == "win").sum()
            draws = (event_df["result_label"] == "draw").sum()
            losses = (event_df["result_label"] == "loss").sum()
            winrate = round((score / games_count) * 100, 1)
        else:
            score = 0
            wins = 0
            draws = 0
            losses = 0
            winrate = None

        event_rows.append({
            "Evento": event["label"],
            "Partidas": games_count,
            "Vitórias": wins,
            "Empates": draws,
            "Derrotas": losses,
            "Pontuação": score,
            "Aproveitamento (%)": winrate
        })

    event_stats = pd.DataFrame(event_rows)

    st.dataframe(
        event_stats,
        use_container_width=True,
        hide_index=True
    )

    event_chart_df = event_stats.dropna(subset=["Aproveitamento (%)"])

    if len(event_chart_df) > 0:
        fig_events = px.bar(
            event_chart_df,
            x="Evento",
            y="Aproveitamento (%)",
            text="Aproveitamento (%)",
            title="Aproveitamento por evento da partida"
        )

        st.plotly_chart(fig_events, use_container_width=True)

    st.markdown("### 🔎 Acessar partidas por evento")

    def show_event_games(title, column_name):
        event_games = filtered_df[filtered_df[column_name] == True].copy()

        with st.expander(f"{title} ({len(event_games)} partidas)"):
            if len(event_games) > 0:
                event_games = event_games.sort_values(
                    by="date",
                    ascending=False
                )

                show_games_table(event_games)
            else:
                st.info("Nenhuma partida encontrada para este evento com os filtros atuais.")

    show_event_games("Troca de damas cedo", "early_queen_trade")
    show_event_games("Roques em lados opostos", "opposite_castling")
    show_event_games("Você não rocou", "user_did_not_castle")

else:
    st.info("Nenhuma partida encontrada para os filtros selecionados.")


# =========================
# CARACTERÍSTICAS MATERIAIS
# =========================

st.subheader("♜ Características materiais da posição final")

if len(filtered_df) > 0:
    material_summary = pd.DataFrame([
        {
            "Característica": "Finais de torres",
            "Partidas": int(filtered_df["rook_ending"].sum()),
            "Aproveitamento (%)": round(
                filtered_df[filtered_df["rook_ending"] == True]["score"].mean() * 100, 1
            ) if filtered_df["rook_ending"].sum() > 0 else None
        },
        {
            "Característica": "Bispos de cores opostas",
            "Partidas": int(filtered_df["opposite_colored_bishops"].sum()),
            "Aproveitamento (%)": round(
                filtered_df[filtered_df["opposite_colored_bishops"] == True]["score"].mean() * 100, 1
            ) if filtered_df["opposite_colored_bishops"].sum() > 0 else None
        },
        {
            "Característica": "Terminei com par de bispos",
            "Partidas": int(filtered_df["bishop_pair"].sum()),
            "Aproveitamento (%)": round(
                filtered_df[filtered_df["bishop_pair"] == True]["score"].mean() * 100, 1
            ) if filtered_df["bishop_pair"].sum() > 0 else None
        }
    ])

    st.dataframe(
        material_summary,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Nenhuma partida encontrada para os filtros selecionados.")

# =========================
# REPERTÓRIO DO USUÁRIO
# =========================

st.subheader("📚 Repertório do usuário")

def build_repertoire_table(base_df, color_name):
    repertoire_df = base_df[
        (base_df["color"] == color_name) &
        (base_df["perspective"].str.startswith("Joguei:"))
    ].copy()

    if len(repertoire_df) == 0:
        return pd.DataFrame()

    total_color_games = len(repertoire_df)

    repertoire_stats = repertoire_df.groupby("opening_family").agg(
        games=("opening_family", "count"),
        score=("score", "sum")
    ).reset_index()

    repertoire_stats["participacao_repertorio"] = (
        repertoire_stats["games"] / total_color_games * 100
    ).round(1)

    repertoire_stats["winrate"] = (
        repertoire_stats["score"] / repertoire_stats["games"] * 100
    ).round(1)

    repertoire_stats = repertoire_stats.sort_values(
        by=["games", "winrate"],
        ascending=[False, False]
    )

    repertoire_stats = repertoire_stats.rename(columns={
        "opening_family": "Abertura/Defesa",
        "games": "Partidas",
        "participacao_repertorio": "Participação no repertório (%)",
        "score": "Pontuação",
        "winrate": "Aproveitamento (%)"
    })

    return repertoire_stats


white_repertoire = build_repertoire_table(filtered_df, "Brancas")
black_repertoire = build_repertoire_table(filtered_df, "Pretas")

col_white_rep, col_black_rep = st.columns(2)

with col_white_rep:
    st.markdown("### ⚪ Repertório de Brancas")

    if len(white_repertoire) > 0:
        st.dataframe(
            white_repertoire,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhuma abertura jogada de brancas encontrada para os filtros atuais.")

with col_black_rep:
    st.markdown("### ⚫ Repertório de Pretas")

    if len(black_repertoire) > 0:
        st.dataframe(
            black_repertoire,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhuma defesa jogada de pretas encontrada para os filtros atuais.")


st.markdown("### 🔍 Variantes mais frequentes")

variant_df = filtered_df[
    filtered_df["perspective"].str.startswith("Joguei:")
].copy()

if len(variant_df) > 0:
    variant_stats = variant_df.groupby(["color", "opening_family", "opening"]).agg(
        games=("opening", "count"),
        score=("score", "sum")
    ).reset_index()

    variant_stats["winrate"] = (
        variant_stats["score"] / variant_stats["games"] * 100
    ).round(1)

    variant_stats = variant_stats.sort_values(
        by=["color", "games", "winrate"],
        ascending=[True, False, False]
    )

    variant_stats = variant_stats.rename(columns={
        "color": "Cor",
        "opening_family": "Família",
        "opening": "Variante ECO/Chess.com",
        "games": "Partidas",
        "score": "Pontuação",
        "winrate": "Aproveitamento (%)"
    })

    st.dataframe(
        variant_stats,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Nenhuma variante jogada encontrada para os filtros atuais.")

# =========================
# ESTATÍSTICAS POR ABERTURA
# =========================

st.subheader("♟ Desempenho por abertura")

if total_games > 0:
    opening_stats = filtered_df.groupby(["color", "perspective"]).agg(
        games=("perspective", "count"),
        score=("score", "sum")
    ).reset_index()

    opening_stats["winrate"] = (
        opening_stats["score"] / opening_stats["games"] * 100
    ).round(1)

    opening_stats["diagnóstico"] = opening_stats.apply(
        lambda row: make_recommendation(row["games"], row["winrate"]),
        axis=1
    )

    opening_stats = opening_stats.sort_values(
        by=["color", "games", "winrate"],
        ascending=[True, False, False]
    )

    st.dataframe(
        opening_stats,
        use_container_width=True,
        hide_index=True
    )

    fig_openings = px.bar(
        opening_stats,
        x="perspective",
        y="winrate",
        color="color",
        text="winrate",
        title="Aproveitamento por abertura"
    )

    st.plotly_chart(fig_openings, use_container_width=True)

else:
    st.warning("Nenhuma partida encontrada para o filtro selecionado.")


# =========================
# BRANCAS E PRETAS SEPARADAS
# =========================

st.subheader("⚪ Relatório com Brancas")

white_df = filtered_df[filtered_df["color"] == "Brancas"]

if len(white_df) > 0:
    white_stats = white_df.groupby("perspective").agg(
        games=("perspective", "count"),
        score=("score", "sum")
    ).reset_index()

    white_stats["winrate"] = (
        white_stats["score"] / white_stats["games"] * 100
    ).round(1)

    white_stats["diagnóstico"] = white_stats.apply(
        lambda row: make_recommendation(row["games"], row["winrate"]),
        axis=1
    )

    white_stats = white_stats.sort_values(
        by=["games", "winrate"],
        ascending=[False, False]
    )

    st.dataframe(
        white_stats,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Nenhuma partida de brancas encontrada.")


st.subheader("⚫ Relatório com Pretas")

black_df = filtered_df[filtered_df["color"] == "Pretas"]

if len(black_df) > 0:
    black_stats = black_df.groupby("perspective").agg(
        games=("perspective", "count"),
        score=("score", "sum")
    ).reset_index()

    black_stats["winrate"] = (
        black_stats["score"] / black_stats["games"] * 100
    ).round(1)

    black_stats["diagnóstico"] = black_stats.apply(
        lambda row: make_recommendation(row["games"], row["winrate"]),
        axis=1
    )

    black_stats = black_stats.sort_values(
        by=["games", "winrate"],
        ascending=[False, False]
    )

    st.dataframe(
        black_stats,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Nenhuma partida de pretas encontrada.")


# =========================
# MELHORES E PIORES ABERTURAS
# =========================

st.subheader("🏆 Melhores e piores recortes")

if total_games > 0:
    reliable_stats = opening_stats[opening_stats["games"] >= 2].copy()

    if len(reliable_stats) > 0:
        best = reliable_stats.sort_values(
            by=["winrate", "games"],
            ascending=[False, False]
        ).head(5)

        worst = reliable_stats.sort_values(
            by=["winrate", "games"],
            ascending=[True, False]
        ).head(5)

        col_best, col_worst = st.columns(2)

        with col_best:
            st.markdown("### Melhores")
            st.dataframe(
                best[["perspective", "games", "score", "winrate", "diagnóstico"]],
                use_container_width=True,
                hide_index=True
            )

        with col_worst:
            st.markdown("### Piores")
            st.dataframe(
                worst[["perspective", "games", "score", "winrate", "diagnóstico"]],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Ainda não há aberturas com pelo menos 2 partidas no filtro selecionado.")
