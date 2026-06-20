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
    supported: bool = True


GENERIC_BOUNDARY = (
    "该数值来自 OpenSim 逆运动学广义坐标，受校准、同步、关键点识别、模型缩放和 IK marker error 影响。"
    "它适合描述动作趋势和活动范围，不等同于医学诊断或康复处方。"
)


def _definition(coord: str, joint: str) -> str:
    return (
        f"读取 OpenSim 逆运动学结果中的 `{coord}` 坐标，表示 {joint} 在缩放 OpenSim 模型中的关节角。"
        "该角度由 OpenSim 通过最小化模型标记点与三维重建标记点的误差计算得到，"
        "不是原始 2D/3D 点坐标直接相减。"
    )


def _meta(zh: str, order: int, plane: str, neutral: str, direction: str, coord: str, joint: str) -> JointMeta:
    return JointMeta(zh, order, plane, neutral, direction, _definition(coord, joint), GENERIC_BOUNDARY)


JOINT_META: dict[str, JointMeta] = {
    "neck_flexion": _meta("颈部屈伸", 10, "矢状面", "头颈自然中立位", "正值表示颈部屈曲，负值表示颈部伸展。", "neck_flexion", "颈部屈伸"),
    "neck_bending": _meta("颈部侧屈", 11, "冠状面", "头颈自然中立位", "正值表示模型定义的侧屈正方向，负值表示相反方向。", "neck_bending", "颈部侧屈"),
    "neck_rotation": _meta("颈部旋转", 12, "水平面", "头颈自然中立位", "正值表示模型定义的轴向旋转正方向，负值表示相反方向。", "neck_rotation", "颈部旋转"),
    "L5_S1_Flex_Ext": _meta("腰骶屈伸 L5-S1", 20, "矢状面", "躯干和骨盆中立位", "正值表示腰骶屈曲方向，负值表示伸展方向。", "L5_S1_Flex_Ext", "腰骶屈伸"),
    "L5_S1_Lat_Bending": _meta("腰骶侧屈 L5-S1", 21, "冠状面", "躯干和骨盆中立位", "正值表示模型定义的侧屈正方向，负值表示相反方向。", "L5_S1_Lat_Bending", "腰骶侧屈"),
    "L5_S1_axial_rotation": _meta("腰骶旋转 L5-S1", 22, "水平面", "躯干和骨盆中立位", "正值表示模型定义的轴向旋转正方向，负值表示相反方向。", "L5_S1_axial_rotation", "腰骶旋转"),
    "arm_flex_l": _meta("左肩屈伸", 30, "矢状面", "上臂自然下垂中立位", "正值表示左肩屈曲，负值表示左肩伸展。", "arm_flex_l", "左肩屈伸"),
    "arm_add_l": _meta("左肩内收外展", 31, "冠状面", "上臂自然下垂中立位", "正值表示左肩内收方向，负值表示左肩外展方向。", "arm_add_l", "左肩内收外展"),
    "arm_rot_l": _meta("左肩内外旋", 32, "水平面", "肩关节中立位", "正值表示左肩内旋方向，负值表示左肩外旋方向。", "arm_rot_l", "左肩内外旋"),
    "arm_flex_r": _meta("右肩屈伸", 33, "矢状面", "上臂自然下垂中立位", "正值表示右肩屈曲，负值表示右肩伸展。", "arm_flex_r", "右肩屈伸"),
    "arm_add_r": _meta("右肩内收外展", 34, "冠状面", "上臂自然下垂中立位", "正值表示右肩内收方向，负值表示右肩外展方向。", "arm_add_r", "右肩内收外展"),
    "arm_rot_r": _meta("右肩内外旋", 35, "水平面", "肩关节中立位", "正值表示右肩内旋方向，负值表示右肩外旋方向。", "arm_rot_r", "右肩内外旋"),
    "elbow_flex_l": _meta("左肘屈伸", 36, "矢状面", "肘关节伸直位", "正值表示左肘屈曲，负值表示左肘过伸或伸展方向。", "elbow_flex_l", "左肘屈伸"),
    "pro_sup_l": _meta("左前臂旋前旋后", 37, "水平面", "前臂中立位", "正值表示左前臂旋前方向，负值表示旋后方向。", "pro_sup_l", "左前臂旋前旋后"),
    "elbow_flex_r": _meta("右肘屈伸", 38, "矢状面", "肘关节伸直位", "正值表示右肘屈曲，负值表示右肘过伸或伸展方向。", "elbow_flex_r", "右肘屈伸"),
    "pro_sup_r": _meta("右前臂旋前旋后", 39, "水平面", "前臂中立位", "正值表示右前臂旋前方向，负值表示旋后方向。", "pro_sup_r", "右前臂旋前旋后"),
    "wrist_flex_l": _meta("左腕屈伸", 40, "矢状面", "腕关节中立位", "正值表示左腕屈曲，负值表示左腕伸展。", "wrist_flex_l", "左腕屈伸"),
    "wrist_dev_l": _meta("左腕尺桡偏", 41, "冠状面", "腕关节中立位", "正值表示模型定义的尺桡偏正方向，负值表示相反方向。", "wrist_dev_l", "左腕尺桡偏"),
    "wrist_flex_r": _meta("右腕屈伸", 42, "矢状面", "腕关节中立位", "正值表示右腕屈曲，负值表示右腕伸展。", "wrist_flex_r", "右腕屈伸"),
    "wrist_dev_r": _meta("右腕尺桡偏", 43, "冠状面", "腕关节中立位", "正值表示模型定义的尺桡偏正方向，负值表示相反方向。", "wrist_dev_r", "右腕尺桡偏"),
    "pelvis_tilt": _meta("骨盆前后倾", 50, "矢状面", "骨盆中立位", "正值表示骨盆前倾，负值表示骨盆后倾。", "pelvis_tilt", "骨盆前后倾"),
    "pelvis_list": _meta("骨盆侧倾", 51, "冠状面", "骨盆中立位", "正值表示 OpenSim 默认 pelvis_list 正方向的侧倾，负值表示相反方向。", "pelvis_list", "骨盆侧倾"),
    "pelvis_rotation": _meta("骨盆旋转", 52, "水平面", "骨盆中立位", "正值表示 OpenSim 默认 pelvis_rotation 正方向的旋转，负值表示相反方向。", "pelvis_rotation", "骨盆旋转"),
    "hip_flexion_l": _meta("左髋屈伸", 60, "矢状面", "解剖中立位", "正值表示左髋屈曲，负值表示左髋伸展。", "hip_flexion_l", "左髋屈伸"),
    "hip_adduction_l": _meta("左髋内收外展", 61, "冠状面", "解剖中立位", "正值表示左髋内收方向，负值表示左髋外展方向。", "hip_adduction_l", "左髋内收外展"),
    "hip_rotation_l": _meta("左髋内外旋", 62, "水平面", "解剖中立位", "正值表示左髋内旋方向，负值表示左髋外旋方向。", "hip_rotation_l", "左髋内外旋"),
    "hip_flexion_r": _meta("右髋屈伸", 63, "矢状面", "解剖中立位", "正值表示右髋屈曲，负值表示右髋伸展。", "hip_flexion_r", "右髋屈伸"),
    "hip_adduction_r": _meta("右髋内收外展", 64, "冠状面", "解剖中立位", "正值表示右髋内收方向，负值表示右髋外展方向。", "hip_adduction_r", "右髋内收外展"),
    "hip_rotation_r": _meta("右髋内外旋", 65, "水平面", "解剖中立位", "正值表示右髋内旋方向，负值表示右髋外旋方向。", "hip_rotation_r", "右髋内外旋"),
    "knee_angle_l": _meta("左膝屈伸", 70, "矢状面", "膝关节伸直位", "正值表示左膝屈曲，负值表示左膝过伸或伸展方向。", "knee_angle_l", "左膝屈伸"),
    "knee_angle_r": _meta("右膝屈伸", 73, "矢状面", "膝关节伸直位", "正值表示右膝屈曲，负值表示右膝过伸或伸展方向。", "knee_angle_r", "右膝屈伸"),
    "ankle_angle_l": _meta("左踝背屈跖屈", 80, "矢状面", "踝关节中立位", "正值表示左踝背屈，负值表示左踝跖屈。", "ankle_angle_l", "左踝背屈跖屈"),
    "subtalar_angle_l": _meta("左距下关节内外翻", 81, "冠状面", "足部中立位", "正值表示左足内翻方向，负值表示左足外翻方向。", "subtalar_angle_l", "左距下关节内外翻"),
    "mtp_angle_l": _meta("左跖趾关节屈伸", 82, "矢状面", "足趾中立位", "正值表示左足趾伸展/背屈方向，负值表示足趾屈曲方向。", "mtp_angle_l", "左跖趾关节屈伸"),
    "ankle_angle_r": _meta("右踝背屈跖屈", 83, "矢状面", "踝关节中立位", "正值表示右踝背屈，负值表示右踝跖屈。", "ankle_angle_r", "右踝背屈跖屈"),
    "subtalar_angle_r": _meta("右距下关节内外翻", 84, "冠状面", "足部中立位", "正值表示右足内翻方向，负值表示右足外翻方向。", "subtalar_angle_r", "右距下关节内外翻"),
    "mtp_angle_r": _meta("右跖趾关节屈伸", 85, "矢状面", "足趾中立位", "正值表示右足趾伸展/背屈方向，负值表示足趾屈曲方向。", "mtp_angle_r", "右跖趾关节屈伸"),
}


def metadata_for(column: str) -> JointMeta:
    if column in JOINT_META:
        return JOINT_META[column]
    clean = column.replace("_", " ")
    return JointMeta(
        zh=clean,
        order=999,
        plane="未知",
        neutral="未知",
        direction="未知指标，未在报告中作为正式关节活动度解释。",
        definition=f"未识别 OpenSim 坐标 `{column}`，报告默认隐藏该列。",
        boundary=GENERIC_BOUNDARY,
        supported=False,
    )


def is_supported_joint_column(column: str) -> bool:
    return metadata_for(column).supported


def ordered_columns(columns: list[str]) -> list[str]:
    return sorted(columns, key=lambda c: (metadata_for(c).order, metadata_for(c).zh))
