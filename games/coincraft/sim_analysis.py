"""
Coincraft RTP analysis.
1. Run N base game spins, track base wins and scatter triggers
2. Run each triggered bonus (3/4/5+ scatters) with correct tier
3. Calculate combined RTP
"""
import random
import csv
import os
import time
from collections import defaultdict

# Game config inline for fast standalone execution
NUM_REELS = 5
NUM_ROWS = 4

PAYTABLE = {
    (5, "H1"): 10.5, (4, "H1"): 4.2, (3, "H1"): 1.4, (2, "H1"): 0.35,
    (5, "H2"): 8.5, (4, "H2"): 3.5, (3, "H2"): 1.05, (2, "H2"): 0.28,
    (5, "H3"): 7, (4, "H3"): 2.8, (3, "H3"): 0.7, (2, "H3"): 0.2,
    (5, "H4"): 4.2, (4, "H4"): 1.75, (3, "H4"): 0.56, (2, "H4"): 0.14,
    (5, "L1"): 2.1, (4, "L1"): 0.85, (3, "L1"): 0.28,
    (5, "L2"): 1.75, (4, "L2"): 0.7, (3, "L2"): 0.21,
    (5, "L3"): 1.4, (4, "L3"): 0.56, (3, "L3"): 0.14,
    (5, "L4"): 1.05, (4, "L4"): 0.42, (3, "L4"): 0.1,
    (5, "L5"): 0.7, (4, "L5"): 0.28, (3, "L5"): 0.07,
}

WILDS = {"W"}
PAY_SYMBOLS = ["H1", "H2", "H3", "H4", "L1", "L2", "L3", "L4", "L5"]

BLOCKER_CONFIG = {
    "B1": {"destroy_chance": 0.60, "values": [1, 2, 3, 4], "weights": [40, 30, 20, 10]},
    "B2": {"destroy_chance": 0.30, "values": [5, 10, 15, 20], "weights": [40, 30, 20, 10]},
    "B3": {"destroy_chance": 0.10, "values": [25, 50, 100, 150], "weights": [50, 30, 15, 5]},
    "B4": {"destroy_chance": 0.01, "values": [250, 500, 1000, 2500, 5000, 25000], "weights": [40, 30, 18, 9, 2, 1]},
}

BLOCKER_CONFIG_BONUS = {
    "B1": {"destroy_chance": 0.70, "values": [1, 2, 3, 4], "weights": [40, 30, 20, 10]},
    "B2": {"destroy_chance": 0.40, "values": [5, 10, 15, 20], "weights": [40, 30, 20, 10]},
    "B3": {"destroy_chance": 0.15, "values": [25, 50, 100, 150], "weights": [50, 30, 15, 5]},
    "B4": {"destroy_chance": 0.02, "values": [250, 500, 1000, 2500, 5000, 25000], "weights": [40, 30, 18, 9, 2.5, 0.5]},
}

BONUS_TIERS = {
    3: {"name": "bonus", "pickaxe_mode": False, "removed_blockers": [], "free_spins": 10},
    4: {"name": "super_bonus", "pickaxe_mode": True, "lives": 3, "removed_blockers": [], "free_spins": 10},
    5: {"name": "super_bonus_plus", "pickaxe_mode": True, "lives": 3, "removed_blockers": ["B1", "B2"], "free_spins": 10},
    6: {"name": "super_bonus_plus", "pickaxe_mode": True, "lives": 3, "removed_blockers": ["B1", "B2"], "free_spins": 10},
}

PICKAXE_CONFIG = {
    "bronze": {"min_hits": 1, "max_hits": 2},
    "silver": {"min_hits": 1, "max_hits": 3},
    "gold": {"min_hits": 2, "max_hits": 5},
    "diamond": {"min_hits": 3, "max_hits": 10},
}
PICKAXE_WEIGHTS = {"bronze": 50, "silver": 30, "gold": 15, "diamond": 5}
PICKAXE_WEIGHT_TOTAL = sum(PICKAXE_WEIGHTS.values())

PICKAXE_DESTROY = {
    "bronze":  {"B1": 0.90, "B2": 0.30, "B3": 0.05, "B4": 0.0},
    "silver":  {"B1": 0.95, "B2": 0.60, "B3": 0.20, "B4": 0.02},
    "gold":    {"B1": 1.0,  "B2": 0.90, "B3": 0.50, "B4": 0.10},
    "diamond": {"B1": 1.0,  "B2": 1.0,  "B3": 0.80, "B4": 0.40},
}

