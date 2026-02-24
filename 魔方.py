#!/usr/bin/env python3
"""
魔方游戏
"""

import curses
import math
import time
import sys
import os
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
    os.system("")

# ============= 常量定义 =============
COLOR_RED = 0      # 红色面
COLOR_ORANGE = 1   # 橙色面  
COLOR_BLUE = 2     # 蓝色面
COLOR_GREEN = 3    # 绿色面
COLOR_WHITE = 4    # 白色面
COLOR_YELLOW = 5   # 黄色面

COLOR_NAMES = ["红色", "橙色", "蓝色", "绿色", "白色", "黄色"]
# 颜色对应的汉字
COLOR_CHARS = ["红", "橙", "蓝", "绿", "白", "黄"]

# RGB颜色定义
COLOR_RGB = [
    (220, 60, 60),     # 红色
    (220, 120, 0),     # 橙色
    (60, 100, 220),    # 蓝色
    (60, 220, 100),    # 绿色
    (255, 255, 255),   # 白色
    (220, 220, 60)     # 黄色
]

# 面到颜色的映射
FACE_TO_COLOR = {
    'F': COLOR_ORANGE,  # 前面
    'B': COLOR_RED, # 后面
    'L': COLOR_BLUE,   # 左面
    'R': COLOR_GREEN,  # 右面
    'U': COLOR_WHITE,  # 上面
    'D': COLOR_YELLOW  # 下面
}

# 面法向量（指向外部）
FACE_NORMALS = {
    'F': (0, 0, -1),    # 前面
    'B': (0, 0, 1),   # 后面
    'L': (-1, 0, 0),   # 左面
    'R': (1, 0, 0),    # 右面
    'U': (0, 1, 0),    # 上面
    'D': (0, -1, 0)    # 下面
}

