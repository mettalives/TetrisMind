import pygame
import random

# ================= CONFIG =================
CELL_SIZE = 30
COLS, ROWS = 10, 20
WIDTH, HEIGHT = COLS * CELL_SIZE, ROWS * CELL_SIZE
FPS = 60

COLORS = {
    'I': (0, 255, 255),
    'O': (255, 255, 0),
    'T': (128, 0, 128),
    'S': (0, 255, 0),
    'Z': (255, 0, 0),
    'J': (0, 0, 255),
    'L': (255, 165, 0),
}
BLACK = (0, 0, 0)
GRAY = (40, 40, 40)
WHITE = (255, 255, 255)

# ================= SHAPES (base) =================
SHAPES_BASE = {
    'I': [[1,1,1,1]],
    'O': [[1,1],[1,1]],
    'T': [[0,1,0],[1,1,1]],
    'S': [[0,1,1],[1,1,0]],
    'Z': [[1,1,0],[0,1,1]],
    'J': [[1,0,0],[1,1,1]],
    'L': [[0,0,1],[1,1,1]],
}

# ================= HELPERS & PRECOMPUTE =================
def rotate(shape):
    return [list(row) for row in zip(*shape[::-1])]

def build_rotations(base):
    """Return unique rotations (max 4) for a base shape."""
    rots = []
    cur = [row[:] for row in base]
    for _ in range(4):
        tup = tuple(tuple(r) for r in cur)
        if tup in {tuple(tuple(r) for r in s) for s in rots}:
            break
        rots.append([r[:] for r in cur])
        cur = rotate(cur)
    return rots

# Build rotation cache, piece->rotations list
ROTATIONS = {p: build_rotations(base) for p, base in SHAPES_BASE.items()}

# Quick index/lookup helpers to avoid repeated .keys()/.values()
PIECES = list(ROTATIONS.keys())
PIECE_TO_IDX = {p: i for i, p in enumerate(PIECES)}
COLOR_LIST = [COLORS[p] for p in PIECES]  # index 0 -> id 1 in grid

def create_grid():
    return [[0]*COLS for _ in range(ROWS)]

def valid_move(grid, shape, offset):
    ox, oy = offset
    # localize for speed
    cols = COLS; rows = ROWS; g = grid
    for y, row in enumerate(shape):
        for x, cell in enumerate(row):
            if cell:
                nx, ny = x + ox, y + oy
                if nx < 0 or nx >= cols or ny >= rows or (ny >= 0 and g[ny][nx]):
                    return False
    return True

def lock_piece(grid, shape, offset, color_idx):
    ox, oy = offset
    for y, row in enumerate(shape):
        for x, cell in enumerate(row):
            if cell:
                grid[y+oy][x+ox] = color_idx + 1  # stored as 1-based

def remove_lines(grid):
    # keep rows that have zeros; drop full rows
    new_grid = [row for row in grid if any(c == 0 for c in row)]
    lines = ROWS - len(new_grid)
    if lines:
        # prepend empty rows
        new_grid = [[0]*COLS for _ in range(lines)] + new_grid
    return new_grid, lines

# Combined heights + holes computation (single pass per column)
def get_heights_and_holes(grid):
    heights = [0]*COLS
    total_holes = 0
    for c in range(COLS):
        block_found = False
        holes_col = 0
        h = 0
        for r in range(ROWS):
            if grid[r][c]:
                if not block_found:
                    heights[c] = ROWS - r
                    block_found = True
                # once block_found, subsequent empty cells are holes
            else:
                if block_found:
                    holes_col += 1
        total_holes += holes_col
    return heights, total_holes

def bumpiness_from_heights(heights):
    s = 0
    for i in range(COLS-1):
        s += abs(heights[i] - heights[i+1])
    return s

def aggregate_height(heights):
    return sum(heights)

def evaluate(grid, lines):
    heights, holes = get_heights_and_holes(grid)
    return (
        -0.51066 * aggregate_height(heights)
        + 0.760666 * lines
        - 0.35663 * holes
        - 0.184483 * bumpiness_from_heights(heights)
    )