WINCAP = 25000


def read_reels(filename):
    reels = []
    path = os.path.join(os.path.dirname(__file__), "reels", filename)
    with open(path) as f:
        rows = list(csv.reader(f))
        for r in range(len(rows[0])):
            reels.append([rows[i][r] for i in range(len(rows))])
    return reels


def draw_board(reels):
    """Draw a random 6x4 board from reelstrips."""
    reel_len = len(reels[0])
    board = []
    for r in range(NUM_REELS):
        start = random.randint(0, reel_len - 1)
        col = [reels[r][(start + row) % reel_len] for row in range(NUM_ROWS)]
        board.append(col)
    return board


def eval_ways(board):
    """Evaluate ways wins. Returns total win."""
    total = 0
    for sym in PAY_SYMBOLS:
        ways = 1
        consecutive = 0
        for r in range(NUM_REELS):
            count = sum(1 for s in board[r] if s == sym or s in WILDS)
            if count > 0:
                ways *= count
                consecutive += 1
            else:
                break
        key = (consecutive, sym)
        if key in PAYTABLE:
            total += PAYTABLE[key] * ways
    return total


def get_winning_wild_positions(board):
    """Find TNT positions that are part of a winning way."""
    winning = set()
    for sym in PAY_SYMBOLS:
        ways, consec = 1, 0
        positions = []
        for r in range(NUM_REELS):
            matches = [(r, row) for row in range(NUM_ROWS) if board[r][row] == sym or board[r][row] in WILDS]
            if matches:
                ways *= len(matches)
                consec += 1
                positions.extend(matches)
            else:
                break
        if (consec, sym) in PAYTABLE:
            for r, row in positions:
                if board[r][row] in WILDS:
                    winning.add((r, row))
    return winning


def eval_blockers(board, config=BLOCKER_CONFIG):
    """Evaluate TNT+blocker interactions. Only TNTs in winning ways trigger."""
    winning_wilds = get_winning_wild_positions(board)
    wild_pos = list(winning_wilds)
    blocker_pos = []
    for r in range(NUM_REELS):
        for row in range(NUM_ROWS):
            s = board[r][row]
            if s in config:
                blocker_pos.append((r, row, s))

    total = 0
    for br, brow, bname in blocker_pos:
        cfg = config[bname]
        num_tnt = sum(1 for wr, wrow in wild_pos if abs(wr - br) <= 1 and abs(wrow - brow) <= 1)
        if num_tnt > 0:
            destroyed = any(random.random() < cfg["destroy_chance"] for _ in range(num_tnt))
            if destroyed:
                total += random.choices(cfg["values"], weights=cfg["weights"])[0]
    return total


def count_scatters(board):
    return min(sum(1 for r in range(NUM_REELS) for row in range(NUM_ROWS) if board[r][row] == "S"), 5)


def pick_pickaxe_type():
    r = random.random() * PICKAXE_WEIGHT_TOTAL
    cumulative = 0
    for pt, w in PICKAXE_WEIGHTS.items():
        cumulative += w
        if r <= cumulative:
            return pt
    return "bronze"


def run_pickaxe_collection(tier, reels):
    """Phase 1: Pure collection - no wins, just gather pickaxes.
    Lives reset to max when pickaxe found. 3 misses in a row = phase over."""
    MAX_HITS = 20
    MIN_HITS = 3
    lives = tier["lives"]
    removed = tier["removed_blockers"]
    total_hits = 0
    collected = []  # list of (pickaxe_type, hits)

    while lives > 0 and total_hits < MAX_HITS:
        board = draw_board(reels)
        found = False
        for r in range(NUM_REELS):
            if total_hits >= MAX_HITS:
                break
            for row in range(NUM_ROWS):
                if total_hits >= MAX_HITS:
                    break
                s = board[r][row]
                if s in BLOCKER_CONFIG and s not in removed:
                    if random.random() < 0.25:
                        found = True
                        pt = pick_pickaxe_type()
                        cfg = PICKAXE_CONFIG[pt]
                        hits = random.randint(cfg["min_hits"], cfg["max_hits"])
                        hits = min(hits, MAX_HITS - total_hits)
                        total_hits += hits
                        collected.append((pt, hits))
        if found:
            lives = tier["lives"]
        else:
            lives -= 1

    return max(total_hits, MIN_HITS), collected


