import math, threading
import numpy as np
import customtkinter as ctk
import moderngl as mgl
from pyopengltk import OpenGLFrame
from cube import CubeState, PIECE_POSITIONS, MOVE_AXIS, MOVE_LAYER, solve

# ── Rubik face colors ──
COLORS = {
    0: (1.0, 1.0, 1.0), 1: (1.0, 1.0, 0.0), 2: (1.0, 0.27, 0.27),
    3: (1.0, 0.53, 0.0), 4: (0.0, 0.8, 0.27), 5: (0.27, 0.27, 1.0),
    6: (0.07, 0.07, 0.08),
}

# ── UI colors ──
BG_DEEP = "#0A0A0F"
BG_CARD = "#14141F"
BG_SURF = "#1A1A2E"
BORDER_SUBTLE = "#2A2A3E"
TEXT_PRIMARY = "#E2E8F0"
TEXT_MUTED = "#8892A0"
BLUE_PRIMARY = "#3B82F6"
BLUE_GLOW = "#60A5FA"
ORANGE_CTA = "#F97316"
GREEN_OK = "#22C55E"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def m_trans(x, y, z):
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = [x, y, z]; return m

def m_persp(fov, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov) * 0.5)
    return np.float32([
        [f/aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far+near)/(near-far), 2*far*near/(near-far)],
        [0, 0, -1, 0],
    ])

def m_rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.float32([[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]])

def m_rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.float32([[c,0,s,0],[0,1,0,0],[-s,0,c,0],[0,0,0,1]])

def m_rot_axis(axis, a):
    m = np.eye(4, dtype=np.float32)
    ax, ay, az = [float(x) for x in axis]
    n = math.sqrt(ax*ax+ay*ay+az*az) or 1
    ax, ay, az = ax/n, ay/n, az/n
    c, s = math.cos(a), math.sin(a)
    m[:3, :3] = [
        [c+ax*ax*(1-c),   ax*ay*(1-c)-az*s, ax*az*(1-c)+ay*s],
        [ay*ax*(1-c)+az*s, c+ay*ay*(1-c),   ay*az*(1-c)-ax*s],
        [az*ax*(1-c)-ay*s, az*ay*(1-c)+ax*s, c+az*az*(1-c)],
    ]; return m


# ── Cubie geometry: 6 faces × 6 verts = 36 verts ──
# Face order matches CubeState._data: +X, -X, +Y, -Y, +Z, -Z
# Each vertex: pos(3) + normal(3) + uv(2) = 8 floats × 36 = 288 floats
def _make_cubie():
    HS = 0.475; T = 0.35  # half-size, bevel-tilt
    uvs = [(0,0),(1,0),(1,1),(1,1),(0,1),(0,0)]
    faces = [
        ([(HS,-HS,-HS),(HS,-HS,HS),(HS,HS,HS),(HS,HS,HS),(HS,HS,-HS),(HS,-HS,-HS)], (1,0,0)),
        ([(-HS,-HS,HS),(-HS,-HS,-HS),(-HS,HS,-HS),(-HS,HS,-HS),(-HS,HS,HS),(-HS,-HS,HS)], (-1,0,0)),
        ([(-HS,HS,-HS),(HS,HS,-HS),(HS,HS,HS),(HS,HS,HS),(-HS,HS,HS),(-HS,HS,-HS)], (0,1,0)),
        ([(-HS,-HS,HS),(HS,-HS,HS),(HS,-HS,-HS),(HS,-HS,-HS),(-HS,-HS,-HS),(-HS,-HS,HS)], (0,-1,0)),
        ([(-HS,-HS,HS),(HS,-HS,HS),(HS,HS,HS),(HS,HS,HS),(-HS,HS,HS),(-HS,-HS,HS)], (0,0,1)),
        ([(HS,-HS,-HS),(-HS,-HS,-HS),(-HS,HS,-HS),(-HS,HS,-HS),(HS,HS,-HS),(HS,-HS,-HS)], (0,0,-1)),
    ]
    data = []
    for verts, fn in faces:
        for v, uv in zip(verts, uvs):
            data.extend(v)
            vx, vy, vz = v
            if   fn[0] != 0: n = np.array([fn[0], -(vy/HS)*T, -(vz/HS)*T], dtype=np.float32)
            elif fn[1] != 0: n = np.array([-(vx/HS)*T, fn[1], -(vz/HS)*T], dtype=np.float32)
            else:            n = np.array([-(vx/HS)*T, -(vy/HS)*T, fn[2]], dtype=np.float32)
            n /= np.linalg.norm(n); data.extend(n.tolist())
            data.extend(uv)
    return np.array(data, dtype=np.float32)

