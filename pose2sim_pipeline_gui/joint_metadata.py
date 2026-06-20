from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JointMeta:
    zh: str
    order: int
    plane: str
    neutral: str
    direction: str
    definition: str
    boundary: str


GENERIC_BOUNDARY = "该数值来自 OpenSim 逆运动学坐标，不等同于医学诊断；质量较差、遮挡多或校准误差大时应谨慎解释。"


def _meta(zh: str, order: int, plane: str, neutral: str, direction: str, definition: str) -> JointMeta:
    return JointMeta(zh, order, plane, neutral, direction, definition, GENERIC_BOUNDARY)


JOINT_META: dict[str, JointMeta] = {
    "neck_flexion": _meta("颈部屈伸", 10, "矢状面", "头颈自然中立位", "正值通常表示屈曲，负值通常表示伸展", "OpenSim 颈部屈伸坐标。"),
    "neck_bending": _meta("颈部侧屈", 11, "冠状面", "头颈自然中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 颈部侧屈坐标。"),
    "neck_rotation": _meta("颈部旋转", 12, "水平面", "头颈自然中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 颈部旋转坐标。"),
    "L5_S1_Flex_Ext": _meta("腰骶屈伸 L5-S1", 20, "矢状面", "躯干骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim L5-S1 屈伸坐标。"),
    "L5_S1_Lat_Bending": _meta("腰骶侧屈 L5-S1", 21, "冠状面", "躯干骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim L5-S1 侧屈坐标。"),
    "L5_S1_axial_rotation": _meta("腰骶旋转 L5-S1", 22, "水平面", "躯干骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim L5-S1 轴向旋转坐标。"),
    "pelvis_tilt": _meta("骨盆前后倾", 50, "矢状面", "骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 骨盆倾斜坐标。"),
    "pelvis_list": _meta("骨盆侧倾", 51, "冠状面", "骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 骨盆侧倾坐标。"),
    "pelvis_rotation": _meta("骨盆旋转", 52, "水平面", "骨盆中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 骨盆旋转坐标。"),
    "hip_flexion_l": _meta("左髋屈伸", 60, "矢状面", "解剖中立位", "正值通常表示屈曲，负值通常表示伸展", "OpenSim 左髋屈伸坐标。"),
    "hip_adduction_l": _meta("左髋内收外展", 61, "冠状面", "解剖中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左髋内收/外展坐标。"),
    "hip_rotation_l": _meta("左髋内外旋", 62, "水平面", "解剖中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左髋旋转坐标。"),
    "knee_angle_l": _meta("左膝屈伸", 70, "矢状面", "膝关节伸直位", "正值通常表示屈曲", "OpenSim 左膝屈伸坐标。"),
    "ankle_angle_l": _meta("左踝背屈跖屈", 80, "矢状面", "踝关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左踝角坐标。"),
    "subtalar_angle_l": _meta("左距下关节内外翻", 81, "冠状面", "足部中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左距下关节坐标。"),
    "mtp_angle_l": _meta("左跖趾关节屈伸", 82, "矢状面", "足趾中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左跖趾关节坐标。"),
    "hip_flexion_r": _meta("右髋屈伸", 63, "矢状面", "解剖中立位", "正值通常表示屈曲，负值通常表示伸展", "OpenSim 右髋屈伸坐标。"),
    "hip_adduction_r": _meta("右髋内收外展", 64, "冠状面", "解剖中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右髋内收/外展坐标。"),
    "hip_rotation_r": _meta("右髋内外旋", 65, "水平面", "解剖中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右髋旋转坐标。"),
    "knee_angle_r": _meta("右膝屈伸", 73, "矢状面", "膝关节伸直位", "正值通常表示屈曲", "OpenSim 右膝屈伸坐标。"),
    "ankle_angle_r": _meta("右踝背屈跖屈", 83, "矢状面", "踝关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右踝角坐标。"),
    "subtalar_angle_r": _meta("右距下关节内外翻", 84, "冠状面", "足部中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右距下关节坐标。"),
    "mtp_angle_r": _meta("右跖趾关节屈伸", 85, "矢状面", "足趾中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右跖趾关节坐标。"),
    "arm_flex_l": _meta("左肩屈伸", 30, "矢状面", "上肢自然下垂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左肩屈伸坐标。"),
    "arm_add_l": _meta("左肩内收外展", 31, "冠状面", "上肢自然下垂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左肩内收/外展坐标。"),
    "arm_rot_l": _meta("左肩内外旋", 32, "水平面", "肩关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左肩旋转坐标。"),
    "elbow_flex_l": _meta("左肘屈伸", 35, "矢状面", "肘关节伸直位", "正值通常表示屈曲", "OpenSim 左肘屈伸坐标。"),
    "pro_sup_l": _meta("左前臂旋前旋后", 36, "水平面", "前臂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左前臂旋前/旋后坐标。"),
    "wrist_flex_l": _meta("左腕屈伸", 40, "矢状面", "腕关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左腕屈伸坐标。"),
    "wrist_dev_l": _meta("左腕尺桡偏", 41, "冠状面", "腕关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 左腕偏移坐标。"),
    "arm_flex_r": _meta("右肩屈伸", 33, "矢状面", "上肢自然下垂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右肩屈伸坐标。"),
    "arm_add_r": _meta("右肩内收外展", 34, "冠状面", "上肢自然下垂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右肩内收/外展坐标。"),
    "arm_rot_r": _meta("右肩内外旋", 35, "水平面", "肩关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右肩旋转坐标。"),
    "elbow_flex_r": _meta("右肘屈伸", 37, "矢状面", "肘关节伸直位", "正值通常表示屈曲", "OpenSim 右肘屈伸坐标。"),
    "pro_sup_r": _meta("右前臂旋前旋后", 38, "水平面", "前臂中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右前臂旋前/旋后坐标。"),
    "wrist_flex_r": _meta("右腕屈伸", 42, "矢状面", "腕关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右腕屈伸坐标。"),
    "wrist_dev_r": _meta("右腕尺桡偏", 43, "冠状面", "腕关节中立位", "正负方向取决于 OpenSim 模型坐标约定", "OpenSim 右腕偏移坐标。"),
}


def metadata_for(column: str) -> JointMeta:
    if column in JOINT_META:
        return JOINT_META[column]
    clean = column.replace("_", " ")
    return JointMeta(
        zh=clean,
        order=999,
        plane="OpenSim 模型坐标",
        neutral="OpenSim 模型中立位",
        direction="正负方向按 OpenSim 坐标定义解释。",
        definition=f"OpenSim 坐标 `{column}`。",
        boundary=GENERIC_BOUNDARY,
    )


def ordered_columns(columns: list[str]) -> list[str]:
    return sorted(columns, key=lambda c: (metadata_for(c).order, metadata_for(c).zh))

