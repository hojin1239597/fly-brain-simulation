"""FlyWire FAFB v783 뇌 지도 위의 파킨슨 모형.

신경 위치, 세포 종류, 집단 사이 시냅스 수는 data/flywire_brain.json에 있다.
그 파일은 FlyWire 공개 연결표와 주석에서 sim/build_flywire.py가 만든다.

빠른 활동은 그 시냅스 비율을 따른다. 아세틸콜린은 흥분, GABA와 글루탐산은
억제, 도파민·세로토닌·옥토파민은 조절 신호다.

파킨슨의 원인은 PAM·PPL이 보내는 시냅스를 줄이는 것이다. 다른 집단의 활동은
그 줄어든 입력으로만 바뀐다. 걸음은 식도하와 하행신경의 활동으로만 정한다.
도파민이 줄었다는 이유로 미는 힘이나 떨림을 따로 넣지 않는다.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from sim.body import Arena

ROOT = Path(__file__).resolve().parents[1]
BRAIN_PATH = ROOT / "data" / "flywire_brain.json"

DT = 0.02
TAU = 0.09
FRAME_DT = 0.1
SETTLE = 3.0
MEASURE = 4.0
FOLLOW = 0.45
CLIMB_RATE = 0.009
GAIN = 3.15
INH_SCALE = 1.25
MOD_GAIN = 2.4
GLOBAL_INH = 0.85
ADAPT_TAU = 0.42
ADAPT_GAIN = 0.7

DISEASES = ("parkinson",)

_BRAIN: dict | None = None
_REFERENCE: dict | None = None
_DOSE: dict[str, list[dict]] = {}


def _brain() -> dict:
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = json.loads(BRAIN_PATH.read_text(encoding="utf-8"))
    return _BRAIN


def _index() -> dict[str, int]:
    return {group["id"]: i for i, group in enumerate(_brain()["groups"])}


def _fast_weights() -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
    data = _brain()
    exc = data["excitatory"]
    inh = data["inhibitory"]
    mod = data["modulatory"]
    n = len(exc)
    we = [[0.0] * n for _ in range(n)]
    wi = [[0.0] * n for _ in range(n)]
    wm = [[0.0] * n for _ in range(n)]
    for post in range(n):
        total = sum(exc[post]) + sum(inh[post]) or 1.0
        for pre in range(n):
            we[post][pre] = exc[post][pre] / total
            wi[post][pre] = inh[post][pre] / total
            wm[post][pre] = mod[post][pre] / total
    return we, wi, wm


def _sigmoid(value: float) -> float:
    if value > 14:
        return 1.0
    if value < -14:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _grade(score: float) -> str:
    if score < 0.02:
        return "거의 없음"
    if score < 0.10:
        return "작음"
    return "큼"


def _bias(ids: dict[str, int], n: int) -> list[float]:
    bias = [-1.15] * n
    bias[ids["OPTIC"]] = -0.55
    bias[ids["AL"]] = -1.05
    bias[ids["KCab"]] = -2.15
    bias[ids["KCg"]] = -2.15
    bias[ids["PAM"]] = -1.55
    bias[ids["PPL"]] = -1.25
    bias[ids["MBON"]] = -1.35
    bias[ids["GNG"]] = -1.25
    bias[ids["DN"]] = -1.2
    return bias


class Living:
    """끊기지 않는 한 마리. 질병과 강도는 바깥에서 넣고, 뇌와 몸이 그 상태를 따라간다."""

    def __init__(self) -> None:
        ids = _index()
        self.n = len(_brain()["groups"])
        self.we, self.wi, self.wm = _fast_weights()
        self.bias = _bias(ids, self.n)
        self.kcab, self.kcg = ids["KCab"], ids["KCg"]
        self.pam, self.ppl = ids["PAM"], ids["PPL"]
        self.gng, self.dn, self.optic = ids["GNG"], ids["DN"], ids["OPTIC"]
        self.disease = "parkinson"
        self.severity = 0.0
        self._body()

    def _body(self) -> None:
        self.arena = Arena()
        self.r = [0.12] * self.n
        self.climb_ema = 0.0
        if _REFERENCE is not None and _REFERENCE.get("rates"):
            self.r = [float(value) for value in _REFERENCE["rates"]]
            self.climb_ema = float(_REFERENCE["climb_raw"])
        self.adapt = list(self.r)
        self.pre = [1.0] * self.n
        self.level = 0.0
        self.t = 0.0
        self.heading = math.pi / 2
        self.samples: list[tuple[float, float, float, float, float]] = []
        self.pam_surv = 1.0
        self.ppl_surv = 1.0
        self.kc_keep = 1.0

    def command(self, disease: str, severity: float) -> None:
        if disease not in DISEASES:
            raise ValueError(disease)
        self.disease = disease
        self.severity = _clip(severity)

    def reset(self) -> None:
        disease, severity = self.disease, self.severity
        self._body()
        self.disease = disease
        self.severity = severity
        self.level = severity

    def advance(self, seconds: float, follow: bool) -> dict:
        steps = max(1, int(round(seconds / DT)))
        frame: dict = {}
        for _ in range(steps):
            if follow:
                alpha = 1.0 - math.exp(-DT / FOLLOW)
                self.level += (self.severity - self.level) * alpha
            else:
                self.level = self.severity
            frame = self._step()
        return frame

    def _losses(self) -> tuple[float, float, float]:
        level = self.level
        return (
            max(0.02, 1.0 - level ** 1.25),
            max(0.02, 1.0 - level ** 1.05),
            1.0,
        )

    def _step(self) -> dict:
        pam_surv, ppl_surv, kc_keep = self._losses()
        self.pam_surv, self.ppl_surv, self.kc_keep = pam_surv, ppl_surv, kc_keep
        self.pre[self.pam] = pam_surv
        self.pre[self.ppl] = ppl_surv
        self.pre[self.kcab] = kc_keep
        self.pre[self.kcg] = kc_keep
        ext = [0.0] * self.n
        ext[self.gng] += 0.55
        ext[self.dn] += 0.28
        neural = [0.0] * self.n
        for post in range(self.n):
            acc = 0.0
            for pre_i in range(self.n):
                acc += (self.we[post][pre_i] - INH_SCALE * self.wi[post][pre_i]) * self.r[pre_i] * self.pre[pre_i]
                acc += MOD_GAIN * self.wm[post][pre_i] * self.r[pre_i] * self.pre[pre_i]
            neural[post] = GAIN * acc
        mean_r = sum(self.r) / self.n
        for i in range(self.n):
            total = neural[i] - GLOBAL_INH * mean_r + self.bias[i] + ext[i] - ADAPT_GAIN * self.adapt[i]
            target = _sigmoid(total)
            self.r[i] += DT / TAU * (target - self.r[i])
            self.adapt[i] += DT / ADAPT_TAU * (self.r[i] - self.adapt[i])
        leg = max(0.0, 0.58 * self.r[self.gng] + 0.42 * self.r[self.dn] - 0.2)
        wing = max(0.0, 0.62 * self.r[self.optic] + 0.38 * self.r[self.dn] - 0.22)
        drive = min(1.0, 0.2 + 0.8 * leg)
        wing_cmd = min(1.0, wing)
        self.heading = _wrap(self.heading + DT * 0.55 * math.sin(self.t * 0.31))
        pose = self.arena.step({
            "walker": {
                "drive": drive,
                "tremor": 0.0,
                "wing": wing_cmd,
                "tone": 1.0,
                "heading": self.heading if drive > 0.12 else None,
                "lift": 0.0,
            },
            "climber": {
                "drive": drive,
                "tremor": 0.0,
                "wing": 0.0,
                "tone": 1.0,
                "heading": None,
                "lift": 0.0,
            },
        })
        if not pose["respawned"]:
            self.climb_ema += 0.015 * (pose["up_speed"] - self.climb_ema)
        self.t += DT
        self.samples.append((self.t, pose["x"], pose["y"], self.climb_ema, drive))
        self.samples = [item for item in self.samples if item[0] >= self.t - MEASURE]
        loss = [1.0] * self.n
        loss[self.pam] = pam_surv
        loss[self.ppl] = ppl_surv
        loss[self.kcab] = kc_keep
        loss[self.kcg] = kc_keep
        return {
            "t": round(self.t, 2),
            "phase": "지내는 중",
            "damage": round(self.level, 3),
            "rates": [round(value, 3) for value in self.r],
            "loss": [round(value, 3) for value in loss],
            "fly": {
                "x": round(pose["x"], 4),
                "y": round(pose["y"], 4),
                "z": round(pose["z"], 4),
                "heading": round(self.heading, 3),
                "quat": pose["quat"],
                "joints": pose["joints"],
                "climb_quat": pose["climb_pose"]["quat"],
                "climb_joints": pose["climb_pose"]["joints"],
                "speed": round(pose["speed"], 4),
                "climb": round(min(1.0, self.climb_ema / CLIMB_RATE), 3),
                "wing": round(wing_cmd, 3),
            },
        }

    def window(self, t0: float, t1: float) -> dict:
        rows = [item for item in self.samples if t0 <= item[0] < t1]
        if len(rows) < 2:
            rows = self.samples
        climb = sum(item[3] for item in rows) / max(1, len(rows))
        drive = sum(item[4] for item in rows) / max(1, len(rows))
        return {
            "disease": self.disease,
            "severity": round(self.level, 4),
            "pam_surv": self.pam_surv,
            "ppl_surv": self.ppl_surv,
            "synapses": round(self.kc_keep, 4),
            "climb_raw": climb,
            "walk_raw": drive,
            "rates": [float(value) for value in self.r],
            "frames": [],
        }


def _wrap(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def _run(disease: str, severity: float, record: bool) -> dict:
    fly = Living()
    fly.command(disease, severity)
    fly.level = severity
    frame = fly.advance(SETTLE + MEASURE, follow=False)
    trial = fly.window(SETTLE, SETTLE + MEASURE)
    if record:
        trial["frames"] = [frame]
    return trial


def _reference() -> dict:
    global _REFERENCE
    if _REFERENCE is None:
        _REFERENCE = _run("parkinson", 0.0, False)
    return _REFERENCE


def _ratio(value: float, baseline: float) -> float:
    if baseline <= 1e-6:
        return 0.0
    return _clip(value / baseline)


def _scored(trial: dict) -> dict:
    ref = _reference()
    locomotion = _ratio(trial["walk_raw"], ref["walk_raw"])
    climbing = _ratio(trial["climb_raw"], ref["climb_raw"])
    groups = _brain()["groups"]
    counts = {group["id"]: group["count"] for group in groups}
    pam_n = counts["PAM"]
    ppl_n = counts["PPL"]
    dopamine = (pam_n * trial["pam_surv"] + ppl_n * trial["ppl_surv"]) / (pam_n + ppl_n)
    trial = {**trial, "dopamine": dopamine}
    names = [group["id"] for group in groups]
    ref_rates = _reference()["rates"]

    def keep(name: str) -> float:
        index = names.index(name)
        base = ref_rates[index]
        if base <= 1e-6:
            return 0.0
        return trial["rates"][index] / base

    focused = ("KCab", "KCg", "MBON", "MB")
    score = sum(1.0 - keep(name) for name in focused) / len(focused)
    score = _clip(score)
    change_label = "도파민 신경 생존"
    change_value = trial["dopamine"]
    remaining_dopamine = round(pam_n * trial["pam_surv"] + ppl_n * trial["ppl_surv"])
    chain = [
        {"label": "뇌 손상", "value": f"{trial['severity'] * 100:.0f}%"},
        {"label": "도파민 신경", "value": f"{remaining_dopamine} / {pam_n + ppl_n}"},
        {"label": "버섯체 활동", "value": f"{(1.0 - score) * 100:.0f}%"},
        {"label": "걸음", "value": f"{locomotion * 100:.0f}%"},
    ]
    story = (
        f"도파민 신경은 {remaining_dopamine} / {pam_n + ppl_n}입니다. "
        f"케니언 α/β 활동은 건강한 파리의 {keep('KCab') * 100:.0f}%, "
        f"γ는 {keep('KCg') * 100:.0f}%, 버섯체 출력은 {keep('MBON') * 100:.0f}%입니다. "
        f"하행신경 활동은 {keep('DN') * 100:.0f}%이고, 그 활동으로 정한 걸음은 {locomotion * 100:.0f}%입니다."
    )
    payload = {
        "disease": trial["disease"],
        "severity": trial["severity"],
        "disease_score": round(score, 4),
        "grade": _grade(score),
        "locomotion": round(locomotion, 4),
        "climbing": round(climbing, 4),
        "dopamine": trial["dopamine"],
        "synapses": trial["synapses"],
        "change_label": change_label,
        "change_value": round(change_value, 4),
        "chain": chain,
        "story": story,
        "groups": [group["id"] for group in groups],
    }
    if trial["frames"]:
        payload["frames"] = trial["frames"]
    return payload


def simulate(disease: str, severity: float) -> dict:
    return _scored(_run(disease, _clip(severity), True))


def public_simulate(disease: str, severity: float) -> dict:
    return simulate(disease, severity)


def dose_response(disease: str) -> list[dict]:
    if disease not in _DOSE:
        points = []
        for step in range(11):
            severity = step / 10
            trial = _scored(_run(disease, severity, False))
            points.append({key: trial[key] for key in (
                "severity", "disease_score", "grade", "locomotion",
                "climbing", "dopamine", "synapses", "change_label", "change_value",
            )})
        _DOSE[disease] = points
    return _DOSE[disease]


def meta() -> dict:
    data = _brain()
    return {
        "dataset": data["source"]["dataset"],
        "neuron_count": data["neuron_count"],
        "citations": data["source"]["citations"],
        "transmitter_rule": data["transmitter_rule"],
        "groups": data["groups"],
        "diseases": {
            "parkinson": {
                "name": "파킨슨",
                "cause": "PAM·PPL·PPM 도파민 신경이 보내는 시냅스를 줄입니다.",
                "body": "걸음은 식도하와 하행신경의 활동이 변한 만큼만 달라집니다.",
            },
        },
        "notes": [
            "점 하나의 위치는 FlyWire FAFB v783에 등록된 신경의 좌표입니다.",
            "파리는 끊기지 않고 접시 위를 지냅니다. 뇌 손상은 PAM·PPL이 보내는 시냅스만 줄입니다.",
            "다른 부위의 활동은 그 시냅스 변화로만 계산됩니다. 미는 힘과 떨림은 도파민 비율로 따로 넣지 않습니다.",
            "몸의 위치와 관절은 MuJoCo가 적분합니다. 발이 바닥에 있을 때만 앞으로 밀고, 그 힘의 크기는 식도하·하행 활동으로 정합니다.",
        ],
    }


_LIVE: Living | None = None


def _living() -> Living:
    global _LIVE
    if _LIVE is None:
        _LIVE = Living()
    return _LIVE


def _fresh_path(fly: Living, trial: dict) -> dict:
    if fly.t < 1.5:
        ref = _reference()
        trial["walk_raw"] = ref["walk_raw"]
        trial["climb_raw"] = ref["climb_raw"]
    return trial


def live_tick(disease: str, severity: float, seconds: float) -> dict:
    fly = _living()
    fly.command(disease, _clip(severity))
    frame = fly.advance(max(FRAME_DT, min(0.4, seconds)), follow=True)
    trial = _fresh_path(fly, fly.window(fly.t - MEASURE, fly.t + DT))
    summary = _scored(trial)
    summary["frame"] = frame
    return summary


def live_reset(disease: str, severity: float) -> dict:
    fly = _living()
    fly.command(disease, _clip(severity))
    fly.reset()
    frame = fly.advance(FRAME_DT, follow=False)
    summary = _scored(_fresh_path(fly, fly.window(0.0, fly.t + DT)))
    summary["frame"] = frame
    return summary


def warmup() -> None:
    _reference()
    for disease in DISEASES:
        dose_response(disease)


def run_checks() -> None:
    _reference()
    report = []
    for disease in DISEASES:
        for severity in (0.0, 0.5, 1.0):
            trial = _run(disease, severity, False)
            scored = _scored(trial)
            report.append((disease, severity, scored, trial))
            names = [group["id"] for group in _brain()["groups"]]
            kcab = trial["rates"][names.index("KCab")]
            dn = trial["rates"][names.index("DN")]
            print(
                f"{disease:10} {severity:.1f}  mb_drop {scored['disease_score']:.3f} {scored['grade']:6}  "
                f"walk {scored['locomotion']:.2f} climb {scored['climbing']:.2f} "
                f"DA {scored['dopamine']:.2f}  KCab {kcab:.3f} DN {dn:.3f}"
            )
    healthy = report[0][2]
    mild_p = report[1][2]
    severe_p = report[2][2]
    names = [group["id"] for group in _brain()["groups"]]
    kcab_i = names.index("KCab")
    dn_i = names.index("DN")
    assert healthy["climbing"] >= 0.8, healthy
    assert healthy["locomotion"] >= 0.8, healthy
    assert healthy["disease_score"] < 0.02, healthy
    assert healthy["dopamine"] > 0.95, healthy
    assert severe_p["dopamine"] < 0.08, severe_p
    assert severe_p["disease_score"] > mild_p["disease_score"] > healthy["disease_score"]
    assert severe_p["locomotion"] > 0.75, severe_p
    assert severe_p["climbing"] > 0.75, severe_p
    assert report[2][3]["rates"][kcab_i] < report[0][3]["rates"][kcab_i]
    assert abs(report[2][3]["rates"][dn_i] - report[0][3]["rates"][dn_i]) < 0.02
    print("확인 통과")


if __name__ == "__main__":
    run_checks()
