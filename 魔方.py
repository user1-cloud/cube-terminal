#!/usr/bin/env python3
"""
魔方游戏
"""

import curses
import math
import time
import sys
import ctypes
import queue
import random
from pynput import mouse
from pynput.keyboard import Controller, Key

def set_console_fullscreen():
    keyboard = Controller()
    # 模拟按下并释放 F11 键
    keyboard.press(Key.f11)
    keyboard.release(Key.f11)

# Windows下启用ANSI转义序列支持
if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    kernel32.SetConsoleMode(handle, mode.value | 0x0004)

# ============= 常量定义 =============
# 颜色定义: (名称, 字符, RGB, 初始面对应面)
_COLORS = [
    ('红色', '█', (255, 40, 40),   'F'),
    ('橙色', '█', (255, 140, 0),   'B'),
    ('蓝色', '█', (60, 100, 255),   'L'),
    ('绿色', '█', (70, 255, 70),   'R'),
    ('白色', '█', (255, 255, 255), 'U'),
    ('黄色', '█', (255, 255, 0),   'D'),
]

COLOR_NAMES = [c[0] for c in _COLORS]
COLOR_CHARS = [c[1] for c in _COLORS]
COLOR_RGB   = [c[2] for c in _COLORS]
INITIAL_FACE_COLOR = {c[3]: i for i, c in enumerate(_COLORS)}

# 面法向量（指向外部）
FACE_NORMALS = {
    'F': (0, 0, -1),    # 前面
    'B': (0, 0, 1),   # 后面
    'L': (-1, 0, 0),   # 左面
    'R': (1, 0, 0),    # 右面
    'U': (0, 1, 0),    # 上面
    'D': (0, -1, 0)    # 下面
}

# 动画参数
ANIMATION_DURATION = 0.3  # 秒
ROTATION_ANGLE = math.pi / 2  # 90度

# ============= 数学工具类 =============
class Vector3:
    """3D向量"""
    __slots__ = ('x', 'y', 'z')
    
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z
    
    def cross(self, other):
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )
    
    @property
    def length(self):
        return math.sqrt(self.dot(self))
    
    def normalized(self):
        l = self.length
        return Vector3(self.x/l, self.y/l, self.z/l) if l > 0 else Vector3(0, 0, 0)
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def __rmul__(self, scalar):
        return self.__mul__(scalar)
    
    def __eq__(self, other):
        if not isinstance(other, Vector3):
            return False
        return (abs(self.x - other.x) < 1e-6 and 
                abs(self.y - other.y) < 1e-6 and 
                abs(self.z - other.z) < 1e-6)
    
    def __repr__(self):
        return f"Vec3({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"

class Quaternion:
    """四元数"""
    __slots__ = ('w', 'x', 'y', 'z')
    
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = float(w)
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    @classmethod
    def from_axis_angle(cls, axis, angle):
        """从轴和角度创建四元数"""
        axis = axis.normalized()
        half_angle = angle / 2.0
        sin_half = math.sin(half_angle)
        
        return cls(
            math.cos(half_angle),
            axis.x * sin_half,
            axis.y * sin_half,
            axis.z * sin_half
        )
    
    def normalize(self):
        """归一化"""
        length = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if length == 0:
            return Quaternion(1, 0, 0, 0)
        return Quaternion(self.w/length, self.x/length, self.y/length, self.z/length)
    
    def conjugate(self):
        """共轭"""
        return Quaternion(self.w, -self.x, -self.y, -self.z)
    
    def multiply(self, other):
        """四元数乘法"""
        w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z
        x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y
        y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x
        z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w
        
        return Quaternion(w, x, y, z)
    
    def rotate_vector(self, vec):
        """旋转向量"""
        q_vec = Quaternion(0, vec.x, vec.y, vec.z)
        q_conj = self.conjugate()
        result = self.multiply(q_vec).multiply(q_conj)
        return Vector3(result.x, result.y, result.z)
    
    def __repr__(self):
        return f"Quat({self.w:.3f}, {self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