# ================= AI =================
def hard_drop(grid, shape, col):
    row = 0
    # start with local copies for speed
    while valid_move(grid, shape, (col, row+1)):
        row += 1
    return row

def best_move(grid, piece_name, rotations_list):
    """Search rotations & columns and return (best_col, best_rot_idx)."""
    best_score = -float('inf')
    best_col = 0
    best_rot = 0
    color_idx = PIECE_TO_IDX[piece_name]

    # Localize frequently used names for speed
    cols = COLS
    g = grid
    for rot_idx, shape in enumerate(rotations_list):
        width = len(shape[0])
        max_col = cols - width + 1
        for col in range(max_col):
            row = hard_drop(g, shape, col)
            if not valid_move(g, shape, (col, row)):
                continue

            # faster shallow copy of rows
            temp = [r[:] for r in g]
            lock_piece(temp, shape, (col, row), color_idx)
            temp, lines = remove_lines(temp)
            score = evaluate(temp, lines)

            if score > best_score:
                best_score = score
                best_col = col
                best_rot = rot_idx

    return best_col, best_rot

# ================= DRAW =================
def draw_grid(surface, grid):
    color_lookup = COLOR_LIST
    blk = BLACK; gry = GRAY
    cell = CELL_SIZE
    for y in range(ROWS):
        row = grid[y]
        for x in range(COLS):
            val = row[x]
            if val == 0:
                color = blk
            else:
                # grid stores 1-based index
                color = color_lookup[val-1]
            rect = pygame.Rect(x*cell, y*cell, cell, cell)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, gry, rect, 1)

def draw_piece(surface, shape, offset, color):
    ox, oy = offset
    cell = CELL_SIZE
    white = WHITE
    for y, row in enumerate(shape):
        for x, cellval in enumerate(row):
            if cellval:
                rect = pygame.Rect((ox+x)*cell, (oy+y)*cell, cell, cell)
                pygame.draw.rect(surface, color, rect)
                pygame.draw.rect(surface, white, rect, 2)

# ================= MAIN =================
pygame.init()
screen = pygame.display.set_mode((WIDTH+200, HEIGHT))
pygame.display.set_caption("Tetris AI - Optimized")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 24)

grid = create_grid()
bag = PIECES[:]  # start bag from PIECES order
random.shuffle(bag)

def next_piece():
    global bag
    if not bag:
        bag = PIECES[:]
        random.shuffle(bag)
    return bag.pop(0)

current_piece = next_piece()
current_rotations = ROTATIONS[current_piece]
current_shape = current_rotations[0]
pos_x, pos_y = 3, 0
score = 0
lines_total = 0
fall_speed = 1  # visual pixels per frame
target_y = 0
running = True

while running:
    screen.fill(BLACK)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # determine best placement on spawn
    if pos_y == 0:
        col, rot = best_move(grid, current_piece, current_rotations)
        pos_x = col
        current_shape = current_rotations[rot]
        target_y = hard_drop(grid, current_shape, pos_x)

    # smooth visual falling
    if pos_y < target_y:
        pos_y += fall_speed
    else:
        pos_y = target_y
        # lock piece (use PIECE_TO_IDX mapping)
        lock_piece(grid, current_shape, (pos_x, pos_y), PIECE_TO_IDX[current_piece])
        grid, lines = remove_lines(grid)
        lines_total += lines
        # scoring: level multiplier
        score += [0, 100, 300, 500, 800][min(lines, 4)] * (lines_total // 10 + 1)

        # next piece
        current_piece = next_piece()
        current_rotations = ROTATIONS[current_piece]
        current_shape = current_rotations[0]
        pos_x, pos_y = 3, 0
        target_y = 0

        if not valid_move(grid, current_shape, (pos_x, pos_y)):
            running = False

    draw_grid(screen, grid)
    draw_piece(screen, current_shape, (pos_x, int(pos_y)), COLORS[current_piece])
    screen.blit(font.render(f"Score: {score}", True, WHITE), (WIDTH+20, 50))
    screen.blit(font.render(f"Lines: {lines_total}", True, WHITE), (WIDTH+20, 90))

    pygame.display.flip()
    clock.tick(FPS)

print(f"GAME OVER → Score: {score} | Lines: {lines_total}")
pygame.quit()
