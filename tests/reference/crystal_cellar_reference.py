from __future__ import annotations

from collections import deque
from dataclasses import dataclass

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


@dataclass(frozen=True)
class BoardCase:
    name: str
    rows: tuple[str, ...]

    def to_input(self) -> str:
        width = len(self.rows[0])
        body = "\n".join(self.rows)
        return f"1\n{self.name} {len(self.rows)} {width}\n{body}\n"


def parse_case(case: BoardCase):
    grid = [list(row) for row in case.rows]
    start = None
    exit_pos = None
    crates = []
    plates = set()
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "@":
                start = (r, c)
                grid[r][c] = "."
            elif ch == "X":
                exit_pos = (r, c)
            elif ch == "o":
                crates.append((r, c))
                grid[r][c] = "."
            elif ch == "p":
                plates.add((r, c))
    assert start is not None
    assert exit_pos is not None
    return grid, start, exit_pos, tuple(sorted(crates)), plates


def solve(case: BoardCase) -> str:
    grid, start, exit_pos, crates, plates = parse_case(case)
    rows, cols = len(grid), len(grid[0])

    def doors_open(boxes: tuple[tuple[int, int], ...]) -> bool:
        return not plates or plates.issubset(set(boxes))

    def inside(pos: tuple[int, int]) -> bool:
        r, c = pos
        return 0 <= r < rows and 0 <= c < cols

    def base_passable(
        pos: tuple[int, int],
        open_doors: bool,
        collapsed: frozenset[tuple[int, int]],
    ) -> bool:
        if not inside(pos):
            return False
        if pos in collapsed:
            return False
        tile = grid[pos[0]][pos[1]]
        if tile == "#":
            return False
        return not (tile == "D" and not open_doors)

    def slide_crate(
        box: tuple[int, int],
        direction: tuple[int, int],
        boxes: tuple[tuple[int, int], ...],
        open_doors: bool,
        collapsed: frozenset[tuple[int, int]],
    ) -> tuple[tuple[int, int], frozenset[tuple[int, int]]] | None:
        occupied = set(boxes)
        occupied.remove(box)
        nr, nc = box[0] + direction[0], box[1] + direction[1]
        pos = (nr, nc)
        touched = set()
        if not base_passable(pos, open_doors, collapsed) or pos in occupied:
            return None
        while grid[pos[0]][pos[1]] in "~c" and pos not in collapsed:
            if grid[pos[0]][pos[1]] == "c":
                touched.add(pos)
            nxt = (pos[0] + direction[0], pos[1] + direction[1])
            if not base_passable(nxt, open_doors, collapsed) or nxt in occupied:
                return None
            pos = nxt
        return pos, frozenset(set(collapsed) | touched)

    start_collapsed: frozenset[tuple[int, int]] = frozenset()
    start_state = (start, crates, start_collapsed)
    seen = {start_state}
    queue = deque([(start, crates, start_collapsed, 0)])
    while queue:
        player, boxes, collapsed, steps = queue.popleft()
        if player == exit_pos:
            return f"{case.name} {steps}\n"
        box_set = set(boxes)
        open_doors = doors_open(boxes)
        for dr, dc in DIRS:
            nxt = (player[0] + dr, player[1] + dc)
            if nxt in box_set:
                pushed = slide_crate(nxt, (dr, dc), boxes, open_doors, collapsed)
                if pushed is None:
                    continue
                landing, new_collapsed = pushed
                new_boxes = tuple(sorted(landing if b == nxt else b for b in boxes))
                new_state = (nxt, new_boxes, new_collapsed)
            else:
                if not base_passable(nxt, open_doors, collapsed):
                    continue
                new_state = (nxt, boxes, collapsed)
            if new_state not in seen:
                seen.add(new_state)
                queue.append((new_state[0], new_state[1], new_state[2], steps + 1))
    return f"{case.name} IMPOSSIBLE\n"