# ============= 颜色工具类 =============
class ColorConverter:
    """颜色转换工具类"""

    @staticmethod
    def rgb_to_256color(r, g, b):
        """将RGB值转换为256色模式中的颜色索引"""
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))

        # 灰度处理
        if r == g == b:
            if r < 8:
                return 232
            elif r > 247:
                return 255
            else:
                gray_index = int((r - 8) / 247 * 23)
                return 232 + gray_index

        # 彩色处理
        r_idx = int(r / 255 * 5)
        g_idx = int(g / 255 * 5)
        b_idx = int(b / 255 * 5)
        return 16 + 36 * r_idx + 6 * g_idx + b_idx

    @staticmethod
    def rgb_from_256color(ci):
        """从256色索引反查RGB（用于抖动误差计算）"""
        if 16 <= ci <= 231:
            ci -= 16
            r = (ci // 36) * 51
            g = ((ci % 36) // 6) * 51
            b = (ci % 6) * 51
            return (r, g, b)
        elif 232 <= ci <= 255:
            gray = 8 + (ci - 232) * 247 // 23
            return (gray, gray, gray)
        else:
            return (0, 0, 0)

    @staticmethod
    def apply_brightness(rgb, brightness):
        """应用亮度因子到RGB颜色"""
        r, g, b = rgb
        brightness = max(0.1, min(1.5, brightness))

        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)

        return (
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b))
        )

# ============= 鼠标控制器 =============
class MouseController:
    """鼠标控制"""
    def __init__(self):
        self.mouse_queue = queue.Queue()
        self.listener = None
        self.is_middle_pressed = False
        self.last_pos = (0, 0)
        
    def start(self):
        """启动鼠标监听"""
        def on_move(x, y):
            if self.is_middle_pressed:
                self.mouse_queue.put(('move', x, y))
        
        def on_click(x, y, button, pressed):
            if button == mouse.Button.middle:
                self.is_middle_pressed = pressed
                if pressed:
                    self.last_pos = (x, y)
                self.mouse_queue.put(('middle_click', x, y, pressed))

        self.listener = mouse.Listener(
            on_move=on_move,
            on_click=on_click,
        )
        self.listener.start()
    
    def stop(self):
        """停止鼠标监听"""
        if self.listener:
            self.listener.stop()
    
    def get_events(self):
        """获取所有鼠标事件"""
        events = []
        while not self.mouse_queue.empty():
            try:
                events.append(self.mouse_queue.get_nowait())
            except queue.Empty:
                break
        return events

# ============= 魔方块 =============
class RubiksCubePiece:
    """魔方块"""
    __slots__ = ('initial_position', 'current_position', 'piece_type', 
                 'local_rotation', 'initial_colors')
    
    def __init__(self, position, piece_type):
        """
        初始化魔方块
        position: 初始位置
        piece_type: 'corner'角块, 'edge'棱块, 'center'中心块
        """
        self.initial_position = Vector3(position.x, position.y, position.z)
        self.current_position = Vector3(position.x, position.y, position.z)
        self.piece_type = piece_type
        self.local_rotation = Quaternion(1, 0, 0, 0)  # 块的局部旋转
        self.initial_colors = {}  # 面的颜色信息 {'face_name': color_index}
        
        self._init_colors()
    
    def _init_colors(self):
        x, y, z = self.initial_position.x, self.initial_position.y, self.initial_position.z
        for face, (nx, ny, nz) in FACE_NORMALS.items():
            if (nx and x == nx) or (ny and y == ny) or (nz and z == nz):
                self.initial_colors[face] = INITIAL_FACE_COLOR[face]
    
    def rotate(self, axis, angle):
        """旋转块 - 更新位置和局部旋转"""
        rotation = Quaternion.from_axis_angle(axis, angle)
        self.current_position = rotation.rotate_vector(self.current_position)
        self.local_rotation = rotation.multiply(self.local_rotation).normalize()
    
    def get_face_corners(self, face_name):
        """获取指定面的四个角点（在块坐标系中）"""
        # 面的角点定义（相对于块中心，大小为1）
        # 注意：顶点顺序需要是逆时针，以确保法向量指向外部
        face_corners = {
            'F': [(-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)],
            'B': [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)],
            'L': [(-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)],
            'R': [(0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5)],
            'U': [(-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5)],
            'D': [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5)]
        }
        
        if face_name not in face_corners:
            return []
        
        # 应用块的局部旋转到角点
        corners = []
        for cx, cy, cz in face_corners[face_name]:
            corner = Vector3(cx, cy, cz)
            rotated_corner = self.local_rotation.rotate_vector(corner)
            corners.append(rotated_corner)
        
        return corners
    
    def get_current_face_color(self, face_name):
        return self.initial_colors.get(face_name)
    
    def reset(self):
        """重置块到初始状态"""
        self.current_position = Vector3(
            self.initial_position.x,
            self.initial_position.y,
            self.initial_position.z
        )
        self.local_rotation = Quaternion(1, 0, 0, 0)
    
    def __repr__(self):
        return f"{self.piece_type}{self.current_position}"

