import numpy as np
import random
from rubik_solver.NaiveCube import NaiveCube
from rubik_solver import utils

# Face direction constants (axis, sign)
FACE_DIRS = [
    (0, 1),   # 0: +X = R (right, red)
    (0, -1),  # 1: -X = L (left, orange)
    (1, 1),   # 2: +Y = U (up, white)
    (1, -1),  # 3: -Y = D (down, yellow)
    (2, 1),   # 4: +Z = F (front, green)
    (2, -1),  # 5: -Z = B (back, blue)
]
FACE_NAMES = {0: 'R', 1: 'L', 2: 'U', 3: 'D', 4: 'F', 5: 'B'}
# Color scheme matching rubik_solver: U=yellow, D=white, R=green, L=blue, F=red, B=orange
# Our color codes: 0=W, 1=Y, 2=R, 3=O, 4=G, 5=B
COLOR_OF_FACE = [4, 5, 1, 0, 2, 3]  # R=4(green), L=5(blue), U=1(yellow), D=0(white), F=2(red), B=3(orange)
FACE_NAME_TO_IDX = {v: k for k, v in FACE_NAMES.items()}

ALL_MOVES = ['U', "U'", 'U2', 'D', "D'", 'D2',
             'R', "R'", 'R2', 'L', "L'", 'L2',
             'F', "F'", 'F2', 'B', "B'", 'B2']

MOVE_AXIS = {
    'U': (1, 1), "U'": (1, -1), 'U2': (1, 2),
    'D': (1, -1), "D'": (1, 1), 'D2': (1, 2),
    'R': (0, 1), "R'": (0, -1), 'R2': (0, 2),
    'L': (0, -1), "L'": (0, 1), 'L2': (0, 2),
    'F': (2, 1), "F'": (2, -1), 'F2': (2, 2),
    'B': (2, -1), "B'": (2, 1), 'B2': (2, 2),
}

MOVE_LAYER = {
    'R': 1, "R'": 1, 'R2': 1,
    'L': -1, "L'": -1, 'L2': -1,
    'U': 1, "U'": 1, 'U2': 1,
    'D': -1, "D'": -1, 'D2': -1,
    'F': 1, "F'": 1, 'F2': 1,
    'B': -1, "B'": -1, 'B2': -1,
}

PIECE_POSITIONS = [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)]


def _rotate_face_indices(axis, sign, coords):
    """Rotate coordinates around an axis. sign=1 is clockwise looking
    toward negative axis direction (standard Rubik's notation)."""
    x, y, z = coords
    if axis == 0:  # R/L moves (around X)
        return (x, z, -y) if sign == 1 else (x, -z, y)
    elif axis == 1:  # U/D moves (around Y)
        return (-z, y, x) if sign == 1 else (z, y, -x)
    else:  # F/B moves (around Z)
        return (y, -x, z) if sign == 1 else (-y, x, z)


def _rotate_face_normal(axis, sign, normal):
    daxis, dsign = normal
    vec = [0, 0, 0]
    vec[daxis] = dsign
    rx, ry, rz = _rotate_face_indices(axis, sign, tuple(vec))
    for i in range(3):
        val = (rx, ry, rz)[i]
        if val != 0:
            return (i, int(val))
    return normal


