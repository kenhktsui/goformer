import os
import time
import subprocess
import random
from goformer.goformer import GoFormer


class LeelaZeroWrapper:
    def __init__(self,
                 leela_zero_path,
                 weight_path='~/.local/share/leela-zero/best-network',
                 board_size=19,
                 komi=7.5,
                 time_limit=3):
        self.process = subprocess.Popen(
            [leela_zero_path, '--gtp', '--cpu-only', '--noponder', '-w', weight_path, '-r', '1', '-t', '1', '-s', '1'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.move_history = []
        self.board_size = board_size
        self.komi = komi
        self.time_limit = time_limit
        self._board = [['.'] * self.board_size for _ in range(self.board_size)]

    def send_command(self, command, timeout=10):
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        return self.get_response(timeout=timeout)

    def get_response(self, timeout):
        response = []
        start_time = time.time()
        while True:
            line = self.process.stdout.readline().strip()
            if line == '':
                break
            response.append(line)

            if time.time() - start_time > timeout:
                print(f"Command timed out after {timeout} seconds, deem resigning.")
                return "resign"

        return response

    def start_game(self):
        self.send_command(f"boardsize {self.board_size}")
        self.send_command("clear_board")
        self.send_command(f"komi {self.komi}")
        self.send_command(f"time_settings 0 {self.time_limit} 1")
        self.move_history = {}
        self._n = 0

    @property
    def n(self):
        return self._n

    def next_round(self):
        self._n += 1
        self.move_history[self._n] = {}

    def update_internal_board(self, color, move):
        if move.lower() == 'pass':
            return
        col = 'ABCDEFGHJKLMNOPQRST'.index(move[0].upper())
        row = self.board_size - int(move[1:])
        self._board[row][col] = 'B' if color.lower() == 'black' else 'W'

    def play_move(self, color, move):
        response = self.send_command(f"play {color} {move}")
        print(f"play {color} {move}")
        if response[0].startswith('='):
            self.move_history[self._n][color] = move
            self.update_internal_board(color, move)
        return response

    def get_leela_move(self, color):
        response = self.send_command(f"genmove {color}")
        move = response[0].split()[-1]
        if move.lower() == 'pass':
            self.move_history[self._n][color] = None
        elif move.lower() == 'resign':
            return 'resign'
        else:
            self.move_history[self.n][color] = move
            self.update_internal_board(color, move)
        return move

    def is_game_over(self):
        flattened_history = []
        for i in range(1, self.n+1):
            flattened_history.extend([m[1] for m in sorted(list(self.move_history[i].items()))])

        if len(flattened_history) < 2:
            return False
        return flattened_history[-1].lower() is None and flattened_history[-2].lower() is None

    def get_final_score(self):
        return self.send_command("final_score")[0].split()[-1]

    def show_internal_board(self):
        # Column labels (skipping 'I')
        col_labels = [chr(i) for i in range(ord('A'), ord('A') + self.board_size + 1) if chr(i) != 'I']

        # Top border with column labels
        board_str = "   " + " ".join(col_labels) + "\n"

        # Board rows with side labels
        for i, row in enumerate(self._board):
            row_num = self.board_size - i
            board_str += f"{row_num:2d} " + " ".join(row) + f" {row_num}\n"
            # Bottom border with column labels
        board_str += "   " + " ".join(col_labels)
        return board_str

    def close(self):
        self.process.terminate()
        self.process.wait()


def play_game(leela, agent, agent_color):
    leela.start_game()
    current_color = 'black'
    is_resign = False

    while True:
        print("\nCurrent board state:")
        print(f"Agent: {agent_color}")
        print(f"Leela: {oppenent_color}")
        print(leela.show_internal_board())

        if current_color == 'black':
            leela.next_round()
        if current_color == agent_color:
            move = agent.predict_next_move_with_leela(leela.move_history)
            print(f"GoFormer plays: {move}")

            if move.lower() == 'pass':
                leela.move_history[leela.n][current_color] = None
            elif move.lower() == 'resign':
                print(f"Agent resigns. Game over!")
                is_resign = True
                break
            else:
                leela.play_move(current_color, move)
        else:
            move = leela.get_leela_move(current_color)
            if move == 'resign':
                print(f"Leela resigns. Game over!")
                is_resign = True
                break
            print(f"Leela Zero plays: {move}")

        final_score = leela.get_final_score()
        print(f"Final score: {final_score}")

        if leela.is_game_over() or is_resign:
            print("Both players passed. Game over!")
            final_score = leela.get_final_score()
            print(f"Final score: {final_score}")
            break

        current_color = 'white' if current_color == 'black' else 'black'

    leela.close()

# Usage
leela_path = "/usr/local/bin/leelaz"  # Replace with your actual path
leela = LeelaZeroWrapper(leela_path,
                         weight_path=os.path.expanduser('~/.local/share/leela-zero/weights.txt'),
                         )


colors = ['black', 'white']
random.shuffle(colors)
agent_color = colors[0]
oppenent_color = colors[1]
agent = GoFormer("kenhktsui/goformer-v0.1", 'b' if agent_color == 'black' else 'w')

print(f"GoFormer are playing as {agent_color}")

play_game(leela, agent, agent_color)