# ============= 魔方类 =============
class RubiksCube:
    """魔方类"""

    @staticmethod
    def _make_face_check(nx, ny, nz):
        if nx: return lambda pos: abs(pos.x - nx) < 0.1
        if ny: return lambda pos: abs(pos.y - ny) < 0.1
        return lambda pos: abs(pos.z - nz) < 0.1

    _FACE_POSITION_CHECK = {}
    for f, n in FACE_NORMALS.items():
        _FACE_POSITION_CHECK[f] = _make_face_check(*n)

    def __init__(self):
        self.pieces = []
        self.rotation = Quaternion(1, 0, 0, 0)  # 整体旋转
        self.scale = 25.0  # 增加缩放值，因为透视会缩小远处的物体
        self.position = Vector3(0, 0, 10)  # 将魔方向后移动，以便透视
        self.light_dir = Vector3(0.3, 0.5, -0.8).normalized()
        
        # 宽高比校正（终端字符通常是长方形，高度大约是宽度的2倍）
        self.aspect_ratio = 2.0  # 高度/宽度的比例
        
        # 透视投影参数
        self.camera_position = Vector3(0, 0, 0)  # 摄像机位置（原点）
        self.focal_length = 8.0  # 焦距，控制透视强度
        
        self._clear_animation()
        self.view_mapping = {k: k for k in FACE_NORMALS}
        
        # 创建魔方块
        self._create_pieces()
    
    def _create_pieces(self):
        """创建所有魔方块"""
        self.pieces = []
        
        # 创建角块（8个）
        for x in (-1, 1):
            for y in (-1, 1):
                for z in (-1, 1):
                    self.pieces.append(RubiksCubePiece(Vector3(x, y, z), 'corner'))
        
        for a in (-1, 1):
            for b in (-1, 1):
                self.pieces.append(RubiksCubePiece(Vector3(0, a, b), 'edge'))
                self.pieces.append(RubiksCubePiece(Vector3(a, 0, b), 'edge'))
                self.pieces.append(RubiksCubePiece(Vector3(a, b, 0), 'edge'))
        
        for nx, ny, nz in FACE_NORMALS.values():
            self.pieces.append(RubiksCubePiece(Vector3(nx, ny, nz), 'center'))
    
    def update_view_mapping(self):
        """更新当前视角下的方位映射（贪心一一匹配）"""
        inv_rotation = self.rotation.conjugate()

        pairs = []
        for view_name, normal_vec in FACE_NORMALS.items():
            view_dir = Vector3(*normal_vec)
            dir_in_cube = inv_rotation.rotate_vector(view_dir)
            for face_name, face_normal_vec in FACE_NORMALS.items():
                dot = dir_in_cube.dot(Vector3(*face_normal_vec))
                pairs.append((dot, view_name, face_name))

        pairs.sort(key=lambda x: x[0], reverse=True)

        used_views = set()
        used_faces = set()
        for dot, view_name, face_name in pairs:
            if view_name not in used_views and face_name not in used_faces and dot > 0.5:
                self.view_mapping[view_name] = face_name
                used_views.add(view_name)
                used_faces.add(face_name)
    
    def rotate_by_mouse_delta(self, dx, dy):
        """通过鼠标旋转整个魔方"""
        rotate_speed = 0.01
        if dx != 0:
            rot_y = Quaternion.from_axis_angle(Vector3(0, 1, 0), -dx * rotate_speed)
            self.rotation = rot_y.multiply(self.rotation).normalize()
        if dy != 0:
            rot_x = Quaternion.from_axis_angle(Vector3(1, 0, 0), -dy * rotate_speed)
            self.rotation = rot_x.multiply(self.rotation).normalize()
        if dx != 0 or dy != 0:
            self.update_view_mapping()
    
    def zoom_by_mouse(self, dy):
        """通过鼠标滚轮缩放"""
        self.scale = max(15.0, min(50.0, self.scale + dy * 0.5))
    
    def rotate_view_direction(self, view_direction, clockwise=True):
        """旋转当前视角下的一个面"""
        actual_face = self.view_mapping.get(view_direction)
        if not actual_face:
            return
        
        self._complete_animation()

        self.animating = True
        self.animation_progress = 0.0
        self.animation_start_time = time.time()
        
        axis = Vector3(*FACE_NORMALS[actual_face]) * -1
        self.current_animation = (axis, actual_face, clockwise)
        self.animation_pieces = self._get_pieces_on_face(actual_face)
        self.animation_rotation = Quaternion.from_axis_angle(axis, 
            self._anim_angle(clockwise))
    
    def _anim_angle(self, clockwise):
        return ROTATION_ANGLE if clockwise else -ROTATION_ANGLE

    def _clear_animation(self):
        self.animating = False
        self.animation_progress = 0.0
        self.current_animation = None
        self.animation_start_time = 0
        self.animation_pieces = []
        self.animation_rotation = None

    def update_animation(self):
        """更新动画"""
        if not self.animating:
            return
        
        elapsed = time.time() - self.animation_start_time
        self.animation_progress = min(1.0, elapsed / ANIMATION_DURATION)
        
        if self.animation_progress >= 1.0:
            self._complete_animation()
    
    def _complete_animation(self):
        """完成动画"""
        if self.current_animation and self.animation_pieces:
            axis, actual_face, clockwise = self.current_animation
            
            angle = self._anim_angle(clockwise)
            for piece in self.animation_pieces:
                piece.rotate(axis, angle)
            
            self._clear_animation()
    
    def _get_pieces_on_face(self, face_char):
        """获取指定面上的所有块"""
        check = self._FACE_POSITION_CHECK.get(face_char)
        if not check:
            return []
        return [p for p in self.pieces if check(p.current_position)]
    
    def get_piece_position(self, piece):
        """获取块的当前位置（考虑动画）"""
        if self.animating and piece in self.animation_pieces:
            axis, _, clockwise = self.current_animation
            partial_angle = self._anim_angle(clockwise) * self.animation_progress
            partial_rotation = Quaternion.from_axis_angle(axis, partial_angle)
            return partial_rotation.rotate_vector(piece.current_position)
        
        return piece.current_position
    
    def get_piece_face_color(self, piece, face_name):
        return piece.get_current_face_color(face_name)
    
    def get_piece_face_corners(self, piece, face_name):
        """获取块的面角点（考虑动画）"""
        corners = piece.get_face_corners(face_name)
        
        if self.animating and piece in self.animation_pieces:
            axis, _, clockwise = self.current_animation
            partial_angle = self._anim_angle(clockwise) * self.animation_progress
            partial_rotation = Quaternion.from_axis_angle(axis, partial_angle)
            corners = [partial_rotation.rotate_vector(c) for c in corners]
        
        piece_pos = self.get_piece_position(piece)
        return [c + piece_pos for c in corners]
    
    def calculate_brightness(self, normal, view_dir=None):
        """Blinn-Phong光照 + 边缘光"""
        n_dot_l = normal.dot(self.light_dir)

        # 环境光
        ambient = 0.25

        # 漫反射 (Lambertian)
        diffuse = max(0, n_dot_l) * 0.7

        brightness = ambient + diffuse

        # 镜面高光 (Blinn-Phong)
        if view_dir is not None:
            half = (self.light_dir + view_dir).normalized()
            spec = max(0, normal.dot(half))
            brightness += pow(spec, 48) * 0.4

        # 边缘光 (rim lighting)
        if view_dir is not None:
            rim = 1.0 - max(0, normal.dot(view_dir))
            brightness += rim * rim * 0.1

        return max(0.15, min(1.5, brightness))
    
    def project_point(self, point, width, height):
        """将3D点投影到2D屏幕"""
        rotated_point = self.rotation.rotate_vector(point)
        world_point = rotated_point + self.position
        
        relative_point = world_point - self.camera_position
        
        if relative_point.z <= 0:
            return -1000, -1000, -relative_point.z
        
        screen_x = (relative_point.x * self.focal_length) / relative_point.z
        screen_y = (-relative_point.y * self.focal_length) / relative_point.z
        
        screen_x = int(screen_x * self.scale + width / 2)
        screen_y = int(screen_y * self.scale / self.aspect_ratio + height / 2)
        
        return screen_x, screen_y, relative_point.length
    
    def _rasterize(self, zbuf, screen_pts, color_idx, corner_brightness,
                   corner_depths, color_cache, color_char):
        """扫描线栅格化+着色 — 插值亮度、算颜色、写z-buffer"""
        if len(screen_pts) < 3:
            return
        base_rgb = COLOR_RGB[color_idx]
        y_coords = [p[1] for p in screen_pts]
        y_min = int(math.floor(min(y_coords)))
        y_max = int(math.ceil(max(y_coords))) - 1
        n = len(screen_pts)

        edges = []
        for i in range(n):
            x1, y1 = screen_pts[i]
            x2, y2 = screen_pts[(i + 1) % n]
            d1, d2 = corner_depths[i], corner_depths[(i + 1) % n]
            b1, b2 = corner_brightness[i], corner_brightness[(i + 1) % n]
            if y1 != y2:
                if y1 > y2:
                    x1, x2 = x2, x1
                    y1, y2 = y2, y1
                    d1, d2 = d2, d1
                    b1, b2 = b2, b1
                dy = y2 - y1
                edges.append((y1, y2,
                              x1, (x2 - x1) / dy,
                              d1, (d2 - d1) / dy,
                              b1, (b2 - b1) / dy))

        for y in range(y_min, y_max + 1):
            yc = y + 0.5
            its = []
            for y1, y2, sx, dx, sd, dd, sb, db in edges:
                if y1 <= yc < y2:
                    f = yc - y1
                    its.append((sx + dx * f, sd + dd * f, sb + db * f))

            if len(its) < 2:
                continue
            its.sort(key=lambda v: v[0])
            x_start, d_start, b_start = its[0]
            x_end, d_end, b_end = its[-1]
            sx = int(math.ceil(x_start - 0.5))
            ex = int(math.floor(x_end - 0.5))
            if ex >= sx:
                for x in range(sx, ex + 1):
                    t = (x - sx) / (ex - sx) if ex != sx else 0
                    d = d_start + (d_end - d_start) * t
                    key = (x, y)
                    if key in zbuf and zbuf[key][0] <= d:
                        continue
                    b = b_start + (b_end - b_start) * t
                    rgb = ColorConverter.apply_brightness(base_rgb, b)
                    ci = ColorConverter.rgb_to_256color(*rgb)
                    if ci not in color_cache:
                        pn = len(color_cache) + 1
                        try:
                            curses.init_pair(pn, ci, 0)
                            color_cache[ci] = pn
                        except:
                            color_cache[ci] = 0
                    zbuf[key] = (d, color_cache.get(ci, 0), color_char)
    
    def get_front_top_edge_piece(self):
        """找到当前正面(F)和上方向(U)的交线棱块"""
        front_face = self.view_mapping.get('F')
        top_face = self.view_mapping.get('U')
        is_on_front = self._FACE_POSITION_CHECK.get(front_face)
        is_on_top = self._FACE_POSITION_CHECK.get(top_face)
        if not is_on_front or not is_on_top:
            return None
        return next((p for p in self.pieces
                     if p.piece_type == 'edge'
                     and is_on_front(self.get_piece_position(p))
                     and is_on_top(self.get_piece_position(p))), None)
    
    def _draw_direction_marker(self, stdscr, width, height):
        """绘制正面上方棱块的方向标记"""
        target_piece = self.get_front_top_edge_piece()
        if not target_piece:
            return
        
        piece_center_3d = self.get_piece_position(target_piece)
        screen_x, screen_y, _ = self.project_point(piece_center_3d, width, height)
        
        max_screen_y, max_screen_x = stdscr.getmaxyx()
        
        if (0 <= screen_y < max_screen_y - 1) and (0 <= screen_x < max_screen_x - 1):
            try:
                stdscr.addch(screen_y, screen_x, '↑', curses.A_REVERSE | curses.A_BOLD)
            except curses.error:
                pass
    
    def draw(self, stdscr, width, height, color_cache):
        """绘制魔方：栅格化着色 → 文字输出"""
        stdscr.clear()
        self.update_animation()

        # === 栅格化（面内1D抖动 + 深度测试） ===
        zbuf = {}
        for piece in self.pieces:
            for face_name in FACE_NORMALS.keys():
                color_idx = self.get_piece_face_color(piece, face_name)
                if color_idx is None:
                    continue

                corners_3d = self.get_piece_face_corners(piece, face_name)
                if len(corners_3d) < 3:
                    continue

                v1 = corners_3d[1] - corners_3d[0]
                v2 = corners_3d[2] - corners_3d[0]
                normal = v1.cross(v2).normalized()
                normal_rotated = self.rotation.rotate_vector(normal)

                center = sum(corners_3d, Vector3(0, 0, 0)) * (1.0 / len(corners_3d))
                world_center = self.rotation.rotate_vector(center) + self.position
                if normal_rotated.dot(world_center - self.camera_position) >= 0:
                    continue

                corner_depths = []
                corner_brightness = []
                screen_points = []
                for c in corners_3d:
                    c_world = self.rotation.rotate_vector(c) + self.position
                    corner_depths.append((c_world - self.camera_position).length)
                    vd = (self.camera_position - c_world).normalized()
                    corner_brightness.append(self.calculate_brightness(normal_rotated, vd))
                    sx, sy, _ = self.project_point(c, width, height)
                    screen_points.append((sx, sy))

                self._rasterize(zbuf, screen_points, color_idx,
                                corner_brightness, corner_depths,
                                color_cache, COLOR_CHARS[color_idx])

        # === 文字输出（curses颜色对） ===
        max_y, max_x = stdscr.getmaxyx()
        for (x, y), (depth, pair, ch) in zbuf.items():
            if 0 <= x < max_x and 0 <= y < max_y:
                try:
                    if pair > 0:
                        stdscr.addch(y, x, ch, curses.color_pair(pair))
                    else:
                        stdscr.addch(y, x, ch)
                except:
                    pass

        self._draw_direction_marker(stdscr, width, height)
        self._draw_ui(stdscr, width, height)
    
    def _draw_ui(self, stdscr, width, height):
        """绘制用户界面"""
        title = "3×3 魔方  "
        if width >= len(title):
            try:
                stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)
            except:
                pass
            
        cmap = self.view_mapping
        controls = [
            "控制说明:",
            "  鼠标中键拖动 - 旋转魔方整体",
            "  鼠标滚轮     - 缩放",
            "  C 键        - 重置魔方",
            "  X 键        - 打乱魔方",
            "  ESC 键      - 退出程序",
            "  ↑ 标记      - 指示当前正面的上方方向",
            "",
            "旋转各个方位面:",
            *(f"{k.upper()}-{_FACE_NAMES[f]}顺时针  Shift+{k.upper()}-{_FACE_NAMES[f]}逆时针"
              for k, f in _FACE_KEYS),
            "",
            "当前视角映射:",
            *(f"  {_FACE_NAMES[f]}({f}) -> {COLOR_NAMES[INITIAL_FACE_COLOR[cmap.get(f, f)]]}面"
              for f in _FACE_NAMES),
        ]
        
        status = [
            f"缩放: {self.scale:.1f}",
            f"动画: {'进行中' if self.animating else '无'}",
        ]
        
        all_lines = controls + status
        
        box_width = max(len(line) for line in all_lines) + 14
        box_height = len(all_lines) + 2
        box_x = width - box_width - 2
        box_y = 2
        
        if (0 < box_x < width - box_width and 0 < box_y < height - box_height):
            try:
                for x in range(box_x, box_x + box_width):
                    if x == box_x:
                        stdscr.addch(box_y, x, '+')
                        stdscr.addch(box_y + box_height - 1, x, '+')
                    elif x == box_x + box_width - 1:
                        stdscr.addch(box_y, x, '+')
                        stdscr.addch(box_y + box_height - 1, x, '+')
                    else:
                        stdscr.addch(box_y, x, '-')
                        stdscr.addch(box_y + box_height - 1, x, '-')
                
                for i, line in enumerate(all_lines):
                    y_pos = box_y + 1 + i
                    if y_pos < height - 1:
                        stdscr.addstr(y_pos, box_x + 2, line)
                
                for y in range(box_y + 1, box_y + box_height - 1):
                    stdscr.addch(y, box_x, '|')
                    stdscr.addch(y, box_x + box_width - 1, '|')
            except:
                pass
        
        footer = "按 ESC 退出程序 | 按 C 重置魔方 | 按 X 打乱魔方               "
        if width >= len(footer):
            try:
                stdscr.addstr(height - 1, (width - len(footer)) // 2, 
                            footer, curses.A_REVERSE)
            except:
                pass
    
    def reset(self):
        """重置魔方到初始状态"""
        for piece in self.pieces:
            piece.reset()
        
        self.rotation = Quaternion(1, 0, 0, 0)
        self.scale = 25.0
        self.position = Vector3(0, 0, 10)
        self._clear_animation()
        self.view_mapping = {k: k for k in FACE_NORMALS}
    
    def scramble(self, moves=20):
        """打乱魔方"""
        self._complete_animation()

        view_directions = ['F', 'B', 'L', 'R', 'U', 'D']
        for _ in range(moves):
            view_direction = random.choice(view_directions)
            clockwise = random.choice([True, False])

            actual_face = self.view_mapping.get(view_direction)
            if not actual_face:
                continue

            pieces_to_rotate = self._get_pieces_on_face(actual_face)
            axis = Vector3(*FACE_NORMALS[actual_face])
            angle = self._anim_angle(clockwise)

            for piece in pieces_to_rotate:
                piece.rotate(axis, angle)

