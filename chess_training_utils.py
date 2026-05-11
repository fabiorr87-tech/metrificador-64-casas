import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import chess
import chess.engine
import pandas as pd


DEFAULT_ENGINE_PATH = os.environ.get(
    "STOCKFISH_PATH",
    "stockfish" if os.name != "nt" else os.path.join("engines", "stockfish.exe")
)


# =========================
# ARQUIVOS E IDENTIFICAÇÃO
# =========================

def load_json_file(filename: str, default: Any) -> Any:
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default
    return data if data is not None else default


def save_json_file(filename: str, data: Any) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_filename_username(username: str) -> str:
    return (username or "").strip().lower().replace(" ", "_")


def progress_filename_for_user(username: str) -> str:
    return f"blunder_progress_{safe_filename_username(username)}.json"


def analysis_filename_for_user(username: str) -> str:
    return f"engine_analysis_{safe_filename_username(username)}.json"


def generate_exercise_id(exercise: Dict[str, Any]) -> str:
    raw = "|".join([
        str(exercise.get("game_url", "")),
        str(exercise.get("fen_before", "")),
        str(exercise.get("played_move_uci", "")),
        str(exercise.get("fullmove_number", "")),
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# =========================
# FORMATAÇÃO E CLASSIFICAÇÃO
# =========================

def format_points(cp_value: Any) -> str:
    if cp_value is None or pd.isna(cp_value):
        return "sem dados"
    points = float(cp_value) / 100
    sign = "+" if points > 0 else ""
    return f"{sign}{points:.2f}".replace(".", ",")


def classify_exercise_difficulty(exercise: Dict[str, Any]) -> str:
    loss_cp = exercise.get("loss_cp")
    before_cp = exercise.get("eval_before_cp")
    after_cp = exercise.get("eval_after_cp")

    try:
        loss = abs(float(loss_cp))
    except Exception:
        loss = 0

    try:
        before = float(before_cp)
        after = float(after_cp)
    except Exception:
        before = 0
        after = 0

    if loss >= 500 or (before >= 100 and after <= -300):
        return "Fácil"
    if loss >= 300 or after <= -250:
        return "Médio"
    return "Difícil"


def classify_exercise_theme(exercise: Dict[str, Any]) -> str:
    reason = str(exercise.get("reason", "")).lower()
    phase = str(exercise.get("phase", "")).lower()
    before = exercise.get("eval_before_cp")
    after = exercise.get("eval_after_cp")

    try:
        before_cp = float(before)
        after_cp = float(after)
    except Exception:
        before_cp = 0
        after_cp = 0

    if "vantagem" in reason or (before_cp >= 100 and after_cp <= 30):
        return "Conversão de vantagem"
    if "perdida" in reason or after_cp <= -250:
        return "Defesa e sobrevivência"
    if phase == "opening":
        return "Abertura"
    return "Tática / cálculo"


def ensure_exercise_metadata(exercise: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(exercise)
    item.setdefault("exercise_id", generate_exercise_id(item))
    item.setdefault("difficulty", classify_exercise_difficulty(item))
    item.setdefault("theme", classify_exercise_theme(item))
    return item


def exercise_label(item: Dict[str, Any], index: int) -> str:
    phase = item.get("phase_label") or item.get("phase") or "fase"
    reason = item.get("reason", "blunder")
    opening = item.get("opening_family") or "Abertura não identificada"
    difficulty = item.get("difficulty") or classify_exercise_difficulty(item)
    loss = item.get("loss_cp")
    loss_text = f" — perda {format_points(loss)}" if loss is not None else ""
    return f"{index + 1}. {phase} — {reason} — {difficulty} — {opening}{loss_text}"


# =========================
# ANÁLISE SALVA E EXERCÍCIOS
# =========================

def load_engine_analysis(filename: str) -> Dict[str, Any]:
    data = load_json_file(filename, {"games": {}})
    if not isinstance(data, dict):
        return {"games": {}}
    data.setdefault("games", {})
    return data


def collect_training_positions(analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    exercises: List[Dict[str, Any]] = []
    games_cache = analysis_data.get("games", {}) if isinstance(analysis_data, dict) else {}

    for game_url, game_analysis in games_cache.items():
        if not isinstance(game_analysis, dict):
            continue

        positions = game_analysis.get("training_positions", [])
        if not isinstance(positions, list):
            continue

        for item in positions:
            if not isinstance(item, dict):
                continue
            if not item.get("fen_before"):
                continue
            item = dict(item)
            item.setdefault("game_url", game_url)
            exercises.append(ensure_exercise_metadata(item))

    return exercises


# =========================
# PROGRESSO DO TREINO
# =========================

def empty_progress(username: str = "") -> Dict[str, Any]:
    return {
        "username": username,
        "version": "blunder_progress_v1",
        "exercises": {}
    }


def load_blunder_progress(filename: str, username: str = "") -> Dict[str, Any]:
    data = load_json_file(filename, empty_progress(username))
    if not isinstance(data, dict):
        data = empty_progress(username)
    data.setdefault("username", username)
    data.setdefault("version", "blunder_progress_v1")
    data.setdefault("exercises", {})
    return data


def save_blunder_progress(filename: str, progress: Dict[str, Any]) -> None:
    save_json_file(filename, progress)


def get_exercise_progress(progress: Dict[str, Any], exercise_id: str) -> Dict[str, Any]:
    exercises = progress.setdefault("exercises", {})
    item = exercises.setdefault(exercise_id, {
        "status": "novo",
        "attempts": [],
        "attempt_count": 0,
        "wrong_count": 0,
        "best_count": 0,
        "last_attempt": None,
        "last_verdict": None,
        "last_seen_at": None,
        "solved_at": None,
    })
    return item


def status_label(status: str) -> str:
    return {
        "novo": "Novo",
        "resolvido": "Resolvido",
        "revisar": "Para revisar",
        "errado": "Errado",
        "ignorado": "Ignorado",
    }.get(status, status or "Novo")


def record_attempt(progress: Dict[str, Any], exercise_id: str, move_text: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
    item = get_exercise_progress(progress, exercise_id)

    if feedback.get("status") != "ok":
        return item

    verdict = feedback.get("verdict")
    now = datetime.now().isoformat(timespec="seconds")
    attempt = {
        "move_text": move_text,
        "user_san": feedback.get("user_san"),
        "verdict": verdict,
        "message": feedback.get("message"),
        "loss_vs_best": feedback.get("loss_vs_best"),
        "created_at": now,
    }

    attempts = item.setdefault("attempts", [])
    attempts.append(attempt)
    item["attempt_count"] = len(attempts)
    item["last_attempt"] = feedback.get("user_san") or move_text
    item["last_verdict"] = verdict
    item["last_seen_at"] = now

    if verdict == "best":
        item["status"] = "resolvido"
        item["solved_at"] = now
        item["best_count"] = int(item.get("best_count", 0)) + 1
    elif verdict in {"good", "playable"}:
        if item.get("status") != "resolvido":
            item["status"] = "revisar"
    elif verdict == "retry":
        if item.get("status") != "resolvido":
            item["status"] = "errado"
        item["wrong_count"] = int(item.get("wrong_count", 0)) + 1

    return item


def mark_exercise_status(progress: Dict[str, Any], exercise_id: str, status: str) -> None:
    item = get_exercise_progress(progress, exercise_id)
    item["status"] = status
    item["last_seen_at"] = datetime.now().isoformat(timespec="seconds")
    if status == "resolvido":
        item["solved_at"] = item["last_seen_at"]


def reset_exercise_progress(progress: Dict[str, Any], exercise_id: str) -> None:
    progress.setdefault("exercises", {}).pop(exercise_id, None)


def progress_stats(exercises: List[Dict[str, Any]], progress: Dict[str, Any]) -> Dict[str, int]:
    ids = [ex.get("exercise_id") for ex in exercises]
    records = progress.get("exercises", {}) if isinstance(progress, dict) else {}
    counts = {
        "total": len(ids),
        "novo": 0,
        "resolvido": 0,
        "revisar": 0,
        "errado": 0,
        "ignorado": 0,
    }
    for exercise_id in ids:
        status = records.get(exercise_id, {}).get("status", "novo")
        if status not in counts:
            status = "novo"
        counts[status] += 1
    return counts


# =========================
# ENGINE E AVALIAÇÃO DE TENTATIVAS
# =========================

def san_to_pt(san):
    """
    Converte a notação SAN gerada pelo python-chess, em inglês,
    para a notação usual em português.

    Exemplos:
    Nc3   -> Cc3
    Qh5   -> Dh5
    Rfc1  -> Tfc1
    Kf1   -> Rf1
    Bxe6  -> Bxe6
    O-O   -> O-O
    O-O-O -> O-O-O
    """
    if not isinstance(san, str):
        return san

    if san.startswith("O-O"):
        return san

    piece_map = {
        "N": "C",  # Knight / Cavalo
        "Q": "D",  # Queen / Dama
        "R": "T",  # Rook / Torre
        "K": "R",  # King / Rei
        "B": "B",  # Bishop / Bispo
    }

    if san and san[0] in piece_map:
        return piece_map[san[0]] + san[1:]

    return san

def get_legal_move_options_pt(board):
    """
    Monta uma lista de lances legais para exibição no selectbox.

    O usuário verá o lance em português, mas o código guardará o lance
    em UCI, que é uma notação sem ambiguidade para o python-chess.

    Exemplo de retorno:
    [
        {"label": "Cc3", "uci": "b1c3", "san": "Nc3"},
        {"label": "Dh5", "uci": "d1h5", "san": "Qh5"}
    ]
    """
    options = []

    for move in board.legal_moves:
        san_en = board.san(move)
        san_pt = san_to_pt(san_en)

        options.append({
            "label": san_pt,
            "uci": move.uci(),
            "san": san_en
        })

    options = sorted(options, key=lambda item: item["label"])

    return options

def parse_user_move(board: chess.Board, move_text: str) -> chess.Move:
    text = (move_text or "").strip()
    if not text:
        raise ValueError("Digite um lance.")

    # Permite notação portuguesa simples: Cf3, Dd1, Txe1, Rg1 etc.
    if text[0] in {"C", "D", "T", "R"}:
        piece_map = {"C": "N", "D": "Q", "T": "R", "R": "K"}
        text_san = piece_map[text[0]] + text[1:]
    else:
        text_san = text

    try:
        return board.parse_san(text_san)
    except Exception:
        pass

    try:
        move = chess.Move.from_uci(text.lower())
        if move in board.legal_moves:
            return move
    except Exception:
        pass

    raise ValueError(
    "Lance inválido para esta posição. Use notação portuguesa, como Cc3, Da3, Tfc1 ou O-O. "
    "Também é aceito UCI interno, como b1c3."
)


def legal_moves_san(board: chess.Board) -> List[str]:
    moves = []
    for move in board.legal_moves:
        try:
            moves.append(board.san(move))
        except Exception:
            pass
    return sorted(moves)


def engine_position_info(engine: chess.engine.SimpleEngine, board: chess.Board, limit: chess.engine.Limit):
    info = engine.analyse(board, limit)
    score_cp = info["score"].pov(chess.WHITE).score(mate_score=100000)
    best_move = None
    pv = info.get("pv")
    if pv and len(pv) > 0:
        best_move = pv[0]
    return score_cp, best_move


def evaluate_attempt(
    exercise: Dict[str, Any],
    move_text: str,
    engine_path: str,
    engine_time: Optional[float] = 0.10,
    engine_depth: int = 10,
) -> Dict[str, Any]:
    if not os.path.exists(engine_path):
        return {
            "status": "error",
            "message": "Stockfish não encontrado. Confira o caminho informado na barra lateral."
        }

    board = chess.Board(exercise["fen_before"])
    user_color = chess.WHITE if exercise.get("user_color") == "white" else chess.BLACK

    try:
        user_move = parse_user_move(board, move_text)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        return {"status": "error", "message": f"Não foi possível iniciar o Stockfish: {e}"}

    try:
        if engine_time is not None:
            limit = chess.engine.Limit(time=float(engine_time))
        else:
            limit = chess.engine.Limit(depth=int(engine_depth))

        eval_before_white, best_move = engine_position_info(engine, board, limit)
        if best_move is None:
            return {"status": "error", "message": "A engine não retornou melhor lance para esta posição."}

        best_san = board.san(best_move)
        user_san = board.san(user_move)

        best_board = board.copy()
        best_board.push(best_move)
        best_after_white, _ = engine_position_info(engine, best_board, limit)

        user_board = board.copy()
        user_board.push(user_move)
        user_after_white, _ = engine_position_info(engine, user_board, limit)

        best_after_user = best_after_white if user_color == chess.WHITE else -best_after_white
        user_after_user = user_after_white if user_color == chess.WHITE else -user_after_white
        eval_before_user = eval_before_white if user_color == chess.WHITE else -eval_before_white

        loss_vs_best = max(0, best_after_user - user_after_user)

        if user_move == best_move:
            verdict = "best"
            message = "Excelente! Você encontrou o melhor lance da engine."
        elif loss_vs_best <= 50:
            verdict = "good"
            message = "Bom lance: ele fica muito perto do melhor lance. Ainda assim, há uma continuação mais precisa para encontrar."
        elif loss_vs_best <= 120:
            verdict = "playable"
            message = "Lance jogável, mas ainda não é a melhor solução. Tente procurar uma opção mais forte."
        else:
            verdict = "retry"
            message = "Esse lance ainda não resolve o problema da posição. Tente novamente."

        return {
            "status": "ok",
            "verdict": verdict,
            "message": message,
            "user_san": user_san,
            "best_san": best_san,
            "eval_before_user": eval_before_user,
            "user_after_user": user_after_user,
            "best_after_user": best_after_user,
            "loss_vs_best": loss_vs_best,
        }

    finally:
        try:
            engine.quit()
        except Exception:
            pass
