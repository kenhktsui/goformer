import sys
import logging
import copy
import pygame
from goformer.goformer import GoFormer, alphabets_wo_I


# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 800  # Increased size to accommodate labels
BOARD_SIZE = 19
CELL_SIZE = (WIDTH - 150) // BOARD_SIZE  # Adjusted for labels
MARGIN = 50  # Margin for labels
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BOARD_COLOR = (220, 179, 92)
FONT_COLOR = (50, 50, 50)
BUTTON_COLOR = (100, 100, 100)
BUTTON_HOVER_COLOR = (150, 150, 150)
AI_TURN_TIMEOUT = 10

# Create the screen
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Go Game")

# Fonts
font = pygame.font.Font(None, 36)
label_font = pygame.font.Font(None, 24)
large_font = pygame.font.Font(None, 48)


class GoGame:
    def __init__(self, player_color, komi):
        self.board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self._player_color = player_color
        self._ai_color = "W" if player_color == "B" else "B"
        self._current_player = "B"  # Black always starts
        self.last_move = None
        self.ai_last_move = None
        self.passed = False
        self.game_over = False
        self.black_score = 0
        self.white_score = komi
        self.komi = komi
        self.move_history = {}
        self.move_count = 0
        self.consecutive_passes = 0
        self.previous_board_state = None  # For Ko rule checking
        self.territory = {'B': 0, 'W': 0}
        self.resigned = False
        self.winner = None

    @property
    def player_color(self):
        return self._player_color

    @property
    def ai_color(self):
        return self._ai_color

    @property
    def current_player(self):
        return self._current_player

    def switch_player(self):
        self._current_player = 'W' if self.current_player == 'B' else 'B'

    @property
    def is_player_turn(self):
        return self.current_player == self.player_color

    def start_turn(self):
        """Prepare for the start of a new turn."""
        pass

    def end_turn(self):
        """End the current turn and switch to the next player."""
        self._current_player = 'W' if self._current_player == 'B' else 'B'
        logging.debug(f"Ending turn. Next player: {self.current_player} (Player's turn: {self.is_player_turn})")

    def place_stone(self, x, y):
        if self.board[y][x] is None and not self.is_ko_violation(x, y):
            # Check if the move is legal (has liberties or captures opponent stones)
            if self.is_legal_move(x, y):
                self.board[y][x] = self.current_player
                self.last_move = (x, y)
                if self.current_player == self.ai_color:
                    self.ai_last_move = (x, y)
                self.passed = False
                self.consecutive_passes = 0

                # Check for captures
                enemy_color = 'W' if self.current_player == 'B' else 'B'
                captured_stones = self.check_captures(x, y, enemy_color, dryrun=False)
                self.update_score(len(captured_stones))
                self.record_move(x, y)
                self.previous_board_state = copy.deepcopy(self.board)

                self.end_turn()
                logging.debug(f"Stone placed at ({x}, {y}) by {self.current_player}")
                return True
            else:
                logging.debug(f"Illegal move attempted at ({x}, {y})")
                return False
        return False

    def is_legal_move(self, x, y):
        # Temporarily place the stone
        self.board[y][x] = self.current_player

        # Check if the move captures any opponent stones
        enemy_color = 'W' if self.current_player == 'B' else 'B'
        captures = self.check_captures(x, y, enemy_color, dryrun=True)

        # Check if the placed stone has liberties
        has_liberties = self.has_liberties([(x, y)])

        # Remove the temporary stone
        self.board[y][x] = None

        # The move is legal if it either captures stones or has liberties
        return len(captures) > 0 or has_liberties

    def check_captures(self, x, y, color_to_capture, dryrun=False):
        captured_stones = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if self.board[ny][nx] == color_to_capture:
                    group = self.find_group(nx, ny)
                    if not self.has_liberties(group):
                        captured_stones.extend(group)

        if dryrun:
            return captured_stones

        # Remove captured stones from the board
        for cx, cy in captured_stones:
            self.board[cy][cx] = None

        return captured_stones

    def is_ko_violation(self, x, y):
        if self.previous_board_state is None:
            return False

        # Create a temporary board with the new move
        temp_board = copy.deepcopy(self.board)
        temp_board[y][x] = self.current_player

        # Check captures on the temporary board
        enemy_color = 'W' if self.current_player == 'B' else 'B'
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if temp_board[ny][nx] == enemy_color:
                    group = self.find_group(nx, ny)
                    if not self.has_liberties(group):
                        for cx, cy in group:
                            temp_board[cy][cx] = None

        # Check if this new board state matches the previous board state
        return temp_board == self.previous_board_state

    def would_capture(self, x, y, board):
        captured = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == ('W' if self.current_player == 'B' else 'B'):
                    group = self.find_group(nx, ny, board)
                    if not self.has_liberties(group, board):
                        captured.extend(group)
        return captured

    def find_group(self, x, y):
        color = self.board[y][x]
        group = set()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) not in group:
                group.add((cx, cy))
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and self.board[ny][nx] == color:
                        stack.append((nx, ny))
        return group

    def pass_turn(self):
        if self.passed:
            print("Both players have passed. Ending game.")
            self.game_over = True
        else:
            self.passed = True
            self.consecutive_passes += 1
            self.record_move(None, None)  # Record a pass
            self.end_turn()

    def resign(self):
        self.game_over = True
        self.resigned = True
        self.winner = 'W' if self.current_player == 'B' else 'B'
        logging.info(f"Player {self.current_player} has resigned. {self.winner} wins.")

    def can_make_move(self):
        """Check if the current player can make any legal move."""
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if self.board[y][x] is None and not self.is_ko_violation(x, y):
                    if self.is_legal_move(x, y):
                        return True
        return False

    def remove_captured_stones(self, x, y):
        captured = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if self.board[ny][nx] == ('W' if self.current_player == 'B' else 'B'):
                    group = self.find_group(nx, ny, self.board)
                    if not self.has_liberties(group, self.board):
                        captured.extend(group)
                        for cx, cy in group:
                            self.board[cy][cx] = None
        return len(captured)

    def has_liberties(self, group):
        for x, y in group:
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    if self.board[ny][nx] is None:
                        return True
        return False

    def update_score(self, captured_stones):
        if self.current_player == 'B':
            self.black_score += captured_stones
        else:
            self.white_score += captured_stones

    def get_score(self):
        return self.black_score, self.white_score

    def record_move(self, x, y):
        if self.current_player == "B":
            self.move_count += 1
        if x is None and y is None:
            move = "PASS"
        else:
            col = chr(x + 65)  # Convert to letter (A-T, skipping I)
            if col >= "I":
                col = chr(ord(col) + 1)
            row = str(BOARD_SIZE - y)
            move = col + row

        if self.current_player == "B":
            self.move_history[self.move_count] = {"black": move}
        else:
            self.move_history[self.move_count]["white"] = move

    def get_move_history(self):
        if not self.move_history:
            return {1: {"black": None, "white": None}}
        return self.move_history

    def calculate_score(self):
        if self.resigned:
            # In case of resignation, the winner gets all points on the board plus komi
            if self.winner == 'B':
                self.black_score = BOARD_SIZE * BOARD_SIZE
                self.white_score = self.komi
            else:
                self.black_score = 0
                self.white_score = BOARD_SIZE * BOARD_SIZE + self.komi
        else:
            self.territory = {'B': 0, 'W': 0}
            visited = set()
            seki_points = set()

            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if (x, y) not in visited and self.board[y][x] is None:
                        territory, borders, is_seki = self.find_territory(x, y)
                        visited.update(territory)
                        if is_seki:
                            seki_points.update(territory)
                        elif len(set(borders)) == 1:  # Territory is surrounded by one color
                            self.territory[borders[0]] += len(territory)

            # Count stones on the board
            black_stones = sum(row.count('B') for row in self.board)
            white_stones = sum(row.count('W') for row in self.board)

            # Calculate final scores
            self.black_score = self.territory['B'] + black_stones
            self.white_score = self.territory['W'] + white_stones + self.komi

            logging.info(f"Final Score - Black: {self.black_score}, White: {self.white_score}")
            if not self.resigned:
                logging.info(f"Territory - Black: {self.territory['B']}, White: {self.territory['W']}")
                logging.info(f"Stones - Black: {black_stones}, White: {white_stones}")
                logging.info(f"Seki points: {len(seki_points)}")

    def find_territory(self, x, y):
        color = self.board[y][x]
        territory = set()
        borders = []
        stack = [(x, y)]
        adjacent_colors = set()

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in territory:
                continue
            territory.add((cx, cy))

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    if self.board[ny][nx] is None and (nx, ny) not in territory:
                        stack.append((nx, ny))
                    elif self.board[ny][nx] is not None:
                        borders.append(self.board[ny][nx])
                        adjacent_colors.add(self.board[ny][nx])

        is_seki = self.check_seki(territory, adjacent_colors)
        return territory, borders, is_seki

    def check_seki(self, territory, adjacent_colors):
        if len(adjacent_colors) != 2:
            return False

        # Check if both colors have few liberties
        for color in adjacent_colors:
            if self.count_liberties(territory, color) > 1:
                return False

        return True

    def count_liberties(self, territory, color):
        liberties = set()
        for x, y in territory:
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                    if self.board[ny][nx] is None and (nx, ny) not in territory:
                        liberties.add((nx, ny))
        return len(liberties)

    def end_game(self):
        self.game_over = True
        self.calculate_score()
        if not self.resigned:
            self.winner = "B" if self.black_score > self.white_score else "W"
        logging.info(f"Game Over! {self.winner} wins!")
        logging.info(f"Final Score - Black: {self.black_score}, White: {self.white_score}")


