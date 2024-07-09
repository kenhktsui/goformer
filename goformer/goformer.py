from typing import Dict, Optional, List, Union, Tuple
from itertools import product
from dataclasses import dataclass
import logging
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer


# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


alphabets = 'ABCDEFGHIJKLMNOPQRS'  # I is not skipped
alphabets_wo_I = 'ABCDEFGHJKLMNOPQRST'  # I is skipped
LEELA_DECODE_MAP_X: Dict[str, str] = {k: v for k, v in zip(alphabets, alphabets_wo_I)}
LEELA_DECODE_MAP_Y: Dict[str, str] = {chr(i).lower(): str(i-65+1) for i in range(65, 65 + 19)}
LEELA_ENCODE_MAP_X: Dict[int, str] = {v: k for k, v in LEELA_DECODE_MAP_X.items()}
LEELA_ENCODE_MAP_Y: Dict[int, str] = {v: k for k, v in LEELA_DECODE_MAP_Y.items()}


@dataclass
class Round:
    n: int
    black_move: str
    white_move: Optional[str] = None

    def to_string(self, version: str, color: str) -> str:
        """

        version 2:
        1. When round is completed
        1a. when player is black
            1. >D16 S1
        1a. when player is white
            1. D16 >S1
        2. When round is not completed
        2a. when player is black
            2. >
        2b. when player is white
            2. C16 >
        """
        # When round is completed
        version_formatting = ">" if version == "2" else ""
        try:
            if self.black_move is not None and self.white_move is not None:
                if color == "b":
                    return f"{self.n}. {version_formatting}{self.encode_a_move(self.black_move)} {self.encode_a_move(self.white_move)}"
                else:
                    return f"{self.n}. {self.encode_a_move(self.black_move)} {version_formatting}{self.encode_a_move(self.white_move)}"
            else:
                if color == "b":
                    return f"{self.n}. {version_formatting}"
                else:
                    return f"{self.n}. {self.encode_a_move(self.black_move)} {version_formatting}"
        except ValueError as e:
            raise ValueError(f"Invalid round: {self.n} {self.black_move} {self.white_move} Exception: {e}")

    @staticmethod
    def encode_a_move(move: str) -> str:
        if move == "PASS":
            return "X"
        assert len(move) <= 3, f"Invalid move: {move}"
        return f"{LEELA_ENCODE_MAP_X[move[0]]}{LEELA_ENCODE_MAP_Y[move[1:]]}"


class GoFormer:
    def __init__(self, artifact_dir: str, color: str, version: str = '2'):
        self._tokenizer = AutoTokenizer.from_pretrained(artifact_dir, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(artifact_dir)
        self._version = version
        self._color = color
        assert isinstance(self._version, str), f"Invalid version: {self._version}"

        self._all_possible_move = [f"{i}{j.lower()}" for i, j in list(product(alphabets, alphabets.lower()))]

    def _create_model_input_string(self, memory_of_moves: List[Round]):
        memory_of_moves_string = " ".join([m.to_string(self._version, self._color) for m in memory_of_moves])
        logging.debug(f"Goformer input: {memory_of_moves_string}")
        return memory_of_moves_string

    def make_move(self, game, n_suggestion: Optional[int] = 19) -> Union[str, Tuple[int, int]]:
        """Output format compatible with game.py"""
        move = self.predict_next_move_with_leela(game.get_move_history(), n_suggestion)
        if move in ['resign', 'PASS']:
            logging.debug(f"GoFormer plays: {move}")
            return move
        else:
            move = alphabets_wo_I.index(move[0]), 19 - int(move[1:])
            logging.debug(f"GoFormer plays: {move}")
            return move

    def predict_next_move_with_leela(self, leela_move_history: Dict[str, dict], n_suggestion: Optional[int] = 19) -> str:
        """Output format compatible with GTP protocol, mainly used for simulation"""
        memory_of_moves = []

        for i in range(1, max(leela_move_history)+1):
            memory_of_moves.append(Round(n=i, black_move=leela_move_history[i].get("black"), white_move=leela_move_history[i].get("white")))
        return self.predict_next_move(memory_of_moves, n_suggestion=n_suggestion)

    def predict_next_move(self, memory_of_moves: List[Round], n_suggestion: Optional[int] = 10) -> str:
        """Output format compatible with GTP protocol"""

        memory_of_moves_string = self._create_model_input_string(memory_of_moves)

        previous_moves = [m.black_move for m in memory_of_moves if m.black_move is not None] + [
                m.white_move for m in memory_of_moves if m.white_move is not None]
        previous_moves = set([Round.encode_a_move(m) for m in previous_moves])
        legal_move_set = set(self._all_possible_move) - previous_moves

        model_inputs = self._tokenizer(memory_of_moves_string, add_special_tokens=False, return_tensors="pt")
        if 'token_type_ids' in model_inputs:
            model_inputs.pop('token_type_ids')

        outputs = self._model.generate(**model_inputs,
                                       num_beams=n_suggestion,
                                       max_new_tokens=3,
                                       num_return_sequences=n_suggestion,
                                       return_dict_in_generate=True,
                                       output_scores=True)
        transition_scores = self._model.compute_transition_scores(
            outputs.sequences, outputs.scores, normalize_logits=True
        )

        input_length = model_inputs["input_ids"].shape[1]
        generated_tokens = outputs.sequences[:, input_length:]

        transition_scores = transition_scores.sum(1).flatten()

        zip_output = sorted(zip(generated_tokens, transition_scores), key=lambda x: x[1])[::-1]
        suggested_moves = [(self._tokenizer.decode(o, skip_special_tokens=True).strip(), p.item())
                           for o, p in zip_output]
        gen_move = None
        gen_move_p = None
        for s, p in suggested_moves:
            if s in legal_move_set:
                gen_move = s
                gen_move_p = p
                break
        if gen_move is None:
            return "PASS"

        logging.debug(f"Goformer output: {gen_move} at {np.exp(gen_move_p)}")
        if gen_move in ['B+R', "W+R"]:
            return "resign"
        elif gen_move == 'X':
            return "PASS"
        else:
            try:
                return f"{LEELA_DECODE_MAP_X[gen_move[0]]}{LEELA_DECODE_MAP_Y[gen_move[1:]]}"
            except:
                raise ValueError(f"Invalid move: {gen_move}")


if __name__ == '__main__':
    agent = GoFormer("kenhktsui/goformer-v0.1", 'b')
    print(agent.predict_next_move(
        [
            Round(n=1, black_move=None, white_move=None)
        ]
    )
    )
    print(agent.predict_next_move(
        [
            Round(n=1, black_move='D16', white_move='S1'),
            Round(n=2, black_move=None, white_move=None)
        ]
    )
    )
