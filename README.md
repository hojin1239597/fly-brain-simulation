# 초파리 뇌·몸 질병 시뮬레이션

FlyWire에 공개된 성체 초파리 뇌(FAFB, materialization 783)의 신경 좌표와 시냅스 수를 쓰고, 몸은 MuJoCo로 적분합니다. 파킨슨이 뇌와 몸에 어떻게 보이는지 보여 줍니다.

```bash
pip install -r requirements.txt
python3 server.py
```

브라우저에서 http://127.0.0.1:8765 를 엽니다. 수치 확인은 `python3 -m sim.model` 입니다.

## 뇌 지도

화면의 점 13만 9248개는 주석 파일의 실제 좌표입니다. 집단 사이 시냅스 수는 Princeton 연결표의 `syn_count`를 더한 것입니다.

- 신경 좌표·세포 종류: [flywire_annotations](https://github.com/flyconnectome/flywire_annotations) `Supplemental_file1_neuron_annotations.tsv` (Schlegel et al., Nature 2024)
- 시냅스 위치: `codex/data/fafb/783/neuropil_synapse_table.csv.gz`
- 연결: `codex/data/fafb/783/connections_princeton_no_threshold.csv.gz` (Dorkenwald et al., Nature 2024)

도파민 신경은 `cell_class == DAN`과 PAM·PPL·PPM 이름만 씁니다. 전달물질 예측이 도파민이라고 적힌 케니언 세포는 넣지 않습니다. 아세틸콜린은 흥분, GABA와 글루탐산은 억제로 두고 활동을 계산합니다.

원본이 `data/raw/`에 있으면 `python3 -m sim.build_flywire`로 `data/flywire_brain.json`과 `data/flywire_points.bin`을 다시 만들 수 있습니다.

## 몸

MuJoCo가 접시 위의 파리와 비탈 위의 파리를 같이 적분합니다. 다리는 관절 목표를 따라가고, 발이 바닥에 닿아 있을 때만 머리가 향한 쪽으로 밉니다. 접촉이 안정하도록 몸집은 실제 초파리보다 크고 무겁습니다. 비탈 끝이나 바닥에 닿으면 아래에서 다시 오릅니다.

## 파킨슨

파리는 끊기지 않고 지냅니다. 뇌 손상을 올리면 PAM 307개와 PPL·PPM 40개가 보내는 시냅스만 줄어듭니다.

다른 부위의 활동은 그 시냅스 변화로만 계산됩니다. 이 세포들의 연결은 대부분 버섯체로 가고, 하행신경 입력에서 차지하는 비율은 0.1%보다 작습니다. 그래서 버섯체 활동은 조금 줄고, 걸음과 기어오르기는 거의 그대로입니다. 느린 걸음이나 떨림은 따로 넣지 않습니다.