CV = _make_cubie()

# Background gradient quad (4 verts: pos2f + uv2f)
BG_VERTS = np.array([-1,-1,0,0, 1,-1,1,0, -1,1,0,1, 1,1,1,1], dtype=np.float32)


# ── GLSL shaders ──
VS = """
#version 330
uniform mat4 u_view_proj;
uniform sampler2D u_inst;
in vec3 in_vert;
in vec3 in_normal;
in vec2 in_uv;
out vec3 v_col;
out vec3 v_normal;
out vec3 v_pos;
out vec2 v_uv;
void main() {
    int i = gl_InstanceID;
    int b = i * 10;
    vec4 r0=texelFetch(u_inst,ivec2(b+0,0),0);
    vec4 r1=texelFetch(u_inst,ivec2(b+1,0),0);
    vec4 r2=texelFetch(u_inst,ivec2(b+2,0),0);
    vec4 r3=texelFetch(u_inst,ivec2(b+3,0),0);
    mat4 m = mat4(r0,r1,r2,r3);
    int f = gl_VertexID / 6;
    v_col = texelFetch(u_inst, ivec2(b+4+f,0),0).rgb;
    v_normal = mat3(m) * in_normal;
    vec4 wp = m * vec4(in_vert,1);
    v_pos = wp.xyz;
    v_uv = in_uv;
    gl_Position = u_view_proj * wp;
}"""
FS = """
#version 330
uniform vec3 u_light_dir;
uniform vec3 u_cam_pos;
uniform float u_ambient;
in vec3 v_col; in vec3 v_normal; in vec3 v_pos; in vec2 v_uv;
out vec4 f_col;
void main() {
    float cr=0.2; vec2 smin=vec2(cr),smax=vec2(1-cr);
    vec2 uc=clamp(v_uv,smin,smax);
    float a=1-smoothstep(cr-0.02,cr+0.02,length(v_uv-uc));
    vec3 base=mix(vec3(0.06,0.06,0.065),v_col,a);
    vec3 N=normalize(v_normal),L=normalize(u_light_dir);
    float df=max(dot(N,L),0);
    vec3 V=normalize(u_cam_pos-v_pos),H=normalize(L+V);
    float sp=pow(max(dot(N,H),0),32);
    f_col=vec4(base*u_ambient+base*df*(1-u_ambient)+vec3(1)*sp*0.4,1);
}"""

BG_VS = """#version 330
in vec2 in_pos; in vec2 in_uv; out vec2 v_uv;
void main(){v_uv=in_uv;gl_Position=vec4(in_pos,1,1);}"""
BG_FS = """#version 330
in vec2 v_uv; out vec4 f;
void main(){
    float d=length(v_uv-vec2(0.5));
    vec3 c1=vec3(0.042,0.042,0.058),c2=vec3(0.01,0.01,0.018);
    f=vec4(mix(c1,c2,smoothstep(0,0.7,d)),1);
}"""


