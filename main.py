import time
import subprocess as sp
import shlex
from icecream import ic
import logging
import textwrap

logging.basicConfig(level=logging.INFO)


GAME_TYPE = "Base+MLP"
MOVE_TIMEOUT_S = 1
MAX_PLIES = 100


def read_message(process):
    MAX_LINES = 100
    msg = ""
    line = ""
    line_cnt = 0
    while line != "ok":
        line = process.stdout.readline().strip()
        if line.startswith("err"):
            raise ValueError(f"protocol error: {msg}")
        msg += line + "\n"
        line_cnt += 1
        if line_cnt > MAX_LINES:
            raise IOError("Too many lines")
    msg = msg.strip("\nok")
    logging.info("message from %d:\n%s", process.pid, textwrap.indent(msg, "    "))
    return msg


def send_message(msg, process):
    logging.info("message to %d:\n%s", process.pid, textwrap.indent(msg, "    "))
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


def play_game():
    referee = create_referee()
    white = create_player()
    black = create_player()

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

    for ply in range(2*MAX_PLIES):
        is_white = ply % 2 == 0
        logging.info("ply: %d is_white: %d", ply, is_white)
        if is_white:
            current = white
            other = black
        else:
            current = black
            other = white

        # FIXME: enforce the timeout
        send_message(f"bestmove time 00:00:{MOVE_TIMEOUT_S:02}", current)
        move = read_message(current)
        # check that the move is valid by first applying it to the referee
        send_message(f"play {move}", referee)
        ans = read_message(referee)
        if ans.startswith("invalidmove"):
            # FIXME: handle the error by giving the victory to the other player
            break
        else:
            game_string = ans
            logging.info("game string:\n%s", textwrap.indent(game_string, "    "))

        game_state = game_string.split(";")[1]
        if game_state == "Draw":
            logging.info("The game ended with a draw!")
            # TODO: report the result
            break
        elif game_state == "WhiteWins":
            logging.info("The white player wins")
            # TODO: report the result
            break
        elif game_state == "BlackWins":
            logging.info("The black player wins")
            # TODO: report the resul
            break

        # Apply the moves
        for player in [current, other]:
            send_message(f"play {move}", player)
            ans = read_message(player)
            if ans.startswith("invalidmove"):
                # FIXME: handle the error by making the corresponding player lose
                break
            


if __name__ == "__main__":
    play_game()
