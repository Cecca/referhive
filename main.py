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
import argparse

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


def start_container(name, image_name="mzinga", gpu_id=None):
    gpu_string = f"--gpus {gpu_id}" if gpu_id is not None else ""
    child = sp.Popen(
        shlex.split(
            f"docker run --name {name} -i --rm {gpu_string} -w /app {image_name}"
        ),
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
    )
    logging.info("start %s, PID %d", name, child.pid)
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


def do_play_game(referee, white, black):
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


def play_game(white_image, black_image, white_gpu=None, black_gpu=None):
    referee = start_container("referee")
    white = start_container("white", white_image, gpu_id=white_gpu)
    black = start_container("black", black_image, gpu_id=black_gpu)

    # Get the greetings
    for sub in [referee, white, black]:
        msg = read_message(sub)
        # Check the they export all the extensions
        # FIXME: handle errors gracefully
        assert msg.split("\n")[1].strip() == "Mosquito;Ladybug;Pillbug"

    outcome = do_play_game(referee, white, black)

    referee.kill()
    white.kill()
    black.kill()

    return outcome


def get_db():
    db = sqlite3.connect("games.db")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS games (
        timestamp      text,
        white          text,
        black          text,
        outcome        text,
        outcome_reason text,
        game_string    text,
        elapsed_s      real
    );
    """)
    return db


def play_tournament(match_list, white_gpu, black_gpu):
    for white, black in match_list:
        date = datetime.datetime.now().isoformat()
        logging.info(
            "playing game between %s (white) (gpu %s) and %s (black) (gpu %s)",
            white,
            white_gpu,
            black,
            black_gpu,
        )
        result = play_game(white, black, white_gpu=white_gpu, black_gpu=black_gpu)
        with get_db() as db:
            db.execute(
                """INSERT INTO games
                   (timestamp, white, black, outcome, outcome_reason, game_string, elapsed_s)
                   VALUES
                   (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    date,
                    white,
                    black,
                    result.outcome.value,
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
            assert len(tokens) == 2
            match_list.append(tokens)

    return match_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser("referhive")
    parser.add_argument("--games", default="tournament.txt")
    parser.add_argument("--white-gpu")
    parser.add_argument("--black-gpu")

    args = parser.parse_args()

    match_list = load_tournament(args.games)
    play_tournament(match_list, args.white_gpu, args.black_gpu)