class CubeCanvas(OpenGLFrame):
    def __init__(self, master, app, **kw):
        self.app = app
        super().__init__(master, **kw)
        self.animate = 16
        self._init_done = False

    def tkResize(self, evt):
        self.width, self.height = evt.width, evt.height
        if self.winfo_ismapped() and self._init_done:
            self._display()

    def initgl(self):
        if self._init_done: return
        try:
            self.ctx = mgl.create_context(require=330)
            self.ctx.enable(mgl.DEPTH_TEST)

            # Background
            self.bg_prog = self.ctx.program(vertex_shader=BG_VS, fragment_shader=BG_FS)
            self.bg_vao = self.ctx.vertex_array(
                self.bg_prog,
                [(self.ctx.buffer(BG_VERTS.tobytes()), '2f 2f', 'in_pos', 'in_uv')],
            )

            # Cube
            self.prog = self.ctx.program(vertex_shader=VS, fragment_shader=FS)
            self.vao = self.ctx.vertex_array(
                self.prog,
                [(self.ctx.buffer(CV.tobytes()), '3f 3f 2f', 'in_vert', 'in_normal', 'in_uv')],
            )
            self.inst_tex = self.ctx.texture(
                (270, 1), 4, dtype='f4',
                data=np.zeros((270, 4), dtype='f4').tobytes(),
            )
            self.inst_tex.repeat_x = False
            self.inst_tex.repeat_y = False
            self.inst_tex.filter = (mgl.NEAREST, mgl.NEAREST)
            self.inst_tex.use(0)
            self.prog['u_inst'] = 0

            # Light uniforms
            ld = np.array([0.5, 1.0, 0.3], dtype=np.float32)
            ld /= np.linalg.norm(ld)
            self.prog['u_light_dir'].write(ld.tobytes())
            self.prog['u_ambient'].write(np.float32(0.25).tobytes())

            self._init_done = True
            self.after(16, self._display)
        except Exception as e:
            print("initgl error:", e)

    def update_inst(self, cube, anim=None):
        data = np.zeros((27, 10, 4), dtype=np.float32)
        for pi in range(27):
            pos = PIECE_POSITIONS[pi]
            model = m_trans(*pos)
            if anim and anim['active'] and pos[anim['axis']] == anim['layer']:
                av = [1,0,0] if anim['axis']==0 else ([0,1,0] if anim['axis']==1 else [0,0,1])
                model = m_rot_axis(av, anim['angle']) @ model
            m = model.T
            data[pi,0]=m[0]; data[pi,1]=m[1]; data[pi,2]=m[2]; data[pi,3]=m[3]
            for fi in range(6):
                c = COLORS.get(cube._data[pi, fi], (0.07,0.07,0.07))
                data[pi,4+fi] = (*c, 0.0)
        self.inst_tex.write(data.tobytes())

    def redraw(self):
        app = self.app
        w, h = self.width or 1, self.height or 1

        self.ctx.viewport = (0, 0, w, h)

        self.ctx.clear(0.035, 0.035, 0.05, 1.0)

        # Background
        self.ctx.disable(mgl.DEPTH_TEST)
        self.bg_vao.render(mgl.TRIANGLE_STRIP)
        self.ctx.enable(mgl.DEPTH_TEST)

        self.update_inst(app.cube, app.anim)

        aspect = w / max(h, 1)
        proj = m_persp(40, aspect, 0.1, 20.0)

        cp, sp = math.cos(app.pitch), math.sin(app.pitch)
        cy, sy = math.cos(app.yaw), math.sin(app.yaw)
        eye = np.array([app.dist*cp*sy, app.dist*sp, app.dist*cp*cy], dtype=np.float32)
        fwd = -eye / app.dist
        right = np.cross(np.array([0,1,0], dtype=np.float32), fwd)
        rn = np.linalg.norm(right)
        if rn < 1e-8:
            right = np.array([1,0,0], dtype=np.float32)
        else:
            right /= rn
        up = np.cross(fwd, right)
        view = np.eye(4, dtype=np.float32)
        view[0,:3]=right; view[1,:3]=up; view[2,:3]=-fwd
        view[:3,3]=[-np.dot(right,eye), -np.dot(up,eye), np.dot(fwd,eye)]

        self.prog['u_cam_pos'].write(eye.tobytes())
        self.prog['u_ambient'].write(np.float32(app.ambient).tobytes())
        self.prog['u_view_proj'].write((proj @ view).T.astype('f4').tobytes())

        self.vao.render(instances=27)


class CubeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Rubik's Cube")
        self.after(0, lambda: self.state('zoomed'))
        self.minsize(900, 600)

        self.cube = CubeState()
        self.yaw = math.pi / 6
        self.pitch = -math.pi / 9
        self.dist = 8.0
        self.move_count = 0
        self.ambient = 0.25
        self.speed = 3.0
        self.move_queue = []
        self._counting = True
        self.anim = {'active':False,'move':'','axis':0,'layer':0,
                     'target':0.0,'elapsed':0.0,'angle':0.0}

        self.grid_columnconfigure(0, minsize=280, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color=BG_CARD, border_width=0, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        right = ctk.CTkFrame(self, fg_color=BG_DEEP, border_width=0, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.canvas = CubeCanvas(right, self)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # ── Sidebar ──
        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.pack(fill="x", pady=(24,16), padx=20)
        ctk.CTkLabel(hdr, text="RUBIK'S CUBE",
                     font=("Segoe UI",20,"bold"), text_color=BLUE_GLOW).pack(anchor="w")
        ctk.CTkLabel(hdr, text="3D Solver & Animator",
                     font=("Segoe UI",11), text_color=TEXT_MUTED).pack(anchor="w", pady=(2,0))

        stat = ctk.CTkFrame(left, fg_color=BG_SURF,
                            border_color=BORDER_SUBTLE, border_width=1, corner_radius=12)
        stat.pack(fill="x", padx=20, pady=(0,16))
        inner = ctk.CTkFrame(stat, fg_color="transparent")
        inner.pack(pady=12, padx=16)
        ctk.CTkLabel(inner, text="MOVES",
                     font=("Segoe UI",9,"bold"), text_color=TEXT_MUTED).pack(anchor="center")
        self.moves_lbl = ctk.CTkLabel(inner, text="0",
                                      font=("Segoe UI",36,"bold"), text_color=TEXT_PRIMARY)
        self.moves_lbl.pack(anchor="center", pady=(4,0))

        spd = ctk.CTkFrame(left, fg_color="transparent")
        spd.pack(fill="x", padx=20, pady=(0,12))
        ctk.CTkLabel(spd, text="SPEED",
                     font=("Segoe UI",9,"bold"), text_color=TEXT_MUTED).pack(anchor="w")
        sr = ctk.CTkFrame(spd, fg_color="transparent")
        sr.pack(fill="x", pady=(6,0))
        self.sl = ctk.CTkSlider(sr, from_=1.0, to=10.0, number_of_steps=36, width=140,
                                command=lambda v: (setattr(self,'speed',v),
                                                   self.sl_lbl.configure(text=f'{v:.2f}x')))
        self.sl.set(3.0); self.sl.pack(side="left")
        self.sl_lbl = ctk.CTkLabel(sr, text="3.00x", width=44,
                                   font=("Segoe UI",11,"bold"), text_color=BLUE_GLOW)
        self.sl_lbl.pack(side="left", padx=(8,0))

        amb = ctk.CTkFrame(left, fg_color="transparent")
        amb.pack(fill="x", padx=20, pady=(0,12))
        ctk.CTkLabel(amb, text="AMBIENT",
                     font=("Segoe UI",9,"bold"), text_color=TEXT_MUTED).pack(anchor="w")
        ar = ctk.CTkFrame(amb, fg_color="transparent")
        ar.pack(fill="x", pady=(6,0))
        self.al = ctk.CTkSlider(ar, from_=0.0, to=1.0, number_of_steps=40, width=140,
                                command=lambda v: (setattr(self,'ambient',v),
                                                   self.al_lbl.configure(text=f'{v:.2f}')))
        self.al.set(0.25); self.al.pack(side="left")
        self.al_lbl = ctk.CTkLabel(ar, text="0.25", width=44,
                                   font=("Segoe UI",11,"bold"), text_color=BLUE_GLOW)
        self.al_lbl.pack(side="left", padx=(8,0))

        act = ctk.CTkFrame(left, fg_color="transparent")
        act.pack(fill="x", padx=20, pady=(0,12))
        ctk.CTkButton(act, text="Scramble", width=72,
                      fg_color=ORANGE_CTA, hover_color="#D95D0E",
                      font=("Segoe UI",12,"bold"), command=self.scramble
                      ).pack(side="left",padx=(0,6))
        ctk.CTkButton(act, text="Solve", width=72,
                      fg_color=GREEN_OK, hover_color="#16A34A",
                      font=("Segoe UI",12,"bold"), command=self.solve_it
                      ).pack(side="left",padx=3)
        ctk.CTkButton(act, text="Reset", width=72,
                      fg_color="#475569", hover_color="#334155",
                      font=("Segoe UI",12,"bold"), command=self.reset
                      ).pack(side="left",padx=(6,0))

        hints = ctk.CTkFrame(left, fg_color="transparent")
        hints.pack(fill="x", side="bottom", padx=20, pady=(0,20))
        ctk.CTkLabel(hints, text="LMB: Y-rotate · RMB: X-rotate · Scroll to zoom",
                     font=("Segoe UI",10), text_color=TEXT_MUTED).pack()

        self._dlx=self._dly=0.0
        self.canvas.bind("<ButtonPress-1>",self._press_l)
        self.canvas.bind("<B1-Motion>",self._drag_l)
        self.canvas.bind("<ButtonPress-3>",self._press_r)
        self.canvas.bind("<B3-Motion>",self._drag_r)
        self.canvas.bind("<MouseWheel>",self._wheel)
        self._t0=0
        self.after(16, self._tick)

    def start_anim(self, move):
        a=MOVE_AXIS[move]
        self.anim.update(active=True,move=move,axis=a[0],layer=MOVE_LAYER[move],
                         target=-a[1]*math.pi/2,elapsed=0.0,angle=0.0)

    def qmove(self, move):
        if move.endswith('2'): self.qmove(move[0]);self.qmove(move[0]);return
        if not self.anim['active']: self.start_anim(move)
        else: self.move_queue.append(move)

    def _press_l(self,e): self._dlx=e.x
    def _drag_l(self,e):
        self.yaw+=(e.x-self._dlx)*0.008; self._dlx=e.x
    def _press_r(self,e): self._dly=e.y
    def _drag_r(self,e):
        self.pitch=max(-1.4,min(1.4,self.pitch+(e.y-self._dly)*0.008)); self._dly=e.y
    def _wheel(self,e): self.dist=max(3.0,min(12.0,self.dist-e.delta*0.02))

    def scramble(self):
        self.move_queue.clear();self.anim['active']=False;self._counting=False
        _,mv=CubeState().randomize(20)
        for m in mv: self.qmove(m)

    def solve_it(self):
        if self.cube.is_solved(): return
        self.move_queue.clear();self.anim['active']=False
        self.move_count=0; self._counting=True
        threading.Thread(target=lambda:[self.move_queue.append(m) for m in solve(self.cube)] or None,
                         daemon=True).start()

    def reset(self):
        self.move_queue.clear();self.anim['active']=False
        self.cube=CubeState();self.move_count=0;self.dist=8.0

    def _tick(self):
        now=self.tk.call('clock','milliseconds')
        dt=min(now-self._t0,200)/1000;self._t0=now
        if self.anim['active']:
            self.anim['elapsed']+=dt
            dur=0.3/self.speed
            t=min(self.anim['elapsed']/dur,1.0)
            self.anim['angle']=self.anim['target']*(t*t*(3-2*t))
            if t>=1.0:
                self.cube=self.cube.apply_move(self.anim['move'])
                if self._counting: self.move_count+=1
                self.anim['active']=False
                if self.move_queue: self.start_anim(self.move_queue.pop(0))
        elif self.move_queue:
            self.start_anim(self.move_queue.pop(0))
        self.moves_lbl.configure(text=str(self.move_count))
        self.after(16,self._tick)


if __name__=='__main__':
    CubeApp().mainloop()