# 旋转轴映射（基于魔方坐标系）
ROTATION_AXES = {
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
    
    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)
    
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
            elif button == mouse.Button.left and pressed:
                self.mouse_queue.put(('left_click', x, y))
        
        def on_scroll(x, y, dx, dy):
            self.mouse_queue.put(('scroll', x, y, dy))
        
        self.listener = mouse.Listener(
            on_move=on_move,
            on_click=on_click,
            on_scroll=on_scroll
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
        """初始化面的颜色"""
        x, y, z = self.initial_position.x, self.initial_position.y, self.initial_position.z
        
        # 设置中心块颜色
        if self.piece_type == 'center':
            if x == -1:      self.initial_colors['L'] = COLOR_BLUE
            elif x == 1:     self.initial_colors['R'] = COLOR_GREEN
            elif y == -1:    self.initial_colors['D'] = COLOR_YELLOW
            elif y == 1:     self.initial_colors['U'] = COLOR_WHITE
            elif z == -1:    self.initial_colors['B'] = COLOR_ORANGE
            elif z == 1:     self.initial_colors['F'] = COLOR_RED
            return
        
        # 设置棱块和角块颜色
        if x == -1:      self.initial_colors['L'] = COLOR_BLUE
        elif x == 1:     self.initial_colors['R'] = COLOR_GREEN
        
        if y == -1:      self.initial_colors['D'] = COLOR_YELLOW
        elif y == 1:     self.initial_colors['U'] = COLOR_WHITE
        
        if z == -1:      self.initial_colors['B'] = COLOR_ORANGE
        elif z == 1:     self.initial_colors['F'] = COLOR_RED
    
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
            'F': [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)],
            'B': [(-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)],
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
        """获取当前状态下指定方向的面颜色"""
        # 获取指定方向的基础法向量
        if face_name not in FACE_NORMALS:
            return None
        
        # 创建法向量
        target_normal = Vector3(*FACE_NORMALS[face_name])
        
        # 计算逆旋转（将目标方向转换到初始坐标系）
        inv_rotation = Quaternion()
        
        # 将目标法向量转换到块的初始坐标系
        initial_normal = inv_rotation.rotate_vector(target_normal)
        
        # 找出哪个初始面的法向量最接近这个方向
        best_match = None
        best_dot = -1
        
        for init_face, init_color in self.initial_colors.items():
            if init_face in FACE_NORMALS:
                init_normal = Vector3(*FACE_NORMALS[init_face])
                dot = initial_normal.dot(init_normal)
                if dot > best_dot:
                    best_dot = dot
                    best_match = init_face
        
        # 返回匹配的面的颜色
        return self.initial_colors.get(best_match) if best_match and best_dot > 0.9 else None
    
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
        
        # 动画状态
        self.animating = False
        self.animation_progress = 0.0
        self.current_animation = None  # (axis, face_char, clockwise)
        self.animation_start_time = 0
        self.animation_pieces = []     # 当前动画中要旋转的块
        self.animation_rotation = None # 当前动画的旋转四元数
        
        # 颜色转换器
        self.color_converter = ColorConverter()
        
        # 当前视角下的方位映射
        self.view_mapping = {
            'F': 'F',  # 前面（红色）
            'B': 'B',  # 后面（橙色）
            'L': 'L',  # 左面（蓝色）
            'R': 'R',  # 右面（绿色）
            'U': 'U',  # 上面（白色）
            'D': 'D'   # 下面（黄色）
        }
        
        # 视角方向向量（在摄像机坐标系中）
        self.view_directions = {
            'F': Vector3(0, 0, -1),    # 前面（朝向屏幕外）
            'B': Vector3(0, 0, 1),   # 后面（朝向屏幕内）
            'L': Vector3(-1, 0, 0),   # 左面（屏幕左边）
            'R': Vector3(1, 0, 0),    # 右面（屏幕右边）
            'U': Vector3(0, 1, 0),    # 上面（屏幕上方）
            'D': Vector3(0, -1, 0)    # 下面（屏幕下方）
        }
        
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
        
        # 创建棱块（12个）
        for y in (-1, 1):
            for z in (-1, 1):
                self.pieces.append(RubiksCubePiece(Vector3(0, y, z), 'edge'))
        
        for x in (-1, 1):
            for z in (-1, 1):
                self.pieces.append(RubiksCubePiece(Vector3(x, 0, z), 'edge'))
        
        for x in (-1, 1):
            for y in (-1, 1):
                self.pieces.append(RubiksCubePiece(Vector3(x, y, 0), 'edge'))
        
        # 创建中心块（6个）
        center_positions = [
            Vector3(-1, 0, 0),  # 蓝色面中心
            Vector3(1, 0, 0),   # 绿色面中心
            Vector3(0, -1, 0),  # 黄色面中心
            Vector3(0, 1, 0),   # 白色面中心
            Vector3(0, 0, -1),  # 橙色面中心
            Vector3(0, 0, 1)    # 红色面中心
        ]
        
        for position in center_positions:
            self.pieces.append(RubiksCubePiece(position, 'center'))
    
    def update_view_mapping(self):
        """更新当前视角下的方位映射"""
        for view_dir_name, view_dir in self.view_directions.items():
            best_face = None
            best_dot = -1
            
            inv_rotation = Quaternion(self.rotation.w, -self.rotation.x, -self.rotation.y, -self.rotation.z)
            dir_in_cube_space = inv_rotation.rotate_vector(view_dir)
            
            for face_name, face_normal_vec in FACE_NORMALS.items():
                face_normal = Vector3(*face_normal_vec)
                dot = dir_in_cube_space.dot(face_normal)
                if dot > best_dot:
                    best_dot = dot
                    best_face = face_name
            
            if best_face and best_dot > 0.5:
                self.view_mapping[view_dir_name] = best_face
    
    def rotate_by_mouse_delta(self, dx, dy):
        """通过鼠标旋转整个魔方"""
        rotate_speed = 0.01
        if dx != 0:
            rot_y = Quaternion.from_axis_angle(Vector3(0, 1, 0), -dx * rotate_speed)
            self.rotation = rot_y.multiply(self.rotation).normalize()
            self.update_view_mapping()
        
        if dy != 0:
            rot_x = Quaternion.from_axis_angle(Vector3(1, 0, 0), -dy * rotate_speed)
            self.rotation = rot_x.multiply(self.rotation).normalize()
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
        
        axis = Vector3(*ROTATION_AXES[actual_face])
        self.current_animation = (axis, actual_face, clockwise)
        self.animation_pieces = self._get_pieces_on_face(actual_face)
        self.animation_rotation = Quaternion.from_axis_angle(axis, 
            ROTATION_ANGLE if clockwise else -ROTATION_ANGLE)
    
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
            
            angle = ROTATION_ANGLE if clockwise else -ROTATION_ANGLE
            for piece in self.animation_pieces:
                piece.rotate(axis, angle)
            
            self.animating = False
            self.animation_progress = 0.0
            self.current_animation = None
            self.animation_pieces = []
            self.animation_rotation = None
    
    def _get_pieces_on_face(self, face_char):
        """获取指定面上的所有块"""
        position_check = {
            'F': lambda pos: abs(pos.z + 1) < 0.1,
            'B': lambda pos: abs(pos.z - 1) < 0.1,
            'L': lambda pos: abs(pos.x + 1) < 0.1,
            'R': lambda pos: abs(pos.x - 1) < 0.1,
            'U': lambda pos: abs(pos.y - 1) < 0.1,
            'D': lambda pos: abs(pos.y + 1) < 0.1
        }
        
        if face_char not in position_check:
            return []
        
        return [p for p in self.pieces if position_check[face_char](p.current_position)]
    
    def get_piece_position(self, piece):
        """获取块的当前位置（考虑动画）"""
        if self.animating and piece in self.animation_pieces:
            axis, _, clockwise = self.current_animation
            partial_angle = (ROTATION_ANGLE if clockwise else -ROTATION_ANGLE) * self.animation_progress
            partial_rotation = Quaternion.from_axis_angle(axis, partial_angle)
            return partial_rotation.rotate_vector(piece.current_position)
        
        return piece.current_position
    
    def get_piece_face_color(self, piece, face_name):
        """获取块的面颜色（考虑动画）"""
        if self.animating and piece in self.animation_pieces:
            axis, _, clockwise = self.current_animation
            partial_angle = (ROTATION_ANGLE if clockwise else -ROTATION_ANGLE) * self.animation_progress
            partial_rotation = Quaternion.from_axis_angle(axis, partial_angle)
            
            combined_rotation = partial_rotation.multiply(piece.local_rotation)
            
            original_rotation = piece.local_rotation
            piece.local_rotation = combined_rotation
            color = piece.get_current_face_color(face_name)
            piece.local_rotation = original_rotation
            
            return color
        
        return piece.get_current_face_color(face_name)
    
    def get_piece_face_corners(self, piece, face_name):
        """获取块的面角点（考虑动画）"""
        corners = piece.get_face_corners(face_name)
        
        if self.animating and piece in self.animation_pieces:
            axis, _, clockwise = self.current_animation
            partial_angle = (ROTATION_ANGLE if clockwise else -ROTATION_ANGLE) * self.animation_progress
            partial_rotation = Quaternion.from_axis_angle(axis, partial_angle)
            corners = [partial_rotation.rotate_vector(c) for c in corners]
        
        piece_pos = self.get_piece_position(piece)
        return [c + piece_pos for c in corners]
    
    def calculate_brightness(self, normal):
        """计算面的亮度因子"""
        dot = normal.dot(self.light_dir)
        ambient = 0.3
        diffuse = max(0, dot) * 0.7
        brightness = ambient + diffuse
        
        if dot > 0.8:
            brightness = min(1.2, brightness + 0.2)
        
        return max(0.25, min(1.2, brightness))
    
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
    
    def draw_polygon(self, stdscr, points, color_pair, color_char):
        """绘制填充多边形"""
        if len(points) < 3:
            return
        
        y_coords = [p[1] for p in points]
        y_min, y_max = int(min(y_coords)), int(max(y_coords))
        
        edges = []
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if y1 != y2:
                if y1 > y2:
                    x1, x2 = x2, x1
                    y1, y2 = y2, y1
                inv_slope = (x2 - x1) / (y2 - y1) if y2 != y1 else 0
                edges.append((y1, y2, x1, inv_slope))
        
        for y in range(y_min, y_max + 1):
            intersections = []
            for y1, y2, x1, inv_slope in edges:
                if y1 <= y < y2:
                    x = x1 + inv_slope * (y - y1)
                    intersections.append(x)
            
            if len(intersections) >= 2:
                intersections.sort()
                for i in range(0, len(intersections), 2):
                    if i + 1 < len(intersections):
                        start_x = max(0, int(intersections[i]))
                        end_x = min(stdscr.getmaxyx()[1] - 1, int(intersections[i + 1]))
                        for x in range(start_x, end_x + 1):
                            try:
                                if color_pair > 0:
                                    stdscr.addch(y, x, color_char, curses.color_pair(color_pair))
                                else:
                                    stdscr.addch(y, x, color_char)
                            except:
                                pass
    
    def get_front_top_edge_piece(self):
        """找到当前正面(F)和上方向(U)的交线棱块"""
        front_face = self.view_mapping.get('F')
        top_face = self.view_mapping.get('U')
        
        if not front_face or not top_face:
            return None
        
        face_position_check = {
            'F': lambda pos: abs(pos.z + 1) < 0.1,
            'B': lambda pos: abs(pos.z - 1) < 0.1,
            'L': lambda pos: abs(pos.x + 1) < 0.1,
            'R': lambda pos: abs(pos.x - 1) < 0.1,
            'U': lambda pos: abs(pos.y - 1) < 0.1,
            'D': lambda pos: abs(pos.y + 1) < 0.1
        }
        
        is_on_front = face_position_check.get(front_face)
        is_on_top = face_position_check.get(top_face)
        
        if not is_on_front or not is_on_top:
            return None
        
        for piece in self.pieces:
            if piece.piece_type == 'edge':
                current_pos = self.get_piece_position(piece)
                if is_on_front(current_pos) and is_on_top(current_pos):
                    return piece
        
        return None
    
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
        """绘制魔方"""
        stdscr.clear()
        self.update_animation()
        
        faces_to_draw = []
        
        for piece in self.pieces:
            for face_name in FACE_NORMALS.keys():
                color_idx = self.get_piece_face_color(piece, face_name)
                if color_idx is None:
                    continue
                
                corners_3d = self.get_piece_face_corners(piece, face_name)
                if len(corners_3d) < 3:
                    continue
                
                center = Vector3(0, 0, 0)
                for corner in corners_3d:
                    center = center + corner
                center = center * (1.0 / len(corners_3d))
                
                rotated_center = self.rotation.rotate_vector(center)
                world_center = rotated_center + self.position
                
                v1 = corners_3d[1] - corners_3d[0]
                v2 = corners_3d[2] - corners_3d[0]
                normal = v1.cross(v2).normalized()
                normal_rotated = self.rotation.rotate_vector(normal)
                
                camera_to_face = world_center - self.camera_position
                
                if normal_rotated.dot(camera_to_face) >= 0:
                    continue
                
                brightness = self.calculate_brightness(normal_rotated)
                face_color_rgb = self.color_converter.apply_brightness(
                    COLOR_RGB[color_idx], brightness)
                
                color_index = self.color_converter.rgb_to_256color(*face_color_rgb)
                
                if color_index not in color_cache:
                    pair_number = len(color_cache) + 1
                    try:
                        curses.init_pair(pair_number, color_index, 0)
                        color_cache[color_index] = pair_number
                    except:
                        color_cache[color_index] = 0
                
                screen_points = []
                for corner in corners_3d:
                    x, y, _ = self.project_point(corner, width, height)
                    screen_points.append((x, y))
                
                depth = camera_to_face.length
                
                # 获取颜色对应的汉字
                color_char = COLOR_CHARS[color_idx]
                
                faces_to_draw.append({
                    'points': screen_points,
                    'color_pair': color_cache.get(color_index, 0),
                    'depth': depth,
                    'color_char': color_char  # 添加汉字字符
                })
        
        faces_to_draw.sort(key=lambda f: f['depth'], reverse=True)
        for face_data in faces_to_draw:
            self.draw_polygon(stdscr, face_data['points'], face_data['color_pair'], face_data['color_char'])
        
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
            
        self.update_view_mapping()
        
        current_F = self.view_mapping.get('F', 'F')
        current_B = self.view_mapping.get('B', 'B')
        current_L = self.view_mapping.get('L', 'L')
        current_R = self.view_mapping.get('R', 'R')
        current_U = self.view_mapping.get('U', 'U')
        current_D = self.view_mapping.get('D', 'D')
        
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
            f"E-前面顺时针 Shift+E-前面逆时针",
            f"Q-后面顺时针 Shift+Q-后面逆时针",
            f"A-左面顺时针 Shift+A-左面逆时针",
            f"D-右面顺时针 Shift+D-右面逆时针",
            f"W-上面顺时针 Shift+W-上面逆时针",
            f"S-下面顺时针 Shift+S-下面逆时针",
            "",
            "当前视角映射:",
            f"  前面(F) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_F, 0)]}面",
            f"  后面(B) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_B, 1)]}面",
            f"  左面(L) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_L, 2)]}面",
            f"  右面(R) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_R, 3)]}面",
            f"  上面(U) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_U, 4)]}面",
            f"  下面(D) -> {COLOR_NAMES[FACE_TO_COLOR.get(current_D, 5)]}面",
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
        self.animating = False
        self.animation_progress = 0.0
        self.current_animation = None
        self.animation_pieces = []
        self.animation_rotation = None
        
        self.view_mapping = {
            'F': 'F',
            'B': 'B',
            'L': 'L',
            'R': 'R',
            'U': 'U',
            'D': 'D'
        }
    
    def scramble(self, moves=20):
        """打乱魔方"""
        view_directions = ['F', 'B', 'L', 'R', 'U', 'D']
        
        for _ in range(moves):
            view_direction = random.choice(view_directions)
            clockwise = random.choice([True, False])
            
            actual_face = self.view_mapping.get(view_direction)
            if not actual_face:
                continue
            
            pieces_to_rotate = self._get_pieces_on_face(actual_face)
            axis = Vector3(*ROTATION_AXES[actual_face])
            angle = ROTATION_ANGLE if clockwise else -ROTATION_ANGLE
            
            for piece in pieces_to_rotate:
                piece.rotate(axis, angle)
        
        self.animating = False
        self.animation_progress = 0.0
        self.current_animation = None
        self.animation_pieces = []
        self.animation_rotation = None

