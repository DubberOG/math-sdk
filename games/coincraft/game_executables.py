import random
from game_calculations import GameCalculations
from src.calculations.ways import Ways
from src.calculations.board import reveal_event


class GameExecutables(GameCalculations):
    """Coincraft game executables - ways wins + blocker mechanics + cascade."""

    def evaluate_ways_board(self):
        """Evaluate ways wins on the board. Returns winning positions."""
        self.win_data = Ways.get_ways_data(self.config, self.board)
        if self.win_data["totalWin"] > 0:
            Ways.record_ways_wins(self)
            self.win_manager.update_spinwin(self.win_data["totalWin"])
        Ways.emit_wayswin_events(self)
        return self._get_winning_positions()

    def _get_winning_positions(self):
        """Get all board positions involved in winning ways."""
        positions = set()
        if hasattr(self, 'win_data') and self.win_data:
            for win in self.win_data.get("wins", []):
                for pos in win.get("positions", []):
                    positions.add((pos["reel"], pos["row"]))
        return positions

    def evaluate_blockers(self, use_bonus_config=False):
        """TNT explodes ALL adjacent symbols (not just blockers) and is consumed.
        Blockers give instant win when destroyed. Regular symbols are just removed.
        Returns (blocker_wins, destroyed_positions, tnt_positions_used)."""
        blocker_cfg_map = (
            self.config.blocker_config_bonus if use_bonus_config and hasattr(self.config, 'blocker_config_bonus')
            else self.config.blocker_config
        )

        blocker_wins = 0
        destroyed_positions = set()
        tnt_used = set()

        # Find ALL TNT positions
        wild_positions = []
        for reel_idx, reel in enumerate(self.board):
            for row_idx, symbol in enumerate(reel):
                if symbol.name == "W":
                    wild_positions.append((reel_idx, row_idx))

        if not wild_positions:
            return blocker_wins, destroyed_positions, tnt_used

        # TNT explodes ALL adjacent symbols (blockers, regulars, scatters - everything)
        for w_reel, w_row in wild_positions:
            has_adjacent = False
            for reel_idx, reel in enumerate(self.board):
                for row_idx, symbol in enumerate(reel):
                    if (reel_idx, row_idx) == (w_reel, w_row):
                        continue  # Skip the TNT itself
                    if abs(reel_idx - w_reel) <= 1 and abs(row_idx - w_row) <= 1:
                        has_adjacent = True
                        if symbol.name in self.config.blocker_config:
                            # Blocker: attempt destroy for instant win
                            b_name = symbol.name
                            blocker_cfg = blocker_cfg_map.get(b_name, self.config.blocker_config[b_name])
                            if random.random() < blocker_cfg["destroy_chance"]:
                                mult = random.choices(blocker_cfg["values"], weights=blocker_cfg["weights"])[0]
                                blocker_wins += mult
                                destroyed_positions.add((reel_idx, row_idx))
                                self.book.add_event({
                                    "type": "blockerDestroy",
                                    "position": [reel_idx, row_idx],
                                    "blockerType": b_name,
                                    "multiplier": mult,
                                })
                            else:
                                self.book.add_event({
                                    "type": "blockerSurvive",
                                    "position": [reel_idx, row_idx],
                                    "blockerType": b_name,
                                })
                        elif symbol.name != "W":
                            # Non-blocker, non-TNT: just destroyed (removed for cascade)
                            destroyed_positions.add((reel_idx, row_idx))
                            self.book.add_event({
                                "type": "tntDestroy",
                                "position": [reel_idx, row_idx],
                                "symbol": symbol.name,
                            })

            # TNT is always consumed after exploding
            if has_adjacent:
                tnt_used.add((w_reel, w_row))

        if blocker_wins > 0:
            self.win_manager.update_spinwin(blocker_wins)

        return blocker_wins, destroyed_positions, tnt_used

    def cascade_board(self):
        """Remove winning/destroyed symbols and fill from reelstrip.
        Returns positions that were removed."""
        removed = getattr(self, '_cascade_remove', set())
        if not removed:
            return set()

        reel_len = len(self.reelstrip[0])
        for r in range(self.config.num_reels):
            removed_rows = sorted([row for rr, row in removed if rr == r])
            if not removed_rows:
                continue
            # Keep remaining symbols
            remaining = [self.board[r][row] for row in range(self.config.num_rows[r]) if row not in removed_rows]
            # Generate new symbols from reelstrip
            needed = self.config.num_rows[r] - len(remaining)
            new_syms = []
            for _ in range(needed):
                pos = random.randint(0, reel_len - 1)
                new_syms.append(self.create_symbol(self.reelstrip[r][pos]))
            # New on top, remaining slide down
            self.board[r] = new_syms + remaining

        self._cascade_remove = set()
        return removed

    def run_cascade_loop(self, use_bonus_config=False, max_cascades=20):
        """Run the full cascade loop for one spin.
        1. Evaluate ways wins → pay out
        2. TNT explodes adjacent blockers → pay out
        3. Remove winning symbols + destroyed blockers + used TNTs
        4. New symbols cascade down
        5. Repeat until no more wins/explosions
        """
        cascade_count = 0
        for _ in range(max_cascades):
            # 1. Ways wins
            winning_pos = self.evaluate_ways_board()

            # 2. TNT explosions (always, no winning way needed)
            blocker_win, destroyed_pos, tnt_used = self.evaluate_blockers(use_bonus_config)

            # 3. Collect positions to remove
            to_remove = set(winning_pos)
            to_remove.update(destroyed_pos)
            to_remove.update(tnt_used)  # TNTs that exploded are consumed

            if not to_remove:
                break  # No cascade

            cascade_count += 1

            # 4. Emit cascade event
            self.book.add_event({
                "type": "cascade",
                "level": cascade_count,
                "removedPositions": [[r, row] for r, row in to_remove],
            })

            # 5. Fill new symbols
            self._cascade_remove = to_remove
            self.cascade_board()

            # Emit new board state
            reveal_event(self)

        return cascade_count