def apply_pickaxe_hits(board, collected, tier, blocker_cfg):
    """Apply pickaxe hits during free spins. Each hit consumed regardless of success.
    Destroy chance depends on pickaxe type vs blocker tier."""
    removed = tier.get("removed_blockers", [])
    total_win = 0

    hit_queue = []
    for pt, hits in collected:
        hit_queue.extend([pt] * hits)

    hit_idx = 0
    for r in range(NUM_REELS):
        if hit_idx >= len(hit_queue):
            break
        for row in range(NUM_ROWS):
            if hit_idx >= len(hit_queue):
                break
            s = board[r][row]
            if s in blocker_cfg and s not in removed:
                pt = hit_queue[hit_idx]
                hit_idx += 1
                chance = PICKAXE_DESTROY.get(pt, {}).get(s, 0)
                if random.random() < chance:
                    cfg = blocker_cfg[s]
                    total_win += random.choices(cfg["values"], weights=cfg["weights"])[0]

    remaining = len(hit_queue) - hit_idx
    if remaining <= 0:
        return total_win, []
    new_collected = []
    left = remaining
    for pt, h in reversed(collected):
        if left <= 0:
            break
        take = min(h, left)
        new_collected.insert(0, (pt, take))
        left -= take
    return total_win, new_collected


def run_bonus(scatter_count, fg_reels, base_reels, blocker_cfg):
    """Run a complete bonus round. Returns total bonus win."""
    tier_key = min(scatter_count, 5)
    tier = BONUS_TIERS[tier_key]

    total_win = 0
    collected = []

    # Phase 1: Pure pickaxe collection (no wins)
    if tier["pickaxe_mode"]:
        _, collected = run_pickaxe_collection(tier, base_reels)

    # Phase 2: Free spins
    for _ in range(tier["free_spins"]):
        board = draw_board(fg_reels)

        # Ways wins
        total_win += eval_ways(board)

        # Apply pickaxe hits (with destroy chance, hits consumed regardless)
        if collected:
            pickaxe_win, collected = apply_pickaxe_hits(board, collected, tier, blocker_cfg)
            total_win += pickaxe_win

        # TNT + blocker evaluation
        total_win += eval_blockers(board, blocker_cfg)

    return min(total_win, WINCAP)


def run_session(num_spins, br0, fg1):
    """Run a single player session and return (total_wagered, total_won, bonus_info)."""
    total_won = 0
    bonus_info = defaultdict(int)  # scatter_count -> times triggered

    for _ in range(num_spins):
        board = draw_board(br0)
        ways_win = eval_ways(board)
        blocker_win = eval_blockers(board)
        base_win = ways_win + blocker_win

        sc = count_scatters(board)
        bonus_win = 0
        if sc >= 3:
            bonus_win = run_bonus(sc, fg1, br0, BLOCKER_CONFIG_BONUS)
            bonus_info[sc] += 1

        round_win = min(base_win + bonus_win, WINCAP)
        total_won += round_win

    return num_spins, total_won, bonus_info