class CubeState:
    def __init__(self, state_array=None):
        if state_array is not None:
            self._data = np.array(state_array, dtype=np.int32)
        else:
            self._data = np.full((27, 6), 6, dtype=np.int32)
            for pi, (px, py, pz) in enumerate(PIECE_POSITIONS):
                for fi, (daxis, dsign) in enumerate(FACE_DIRS):
                    coord = (px, py, pz)[daxis]
                    if coord == dsign:
                        self._data[pi, fi] = COLOR_OF_FACE[fi]

    def _pos_to_idx(self, pos):
        x, y, z = pos
        return (x + 1) * 9 + (y + 1) * 3 + (z + 1)

    def _apply_rotation(self, axis, layer, sign):
        new_data = self._data.copy()
        for pi, pos in enumerate(PIECE_POSITIONS):
            if pos[axis] != layer:
                continue
            new_pos = _rotate_face_indices(axis, sign, pos)
            new_pi = self._pos_to_idx(new_pos)
            for fi in range(6):
                rotated_fi_tuple = _rotate_face_normal(axis, sign, FACE_DIRS[fi])
                for rfi, fd in enumerate(FACE_DIRS):
                    if fd == rotated_fi_tuple:
                        new_data[new_pi, rfi] = self._data[pi, fi]
                        break
        self._data = new_data

    def apply_move(self, move):
        axis, sign = MOVE_AXIS[move]
        layer = MOVE_LAYER[move]
        is_double = sign == 2
        rot_sign = MOVE_AXIS[move.replace('2', '')][1] if is_double else sign
        result = self.copy()
        result._apply_rotation(axis, layer, rot_sign)
        if is_double:
            result._apply_rotation(axis, layer, rot_sign)
        return result

    def apply_moves(self, moves):
        state = self
        for move in moves:
            state = state.apply_move(move)
        return state

    def randomize(self, n):
        moves = []
        last_axis = None
        for _ in range(n):
            move = random.choice(['U', 'D', 'R', 'L', 'F', 'B'])
            axis = MOVE_AXIS[move][0]
            while last_axis is not None and axis == last_axis:
                move = random.choice(['U', 'D', 'R', 'L', 'F', 'B'])
                axis = MOVE_AXIS[move][0]
            variant = random.choice(['', "'", '2'])
            full_move = move + variant
            moves.append(full_move)
            last_axis = axis
        return self.apply_moves(moves), moves

    def is_solved(self):
        for fi, (daxis, dsign) in enumerate(FACE_DIRS):
            expected_color = COLOR_OF_FACE[fi]
            for pi, pos in enumerate(PIECE_POSITIONS):
                coord = pos[daxis]
                if coord == dsign:
                    if self._data[pi, fi] != expected_color:
                        return False
        return True

    def copy(self):
        return CubeState(self._data.copy())

    def __eq__(self, other):
        return np.array_equal(self._data, other._data)

    def __hash__(self):
        return hash(self._data.tobytes())

    @staticmethod
    def _sticker_coord(face_idx, row, col):
        if face_idx == 0:   return (1, 1 - row, 1 - col)
        if face_idx == 1:   return (-1, 1 - row, col - 1)
        if face_idx == 2:   return (col - 1, 1, row - 1)
        if face_idx == 3:   return (col - 1, -1, 1 - row)
        if face_idx == 4:   return (col - 1, 1 - row, 1)
        return (1 - col, 1 - row, -1)

    def get_face_colors(self):
        faces = []
        for fi in range(6):
            face = np.zeros(9, dtype=np.int32)
            for r in range(3):
                for c in range(3):
                    pi = self._pos_to_idx(self._sticker_coord(fi, r, c))
                    face[r * 3 + c] = self._data[pi, fi]
            faces.append(face)
        return faces

    def _get_sticker_at(self, face_idx, row, col):
        pi = self._pos_to_idx(self._sticker_coord(face_idx, row, col))
        return self._data[pi, face_idx]

    def extract_flat_stickers(self):
        arr = np.zeros(54, dtype=np.int32)
        idx = 0
        for fi in range(6):
            for r in range(3):
                for c in range(3):
                    arr[idx] = self._get_sticker_at(fi, r, c)
                    idx += 1
        return arr

    def to_naive_cube(self):
        """Convert to rubik_solver's NaiveCube for solving.

        NaiveCube.set_cube expects 54-char string in 'ULFRBD' face order
        with colors: w=white, y=yellow, r=red, o=orange, g=green, b=blue.
        This now matches our color scheme (0=W→w, 1=Y→y, 2=R→r, 3=O→o, 4=G→g, 5=B→b).
        """
        color_chars = {0: 'w', 1: 'y', 2: 'r', 3: 'o', 4: 'g', 5: 'b'}
        face_order = [2, 1, 4, 0, 5, 3]  # U, L, F, R, B, D in our face idx
        fc = ''
        for fi in face_order:
            for r in range(3):
                for c in range(3):
                    pi = self._pos_to_idx(self._sticker_coord(fi, r, c))
                    fc += color_chars[self._data[pi, fi]]
        nc = NaiveCube()
        nc.set_cube(fc)
        return nc


def solve(cube_state, method='Kociemba'):
    """Solve a CubeState using rubik_solver. Returns list of move strings."""
    nc = cube_state.to_naive_cube()
    moves = utils.solve(nc, method)
    return [str(m) for m in moves]


def self_test():
    cube = CubeState()
    assert cube.is_solved(), "Initial state should be solved"

    c2 = cube.apply_move('R').apply_move("R'")
    assert c2.is_solved(), f"R R' should be solved"

    for base in ['U', 'D', 'R', 'L', 'F', 'B']:
        inv = base + "'"
        c = cube.apply_move(base).apply_move(inv)
        assert c.is_solved(), f"{base} {inv} should be solved"

    for base in ['U', 'D', 'R', 'L', 'F', 'B']:
        dbl = base + '2'
        c1 = cube.apply_move(dbl)
        c2 = cube.apply_move(base).apply_move(base)
        assert c1 == c2, f"{dbl} should equal {base}{base}"

    scrambled, rand_moves = cube.randomize(5)
    inv_map = {}
    for m in ALL_MOVES:
        if m.endswith('2'):
            inv_map[m] = m
        elif "'" in m:
            inv_map[m] = m.replace("'", "")
        else:
            inv_map[m] = m + "'"
    reversed_moves = [inv_map[m] for m in reversed(rand_moves)]
    unscrambled = scrambled.apply_moves(reversed_moves)
    assert unscrambled.is_solved(), "Reverse of randomize should be solved"

    print("All cube state tests passed!")

    solution = solve(scrambled)
    solved = scrambled.apply_moves(solution)
    assert solved.is_solved(), "Solver should solve the cube"
    print(f"Solver test passed! ({len(solution)} moves)")


if __name__ == '__main__':
    self_test()
