import datetime
from enum import Enum
import time
import subprocess as sp
import shlex
from icecream import ic
import logging
import textwrap
from dataclasses import dataclass
import os
import sqlite3

logging.basicConfig(level=logging.INFO)


GAME_TYPE = "Base+MLP"
MOVE_TIMEOUT_S = 5
MAX_PLIES = 100


def read_message(process, timeout=None):
    MAX_LINES = 100
    os.set_blocking(process.stdout.fileno(), False)
    msg = ""
    line = ""
    line_cnt = 0
    start = time.time()
    while line != "ok":
        if timeout is not None and time.time() - start > timeout:
            raise TimeoutError("Timeout exceeded")
        line = process.stdout.readline().strip()
        if line:
            if line.startswith("err"):
                raise ValueError(f"protocol error: {msg}")
            msg += line + "\n"
            line_cnt += 1
            if line_cnt > MAX_LINES:
                raise IOError("Too many lines")
        time.sleep(0.1)
    msg = msg.strip("\nok")
    logging.debug("message from %d:\n%s", process.pid, textwrap.indent(msg, "    "))
    return msg


def send_message(msg, process):
    logging.debug("message to %d:\n%s", process.pid, textwrap.indent(msg, "    "))
    process.stdin.write(msg + "\n")
    process.stdin.flush()


def create_referee(image_name="mzinga"):
    child = sp.Popen(
        shlex.split(f"docker run -i --rm -w /app {image_name}"),
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
    )
    logging.info("start referee, PID %d", child.pid)
    return child


def create_player(image_name="mzinga"):
    child = sp.Popen(
        shlex.split(f"docker run -i --rm -w /app {image_name}"),
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
    )
    logging.info("start player, PID %d", child.pid)
    return child


class Outcome(Enum):
    WHITE_WINS = "WhiteWins"
    BLACK_WINS = "BlackWins"
    DRAW = "Draw"


@dataclass
class GameOucome(object):
    outcome: Outcome
    reason: str
    game_string: str
    elapsed_s: float


def play_game(white_image, black_image):
    referee = create_referee()
    white = create_player(white_image)
    black = create_player(black_image)

    # Get the greetings
    for sub in [referee, white, black]:
        msg = read_message(sub)
        # Check the they export all the extensions
        # FIXME: handle errors gracefully
        assert msg.split("\n")[1].strip() == "Mosquito;Ladybug;Pillbug"

    # Start the game for each engine
    for sub in [referee, white, black]:
        send_message(f"newgame {GAME_TYPE}", sub)
        msg = read_message(sub)

    # The string describing the status of the board
    game_string = ""
    start_time = time.time()

    for ply in range(2 * MAX_PLIES):
        is_white = ply % 2 == 0
        logging.info("ply: %d is_white: %d", ply, is_white)
        if is_white:
            current = white
        else:
            current = black

        send_message(f"bestmove time 00:00:{MOVE_TIMEOUT_S:02}", current)
        # Enforce the timeout, while allowing an additional grace period
        try:
            move = read_message(current, timeout=MOVE_TIMEOUT_S + 1)
        except:
            return GameOucome(
                Outcome.BLACK_WINS if is_white else Outcome.WHITE_WINS,
                reason="timeout while recommending best move",
                game_string=game_string,
                elapsed_s=time.time() - start_time,
            )
        # check that the move is valid by first applying it to the referee
        send_message(f"play {move}", referee)
        ans = read_message(referee)
        if ans.startswith("invalidmove"):
            if is_white:
                return GameOucome(
                    Outcome.BLACK_WINS,
                    reason="white proposed invalid move",
                    game_string=game_string,
                    elapsed_s=time.time() - start_time,
                )
            else:
                return GameOucome(
                    Outcome.WHITE_WINS,
                    reason="black proposed invalid move",
                    game_string=game_string,
                    elapsed_s=time.time() - start_time,
                )
        else:
            game_string = ans
            logging.info("game string:\n%s", textwrap.indent(game_string, "    "))

        game_state = game_string.split(";")[1]
        if game_state in ["Draw", "WhiteWins", "BlackWins"]:
            outcome = Outcome(game_state)
            logging.info("The game ended: %s", outcome)
            return GameOucome(
                outcome,
                reason="normal ending",
                game_string=game_string,
                elapsed_s=time.time() - start_time,
            )

        # Apply the moves
        for i, player in enumerate([white, black]):
            send_message(f"play {move}", player)
            ans = read_message(player)
            if ans.startswith("invalidmove"):
                if i == 0:
                    return GameOucome(
                        Outcome.BLACK_WINS,
                        reason="unrecognized valid move by white",
                        game_string=game_string,
                        elapsed_s=time.time() - start_time,
                    )
                else:
                    return GameOucome(
                        Outcome.WHITE_WINS,
                        reason="unrecognized valid move by black",
                        game_string=game_string,
                        elapsed_s=time.time() - start_time,
                    )

    return GameOucome(
        Outcome.DRAW,
        reason="maxed out plies",
        game_string=game_string,
        elapsed_s=time.time() - start_time,
    )


def get_db():
    db = sqlite3.connect("games.db")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS games (
        date           text,
        white          text,
        black          text,
        outcome        text,
        outcome_reason text,
        game_string    text,
        elapsed_s      real
    );
    """)
    return db


def play_tournament(match_list):
    for white, black in match_list:
        date = datetime.datetime.now().isoformat()
        logging.info("playing game between %s (white) and %s (black)", white, black)
        result = play_game(white, black)
        with get_db() as db:
            db.execute(
                """INSERT INTO games
                   (date, white, black, outcome, outcome_reason, game_string, elapsed)
                   VALUES
                   (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    date,
                    white,
                    black,
                    str(result.outcome),
                    result.reason,
                    result.game_string,
                    result.elapsed_s,
                ],
            )


def load_tournament(path):
    match_list = []
    with open(path) as fp:
        for line in fp.readlines():
            if line.startswith("#") or len(line.strip()) == 0:
                continue
            tokens = tuple(t.strip() for t in line.split(","))
            ic(tokens)
            assert len(tokens) == 2
            match_list.append(tokens)

    return match_list


if __name__ == "__main__":
    match_list = load_tournament("tournament.txt")
    play_tournament(match_list)
    # result = play_game("mzinga", "mzinga-cpp")
    # print(result)