HAND_CASES = [
    BoardCase("plain_walk", ("#####", "#@.X#", "#####")),
    BoardCase("wall_detour", ("#######", "#@#..X#", "#...###", "#######")),
    BoardCase("single_push", ("#######", "#@o.X.#", "#######")),
    BoardCase("blocked_push", ("######", "#@o#X#", "#....#", "######")),
    BoardCase("door_without_plate", ("#######", "#@D.X.#", "#######")),
    BoardCase("plate_opens_corridor", ("#########", "#@....DX#", "#.o.....#", "#.p.....#", "#########")),
    BoardCase("two_plate_lock", ("############", "#@.....D.X##", "#.o........#", "#.p...o....#", "#.....p....#", "############")),
    BoardCase("ice_to_plate", ("##########", "#@....D.X#", "#..o~~p###", "###....###", "##########")),
    BoardCase("ice_bad_landing", ("#######", "#@o~~X#", "#######")),
    BoardCase("cracked_shortcut_closes", ("########", "#@ocX..#", "#......#", "#......#", "########")),
    BoardCase("crate_blocks_exit", ("#######", "#@oX..#", "#######")),
    BoardCase("around_after_push", ("#######", "#@o...#", "#.##X.#", "#.....#", "#######")),
    BoardCase("door_detour_preserved", ("#########", "#@D...X.#", "#.#####.#", "#.......#", "#########")),
]


GENERATED_CASES = [
    BoardCase("gen_plate_lane_01", ("#########", "#@....DX#", "#.o.....#", "#.p.....#", "#########")),
    BoardCase("gen_plate_lane_02", ("##########", "#@.....DX#", "#..o.....#", "#..p.....#", "##########")),
    BoardCase("gen_plate_lane_03", ("###########", "#@......DX#", "#...o.....#", "#...p.....#", "###########")),
    BoardCase("gen_ice_lane_01", ("#########", "#@...D.X#", "#..o~p###", "###...###", "#########")),
    BoardCase("gen_ice_lane_02", ("##########", "#@....D.X#", "#..o~~p###", "###....###", "##########")),
    BoardCase("gen_ice_lane_03", ("###########", "#@.....D.X#", "#..o~~~p###", "###.....###", "###########")),
    BoardCase("gen_crack_detour_01", ("########", "#@oc.X.#", "#......#", "#......#", "########")),
    BoardCase("gen_crack_detour_02", ("########", "#@o.cX.#", "#......#", "#......#", "########")),
    BoardCase("gen_crack_detour_03", ("########", "#.Xco@.#", "#......#", "#......#", "########")),
    BoardCase("gen_double_01", ("############", "#@.....D.X##", "#.o........#", "#.p...o....#", "#.....p....#", "############")),
    BoardCase("gen_double_02", ("#############", "#@......D.X##", "#..o........#", "#..p...o....#", "#......p....#", "#############")),
    BoardCase("gen_branch_01", ("#########", "#@o.pD.X#", "#..#...##", "#......##", "#########")),
    BoardCase("gen_branch_02", ("##########", "#@o..pD.X#", "#..##...##", "#.......##", "##########")),
    BoardCase("gen_impossible_01", ("########", "#@o#pDX#", "#.....##", "########")),
    BoardCase("gen_impossible_02", ("########", "#@o~~#X#", "#..pD.##", "########")),
    BoardCase("gen_no_crate_maze_01", ("########", "#@....X#", "#.####.#", "#......#", "########")),
    BoardCase("gen_no_crate_maze_02", ("########", "#@#...X#", "#.#.####", "#......#", "########")),
    BoardCase("gen_slide_turn_01", ("##########", "#@o~..X.##", "#...#...##", "##########")),
    BoardCase("gen_slide_turn_02", ("###########", "#@o~~..X.##", "#....#...##", "###########")),
    BoardCase("gen_reopen_01", ("###########", "#@o.pD..X##", "#...o....##", "###########")),
    BoardCase("gen_reopen_02", ("############", "#@o..pD..X##", "#....o....##", "############")),
    BoardCase("gen_hall_lock_01", ("##########", "#@o.pD..X#", "#..#....##", "#.......##", "##########")),
    BoardCase("gen_hall_lock_02", ("###########", "#@o~~pD..X#", "#...#....##", "#........##", "###########")),
]


ALL_CASES = HAND_CASES + GENERATED_CASES
