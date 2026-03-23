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

    def evaluate_blockers(self, use_bonus_config=False):
        """Check if any TNT wilds are adjacent to blockers and resolve them."""
        blocker_cfg_map = (
            self.config.blocker_config_bonus if use_bonus_config and hasattr(self.config, 'blocker_config_bonus')
            else self.config.blocker_config
        )

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
            blocker_cfg = blocker_cfg_map.get(b_name, self.config.blocker_config[b_name])
            # TNT must be directly adjacent (same/neighboring reel AND row)
            num_tnt_nearby = sum(
                1 for w_reel, w_row in wild_positions
                if abs(w_reel - b_reel) <= 1 and abs(w_row - b_row) <= 1
            )
            if num_tnt_nearby > 0:
                # Each TNT gets independent chance
                destroyed = False
                for _ in range(num_tnt_nearby):
                    if random.random() < blocker_cfg["destroy_chance"]:
                        destroyed = True
                        break

                if destroyed:
                    mult = random.choices(blocker_cfg["values"], weights=blocker_cfg["weights"])[0]
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