def main():
    BATCH_SIZE = 500
    NUM_BATCHES = 40000  # 40000 x 500 = 20M total spins
    TOTAL_SIMS = BATCH_SIZE * NUM_BATCHES

    br0 = read_reels("BR0.csv")
    fg0 = read_reels("FG0.csv")
    fg1 = read_reels("FG1.csv")

    print(f"Running {TOTAL_SIMS:,} spins in {NUM_BATCHES:,} sessions of {BATCH_SIZE} spins...")
    start = time.time()

    session_rtps = []
    all_scatter_triggers = defaultdict(list)
    total_won_all = 0
    total_wagered_all = 0
    max_single_session_rtp = 0
    min_single_session_rtp = float('inf')

    # RTP brackets for sessions
    rtp_brackets = defaultdict(int)

    for batch in range(NUM_BATCHES):
        random.seed(batch * BATCH_SIZE + 1)
        wagered, won, bonus_info = run_session(BATCH_SIZE, br0, fg1)

        session_rtp = won / wagered if wagered > 0 else 0
        session_rtps.append(session_rtp)
        total_won_all += won
        total_wagered_all += wagered
        max_single_session_rtp = max(max_single_session_rtp, session_rtp)
        min_single_session_rtp = min(min_single_session_rtp, session_rtp)

        for sc, count in bonus_info.items():
            for _ in range(count):
                all_scatter_triggers[sc].append(session_rtp)

        # Bracket the session RTP
        if session_rtp < 0.5:
            rtp_brackets["<50%"] += 1
        elif session_rtp < 0.8:
            rtp_brackets["50-80%"] += 1
        elif session_rtp < 1.0:
            rtp_brackets["80-100%"] += 1
        elif session_rtp < 1.5:
            rtp_brackets["100-150%"] += 1
        elif session_rtp < 3.0:
            rtp_brackets["150-300%"] += 1
        elif session_rtp < 10.0:
            rtp_brackets["300-1000%"] += 1
        else:
            rtp_brackets["1000%+"] += 1

    elapsed = time.time() - start
    overall_rtp = total_won_all / total_wagered_all

    import statistics
    median_rtp = statistics.median(session_rtps)
    stddev_rtp = statistics.stdev(session_rtps)
    p10 = sorted(session_rtps)[int(NUM_BATCHES * 0.10)]
    p25 = sorted(session_rtps)[int(NUM_BATCHES * 0.25)]
    p75 = sorted(session_rtps)[int(NUM_BATCHES * 0.75)]
    p90 = sorted(session_rtps)[int(NUM_BATCHES * 0.90)]
    p99 = sorted(session_rtps)[int(NUM_BATCHES * 0.99)]

    print(f"\n{'='*60}")
    print(f" COINCRAFT - {TOTAL_SIMS:,} SPINS ({elapsed:.1f}s)")
    print(f" {NUM_BATCHES:,} sessions of {BATCH_SIZE} spins each")
    print(f"{'='*60}")
    print(f"")
    print(f" OVERALL RTP: {overall_rtp*100:.2f}%")
    print(f"")
    print(f" SESSION RTP DISTRIBUTION ({BATCH_SIZE} spins/session):")
    print(f"   Median:  {median_rtp*100:.1f}%")
    print(f"   Mean:    {overall_rtp*100:.1f}%")
    print(f"   Std dev: {stddev_rtp*100:.1f}%")
    print(f"   Min:     {min_single_session_rtp*100:.1f}%")
    print(f"   P10:     {p10*100:.1f}%")
    print(f"   P25:     {p25*100:.1f}%")
    print(f"   P75:     {p75*100:.1f}%")
    print(f"   P90:     {p90*100:.1f}%")
    print(f"   P99:     {p99*100:.1f}%")
    print(f"   Max:     {max_single_session_rtp*100:.1f}%")
    print(f"")
    print(f" SESSION RTP BRACKETS:")
    bracket_order = ["<50%", "50-80%", "80-100%", "100-150%", "150-300%", "300-1000%", "1000%+"]
    for b in bracket_order:
        c = rtp_brackets.get(b, 0)
        if c > 0:
            pct = c / NUM_BATCHES * 100
            print(f"   {b:>10s}: {c:>6,} sessions ({pct:>5.1f}%)")
    print(f"")

    # Bonus stats
    total_bonuses = sum(len(v) for v in all_scatter_triggers.values())
    print(f" BONUS TRIGGERS (across all sessions):")
    print(f"   Total: {total_bonuses:,} (avg {total_bonuses/NUM_BATCHES:.1f} per session)")
    for sc in sorted(all_scatter_triggers.keys()):
        count = len(all_scatter_triggers[sc])
        freq = TOTAL_SIMS / count
        print(f"   {sc} scatters: {count:>6,} (1/{freq:,.0f} spins)")

    # Player experience insight
    no_bonus = sum(1 for rtp in session_rtps if rtp < 0.9)
    big_winner = sum(1 for rtp in session_rtps if rtp > 3.0)
    print(f"")
    print(f" PLAYER EXPERIENCE:")
    print(f"   Sessions with <90% RTP (feels bad): {no_bonus:,} ({no_bonus/NUM_BATCHES*100:.1f}%)")
    print(f"   Sessions with >300% RTP (big win):  {big_winner:,} ({big_winner/NUM_BATCHES*100:.1f}%)")
    print(f"   Sessions with no bonus at all:      ~{int(NUM_BATCHES * (1-1/320)**500):,} ({(1-1/320)**500*100:.1f}%)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
