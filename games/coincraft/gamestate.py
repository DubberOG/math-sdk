"""Coincraft game logic - Megaways mining slot with blockers and bonus."""

from game_override import GameStateOverride


class GameState(GameStateOverride):
    """Handle basegame and bonus game logic."""

    def run_spin(self, sim: int, simulation_seed=None) -> None:
        self.reset_seed(sim)
        self.repeat = True
        while self.repeat:
            self.reset_book()
            self.draw_board(emit_event=True)

            # Evaluate ways wins
            self.evaluate_ways_board()

            # Evaluate blocker interactions with TNT
            self.evaluate_blockers()

            self.win_manager.update_gametype_wins(self.gametype)

            # Check scatter condition for bonus
            if self.check_fs_condition() and self.check_freespin_entry():
                self.run_freespin_from_base()

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    def run_freespin(self) -> None:
        """Bonus game: enhanced base game with increased blocker frequency."""
        self.reset_fs_spin()
        while self.fs < self.tot_fs:
            self.update_freespin()
            self.draw_board(emit_event=True)

            # Same evaluation as base but with bonus reels (more blockers)
            self.evaluate_ways_board()
            self.evaluate_blockers()

            if self.check_fs_condition():
                self.update_fs_retrigger_amt()

            self.win_manager.update_gametype_wins(self.gametype)
        self.end_freespin()
