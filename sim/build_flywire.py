"""FlyWire FAFB v783 공개 자료로 뇌 지도 파일을 만든다.

입력 (data/raw, 저장소에는 넣지 않는다):
- flyconnectome/flywire_annotations 의 Supplemental_file1_neuron_annotations.tsv
  Schlegel et al., Nature 2024. 신경 13만 개의 좌표와 세포 종류.
- Codex neuropil_synapse_table.csv.gz (materialization 783)
  신경마다 어느 신경필에 시냅스가 있는지.
- Codex connections_princeton_no_threshold.csv.gz
  Dorkenwald et al., Nature 2024. 신경-신경 시냅스 수.

출력:
- data/flywire_brain.json  집단 이름, 세포 수, 집단 사이 시냅스 수
- data/flywire_points.bin  화면에 뿌릴 좌표
"""

from __future__ import annotations

import csv
import gzip
import json
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT_JSON = ROOT / "data" / "flywire_brain.json"
OUT_BIN = ROOT / "data" / "flywire_points.bin"

GROUPS = [
    "OPTIC",
    "AL",
    "LH",
    "KCab",
    "KCg",
    "PAM",
    "PPL",
    "MBON",
    "MB",
    "EB",
    "FB",
    "PB",
    "GNG",
    "DN",
    "CENTRAL",
]

OPTIC_NP = {"LA", "ME", "LO", "LOP", "AME"}
SEZ_NP = {"GNG", "SAD", "AMMC"}

LABELS = {
    "OPTIC": ("시각엽", "LA·ME·LO·LOP"),
    "AL": ("더듬이엽", "후각"),
    "LH": ("측각", "선천 후각"),
    "KCab": ("케니언 α/β", "Kenyon_Cell"),
    "KCg": ("케니언 γ", "Kenyon_Cell"),
    "PAM": ("PAM 도파민", "DAN"),
    "PPL": ("PPL·PPM 도파민", "DAN"),
    "MBON": ("버섯체 출력", "MBON"),
    "MB": ("버섯체 그 밖", "MB"),
    "EB": ("타원체", "EB"),
    "FB": ("부채꼴체", "FB"),
    "PB": ("원뇌교", "PB·NO"),
    "GNG": ("식도하", "GNG·SAD"),
    "DN": ("하행신경", "descending"),
    "CENTRAL": ("나머지 중심뇌", "central"),
}


def base_neuropil(name: str) -> str:
    if name.endswith("_L") or name.endswith("_R"):
        return name[:-2]
    return name


def dan_group(cell_class: str, cell_type: str) -> str | None:
    if cell_type.startswith(("DNp", "DNpe")):
        return None
    if cell_class == "DAN" or cell_type.startswith(("PAM", "PPL", "PPM")):
        return "PAM" if cell_type.startswith("PAM") else "PPL"
    return None


def assign(row: dict[str, str], neuropil: str | None) -> str:
    cell_class = row["cell_class"]
    cell_type = row["cell_type"]
    super_class = row["super_class"]
    sub = row["cell_sub_class"]
    dopamine = dan_group(cell_class, cell_type)
    if dopamine:
        return dopamine
    if cell_class == "Kenyon_Cell":
        if sub == "KCg" or cell_type.startswith("KCg") or "KCg" in cell_type:
            return "KCg"
        return "KCab"
    if cell_class == "MBON":
        return "MBON"
    if super_class == "descending":
        return "DN"
    if super_class in {"optic", "visual_projection", "visual_centrifugal"}:
        return "OPTIC"
    if neuropil in OPTIC_NP:
        return "OPTIC"
    if neuropil == "AL" or cell_class in {"olfactory", "ALPN", "ALLN"}:
        return "AL"
    if neuropil == "LH" or cell_class == "LHLN":
        return "LH"
    if neuropil == "EB":
        return "EB"
    if neuropil == "FB":
        return "FB"
    if neuropil in {"PB", "NO"}:
        return "PB"
    if neuropil and neuropil.startswith("MB"):
        return "MB"
    if neuropil in SEZ_NP:
        return "GNG"
    return "CENTRAL"


