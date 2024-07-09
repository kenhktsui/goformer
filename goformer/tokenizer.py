from typing import List, Optional, Dict, Tuple
import json
import os
from transformers import PreTrainedTokenizer


class AlphabetTokenizer(PreTrainedTokenizer):
    special_tokens_dict = {
        'unk_token': '[UNK]',
        'sep_token': '[SEP]',
        'pad_token': '[PAD]',
        'cls_token': '[CLS]',
        'mask_token': '[MASK]'
    }

    def __init__(self, **kwargs):
        self.alphabet = [chr(i) for i in range(65, 65+19)] + [chr(i).lower() for i in range(65, 65+19)] + [str(i) for i in range(0, 10)] + ['.', '+', '-', ' ', 'W', '>', 'X']
        self.vocab = {char: i for i, char in enumerate(self.alphabet)}
        self.inv_vocab = {i: char for char, i in self.vocab.items()}

        # Initialize with default special tokens
        super().__init__(
            **kwargs
        )
        # override default _add_tokens of special tokens, and we add manually afterwards
        self._added_tokens_decoder = {}
        self.add_special_tokens(self.special_tokens_dict)

    def get_vocab(self) -> Dict[str, int]:
        return dict(self.vocab)

    def _tokenize(self, text: str) -> List[str]:
        return [char for char in text if char in self.alphabet or char in self.vocab]

    def _convert_token_to_id(self, token: str) -> int:
        return self.vocab.get(token, self.vocab.get(self.unk_token))

    def _convert_id_to_token(self, index: int) -> str:
        return self.inv_vocab.get(index, self.unk_token)

    def convert_tokens_to_string(self, tokens: List[str]) -> str:
        return ''.join(tokens)

    def build_inputs_with_special_tokens(self, token_ids_0: List[int], token_ids_1: Optional[List[int]] = None) -> List[int]:
        if token_ids_1 is None:
            return [self.cls_token_id] + token_ids_0 + [self.sep_token_id]
        cls = [self.cls_token_id]
        sep = [self.sep_token_id]
        return cls + token_ids_0 + sep + token_ids_1 + sep

    def add_special_tokens(self, special_tokens_dict: Dict[str, str]) -> int:
        """Override add_special_tokens to update both vocab and inv_vocab"""
        added_tokens = 0
        for token_name, token in special_tokens_dict.items():
            if token not in self.vocab:
                self.vocab[token] = len(self.vocab)
                self.inv_vocab[len(self.inv_vocab)] = token
                self.all_special_tokens_extended.append(token)
                setattr(self, f"{token_name}_token", token)
                added_tokens += 1
        return added_tokens

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    def save_vocabulary(self, save_directory: str, filename_prefix: Optional[str] = None) -> Tuple[str]:
        """Save the vocabulary and special tokens file to a directory."""
        if not os.path.isdir(save_directory):
            raise ValueError(f"Vocabulary path ({save_directory}) should be a directory")

        vocab_file = os.path.join(
            save_directory, (filename_prefix + "-" if filename_prefix else "") + "vocab.json"
        )

        with open(vocab_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.vocab, ensure_ascii=False))

        return (vocab_file,)
