# Rublik Cube Solver 3D

A 3D Rubik's Cube solver and animator built with Python, ModernGL, and CustomTkinter.

## Features

- **3D rendering** — OpenGL 3.3 via ModernGL with real-time lighting, beveled cubies, and smooth animations
- **Solver** — Kociemba algorithm via `rubik_solver`; solves any scramble in ~20 moves
- **Controls** — Scramble, Solve, Reset buttons + camera (LMB/RMB drag, scroll zoom)
- **Customize** — Adjustable speed and ambient lighting via sliders

## Requirements

- Python 3.10+
- OpenGL 3.3 capable GPU

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python rubik.py
```

## Controls

| Input | Action |
|-------|--------|
| Left drag | Y-axis rotation |
| Right drag | X-axis rotation |
| Scroll | Zoom |

## Project Structure

```
cube.py          — Cube state, moves, rotation, solver integration
rubik.py         — 3D GUI application (ModernGL + CustomTkinter)
requirements.txt — Dependencies
```

## How It Works

`CubeState` represents the cube as a 27×6 array (27 cubies × 6 face colors). Moves rotate slice coordinates and remap face normals. The solver converts to `rubik_solver`'s NaiveCube format and runs Kociemba's algorithm. The GUI renders each cubie as an instanced beveled quad with per-face colors and smooth stepped animation between moves.