# ============= 主程序 =============
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
                
                elif event_type == 'scroll':
                    if len(event) >= 4:
                        _, x, y, dy = event
                        cube.zoom_by_mouse(dy)
            
            try:
                key = stdscr.getch()
                
                if key == 27:
                    break
                elif key in (ord('c'), ord('C')):
                    cube.reset()
                elif key in (ord('x'), ord('X')):
                    cube.scramble(16)
                elif key == ord('e'):
                    cube.rotate_view_direction('F', clockwise=True)
                elif key == ord('E'):
                    cube.rotate_view_direction('F', clockwise=False)
                elif key == ord('q'):
                    cube.rotate_view_direction('B', clockwise=True)
                elif key == ord('Q'):
                    cube.rotate_view_direction('B', clockwise=False)
                elif key == ord('a'):
                    cube.rotate_view_direction('L', clockwise=True)
                elif key == ord('A'):
                    cube.rotate_view_direction('L', clockwise=False)
                elif key == ord('d'):
                    cube.rotate_view_direction('R', clockwise=True)
                elif key == ord('D'):
                    cube.rotate_view_direction('R', clockwise=False)
                elif key == ord('w'):
                    cube.rotate_view_direction('U', clockwise=True)
                elif key == ord('W'):
                    cube.rotate_view_direction('U', clockwise=False)
                elif key == ord('s'):
                    cube.rotate_view_direction('D', clockwise=True)
                elif key == ord('S'):
                    cube.rotate_view_direction('D', clockwise=False)
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
    print("  E - 前面顺时针   Shift+E - 前面逆时针")
    print("  Q - 后面顺时针   Shift+Q - 后面逆时针")
    print("  A - 左面顺时针   Shift+A - 左面逆时针")
    print("  D - 右面顺时针   Shift+D - 右面逆时针")
    print("  W - 上面顺时针   Shift+W - 上面逆时针")
    print("  S - 下面顺时针   Shift+S - 下面逆时针")
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