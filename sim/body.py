"""MuJoCo로 초파리 몸을 민다.

접시 위의 파리와 비탈의 파리를 한 장면에서 같이 적분한다.
다리 관절은 위치 구동이고, 바닥에 발이 닿아 있을 때만 앞으로 민다.
떨림은 관절 목표와 몸통 토크에 더한다. 기어오르기는 같은 걸음이
중력에 맞서 비탈을 오르는 높이다.
"""

from __future__ import annotations

import math

import mujoco
import numpy as np

ARENA_RADIUS = 0.34
RAMP_GAIN = 0.02
JOINT_NAMES = (
    "abdomen",
    "wing_l",
    "wing_r",
    "hip_fl",
    "knee_fl",
    "hip_fr",
    "knee_fr",
    "hip_ml",
    "knee_ml",
    "hip_mr",
    "knee_mr",
    "hip_hl",
    "knee_hl",
    "hip_hr",
    "knee_hr",
)
LEGS = (
    ("fl", 0.010, 0.008, 0.0),
    ("fr", 0.010, -0.008, math.pi),
    ("ml", 0.0, 0.010, math.pi),
    ("mr", 0.0, -0.010, 0.0),
    ("hl", -0.010, 0.007, 0.0),
    ("hr", -0.010, -0.007, math.pi),
)

_MODEL: mujoco.MjModel | None = None


def _xml() -> str:
    parts = [
        """
<mujoco model="fruitfly">
  <compiler angle="radian" inertiafromgeom="true"/>
  <option timestep="0.005" gravity="0 0 -9.81" integrator="implicitfast" cone="elliptic" iterations="12" ls_iterations="6"/>
  <default>
    <geom rgba="0.77 0.64 0.45 1" condim="3" friction="1.2 0.05 0.01" solref="0.02 1"/>
    <joint damping="0.002" armature="0.00008"/>
    <position kp="0.055" kv="0.0035" ctrllimited="true" ctrlrange="-1.4 1.4"/>
  </default>
  <worldbody>
    <light pos="0 0 1.2" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="2 2 0.1" friction="0.18 0.01 0.002"/>
"""
    ]
    for index in range(18):
        angle = 2 * math.pi * index / 18
        length = ARENA_RADIUS * math.tan(math.pi / 18)
        parts.append(
            f'<geom name="rim{index}" type="box" pos="{ARENA_RADIUS * math.cos(angle):.4f} '
            f'{ARENA_RADIUS * math.sin(angle):.4f} 0.025" euler="0 0 {angle + math.pi / 2:.4f}" '
            f'size="{length:.4f} 0.008 0.025" rgba="0.25 0.32 0.22 1"/>'
        )
    parts.append(
        """
    <geom name="ramp" type="box" pos="0.78 0.55 0.08" euler="0 -0.42 0"
          size="0.24 0.1 0.006" friction="0.28 0.015 0.002" rgba="0.45 0.5 0.42 1"/>
"""
    )
    for prefix, origin in (("w", "0 0 0.04"), ("c", "0.62 0.50 0.08")):
        yaw = "0.6" if prefix == "c" else "1.5708"
        parts.append(
            f"""
    <body name="{prefix}_thorax" pos="{origin}" euler="0 0 {yaw}">
      <freejoint name="{prefix}_root"/>
      <geom name="{prefix}_thorax" type="ellipsoid" size="0.013 0.008 0.007" mass="0.0011"/>
      <body name="{prefix}_abdomen" pos="-0.012 0 0">
        <joint name="{prefix}_abdomen" type="hinge" axis="0 1 0" range="-1.1 0.5"/>
        <geom type="ellipsoid" size="0.012 0.007 0.006" pos="-0.009 0 0" mass="0.0007"/>
      </body>
      <body name="{prefix}_head" pos="0.013 0 0.002">
        <geom type="sphere" size="0.006" mass="0.00015"/>
        <geom type="sphere" pos="0.002 0.0045 0.001" size="0.0035" rgba="0.75 0.12 0.08 1" mass="0.00001"/>
        <geom type="sphere" pos="0.002 -0.0045 0.001" size="0.0035" rgba="0.75 0.12 0.08 1" mass="0.00001"/>
      </body>
      <body name="{prefix}_wing_l" pos="-0.002 0.005 0.006">
        <joint name="{prefix}_wing_l" type="hinge" axis="1 0 0" range="-0.5 1.5"/>
        <geom type="box" size="0.011 0.009 0.0004" pos="-0.002 0.012 0" mass="0.00002" rgba="0.85 0.92 0.95 0.45"/>
      </body>
      <body name="{prefix}_wing_r" pos="-0.002 -0.005 0.006">
        <joint name="{prefix}_wing_r" type="hinge" axis="1 0 0" range="-1.5 0.5"/>
        <geom type="box" size="0.011 0.009 0.0004" pos="-0.002 -0.012 0" mass="0.00002" rgba="0.85 0.92 0.95 0.45"/>
      </body>
"""
        )
        for name, x, y, _phase in LEGS:
            sign = 1 if y > 0 else -1
            parts.append(
                f"""
      <body name="{prefix}_leg_{name}" pos="{x:.4f} {y:.4f} -0.004">
        <joint name="{prefix}_hip_{name}" type="hinge" axis="{0:.1f} {sign:.1f} 0" range="-1.2 1.2"/>
        <geom type="capsule" fromto="0 0 0 {0.003 * sign:.4f} {0.006 * sign:.4f} -0.003" size="0.0013"/>
        <body pos="{0.003 * sign:.4f} {0.006 * sign:.4f} -0.003">
          <joint name="{prefix}_knee_{name}" type="hinge" axis="0 {sign:.1f} 0" range="-0.2 1.6"/>
          <geom name="{prefix}_foot_{name}" type="capsule" fromto="0 0 0 {0.002 * sign:.4f} {0.005 * sign:.4f} -0.014"
                size="0.001" friction="0.23 0.02 0.002"/>
        </body>
      </body>
"""
            )
        parts.append("    </body>")
    parts.append("  </worldbody>\n  <actuator>")
    for prefix in ("w", "c"):
        for joint in JOINT_NAMES:
            parts.append(f'<position name="{prefix}_{joint}" joint="{prefix}_{joint}"/>')
    parts.append("</actuator>\n</mujoco>")
    return "".join(parts)


