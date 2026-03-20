from game_executables import GameExecutables


class GameStateOverride(GameExecutables):
    """
    Override/extend universal state functions for Coincraft.
    Handles blocker evaluation and bonus game state.
    """

    def reset_book(self):
        super().reset_book()
        # Coincraft-specific state
        self.blocker_wins = 0
        self.bonus_phase = None
        self.bonus_lives = 3
        self.pickaxes = []

    def assign_special_sym_function(self):
        self.special_symbol_functions = {}

    def check_game_repeat(self):
        if self.repeat is False:
            win_criteria = self.get_current_betmode_distributions().get_win_criteria()
            if win_criteria is not None and self.final_win != win_criteria:
                self.repeat = True