def draw_board():
    screen.fill(BOARD_COLOR)
    for i in range(BOARD_SIZE):
        pygame.draw.line(
            screen,
            BLACK,
            (MARGIN + CELL_SIZE // 2, MARGIN + i * CELL_SIZE + CELL_SIZE // 2),
            (WIDTH - MARGIN - CELL_SIZE * 2, MARGIN + i * CELL_SIZE + CELL_SIZE // 2),
        )
        pygame.draw.line(
            screen,
            BLACK,
            (MARGIN + i * CELL_SIZE + CELL_SIZE // 2, MARGIN + CELL_SIZE // 2),
            (
                MARGIN + i * CELL_SIZE + CELL_SIZE // 2,
                HEIGHT - MARGIN - CELL_SIZE // 2 - 50,
            ),
        )

    # Draw labels
    letters = "ABCDEFGHJKLMNOPQRST"
    for i, letter in enumerate(letters):
        text = label_font.render(letter, True, BLACK)
        screen.blit(
            text,
            (
                MARGIN + i * CELL_SIZE - text.get_width() // 2 + CELL_SIZE // 2,
                MARGIN // 2,
            ),
        )

    for i in range(1, BOARD_SIZE + 1):
        text = label_font.render(str(i), True, BLACK)
        ytick_position = (
            HEIGHT
            - MARGIN
            - (i * CELL_SIZE)
            + CELL_SIZE // 2
            - text.get_height() // 2
            - 50
        )
        screen.blit(text, (MARGIN // 2 - text.get_width() // 2, ytick_position))
        screen.blit(text, (WIDTH - MARGIN // 2 - text.get_width() // 2, ytick_position))


def draw_stones(game):
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if game.board[y][x]:
                color = BLACK if game.board[y][x] == "B" else WHITE
                pygame.draw.circle(
                    screen,
                    color,
                    (
                        MARGIN + x * CELL_SIZE + CELL_SIZE // 2,
                        MARGIN + y * CELL_SIZE + CELL_SIZE // 2,
                    ),
                    CELL_SIZE // 2 - 2,
                )

                # Highlight the AI's last move
                if (x, y) == game.ai_last_move:
                    highlight_color = (
                        (255, 0, 0) if game.ai_color == "B" else (0, 255, 0)
                    )
                    pygame.draw.circle(
                        screen,
                        highlight_color,
                        (
                            MARGIN + x * CELL_SIZE + CELL_SIZE // 2,
                            MARGIN + y * CELL_SIZE + CELL_SIZE // 2,
                        ),
                        CELL_SIZE // 4,
                        2,
                    )


def draw_score(black_score, white_score, komi):
    score_text = f"Black: {black_score:.1f}  White: {white_score:.1f}  (Komi: {komi})"
    text_surface = font.render(score_text, True, FONT_COLOR)
    screen.blit(text_surface, (10, HEIGHT - 40))


def draw_turn_indicator(game):
    turn_text = "Your Turn" if game.is_player_turn else "AI's Turn"
    color_text = "Black" if game.player_color == 'B' else "White"
    indicator_text = f"You are {color_text} | {turn_text}"
    text_surface = font.render(indicator_text, True, FONT_COLOR)
    screen.blit(text_surface, (WIDTH - text_surface.get_width() - 10, HEIGHT - 40))


def draw_button(text, x, y, w, h, inactive_color, active_color):
    mouse = pygame.mouse.get_pos()
    click = pygame.mouse.get_pressed()

    if x + w > mouse[0] > x and y + h > mouse[1] > y:
        pygame.draw.rect(screen, active_color, (x, y, w, h))
        if click[0] == 1:
            return True
    else:
        pygame.draw.rect(screen, inactive_color, (x, y, w, h))

    text_surf = font.render(text, True, BLACK)
    text_rect = text_surf.get_rect()
    text_rect.center = ((x + (w / 2)), (y + (h / 2)))
    screen.blit(text_surf, text_rect)
    return False


def color_selection_screen():
    selected_color = None

    while selected_color is None:
        screen.fill(BOARD_COLOR)
        title = large_font.render("Welcome to Goformer, a Transformer Decoder", True, BLACK)
        subtitle = large_font.render("Start by Choosing Your Color", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))
        screen.blit(subtitle, (WIDTH // 2 - title.get_width() // 2, 100))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if draw_button(
            "Black",
            WIDTH // 4 - 75,
            HEIGHT // 2 - 25,
            150,
            50,
            BUTTON_COLOR,
            BUTTON_HOVER_COLOR
        ):
            selected_color = "B"
        if draw_button(
            "White",
            3 * WIDTH // 4 - 75,
            HEIGHT // 2 - 25,
            150,
            50,
            BUTTON_COLOR,
            BUTTON_HOVER_COLOR
        ):
            selected_color = "W"

        pygame.display.flip()

    return selected_color


def komi_selection_screen():
    komi = 7.5  # Default komi value
    input_active = False
    input_text = str(komi)

    while True:
        screen.fill(BOARD_COLOR)
        title = large_font.render("Set Komi (Default: 7.5)", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))

        input_box = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 25, 200, 50)
        color = BUTTON_HOVER_COLOR if input_active else BUTTON_COLOR
        pygame.draw.rect(screen, color, input_box)

        text_surface = font.render(input_text, True, BLACK)
        screen.blit(text_surface, (input_box.x + 5, input_box.y + 5))

        confirm_text = font.render("Press ENTER to confirm", True, BLACK)
        screen.blit(
            confirm_text, (WIDTH // 2 - confirm_text.get_width() // 2, HEIGHT // 2 + 50)
        )

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    try:
                        komi = float(input_text)
                        return komi
                    except ValueError:
                        input_text = str(7.5)  # Reset to default if invalid input
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    input_text += event.unicode


def show_end_game_screen(game):
    restart = False
    exit_game = False

    while not restart:
        screen.fill(BOARD_COLOR)

        if game.resigned:
            winner_text = large_font.render(f"{'Black' if game.winner == 'B' else 'White'} wins by resignation!", True,
                                            BLACK)
        else:
            winner_text = large_font.render(f"{'Black' if game.winner == 'B' else 'White'} wins!", True, BLACK)
        screen.blit(winner_text, (WIDTH // 2 - winner_text.get_width() // 2, HEIGHT // 2 - 200))

        score_text = font.render(f"Final Score - Black: {game.black_score:.1f}, White: {game.white_score:.1f}", True,
                                 BLACK)
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, HEIGHT // 2 - 100))

        if not game.resigned:
            territory_text = font.render(f"Territory - Black: {game.territory['B']}, White: {game.territory['W']}",
                                         True, BLACK)
            screen.blit(territory_text, (WIDTH // 2 - territory_text.get_width() // 2, HEIGHT // 2 - 50))

            stones_black = sum(row.count('B') for row in game.board)
            stones_white = sum(row.count('W') for row in game.board)
            stones_text = font.render(f"Stones - Black: {stones_black}, White: {stones_white}", True, BLACK)
            screen.blit(stones_text, (WIDTH // 2 - stones_text.get_width() // 2, HEIGHT // 2))

        komi_text = font.render(f"Komi: {game.komi}", True, BLACK)
        screen.blit(komi_text, (WIDTH // 2 - komi_text.get_width() // 2, HEIGHT // 2 + 50))

        if draw_button("New Game", WIDTH // 2 - 160, HEIGHT // 2 + 150, 150, 50, BUTTON_COLOR, BUTTON_HOVER_COLOR):
            restart = True
        if draw_button("Exit", WIDTH // 2 + 10, HEIGHT // 2 + 150, 150, 50, BUTTON_COLOR, BUTTON_HOVER_COLOR):
            exit_game = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        pygame.display.flip()
        pygame.time.wait(100)  # Small delay to prevent excessive CPU usage

    return restart, exit_game


def update_display(game):
    draw_board()
    draw_stones(game)
    draw_score(game.black_score, game.white_score, game.komi)
    draw_turn_indicator(game)
    if game.ai_last_move:
        draw_last_move_indicator(game.ai_last_move)
    pygame.display.flip()


def draw_last_move_indicator(last_move):
    if last_move == 'PASS':
        move_text = "AI passed"
    else:
        x, y = last_move
        move_text = f"AI's last move: {alphabets_wo_I[x]}{BOARD_SIZE - y}"
    text_surface = font.render(move_text, True, FONT_COLOR)
    screen.blit(text_surface, (10, HEIGHT - 80))


def handle_ai_turn(game, ai_bot):
    logging.debug("Starting AI turn")
    ai_move = ai_bot.make_move(game)
    logging.debug(f"AI attempting to place stone at {ai_move}")
    if ai_move == "PASS":
        game.pass_turn()
        game.ai_last_move = "PASS"
        return
    elif ai_move == "resign":
        game.resign()
        game.ai_last_move = "resign"
        return
    else:
        if game.place_stone(*ai_move):
            logging.debug("AI successfully placed stone")
            game.ai_last_move = ai_move  # Update AI's last move
        else:
            logging.error("AI failed to place stone in a legal position, deemed as passing turn")
            game.pass_turn()
            game.ai_last_move = "PASS"
        return


def handle_player_turn(game):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos
            board_x = (x - MARGIN) // CELL_SIZE
            board_y = (y - MARGIN) // CELL_SIZE
            if 0 <= board_x < BOARD_SIZE and 0 <= board_y < BOARD_SIZE:
                if game.place_stone(board_x, board_y):
                    return  # End turn after successful move
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                game.pass_turn()
                return  # End turn after pass
            elif event.key == pygame.K_r:
                game.resign()
                return


def print_game_state(game):
    print(f"History: {game.get_move_history()}")
    print(f"Current Player: {game.current_player}")
    print(f"Player Turn: {game.is_player_turn}")


def main():
    while True:
        player_color = color_selection_screen()
        komi = komi_selection_screen()
        logging.info("Player Color:", player_color)

        game_in_progress = True
        while game_in_progress:
            game = GoGame(player_color, komi)
            if player_color == "B":
                agent_color = "w"
            elif player_color == "W":
                agent_color = "b"
            ai_bot = GoFormer("kenhktsui/goformer-v0.1", agent_color)

            clock = pygame.time.Clock()

            while not game.game_over:
                game.start_turn()
                update_display(game)

                if game.is_player_turn:
                    handle_player_turn(game)
                else:
                    handle_ai_turn(game, ai_bot)

                if game.consecutive_passes == 2 or not game.can_make_move():
                    game.end_game()

                clock.tick(60)

            game.end_game()
            print_game_state(game)
            restart, exit_game = show_end_game_screen(game)
            if exit_game:
                pygame.quit()
                sys.exit()
            if restart:
                game_in_progress = False


if __name__ == "__main__":
    main()