def model() -> mujoco.MjModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = mujoco.MjModel.from_xml_string(_xml())
    return _MODEL


def _yaw_of(quat: np.ndarray) -> float:
    qw, qx, qy, qz = quat
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def _attitude(quat: np.ndarray) -> tuple[float, float, float]:
    qw, qx, qy, qz = (float(v) for v in quat)
    roll = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (qw * qy - qz * qx))))
    return roll, pitch, _yaw_of(quat)


def _wrap(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def _quat_to_three(quat: np.ndarray) -> list[float]:
    """MuJoCo (w,x,y,z), z가 위. Three.js는 y가 위이고 (x,y,z,w)."""
    rotation = np.zeros(9)
    mujoco.mju_quat2Mat(rotation, np.asarray(quat, dtype=float))
    matrix = rotation.reshape(3, 3)
    swap = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])
    turned = swap @ matrix @ swap.T
    trace = float(turned[0, 0] + turned[1, 1] + turned[2, 2])
    if trace > 0:
        scale = math.sqrt(trace + 1.0) * 2
        qw = 0.25 * scale
        qx = (turned[2, 1] - turned[1, 2]) / scale
        qy = (turned[0, 2] - turned[2, 0]) / scale
        qz = (turned[1, 0] - turned[0, 1]) / scale
    else:
        qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
    return [round(qx, 4), round(qy, 4), round(qz, 4), round(qw, 4)]


