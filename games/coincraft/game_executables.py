import random
from game_calculations import GameCalculations
from src.calculations.ways import Ways


class GameExecutables(GameCalculations):
    """Coincraft game executables - ways wins + blocker mechanics."""

    def evaluate_ways_board(self):
        """Evaluate ways wins on the board."""
        self.win_data = Ways.get_ways_data(self.config, self.board)
        if self.win_data["totalWin"] > 0:
            Ways.record_ways_wins(self)
            self.win_manager.update_spinwin(self.win_data["totalWin"])
        Ways.emit_wayswin_events(self)

    def evaluate_blockers(self):
        """Check if any TNT wilds are adjacent to blockers and resolve them."""
        blocker_wins = 0
        wild_positions = []
        blocker_positions = []

        for reel_idx, reel in enumerate(self.board):
            for row_idx, symbol in enumerate(reel):
                if symbol.name == "W":
                    wild_positions.append((reel_idx, row_idx))
                elif symbol.name in self.config.blocker_config:
                    blocker_positions.append((reel_idx, row_idx, symbol.name))

        for b_reel, b_row, b_name in blocker_positions:
            blocker_cfg = self.config.blocker_config[b_name]
            # Each TNT on the same reel or adjacent reel can attempt to destroy
            num_tnt_nearby = sum(
                1 for w_reel, w_row in wild_positions
                if abs(w_reel - b_reel) <= 1
            )
            if num_tnt_nearby > 0:
                # Each TNT gets independent chance
                destroyed = False
                for _ in range(num_tnt_nearby):
                    if random.random() < blocker_cfg["destroy_chance"]:
                        destroyed = True
                        break

                if destroyed:
                    # Use discrete steps of 0.1 to ensure payout increments of 10
                    min_steps = int(blocker_cfg["min_mult"] * 10)
                    max_steps = int(blocker_cfg["max_mult"] * 10)
                    mult = random.randint(min_steps, max_steps) / 10.0
                    blocker_wins += mult
                    self.book.add_event({
                        "type": "blockerDestroy",
                        "position": [b_reel, b_row],
                        "blockerType": b_name,
                        "multiplier": mult,
                    })
                else:
                    self.book.add_event({
                        "type": "blockerSurvive",
                        "position": [b_reel, b_row],
                        "blockerType": b_name,
                    })

        if blocker_wins > 0:
            self.win_manager.update_spinwin(blocker_wins)

        return blocker_wins
