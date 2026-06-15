# crossword_gen.py
# Greedy interlocking crossword generator.
# Produces a classic-style grid: words cross at shared letters, no invalid
# adjacencies, numbered cells, and across/down clue lists.

import random


def _new_grid(size):
    return [[None] * size for _ in range(size)]


def _fits(grid, word, r, c, dr, dc):
    """Return (ok, crossings) for placing `word` at (r,c) heading (dr,dc)."""
    size = len(grid)
    L = len(word)

    # Cell immediately before the start must be empty/off-grid.
    br, bc = r - dr, c - dc
    if 0 <= br < size and 0 <= bc < size and grid[br][bc] is not None:
        return False, 0
    # Cell immediately after the end must be empty/off-grid.
    ar, ac = r + dr * L, c + dc * L
    if 0 <= ar < size and 0 <= ac < size and grid[ar][ac] is not None:
        return False, 0

    crossings = 0
    for i, ch in enumerate(word):
        rr, cc = r + dr * i, c + dc * i
        if not (0 <= rr < size and 0 <= cc < size):
            return False, 0
        cell = grid[rr][cc]
        if cell is not None:
            if cell != ch:
                return False, 0
            crossings += 1  # valid crossing
        else:
            # New (empty) cell: its perpendicular neighbors must be empty,
            # otherwise we'd glue an unintended parallel word.
            pr, pc = dc, dr  # perpendicular direction
            for sign in (1, -1):
                nr, nc = rr + pr * sign, cc + pc * sign
                if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] is not None:
                    return False, 0
    return True, crossings


def _place(grid, word, r, c, dr, dc):
    for i, ch in enumerate(word):
        grid[r + dr * i][c + dc * i] = ch


def _generate_once(words, size, target):
    """One greedy attempt. Returns (placed, grid) where placed is a list of
    dicts: {word, clue, r, c, dir}."""
    grid = _new_grid(size)
    placed = []

    # Place the first (longest) word horizontally near the middle.
    first_word, first_clue = words[0]
    r0 = size // 2
    c0 = (size - len(first_word)) // 2
    _place(grid, first_word, r0, c0, 0, 1)
    placed.append({"word": first_word, "clue": first_clue, "r": r0, "c": c0, "dir": "across"})
    used = {first_word}

    # Build a quick index of placed letters -> list of (row, col).
    def letter_positions():
        pos = {}
        for rr in range(size):
            for cc in range(size):
                ch = grid[rr][cc]
                if ch is not None:
                    pos.setdefault(ch, []).append((rr, cc))
        return pos

    for word, clue in words[1:]:
        if len(placed) >= target:
            break
        if word in used:
            continue

        positions = letter_positions()
        best = None  # (crossings, r, c, dr, dc)

        for i, ch in enumerate(word):
            for (pr, pc) in positions.get(ch, []):
                # Try placing the word so letter i lands on (pr,pc), both dirs.
                for dr, dc in ((1, 0), (0, 1)):
                    r = pr - dr * i
                    c = pc - dc * i
                    ok, crossings = _fits(grid, word, r, c, dr, dc)
                    if ok and crossings >= 1:
                        if best is None or crossings > best[0]:
                            best = (crossings, r, c, dr, dc)

        if best is not None:
            _, r, c, dr, dc = best
            _place(grid, word, r, c, dr, dc)
            placed.append({
                "word": word, "clue": clue, "r": r, "c": c,
                "dir": "down" if dr == 1 else "across",
            })
            used.add(word)

    return placed, grid


def _trim_and_number(placed, size):
    """Crop to bounding box, renumber cells, build clue lists + solution grid."""
    rows = [p["r"] for p in placed]
    cols = [p["c"] for p in placed]
    end_rows = [p["r"] + (len(p["word"]) if p["dir"] == "down" else 1) for p in placed]
    end_cols = [p["c"] + (len(p["word"]) if p["dir"] == "across" else 1) for p in placed]
    min_r, max_r = min(rows), max(end_rows)
    min_c, max_c = min(cols), max(end_cols)
    H = max_r - min_r
    W = max_c - min_c

    # Shift all words into the cropped frame and paint the solution grid.
    sol = [[None] * W for _ in range(H)]
    shifted = []
    for p in placed:
        nr, nc = p["r"] - min_r, p["c"] - min_c
        shifted.append({**p, "r": nr, "c": nc})
        dr, dc = (1, 0) if p["dir"] == "down" else (0, 1)
        for i, ch in enumerate(p["word"]):
            sol[nr + dr * i][nc + dc * i] = ch

    # Number the starting cells (standard crossword numbering).
    number_at = {}
    n = 0
    for rr in range(H):
        for cc in range(W):
            if sol[rr][cc] is None:
                continue
            starts_across = (cc == 0 or sol[rr][cc - 1] is None) and \
                            (cc + 1 < W and sol[rr][cc + 1] is not None)
            starts_down = (rr == 0 or sol[rr - 1][cc] is None) and \
                          (rr + 1 < H and sol[rr + 1][cc] is not None)
            if starts_across or starts_down:
                n += 1
                number_at[(rr, cc)] = n

    across, down = [], []
    for p in shifted:
        num = number_at.get((p["r"], p["c"]))
        entry = {
            "num": num, "clue": p["clue"], "answer": p["word"],
            "row": p["r"], "col": p["c"], "dir": p["dir"], "len": len(p["word"]),
        }
        (across if p["dir"] == "across" else down).append(entry)

    across.sort(key=lambda e: e["num"])
    down.sort(key=lambda e: e["num"])

    return {
        "height": H,
        "width": W,
        "solution": sol,
        "numbers": {f"{r},{c}": num for (r, c), num in number_at.items()},
        "across": across,
        "down": down,
        "word_count": len(shifted),
    }


def generate_crossword(flat_words, target=50, size=45, attempts=12, seed=None):
    """Generate a crossword with at least `target` words if possible.
    Tries multiple shuffles and keeps the densest result."""
    if seed is not None:
        random.seed(seed)

    best_placed = None
    for _ in range(attempts):
        pool = flat_words[:]
        random.shuffle(pool)
        # Longest first improves interlock; keep some shuffle for variety.
        pool.sort(key=lambda wc: len(wc[0]), reverse=True)
        placed, _ = _generate_once(pool, size, target)
        if best_placed is None or len(placed) > len(best_placed):
            best_placed = placed
        if len(best_placed) >= target:
            break

    return _trim_and_number(best_placed, size)
