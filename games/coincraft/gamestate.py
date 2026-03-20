"""Coincraft game logic - Megaways mining slot with blockers and bonus."""

import random
from game_override import GameStateOverride
from src.calculations.board import reveal_event, get_random_outcome


class GameState(GameStateOverride):
    """Handle basegame and bonus game logic with bonus tiers."""

    def check_fs_condition(self, scatter_key: str = "scatter") -> bool:
        """Override: remove the 'not self.repeat' guard so scatters work naturally."""
        if not self.config.freespin_triggers.get(self.gametype, {}):
            return False
        if self.count_special_symbols(scatter_key) >= min(
            self.config.freespin_triggers[self.gametype].keys()
        ):
            return True
        return False

    def check_freespin_entry(self, scatter_key: str = "scatter") -> bool:
        """Override: allow natural freegame entry even when force_freegame is False."""
        if not self.config.freespin_triggers.get(self.gametype, {}):
            return False
        scatter_count = len(self.special_syms_on_board.get(scatter_key, []))
        min_scatters = min(self.config.freespin_triggers[self.gametype].keys())
        if scatter_count >= min_scatters:
            return True
        return False

    def draw_board(self, emit_event: bool = True, trigger_symbol: str = "scatter") -> None:
        """Override: allow natural scatter landings instead of filtering them out."""
        if (
            self.get_current_distribution_conditions()["force_freegame"]
            and self.gametype == self.config.basegame_type
        ):
            num_scatters = get_random_outcome(self.get_current_distribution_conditions()["scatter_triggers"])
            self.force_special_board(trigger_symbol, num_scatters)
        else:
            # Natural landing - no scatter filtering
            self.create_board_reelstrips()
        if emit_event:
            reveal_event(self)

    def get_scatter_count(self):
        """Count scatters on current board."""
        return self.count_special_symbols("scatter")

    def get_bonus_tier(self, scatter_count):
        """Get bonus tier config based on scatter count."""
        # Get highest matching tier
        for sc in sorted(self.config.bonus_tiers.keys(), reverse=True):
            if scatter_count >= sc:
                return self.config.bonus_tiers[sc]
        return self.config.bonus_tiers[3]  # fallback

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
                scatter_count = self.get_scatter_count()
                tier = self.get_bonus_tier(scatter_count)

                # Phase 1: Pickaxe collection (for 4+ scatters)
                self._collected_pickaxes = []
                self._bonus_tier = tier
                if tier["pickaxe_mode"]:
                    self._collected_pickaxes = self.run_pickaxe_collection(tier)

                # Phase 2: Free spins - use our own trigger instead of SDK's
                self.record({
                    "kind": scatter_count,
                    "symbol": "scatter",
                    "gametype": self.gametype,
                })
                self.tot_fs = tier["free_spins"]
                from src.events.events import fs_trigger_event
                fs_trigger_event(self, basegame_trigger=True, freegame_trigger=False)
                self.run_freespin()

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    def run_pickaxe_collection(self, tier):
        """Phase 1: Collect pickaxes with limited lives.

        Each spin of the collection phase:
        - 1-2 pickaxes can land per spin (from blocker positions on board)
        - If no pickaxe lands, lose a life
        - When all lives lost, phase 1 ends
        - Min total hits: 5, Max total hits: 30
        """
        MAX_TOTAL_HITS = 30
        MIN_TOTAL_HITS = 5

        lives = tier["lives"]
        removed_blockers = tier["removed_blockers"]
        collected = []
        total_hits = 0

        # Pickaxe type weights - bronze common, diamond very rare
        pickaxe_weights = {"bronze": 50, "silver": 30, "gold": 15, "diamond": 5}
        weight_total = sum(pickaxe_weights.values())
        pickaxe_types = list(pickaxe_weights.keys())

        self.book.add_event({
            "type": "pickaxePhaseStart",
            "tier": tier["name"],
            "lives": lives,
            "removedBlockers": removed_blockers,
        })

        while lives > 0 and total_hits < MAX_TOTAL_HITS:
            # Draw a board for pickaxe collection
            self.create_board_reelstrips()
            reveal_event(self)

            # Find blocker positions that can drop pickaxes
            pickaxe_positions = []
            for reel_idx, reel in enumerate(self.board):
                for row_idx, symbol in enumerate(reel):
                    if symbol.name in self.config.blocker_config:
                        if symbol.name not in removed_blockers:
                            pickaxe_positions.append((reel_idx, row_idx))

            # Each valid blocker position has a 25% chance to drop a pickaxe
            pickaxes_this_spin = []
            for reel_idx, row_idx in pickaxe_positions:
                if total_hits >= MAX_TOTAL_HITS:
                    break
                if random.random() < 0.25:
                    # Determine pickaxe type via weighted random
                    r = random.random() * weight_total
                    cumulative = 0
                    chosen_type = "bronze"
                    for pt, w in pickaxe_weights.items():
                        cumulative += w
                        if r <= cumulative:
                            chosen_type = pt
                            break

                    cfg = self.config.pickaxe_config[chosen_type]
                    hits = random.randint(cfg["min_hits"], cfg["max_hits"])

                    # Cap total hits
                    if total_hits + hits > MAX_TOTAL_HITS:
                        hits = MAX_TOTAL_HITS - total_hits

                    total_hits += hits
                    pickaxes_this_spin.append({"type": chosen_type, "hits": hits})
                    collected.append({"type": chosen_type, "hits": hits})

                    self.book.add_event({
                        "type": "pickaxeCollected",
                        "pickaxeType": chosen_type,
                        "hits": hits,
                        "position": [reel_idx, row_idx],
                    })

            if not pickaxes_this_spin:
                lives -= 1
                self.book.add_event({
                    "type": "pickaxeLifeLost",
                    "livesRemaining": lives,
                })

        # Ensure minimum hits
        if total_hits < MIN_TOTAL_HITS:
            extra = MIN_TOTAL_HITS - total_hits
            collected.append({"type": "bronze", "hits": extra})
            total_hits = MIN_TOTAL_HITS
            self.book.add_event({
                "type": "pickaxeBonus",
                "pickaxeType": "bronze",
                "hits": extra,
            })

        self.book.add_event({
            "type": "pickaxePhaseEnd",
            "totalPickaxes": len(collected),
            "totalHits": total_hits,
        })

        return collected

    def run_freespin(self) -> None:
        """Bonus game: enhanced base game with blockers.
        If pickaxes were collected, they auto-destroy blockers.
        Uses enhanced blocker config for bonus buy mode.
        """
        self.reset_fs_spin()
        pickaxes = getattr(self, '_collected_pickaxes', [])
        tier = getattr(self, '_bonus_tier', None)
        remaining_hits = sum(p["hits"] for p in pickaxes)

        # Use enhanced blocker config for bonus buy (FG1 reels)
        is_bonus_buy = hasattr(self.config, 'blocker_config_bonus') and self.betmode == 'bonus'

        while self.fs < self.tot_fs:
            self.update_freespin()
            self.draw_board(emit_event=True)

            # Evaluate ways wins
            self.evaluate_ways_board()

            # Apply pickaxe hits to blockers before TNT evaluation
            if remaining_hits > 0:
                remaining_hits = self.apply_pickaxe_hits(remaining_hits, tier, is_bonus_buy)

            # Evaluate remaining blockers with TNT (use enhanced config for bonus buy)
            self.evaluate_blockers(use_bonus_config=is_bonus_buy)

            self.win_manager.update_gametype_wins(self.gametype)

        self.end_freespin()

        # Clean up
        self._collected_pickaxes = []
        self._bonus_tier = None

    def apply_pickaxe_hits(self, remaining_hits, tier, is_bonus_buy=False):
        """Use pickaxe hits to destroy blockers on the board."""
        removed_blockers = tier["removed_blockers"] if tier else []
        blocker_cfg_map = (
            self.config.blocker_config_bonus if is_bonus_buy and hasattr(self.config, 'blocker_config_bonus')
            else self.config.blocker_config
        )

        for reel_idx, reel in enumerate(self.board):
            if remaining_hits <= 0:
                break
            for row_idx, symbol in enumerate(reel):
                if remaining_hits <= 0:
                    break
                if symbol.name in self.config.blocker_config:
                    # Skip blockers already removed by tier
                    if symbol.name in removed_blockers:
                        continue

                    blocker_cfg = blocker_cfg_map.get(symbol.name, self.config.blocker_config[symbol.name])
                    # Pickaxe always destroys
                    min_steps = int(blocker_cfg["min_mult"] * 10)
                    max_steps = int(blocker_cfg["max_mult"] * 10)
                    mult = random.randint(min_steps, max_steps) / 10.0
                    self.win_manager.update_spinwin(mult)
                    remaining_hits -= 1

                    self.book.add_event({
                        "type": "pickaxeUsed",
                        "position": [reel_idx, row_idx],
                        "blockerType": symbol.name,
                        "multiplier": mult,
                        "hitsRemaining": remaining_hits,
                    })

        return remaining_hits