# ============= 主程序 =============
_FACE_NAMES = {'F': '前面', 'B': '后面', 'L': '左面', 'R': '右面', 'U': '上面', 'D': '下面'}
_FACE_KEYS = [('e', 'F'), ('q', 'B'), ('a', 'L'), ('d', 'R'), ('w', 'U'), ('s', 'D')]

_KEY_ACTIONS = {}
for _key, _face in _FACE_KEYS:
    _KEY_ACTIONS[ord(_key)] = (_face, True)
    _KEY_ACTIONS[ord(_key.upper())] = (_face, False)

def main(stdscr):
    """主函数"""
    curses.curs_set(0)
    stdscr.nodelay(1)
    
    if not curses.has_colors():
        stdscr.addstr(0, 0, "终端不支持颜色！")
        stdscr.refresh()
        stdscr.getch()
        return
    
    curses.start_color()
    curses.use_default_colors()
    curses.mousemask(curses.ALL_MOUSE_EVENTS)

    color_cache = {}
    cube = RubiksCube()
    mouse_controller = MouseController()
    mouse_controller.start()
    
    try:
        while True:
            height, width = stdscr.getmaxyx()
            
            if width < 80 or height < 40:
                stdscr.clear()
                msg = "请将终端窗口调整到至少 80x40 大小"
                try:
                    stdscr.addstr(height//2, max(0, (width - len(msg))//2), msg)
                except:
                    pass
                stdscr.refresh()
                time.sleep(0.5)
                continue
            
            for event in mouse_controller.get_events():
                event_type = event[0]
                
                if event_type == 'middle_click':
                    if len(event) >= 4:
                        _, x, y, pressed = event
                        if pressed:
                            mouse_controller.last_pos = (x, y)
                
                elif event_type == 'move':
                    if len(event) >= 3:
                        _, x, y = event
                        if mouse_controller.is_middle_pressed:
                            last_x, last_y = mouse_controller.last_pos
                            dx, dy = x - last_x, y - last_y
                            
                            if dx != 0 or dy != 0:
                                cube.rotate_by_mouse_delta(dx, dy)
                                mouse_controller.last_pos = (x, y)
                
            try:
                key = stdscr.getch()
                
                if key == curses.KEY_MOUSE:
                    try:
                        _, _, _, _, bstate = curses.getmouse()
                        if bstate & curses.BUTTON4_PRESSED:
                            cube.zoom_by_mouse(1)
                        elif bstate & curses.BUTTON5_PRESSED:
                            cube.zoom_by_mouse(-1)
                    except:
                        pass
                elif key == 27:
                    break
                elif key in (ord('c'), ord('C')):
                    cube.reset()
                elif key in (ord('x'), ord('X')):
                    cube.scramble(16)
                elif key in _KEY_ACTIONS:
                    face, cw = _KEY_ACTIONS[key]
                    cube.rotate_view_direction(face, clockwise=cw)
            except:
                pass
            
            cube.draw(stdscr, width, height, color_cache)
            stdscr.refresh()
            
            time.sleep(0.016)
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        import traceback
        error_msg = f"游戏发生错误: {str(e)}"
        if stdscr:
            try:
                stdscr.clear()
                stdscr.addstr(0, 0, error_msg)
                stdscr.addstr(2, 0, "按任意键退出...")
                stdscr.refresh()
                stdscr.getch()
            except:
                pass
        print(f"\n错误详情: {e}")
        traceback.print_exc()
    finally:
        mouse_controller.stop()

def start_program():
    """启动程序"""
    print("=" * 8)
    print("魔方")
    print("=" * 8)
    print("\n控制方式：")
    print("  • 鼠标中键拖动 - 旋转魔方整体")
    print("  • 鼠标滚轮     - 缩放")
    print("  • C 键        - 重置魔方")
    print("  • X 键        - 打乱魔方")
    print("  • ESC 键      - 退出程序")
    print("\n旋转各个方位面（基于当前视角）：")
    for k, f in _FACE_KEYS:
        print(f"  {k.upper()} - {_FACE_NAMES[f]}顺时针   Shift+{k.upper()} - {_FACE_NAMES[f]}逆时针")
    print("\n视角映射：")
    print("  • 旋转魔方后，UI会显示当前每个方位对应的实际颜色面")
    print("  • 例如：旋转魔方后，F可能对应蓝色面，这时按F键会旋转蓝色面")
    print("  • ↑ 标记：始终指向当前正面的上方方向，帮助识别方位")
    print("\n" + "=" * 70)
    print("  请使用英文输入法进行游戏，并取消大写锁定")
    print("  请全屏进行游戏")
    print("=" * 70)
    
    print("\n按 Enter 键开始游戏...")
    
    try:
        input()
    except:
        pass
    
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n游戏被用户中断")
    except Exception as e:
        print(f"\n游戏发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n游戏已结束")

if __name__ == "__main__":
    set_console_fullscreen()
    start_program()