class Arena:
    """접시 파리와 비탈 파리를 한 번에 적분한다."""

    def __init__(self) -> None:
        self.model = model()
        self.data = mujoco.MjData(self.model)
        self.phase = {"w": 0.0, "c": 0.0}
        self.climb_height = 0.0
        self._climb_origin = 0.0
        self._uphill = np.array([1.0, 0.0, 0.0])
        self._ramp_normal = np.array([0.0, 0.0, 1.0])
        self._prev = {"w": np.zeros(3), "c": np.zeros(3)}
        self._hold = None
        self._climb_start = np.array([0.0, 0.0, 0.04, 1.0, 0.0, 0.0, 0.0])
        self._adr = {}
        self._act = {}
        self._body = {}
        self._feet = {}
        for prefix in ("w", "c"):
            root = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{prefix}_root")
            self._adr[prefix] = (
                int(self.model.jnt_qposadr[root]),
                int(self.model.jnt_dofadr[root]),
            )
            self._body[prefix] = int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, f"{prefix}_thorax"))
            self._act[prefix] = {
                name: int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{prefix}_{name}"))
                for name in JOINT_NAMES
            }
            self._feet[prefix] = {
                int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, f"{prefix}_foot_{name}"))
                for name, *_rest in LEGS
            }
        self._place_climber()
        self._settle()

    def _place_climber(self) -> None:
        mujoco.mj_forward(self.model, self.data)
        geom = int(mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "ramp"))
        center = self.data.geom_xpos[geom].copy()
        normal = self.data.geom_xmat[geom].reshape(3, 3)[:, 2].copy()
        normal /= np.linalg.norm(normal)
        if normal[2] < 0:
            normal *= -1
        gravity = np.array([0.0, 0.0, -1.0])
        downhill = gravity - np.dot(gravity, normal) * normal
        uphill = -downhill
        uphill /= np.linalg.norm(uphill)
        self._uphill = uphill
        self._ramp_normal = normal
        axis_z = normal
        axis_x = uphill - np.dot(uphill, axis_z) * axis_z
        axis_x /= np.linalg.norm(axis_x)
        axis_y = np.cross(axis_z, axis_x)
        rotation = np.column_stack([axis_x, axis_y, axis_z])
        quat = np.zeros(4)
        mujoco.mju_mat2Quat(quat, rotation.reshape(-1))
        address, _dof = self._adr["c"]
        self.data.qpos[address : address + 3] = center - uphill * 0.14 + normal * 0.03
        self.data.qpos[address + 3 : address + 7] = quat
        self.data.qvel[:] = 0
        mujoco.mj_forward(self.model, self.data)

    def _settle(self) -> None:
        for _ in range(60):
            self._drive("w", drive=0.0, tremor=0.0, wing=0.0, tone=1.0, heading=None, lift=0.0)
            self._drive("c", drive=0.0, tremor=0.0, wing=0.0, tone=1.0, heading=None, lift=0.0, thrust=self._uphill)
            mujoco.mj_step(self.model, self.data)
        self._climb_origin = float(self.data.xpos[self._body["c"], 2])
        self.climb_height = 0.0
        address, _dof = self._adr["c"]
        self._climb_start = self.data.qpos[address : address + 7].copy()

    def _feet_down(self, prefix: str) -> int:
        count = 0
        for index in range(self.data.ncon):
            geom1 = int(self.data.contact[index].geom1)
            geom2 = int(self.data.contact[index].geom2)
            if geom1 in self._feet[prefix] or geom2 in self._feet[prefix]:
                count += 1
        return count

    def _drive(
        self,
        prefix: str,
        drive: float,
        tremor: float,
        wing: float,
        tone: float,
        heading: float | None,
        lift: float,
        thrust: np.ndarray | None = None,
    ) -> None:
        step = float(self.model.opt.timestep)
        omega = 7.0 + 28.0 * drive
        self.phase[prefix] += step * omega
        qpos, qvel = self._adr[prefix]
        quat = self.data.qpos[qpos + 3 : qpos + 7]
        _roll, _pitch, yaw = _attitude(quat)
        spatial = np.zeros(6)
        mujoco.mj_objectVelocity(self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, self._body[prefix], spatial, 0)
        ang = spatial[:3]
        lin = spatial[3:]
        shake = tremor * math.sin(self.phase[prefix] * 9.0)
        for name, _x, _y, offset in LEGS:
            swing = math.sin(self.phase[prefix] + offset)
            hip = 1.15 * drive * swing + 0.55 * shake
            knee = 0.22 + max(0.0, swing) * min(1.15, 3.2 * drive)
            self.data.ctrl[self._act[prefix][f"hip_{name}"]] = hip
            self.data.ctrl[self._act[prefix][f"knee_{name}"]] = knee
        self.data.ctrl[self._act[prefix]["abdomen"]] = -0.85 * (1.0 - tone) + 0.25 * shake
        flap = math.sin(self.phase[prefix] * (2.2 + 5.0 * wing)) * (0.15 + 1.15 * wing)
        self.data.ctrl[self._act[prefix]["wing_l"]] = 0.25 + flap
        self.data.ctrl[self._act[prefix]["wing_r"]] = -0.25 - flap

        body = self._body[prefix]
        self.data.xfrc_applied[body] = 0.0
        hold = 1.0 - 0.8 * tremor
        torque = np.zeros(3)
        if heading is not None:
            torque[2] = 0.00045 * max(0.35, drive) * _wrap(heading - yaw)
        rotation = np.zeros(9)
        mujoco.mju_quat2Mat(rotation, np.asarray(quat, dtype=float))
        upright = np.array([0.0, 0.0, 1.0]) if prefix == "w" else self._ramp_normal
        torque += 0.0008 * np.cross(rotation.reshape(3, 3)[:, 2], upright)
        torque -= 0.00004 * hold * np.asarray(ang, dtype=float)
        force = np.zeros(3)
        if self._feet_down(prefix) > 0 and drive > 0:
            push = min(0.018 if thrust is None else 0.05, 0.038 * (drive ** 0.64))
            if thrust is None:
                force[0] += push * math.cos(yaw)
                force[1] += push * math.sin(yaw)
            else:
                force += push * thrust
        if prefix == "w":
            address, _dof = self._adr[prefix]
            x = float(self.data.qpos[address])
            y = float(self.data.qpos[address + 1])
            radius = math.hypot(x, y)
            limit = ARENA_RADIUS * 0.82
            if radius > limit:
                inward = 6.0 * (radius - limit) / radius
                force[0] -= inward * x
                force[1] -= inward * y
                outward = (float(lin[0]) * x + float(lin[1]) * y) / radius
                if outward > 0.0:
                    force[0] -= 0.35 * outward * x / radius
                    force[1] -= 0.35 * outward * y / radius
        force[0] -= 0.18 * float(lin[0])
        force[1] -= 0.18 * float(lin[1])
        force[2] += 0.018 * lift - 0.02 * float(lin[2])
        self.data.xfrc_applied[body, 0:3] = force
        self.data.xfrc_applied[body, 3:6] = torque

    def _recycle_climber(self) -> bool:
        """비탈 끝이나 바닥에 닿으면 아래쪽에 다시 둔다."""
        address, dof = self._adr["c"]
        pos = self.data.qpos[address : address + 3]
        along = float(np.dot(pos - self._climb_start[:3], self._uphill))
        if along < 0.18 and float(pos[2]) > 0.03:
            return False
        self.data.qpos[address : address + 7] = self._climb_start
        self.data.qvel[dof : dof + 6] = 0.0
        mujoco.mj_forward(self.model, self.data)
        return True

    def freeze_climber(self) -> None:
        address, dof = self._adr["c"]
        self._hold = (self.data.qpos[address:].copy(), address, dof)

    def step(self, command: dict) -> dict:
        substeps = max(1, int(round(0.02 / float(self.model.opt.timestep))))
        before = {prefix: self.data.xpos[self._body[prefix]].copy() for prefix in ("w", "c")}
        for _ in range(substeps):
            self._drive("w", **command["walker"])
            self._drive("c", thrust=self._uphill, **command["climber"])
            mujoco.mj_step(self.model, self.data)
            if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all():
                raise RuntimeError("MuJoCo 상태가 숫자가 아니게 됐습니다")
            if self._hold is not None:
                held, address, dof = self._hold
                self.data.qpos[address:] = held
                self.data.qvel[dof:] = 0
        for prefix in ("w", "c"):
            delta = self.data.xpos[self._body[prefix]] - before[prefix]
            self._prev[prefix] = np.array([float(delta[0]), float(delta[1]), float(delta[2])]) / 0.02
        up_speed = max(0.0, float(self._prev["c"][2]))
        recycled = False
        if self._hold is None:
            climbed = float(self.data.xpos[self._body["c"], 2]) - self._climb_origin
            self.climb_height = max(self.climb_height, climbed)
            recycled = self._recycle_climber()
        pose = self.snapshot()
        pose["up_speed"] = 0.0 if recycled else up_speed
        pose["respawned"] = recycled
        return pose

    def _pose(self, prefix: str) -> dict:
        qpos, _qvel = self._adr[prefix]
        pos = self.data.qpos[qpos : qpos + 3]
        quat = self.data.qpos[qpos + 3 : qpos + 7]
        lin = self._prev[prefix]
        joints = {}
        wing_rate = 0.0
        for name in JOINT_NAMES:
            joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{prefix}_{name}")
            joints[name] = round(float(self.data.qpos[int(self.model.jnt_qposadr[joint])]), 4)
            if name.startswith("wing"):
                wing_rate += abs(float(self.data.qvel[int(self.model.jnt_dofadr[joint])]))
        return {
            "x": float(pos[0]) / ARENA_RADIUS,
            "y": float(pos[1]) / ARENA_RADIUS,
            "z": float(pos[2]),
            "speed": float(math.hypot(lin[0], lin[1])),
            "quat": _quat_to_three(quat),
            "joints": joints,
            "wing_rate": wing_rate,
        }

    def snapshot(self) -> dict:
        walker = self._pose("w")
        climber = self._pose("c")
        walker["climb"] = max(0.0, min(1.0, self.climb_height / RAMP_GAIN))
        walker["climb_pose"] = {
            "z": climber["z"],
            "quat": climber["quat"],
            "joints": climber["joints"],
            "height": round(self.climb_height, 4),
        }
        return walker


def _demo() -> None:
    def blank(drive: float, tremor: float, tone: float, heading: float | None = None) -> dict:
        pack = {
            "drive": drive,
            "tremor": tremor,
            "wing": 0.2,
            "tone": tone,
            "heading": heading,
            "lift": 0.0,
        }
        return {"walker": pack, "climber": {**pack, "heading": None}}

    for label, drive, tremor, tone in (("steady", 0.85, 0.0, 1.0), ("shake", 0.85, 0.75, 1.0)):
        arena = Arena()
        for _ in range(int(1.15 / 0.02)):
            pose = arena.step(blank(drive, tremor, tone, heading=math.pi / 2))
        print(
            label,
            "pos",
            round(pose["x"], 3),
            round(pose["y"], 3),
            "speed",
            round(pose["speed"], 3),
            "climb",
            round(pose["climb"], 3),
            "height",
            pose["climb_pose"]["height"],
            "abd",
            pose["joints"]["abdomen"],
        )


if __name__ == "__main__":
    _demo()
