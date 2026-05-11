import os
import sys
from pathlib import Path

import chess
import chess.svg
import streamlit as st
import streamlit.components.v1 as components

# Garante que a página encontre o arquivo auxiliar mesmo rodando a partir da pasta pages/.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chess_training_utils import (
    DEFAULT_ENGINE_PATH,
    analysis_filename_for_user,
    classify_exercise_difficulty,
    classify_exercise_theme,
    collect_training_positions,
    evaluate_attempt,
    exercise_label,
    format_points,
    get_exercise_progress,
    legal_moves_san,
    load_blunder_progress,
    load_engine_analysis,
    mark_exercise_status,
    progress_filename_for_user,
    progress_stats,
    record_attempt,
    reset_exercise_progress,
    save_blunder_progress,
    status_label,
    get_legal_move_options_pt,
    san_to_pt,
)


st.set_page_config(
    page_title="Treinador de Blunders — Metrificador 64 Casas",
    page_icon="🧩",
    layout="wide"
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #eaf3ff 0%, #dcecff 45%, #f7fbff 100%);
        color: #1f2937;
    }
    h1, h2, h3 { color: #0f172a; }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #dbeafe 0%, #eff6ff 100%);
        border-right: 1px solid rgba(59, 130, 246, 0.18);
    }
    .trainer-card {
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    }
    .success-box {
        background: #dcfce7;
        border: 1px solid #86efac;
        color: #14532d;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        font-weight: 600;
    }
    .warning-box {
        background: #fef9c3;
        border: 1px solid #fde68a;
        color: #713f12;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        font-weight: 600;
    }
    .danger-box {
        background: #fee2e2;
        border: 1px solid #fecaca;
        color: #7f1d1d;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        font-weight: 600;
    }
    .neutral-box {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def apply_filters(exercises, progress, phase_filter, reason_filter, color_filter, difficulty_filter, theme_filter, status_filter):
    filtered = list(exercises)

    if phase_filter != "Todos":
        filtered = [ex for ex in filtered if (ex.get("phase_label") or ex.get("phase")) == phase_filter]
    if reason_filter != "Todos":
        filtered = [ex for ex in filtered if ex.get("reason") == reason_filter]
    if color_filter != "Todas":
        filtered = [ex for ex in filtered if ex.get("color") == color_filter]
    if difficulty_filter != "Todas":
        filtered = [ex for ex in filtered if (ex.get("difficulty") or classify_exercise_difficulty(ex)) == difficulty_filter]
    if theme_filter != "Todos":
        filtered = [ex for ex in filtered if (ex.get("theme") or classify_exercise_theme(ex)) == theme_filter]

    if status_filter != "Todos":
        target = {
            "Novos": "novo",
            "Resolvidos": "resolvido",
            "Para revisar": "revisar",
            "Errados": "errado",
            "Ignorados": "ignorado",
        }.get(status_filter)
        if target:
            filtered = [
                ex for ex in filtered
                if get_exercise_progress(progress, ex["exercise_id"]).get("status", "novo") == target
            ]

    return filtered


def reset_feedback_if_new_exercise(exercise_id):
    if st.session_state.get("current_exercise_id") != exercise_id:
        st.session_state["current_exercise_id"] = exercise_id
        st.session_state["trainer_feedback"] = None
        st.session_state["move_text_manual"] = ""
        st.session_state["legal_move_choice"] = ""


def progress_badge(status):
    if status == "resolvido":
        return "✅ Resolvido"
    if status == "revisar":
        return "🟡 Para revisar"
    if status == "errado":
        return "🔴 Errado"
    if status == "ignorado":
        return "⏭️ Ignorado"
    return "🆕 Novo"


def exercise_sort_key(exercise, progress):
    """
    Ordena a fila do treinador para priorizar exercícios ainda pendentes.

    Ordem:
    1. Errados
    2. Para revisar
    3. Novos
    4. Ignorados
    5. Resolvidos

    Dentro de cada grupo, exercícios com maior perda de avaliação aparecem antes.
    """
    exercise_id = exercise.get("exercise_id")
    exercise_progress = get_exercise_progress(progress, exercise_id) if exercise_id else {}
    status = exercise_progress.get("status", "novo")

    status_priority = {
        "errado": 0,
        "revisar": 1,
        "novo": 2,
        "ignorado": 3,
        "resolvido": 4,
    }

    priority = status_priority.get(status, 2)

    try:
        loss_cp = float(exercise.get("loss_cp") or 0)
    except Exception:
        loss_cp = 0

    return (priority, -loss_cp, exercise.get("exercise_id", ""))


st.title("🧩 Treinador de Blunders")
st.caption("Treine posições críticas extraídas das próprias partidas analisadas com Stockfish.")

st.sidebar.header("Configuração")

username_default = st.session_state.get("chess_username", "") or ""
username = st.sidebar.text_input(
    "Username do Chess.com",
    value=username_default,
    placeholder="Exemplo: fabiorr87"
).strip()

engine_path_default = st.session_state.get("engine_path", DEFAULT_ENGINE_PATH)
engine_path = st.sidebar.text_input(
    "Caminho do Stockfish",
    value=engine_path_default
)
st.session_state["engine_path"] = engine_path

analysis_speed = st.sidebar.selectbox(
    "Velocidade da avaliação",
    ["Rápida", "Normal", "Por profundidade"],
    index=0
)

if analysis_speed == "Rápida":
    engine_time = 0.05
    engine_depth = 8
elif analysis_speed == "Normal":
    engine_time = 0.12
    engine_depth = 10
else:
    engine_time = None
    engine_depth = st.sidebar.slider("Profundidade", min_value=6, max_value=16, value=10)

if not username:
    st.info("Digite um username na barra lateral para carregar os exercícios.")
    st.stop()

analysis_filename = analysis_filename_for_user(username)
progress_filename = progress_filename_for_user(username)

analysis_data = load_engine_analysis(analysis_filename)
exercises = collect_training_positions(analysis_data)
progress = load_blunder_progress(progress_filename, username=username)

if len(exercises) == 0:
    st.warning(
        "Nenhum exercício de blunder foi encontrado para este usuário. "
        "Volte ao dashboard principal, analise partidas filtradas com Stockfish e depois retorne a esta página. "
        "Partidas já analisadas em versões antigas precisam ser reanalisadas para gerar exercícios."
    )
    st.stop()

# Garante metadados de progresso para exercícios novos sem gravar tentativas falsas.
for ex in exercises:
    get_exercise_progress(progress, ex["exercise_id"])
save_blunder_progress(progress_filename, progress)

stats = progress_stats(exercises, progress)
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("Exercícios", stats["total"])
col_m2.metric("Novos", stats["novo"])
col_m3.metric("Resolvidos", stats["resolvido"])
col_m4.metric("Para revisar", stats["revisar"])
col_m5.metric("Errados", stats["errado"])

st.sidebar.header("Filtros")
phase_options = ["Todos"] + sorted({ex.get("phase_label") or ex.get("phase") for ex in exercises if ex.get("phase_label") or ex.get("phase")})
reason_options = ["Todos"] + sorted({ex.get("reason") for ex in exercises if ex.get("reason")})
color_options = ["Todas", "Brancas", "Pretas"]
difficulty_options = ["Todas"] + sorted({ex.get("difficulty") or classify_exercise_difficulty(ex) for ex in exercises})
theme_options = ["Todos"] + sorted({ex.get("theme") or classify_exercise_theme(ex) for ex in exercises})
status_options = ["Todos", "Novos", "Para revisar", "Errados", "Resolvidos", "Ignorados"]

phase_filter = st.sidebar.selectbox("Fase", phase_options)
reason_filter = st.sidebar.selectbox("Tipo de blunder", reason_options)
color_filter = st.sidebar.selectbox("Cor", color_options)
difficulty_filter = st.sidebar.selectbox("Dificuldade", difficulty_options)
theme_filter = st.sidebar.selectbox("Tema", theme_options)
status_filter = st.sidebar.selectbox("Status de treino", status_options)

filtered = apply_filters(
    exercises,
    progress,
    phase_filter,
    reason_filter,
    color_filter,
    difficulty_filter,
    theme_filter,
    status_filter,
)

# Mantém os exercícios resolvidos no final da fila.
# Assim, ao fechar e abrir novamente o treinador, os pendentes aparecem primeiro.
filtered = sorted(
    filtered,
    key=lambda ex: exercise_sort_key(ex, progress)
)

if len(filtered) == 0:
    st.info("Nenhum exercício encontrado com os filtros atuais.")
    st.stop()

if "trainer_index" not in st.session_state:
    st.session_state["trainer_index"] = 0

if st.session_state["trainer_index"] >= len(filtered):
    st.session_state["trainer_index"] = 0

selected_index = st.selectbox(
    "Escolha um exercício",
    options=list(range(len(filtered))),
    index=st.session_state["trainer_index"],
    format_func=lambda i: exercise_label(filtered[i], i)
)

exercise = filtered[selected_index]
exercise_id = exercise["exercise_id"]
reset_feedback_if_new_exercise(exercise_id)
st.session_state["trainer_index"] = selected_index
exercise_progress = get_exercise_progress(progress, exercise_id)

st.markdown(
    f'<div class="neutral-box">Status deste exercício: {progress_badge(exercise_progress.get("status", "novo"))} '
    f'• Tentativas: {exercise_progress.get("attempt_count", 0)}</div>',
    unsafe_allow_html=True
)

col_board, col_info = st.columns([1, 1.15])

with col_board:
    board = chess.Board(exercise["fen_before"])
    orientation = chess.WHITE if exercise.get("user_color") == "white" else chess.BLACK
    board_svg = chess.svg.board(board=board, size=460, orientation=orientation)
    components.html(board_svg, height=480)

with col_info:
    st.markdown('<div class="trainer-card">', unsafe_allow_html=True)
    st.markdown("### Posição de treino")
    st.write(f"**Fase:** {exercise.get('phase_label', exercise.get('phase', ''))}")
    st.write(f"**Tema:** {exercise.get('theme') or classify_exercise_theme(exercise)}")
    st.write(f"**Dificuldade:** {exercise.get('difficulty') or classify_exercise_difficulty(exercise)}")
    st.write(f"**Motivo:** {exercise.get('reason', '')}")
    st.write(f"**Cor do usuário:** {exercise.get('color', '')}")
    st.write(f"**Adversário:** {exercise.get('opponent') or 'não informado'}")
    if exercise.get("opponent_rating"):
        st.write(f"**Rating adversário:** {exercise.get('opponent_rating')}")
    st.write(f"**Abertura:** {exercise.get('opening') or exercise.get('opening_family') or 'não identificada'}")
    st.write(f"**Avaliação antes:** {format_points(exercise.get('eval_before_cp'))} pontos")
    st.write(f"**Avaliação após o lance da partida:** {format_points(exercise.get('eval_after_cp'))} pontos")
    st.write(f"**Lance jogado na partida:** `{exercise.get('played_move_san')}`")
    if exercise.get("game_url"):
        st.markdown(f"[Abrir partida no Chess.com]({exercise.get('game_url')})")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("### Encontre um lance melhor")
st.caption(
    "Você pode digitar o lance em notação portuguesa, como Cc3, Da3, Tfc1 ou O-O. "
    "Também pode escolher um lance legal na lista."
)

input_mode = st.radio(
    "Modo de resposta",
    ["Digitar lance", "Selecionar lance legal"],
    horizontal=True,
    key=f"input_mode_{exercise.get('exercise_id', selected_index)}"
)

move_to_evaluate = ""

with st.form("move_attempt_form", clear_on_submit=False):
    if input_mode == "Digitar lance":
        move_to_evaluate = st.text_input(
            "Seu lance",
            placeholder="Exemplo: Cc3, Da3, Tfc1 ou O-O",
            key=f"move_text_manual_{exercise.get('exercise_id', selected_index)}"
        )
    else:
        legal_move_options = [{"label": "Selecione...", "uci": ""}] + get_legal_move_options_pt(board)

        selected_legal = st.selectbox(
            "Escolha um lance legal",
            options=legal_move_options,
            format_func=lambda item: item["label"],
            key=f"legal_move_choice_{exercise.get('exercise_id', selected_index)}"
        )

        move_to_evaluate = selected_legal["uci"] if selected_legal else ""

    submitted = st.form_submit_button("Avaliar lance")

    if submitted:
        feedback = evaluate_attempt(
            exercise=exercise,
            move_text=move_to_evaluate,
            engine_path=engine_path,
            engine_time=engine_time,
            engine_depth=engine_depth
        )
        st.session_state["trainer_feedback"] = feedback

        if feedback.get("status") == "ok":
            record_attempt(progress, exercise_id, move_to_evaluate, feedback)
            save_blunder_progress(progress_filename, progress)
            exercise_progress = get_exercise_progress(progress, exercise_id)

    feedback = st.session_state.get("trainer_feedback")

    if feedback:
        if feedback.get("status") == "error":
            st.markdown(f'<div class="danger-box">{feedback.get("message")}</div>', unsafe_allow_html=True)
        else:
            verdict = feedback.get("verdict")
            if verdict == "best":
                css_class = "success-box"
            elif verdict in ["good", "playable"]:
                css_class = "warning-box"
            else:
                css_class = "danger-box"

            st.markdown(f'<div class="{css_class}">{feedback.get("message")}</div>', unsafe_allow_html=True)
            st.write(f"**Seu lance:** `{feedback.get('user_san')}`")
            st.write(f"**Avaliação antes:** {format_points(feedback.get('eval_before_user'))} pontos")
            st.write(f"**Avaliação após seu lance:** {format_points(feedback.get('user_after_user'))} pontos")

            if verdict == "best":
                st.write(f"**Melhor lance:** `{feedback.get('best_san')}`")
                st.write(f"**Avaliação após o melhor lance:** {format_points(feedback.get('best_after_user'))} pontos")
            else:
                st.caption("Tente novamente para encontrar a melhor continuação. Você pode revelar a solução abaixo, se quiser estudar a posição.")

st.markdown("### Controle de progresso")
col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    if st.button("✅ Marcar como resolvido"):
        mark_exercise_status(progress, exercise_id, "resolvido")
        save_blunder_progress(progress_filename, progress)
        st.session_state["trainer_feedback"] = None
        st.session_state["trainer_index"] = 0
        st.rerun()
with col_b:
    if st.button("🟡 Marcar para revisar"):
        mark_exercise_status(progress, exercise_id, "revisar")
        save_blunder_progress(progress_filename, progress)
        st.session_state["trainer_feedback"] = None
        st.session_state["trainer_index"] = 0
        st.rerun()
with col_c:
    if st.button("⏭️ Ignorar"):
        mark_exercise_status(progress, exercise_id, "ignorado")
        save_blunder_progress(progress_filename, progress)
        st.session_state["trainer_feedback"] = None
        st.session_state["trainer_index"] = 0
        st.rerun()
with col_d:
    if st.button("♻️ Resetar progresso"):
        reset_exercise_progress(progress, exercise_id)
        save_blunder_progress(progress_filename, progress)
        st.session_state["trainer_feedback"] = None
        st.rerun()

show_solution = st.checkbox("Mostrar solução da engine")
if show_solution:
    st.markdown("### Solução")
    st.write(f"**Melhor lance salvo na análise:** `{exercise.get('best_move_san') or 'não informado'}`")
    st.write(f"**Lance jogado na partida:** `{exercise.get('played_move_san')}`")
    st.write(f"**Perda estimada no lance da partida:** {format_points(exercise.get('loss_cp'))} pontos")

attempts = exercise_progress.get("attempts", [])
if attempts:
    with st.expander("Histórico de tentativas deste exercício", expanded=False):
        for idx, attempt in enumerate(reversed(attempts[-10:]), start=1):
            st.write(
                f"{idx}. `{attempt.get('user_san') or attempt.get('move_text')}` — "
                f"{attempt.get('verdict')} — perda para o melhor: {format_points(attempt.get('loss_vs_best'))} pontos"
            )

col_next1, col_next2, col_next3 = st.columns([1, 1, 4])
with col_next1:
    if st.button("Próximo exercício"):
        st.session_state["trainer_index"] = (selected_index + 1) % len(filtered)
        st.session_state["trainer_feedback"] = None
        st.rerun()
with col_next2:
    if st.button("Limpar tentativa"):
        st.session_state["trainer_feedback"] = None
        st.rerun()
with col_next3:
    st.caption(f"Arquivo de progresso: `{progress_filename}`")

st.markdown("---")
st.caption(
    "Os exercícios são gerados quando o dashboard principal analisa partidas com Stockfish. "
    "Esta versão adiciona progresso persistente, filtros por status/dificuldade/tema e histórico de tentativas."
)
