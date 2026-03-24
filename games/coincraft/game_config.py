import os
from src.config.config import Config
from src.config.distributions import Distribution
from src.config.betmode import BetMode


class GameConfig(Config):
    """Coincraft game configuration - Megaways mining slot."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()
        self.game_id = "coincraft"
        self.provider_number = 0
        self.working_name = "coincraft"
        self.wincap = 25000
        self.win_type = "ways"
        self.rtp = 0.96
        self.construct_paths()

        # Game Dimensions - 6 reels x 4 rows
        self.num_reels = 6
        self.num_rows = [4] * self.num_reels

        # Paytable - 6 reels, cascade mechanic
        # H1 (Miner-man): pays from 2+ (unique)
        # H2-H4: pay from 3+
        # L1-L5: pay from 3+
        self.paytable = {
            # H1 - Miner-man (pays from 2+)
            (6, "H1"): 25, (5, "H1"): 10, (4, "H1"): 5, (3, "H1"): 2, (2, "H1"): 0.5,
            # H2 - Canary bird
            (6, "H2"): 20, (5, "H2"): 8, (4, "H2"): 4, (3, "H2"): 1.5,
            # H3 - Bat
            (6, "H3"): 15, (5, "H3"): 6, (4, "H3"): 3, (3, "H3"): 1,
            # H4 - Lantern
            (6, "H4"): 10, (5, "H4"): 4, (4, "H4"): 2, (3, "H4"): 0.8,
            # L1 - A
            (6, "L1"): 5, (5, "L1"): 2, (4, "L1"): 1, (3, "L1"): 0.4,
            # L2 - K
            (6, "L2"): 4, (5, "L2"): 1.5, (4, "L2"): 0.8, (3, "L2"): 0.3,
            # L3 - Q
            (6, "L3"): 3, (5, "L3"): 1.2, (4, "L3"): 0.6, (3, "L3"): 0.2,
            # L4 - J
            (6, "L4"): 2.5, (5, "L4"): 1, (4, "L4"): 0.5, (3, "L4"): 0.2,
            # L5 - 10
            (6, "L5"): 2, (5, "L5"): 0.8, (4, "L5"): 0.4, (3, "L5"): 0.1,
        }

        self.include_padding = True
        self.special_symbols = {
            "wild": ["W"],       # TNT
            "scatter": ["S"],    # Bonus trigger
            "multiplier": [],
            "blocker": ["B1", "B2", "B3", "B4"],  # Bronze, Silver, Gold, Diamond
            # No empty/X symbols - dead spins occur naturally from symbol distribution
        }

        # Blocker properties - discrete weighted steps
        self.blocker_config = {
            "B1": {"destroy_chance": 0.60, "values": [1, 2, 3, 4], "weights": [40, 30, 20, 10]},
            "B2": {"destroy_chance": 0.30, "values": [5, 10, 15, 20], "weights": [40, 30, 20, 10]},
            "B3": {"destroy_chance": 0.10, "values": [25, 50, 100, 150], "weights": [50, 30, 15, 5]},
            "B4": {"destroy_chance": 0.01, "values": [250, 500, 1000, 2500, 5000, 25000], "weights": [40, 30, 18, 9, 2, 1]},
        }

        # Enhanced blocker config for bonus buy freegame
        self.blocker_config_bonus = {
            "B1": {"destroy_chance": 0.80, "values": [1, 2, 3, 4], "weights": [40, 30, 20, 10]},
            "B2": {"destroy_chance": 0.50, "values": [5, 10, 15, 20], "weights": [35, 30, 20, 15]},
            "B3": {"destroy_chance": 0.15, "values": [25, 50, 100, 150], "weights": [45, 30, 15, 10]},
            "B4": {"destroy_chance": 0.03, "values": [250, 500, 1000, 2500, 5000, 25000], "weights": [35, 30, 20, 10, 4.5, 0.5]},
        }

        # Pickaxe config for bonus game
        self.pickaxe_config = {
            "bronze":  {"min_hits": 1, "max_hits": 2},
            "silver":  {"min_hits": 1, "max_hits": 3},
            "gold":    {"min_hits": 2, "max_hits": 5},
            "diamond": {"min_hits": 3, "max_hits": 10},
        }

        # Pickaxe destroy chance per blocker tier
        # Each hit is consumed regardless of success
        self.pickaxe_destroy_chance = {
            "bronze":  {"B1": 0.90, "B2": 0.30, "B3": 0.05, "B4": 0.0},
            "silver":  {"B1": 0.95, "B2": 0.60, "B3": 0.20, "B4": 0.02},
            "gold":    {"B1": 1.0,  "B2": 0.90, "B3": 0.50, "B4": 0.10},
            "diamond": {"B1": 1.0,  "B2": 1.0,  "B3": 0.80, "B4": 0.40},
        }

        # Bonus tiers based on scatter count:
        # 3 scatters: 10 free spins, enhanced base game
        # 4 scatters: pickaxe collection (3 lives) THEN 10 free spins
        # 5 scatters: enhanced pickaxe collection (3 lives, no bronze/silver) THEN 10 free spins
        self.bonus_tiers = {
            3: {"name": "bonus", "lives": 0, "pickaxe_mode": False, "removed_blockers": [], "free_spins": 10},
            4: {"name": "super_bonus", "lives": 3, "pickaxe_mode": True, "removed_blockers": [], "free_spins": 10},
            5: {"name": "super_bonus_plus", "lives": 3, "pickaxe_mode": True, "removed_blockers": ["B1", "B2"], "free_spins": 10},
        }

        self.freespin_triggers = {
            self.basegame_type: {i: 10 for i in range(3, 25)},
            self.freegame_type: {},  # No retrigger in freegame (FG0/FG1 have no scatters)
        }
        self.anticipation_triggers = {self.basegame_type: 2, self.freegame_type: 1}

        # Reels:
        # BR0 = base game
        # BN0 = bonus trigger (more scatters for buy bonus)
        # FG0 = freegame from natural bonus (more TNT/blockers, no scatters)
        # FG1 = freegame from buy bonus (even richer, no scatters)
        reels = {"BR0": "BR0.csv", "BN0": "BN0.csv", "FG0": "FG0.csv", "FG1": "FG1.csv", "WCAP": "WCAP.csv"}
        self.reels = {}
        for r, f in reels.items():
            self.reels[r] = self.read_reels_csv(os.path.join(self.reels_path, f))

        mode_maxwins = {
            "base": 25000,
            "bonus_boost": 25000,
            "free_spins": 25000,
            "crazy_mining": 25000,
            "ultimate_mining": 25000,
        }

        self.bet_modes = [
            # Base game - normal play
            BetMode(
                name="base",
                cost=1.0,
                rtp=self.rtp,
                max_win=mode_maxwins["base"],
                auto_close_disabled=False,
                is_feature=True,
                is_buybonus=False,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.05,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FG0": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": True,
                            "scatter_triggers": {3: 100, 4: 20, 5: 5},
                        },
                    ),
                    Distribution(
                        criteria="0",
                        quota=0.60,
                        win_criteria=0.0,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FG0": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.35,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FG0": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                ],
            ),
            # Bonus Hunt - increased chance to trigger bonus (cost 10x)
            BetMode(
                name="bonus_boost",
                cost=2.0,
                rtp=self.rtp,
                max_win=mode_maxwins["bonus_boost"],
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.5,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BN0": 1},
                                self.freegame_type: {"FG0": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": True,
                            "scatter_triggers": {3: 100, 4: 20, 5: 5},
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.5,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BN0": 1},
                                self.freegame_type: {"FG0": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                ],
            ),
            # Free Spins - guaranteed 3 scatters (cost 100x)
            BetMode(
                name="free_spins",
                cost=100.0,
                rtp=self.rtp,
                max_win=mode_maxwins["free_spins"],
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=1,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BN0": 1},
                                self.freegame_type: {"FG1": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": True,
                            "scatter_triggers": {3: 1},
                        },
                    ),
                ],
            ),
            # Ultimate Mining - guaranteed 4 scatters, pickaxe collection (cost 250x)
            BetMode(
                name="crazy_mining",
                cost=250.0,
                rtp=self.rtp,
                max_win=mode_maxwins["crazy_mining"],
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=1,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BN0": 1},
                                self.freegame_type: {"FG1": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": True,
                            "scatter_triggers": {4: 1},
                        },
                    ),
                ],
            ),
            # Mining Bonanza - guaranteed 5 scatters, enhanced pickaxe (cost 500x)
            BetMode(
                name="ultimate_mining",
                cost=500.0,
                rtp=self.rtp,
                max_win=mode_maxwins["ultimate_mining"],
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=1,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BN0": 1},
                                self.freegame_type: {"FG1": 1},
                            },
                            "force_wincap": False,
                            "force_freegame": True,
                            "scatter_triggers": {5: 1},
                        },
                    ),
                ],
            ),
        ]