def primary_neuropils(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        output_cols: dict[str, list[int]] = defaultdict(list)
        input_cols: dict[str, list[int]] = defaultdict(list)
        for index, name in enumerate(header):
            if name.startswith("output synapses in "):
                output_cols[base_neuropil(name.removeprefix("output synapses in "))].append(index)
            elif name.startswith("input synapses in "):
                input_cols[base_neuropil(name.removeprefix("input synapses in "))].append(index)
        bases = sorted(set(output_cols) | set(input_cols))
        for row in reader:
            best_name = ""
            best_value = 0
            for name in bases:
                total = 0
                for index in output_cols.get(name, ()):
                    total += int(row[index] or 0)
                if total == 0:
                    for index in input_cols.get(name, ()):
                        total += int(row[index] or 0)
                if total > best_value:
                    best_value = total
                    best_name = name
            if best_name:
                found[row[0]] = best_name
    return found


def main() -> None:
    print("신경필 표를 읽는 중")
    neuropil_of = primary_neuropils(RAW / "neuropil_synapse_table.csv.gz")
    print(f"  시냅스 위치가 있는 신경 {len(neuropil_of):,}")

    print("주석과 좌표를 읽는 중")
    group_of: dict[str, int] = {}
    sums = [[0.0, 0.0, 0.0] for _ in GROUPS]
    counts = [0 for _ in GROUPS]
    points: list[tuple[float, float, float, int]] = []
    index_of = {name: index for index, name in enumerate(GROUPS)}
    with open(RAW / "Supplemental_file1_neuron_annotations.tsv", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row["pos_x"]:
                continue
            name = assign(row, neuropil_of.get(row["root_id"]))
            index = index_of[name]
            # FAFB voxel is 4 x 4 x 40 nm.
            x = float(row["pos_x"]) * 4.0
            y = float(row["pos_y"]) * 4.0
            z = float(row["pos_z"]) * 40.0
            group_of[row["root_id"]] = index
            sums[index][0] += x
            sums[index][1] += y
            sums[index][2] += z
            counts[index] += 1
            points.append((x, y, z, index))
    print(f"  좌표가 있는 신경 {len(points):,}")

    print("시냅스 연결을 전달물질별로 더하는 중")
    exc = [[0 for _ in GROUPS] for _ in GROUPS]
    inh = [[0 for _ in GROUPS] for _ in GROUPS]
    mod = [[0 for _ in GROUPS] for _ in GROUPS]
    nt_counts: dict[str, int] = defaultdict(int)
    used = 0
    skipped = 0
    # FlyWire 예측 전달물질. 글루탐산은 초파리 중심뇌에서 대개 억제로 둔다.
    excitatory = {"ACH", "ACETYLCHOLINE"}
    inhibitory = {"GABA", "GLUT", "GLUTAMATE"}
    modulatory = {"DA", "DOPAMINE", "SER", "SEROTONIN", "OCT", "OCTOPAMINE", "HIS", "HISTAMINE"}
    with gzip.open(RAW / "connections_princeton_no_threshold.csv.gz", "rt", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=1):
            pre = group_of.get(row["pre_root_id"])
            post = group_of.get(row["post_root_id"])
            kind = (row.get("nt_type") or "").upper()
            nt_counts[kind] += int(row["syn_count"] or 0)
            if pre is None or post is None:
                skipped += 1
            else:
                count = int(row["syn_count"] or 0)
                if kind in excitatory:
                    exc[post][pre] += count
                elif kind in inhibitory:
                    inh[post][pre] += count
                elif kind in modulatory:
                    mod[post][pre] += count
                used += 1
            if row_number % 1000000 == 0:
                print(f"  {row_number:,}행")
    print(f"  사용한 연결 {used:,}  주석 밖 {skipped:,}")
    print("  전달물질", dict(sorted(nt_counts.items(), key=lambda item: -item[1])[:12]))
    matrix = [[exc[i][j] + inh[i][j] + mod[i][j] for j in range(len(GROUPS))] for i in range(len(GROUPS))]

    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    zs = [item[2] for item in points]
    center = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    scale = 2.0 / span

    def norm(value: float, axis: int) -> float:
        return (value - center[axis]) * scale

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_BIN.open("wb") as handle:
        handle.write(struct.pack("<I", len(points)))
        for x, y, z, index in points:
            handle.write(struct.pack("<hhhB", 
                max(-32767, min(32767, int(norm(x, 0) * 16000))),
                max(-32767, min(32767, int(norm(y, 1) * 16000))),
                max(-32767, min(32767, int(norm(z, 2) * 16000))),
                index,
            ))

    groups = []
    for index, name in enumerate(GROUPS):
        label, detail = LABELS[name]
        centroid = [0.0, 0.0, 0.0]
        if counts[index]:
            centroid = [round(norm(sums[index][axis] / counts[index], axis), 4) for axis in range(3)]
        groups.append({
            "id": name,
            "name": label,
            "detail": detail,
            "count": counts[index],
            "centroid": centroid,
        })

    payload = {
        "source": {
            "dataset": "FlyWire FAFB v783",
            "neurons": "https://github.com/flyconnectome/flywire_annotations Supplemental_file1_neuron_annotations.tsv",
            "neuropils": "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/neuropil_synapse_table.csv.gz",
            "connections": "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/connections_princeton_no_threshold.csv.gz",
            "citations": [
                "Dorkenwald et al. 2024 Nature. Neuronal wiring diagram of an adult brain.",
                "Schlegel et al. 2024 Nature. Whole-brain annotation and multi-connectome cell typing of Drosophila.",
            ],
        },
        "neuron_count": len(points),
        "coordinate_scale": scale,
        "groups": groups,
        "synapses": matrix,
        "excitatory": exc,
        "inhibitory": inh,
        "modulatory": mod,
        "transmitter_rule": "ACH 흥분, GABA·glutamate 억제, dopamine·serotonin·octopamine·histamine 조절",
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 {OUT_JSON}  {OUT_BIN} ({OUT_BIN.stat().st_size/1e6:.1f} MB)")
    print(f"{'':12}" + "".join(f"{name[:6]:>8}" for name in GROUPS))
    for index, name in enumerate(GROUPS):
        print(f"{name:12}" + "".join(f"{matrix[index][column]/1000:8.0f}" for column in range(len(GROUPS))))


if __name__ == "__main__":
    main()
