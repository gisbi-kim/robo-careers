"""Research-field glossary.

Each key is a lowercase normalized phrase. `lookup_phrases(prettified_phrases, lang)`
scans each phase phrase for occurrences of any glossary key and returns a list
of unique {term, gloss} entries, longest-match preferred.

Coverage target: core robotics sub-fields a first-year PhD student might not
immediately recognize. If a phase phrase matches nothing, we simply emit no
glossary for that phase — better to stay silent than to invent.
"""
from __future__ import annotations

import re
from typing import Iterable


# key: lowercase phrase. value: {"display": capitalized term, "ko": ..., "en": ...}
# Keep ko/en to one line each — this is context, not a textbook.
GLOSSARY: dict[str, dict[str, str]] = {
    # --- SLAM / localization / mapping ---
    "slam": {
        "display": "SLAM",
        "ko": "Simultaneous Localization and Mapping — 로봇이 미지 환경에서 자기 위치와 지도를 동시에 추정하는 문제.",
        "en": "Simultaneous Localization and Mapping — a robot estimating its own pose and a map of the environment at the same time.",
    },
    "visual slam": {
        "display": "Visual SLAM",
        "ko": "카메라 영상만을 센서로 삼아 수행하는 SLAM.",
        "en": "SLAM performed using camera imagery as the primary sensor.",
    },
    "lidar slam": {
        "display": "LiDAR SLAM",
        "ko": "LiDAR 포인트 클라우드를 기반으로 수행하는 SLAM.",
        "en": "SLAM driven by LiDAR point-cloud measurements.",
    },
    "orb-slam": {
        "display": "ORB-SLAM",
        "ko": "ORB 특징점 기반의 대표적인 visual SLAM 시스템 (Mur-Artal et al., 2015).",
        "en": "A landmark feature-based visual SLAM system (Mur-Artal et al., 2015).",
    },
    "place recognition": {
        "display": "Place Recognition",
        "ko": "이전에 방문한 장소를 다시 식별하는 문제 — SLAM의 loop closure 핵심.",
        "en": "Recognizing previously visited places — central to loop closure in SLAM.",
    },
    "scan context": {
        "display": "Scan Context",
        "ko": "LiDAR 포인트 클라우드의 방위각·거리 2D 디스크립터 (Kim & Kim, 2018).",
        "en": "A polar-angle × range 2D descriptor of LiDAR scans (Kim & Kim, 2018).",
    },
    "loop closure": {
        "display": "Loop Closure",
        "ko": "이동 경로가 기존 방문 지점으로 돌아왔음을 감지해 오차 누적을 교정하는 SLAM 단계.",
        "en": "Detecting that a trajectory has returned to a previously seen place so drift can be corrected.",
    },
    "pose graph": {
        "display": "Pose Graph",
        "ko": "자세 노드와 상대 측정 엣지로 구성된 SLAM 최적화 그래프.",
        "en": "A graph of pose nodes and relative-measurement edges used in SLAM optimization.",
    },
    "factor graph": {
        "display": "Factor Graph",
        "ko": "확률 분포를 변수-팩터 이분 그래프로 표현하는 추정 프레임워크.",
        "en": "A bipartite variable–factor graph used to represent probabilistic estimation problems.",
    },
    "bundle adjustment": {
        "display": "Bundle Adjustment",
        "ko": "카메라 파라미터와 3D 포인트를 동시에 최적화하는 SfM/SLAM의 핵심 연산.",
        "en": "Joint optimization of camera parameters and 3D points — the core of SfM/SLAM refinement.",
    },
    "visual odometry": {
        "display": "Visual Odometry",
        "ko": "연속 영상에서 카메라의 상대 움직임을 추정하는 기법.",
        "en": "Estimating camera motion from consecutive images.",
    },
    "visual inertial": {
        "display": "Visual-Inertial",
        "ko": "카메라와 관성 센서(IMU)를 결합한 상태 추정.",
        "en": "State estimation fusing a camera with inertial (IMU) measurements.",
    },
    "rao-blackwellized": {
        "display": "Rao-Blackwellized",
        "ko": "추정 변수를 샘플링 부분과 해석적 부분으로 분해해 효율을 높이는 필터 기법.",
        "en": "A filter that partitions variables into sampled and analytic parts for efficiency — core of FastSLAM/GMapping.",
    },
    "particle filter": {
        "display": "Particle Filter",
        "ko": "가중치 샘플들로 사후 분포를 근사하는 비선형 베이즈 필터.",
        "en": "A non-linear Bayesian filter that approximates the posterior with weighted samples.",
    },
    "grid mapping": {
        "display": "Grid Mapping",
        "ko": "환경을 균일한 2D/3D 격자 셀로 표현하는 SLAM 접근.",
        "en": "Representing the environment as a uniform 2D/3D occupancy grid.",
    },
    "icp": {
        "display": "ICP",
        "ko": "Iterative Closest Point — 포인트 클라우드 정합의 표준 알고리즘.",
        "en": "Iterative Closest Point — the standard point-cloud registration algorithm.",
    },
    "kiss-icp": {
        "display": "KISS-ICP",
        "ko": "경량·간결한 ICP 기반 LiDAR odometry (Vizzo et al., 2023).",
        "en": "A deliberately minimal ICP-based LiDAR odometry (Vizzo et al., 2023).",
    },
    "semantic segmentation": {
        "display": "Semantic Segmentation",
        "ko": "픽셀·포인트마다 의미 클래스(차, 사람, 도로 등)를 할당하는 조밀 분류.",
        "en": "Dense per-pixel/per-point labelling with semantic classes (car, road, person, …).",
    },
    "panoptic": {
        "display": "Panoptic Segmentation",
        "ko": "의미(semantic)와 개체(instance) 분할을 통합한 조밀 인식.",
        "en": "Dense perception that unifies semantic classes and per-instance masks.",
    },
    "moving object segmentation": {
        "display": "Moving Object Segmentation",
        "ko": "센서 데이터에서 정적 배경과 움직이는 물체를 분리해내는 문제.",
        "en": "Separating moving objects from the static background in sensor streams.",
    },
    "nerf": {
        "display": "NeRF",
        "ko": "연속 신경망으로 3D 장면을 표현·렌더하는 표현 기법 (2020).",
        "en": "Neural Radiance Fields — a continuous neural representation of 3D scenes (2020).",
    },
    "gaussian splatting": {
        "display": "Gaussian Splatting",
        "ko": "3D 가우시안 프리미티브로 장면을 표현·실시간 렌더하는 최신 기법.",
        "en": "Representing and rendering 3D scenes as a set of 3D Gaussian primitives.",
    },
    "depth estimation": {
        "display": "Depth Estimation",
        "ko": "단안·스테레오 영상에서 씬의 거리(깊이)를 추정.",
        "en": "Inferring scene depth from monocular or stereo imagery.",
    },
    "optical flow": {
        "display": "Optical Flow",
        "ko": "연속 영상 사이 픽셀별 2D 움직임 벡터장.",
        "en": "Per-pixel 2D motion field between consecutive images.",
    },
    "3d reconstruction": {
        "display": "3D Reconstruction",
        "ko": "영상·센서 데이터로부터 3D 지오메트리를 복원하는 문제.",
        "en": "Recovering 3D geometry from images or sensor data.",
    },
    "radar": {
        "display": "Radar",
        "ko": "전파 기반 거리·속도 센서 — 악천후에 강건한 로보틱스 인식 옵션.",
        "en": "Radio-frequency range/velocity sensor — robust perception option in adverse weather.",
    },
    "sonar": {
        "display": "Sonar",
        "ko": "음파 기반 수중 거리 센서.",
        "en": "Acoustic ranging sensor, standard in underwater robotics.",
    },
    "dense mapping": {
        "display": "Dense Mapping",
        "ko": "희소 특징점이 아닌 조밀한 표면·부피 표현으로 지도를 만드는 기법.",
        "en": "Building maps as dense surface or volumetric representations rather than sparse features.",
    },
    "pose-graph": {
        "display": "Pose-Graph SLAM",
        "ko": "자세 노드 + 상대 측정 엣지로 정의된 SLAM 최적화 문제.",
        "en": "SLAM formulated as a graph of pose nodes and relative-measurement edges.",
    },
    "localization": {
        "display": "Localization",
        "ko": "주어진 지도 안에서 로봇의 자기 위치를 추정하는 문제.",
        "en": "Estimating a robot's own pose within a pre-built map.",
    },
    "mulran": {
        "display": "MulRan",
        "ko": "SNU Ayoung Kim 팀의 LiDAR+radar 도시 주행 데이터셋.",
        "en": "A LiDAR + radar urban-driving dataset from Ayoung Kim's group (SNU).",
    },
    "kitti": {
        "display": "KITTI",
        "ko": "자율주행 비전·LiDAR 벤치마크 (Geiger et al., 2012).",
        "en": "Canonical autonomous-driving vision/LiDAR benchmark (Geiger et al., 2012).",
    },
    "semantickitti": {
        "display": "SemanticKITTI",
        "ko": "KITTI에 시맨틱·파놉틱 라벨을 더한 LiDAR 인식 벤치마크.",
        "en": "KITTI extended with per-point semantic/panoptic labels for LiDAR perception research.",
    },

    # --- Motion planning / control ---
    "motion planning": {
        "display": "Motion Planning",
        "ko": "시작점에서 목표점까지 충돌 없이 이동하는 궤적을 찾는 문제.",
        "en": "Finding a collision-free trajectory from start to goal.",
    },
    "rrt": {
        "display": "RRT",
        "ko": "Rapidly-exploring Random Tree — 샘플링 기반 경로 계획의 고전.",
        "en": "Rapidly-exploring Random Tree — a classic sampling-based path planner.",
    },
    "prm": {
        "display": "PRM",
        "ko": "Probabilistic Roadmap — 오프라인 샘플링으로 로드맵을 구축하는 플래너.",
        "en": "Probabilistic Roadmap — an offline-sampled graph planner.",
    },
    "trajectory optimization": {
        "display": "Trajectory Optimization",
        "ko": "미분 가능 비용 함수를 최소화해 연속 궤적을 찾는 계획 접근.",
        "en": "Finding continuous trajectories by minimizing a differentiable cost.",
    },
    "convex sets": {
        "display": "Graphs of Convex Sets (GCS)",
        "ko": "연결된 볼록 집합 그래프에서 최적 경로를 찾는 현대 동력학 플래닝 프레임워크 (Tedrake, 2022).",
        "en": "Planning by finding optimal paths through a graph of interconnected convex regions (Tedrake, 2022).",
    },
    "mpc": {
        "display": "MPC",
        "ko": "Model Predictive Control — 매 스텝 짧은 호라이즌을 최적화해 제어입력을 결정.",
        "en": "Model Predictive Control — repeatedly solve a short-horizon optimal control problem online.",
    },
    "lqr": {
        "display": "LQR",
        "ko": "선형 이차 레귤레이터 — 선형계에서 해석적 최적 제어 해.",
        "en": "Linear Quadratic Regulator — closed-form optimal control for linear systems.",
    },
    "reciprocal velocity": {
        "display": "Reciprocal Velocity Obstacles (RVO)",
        "ko": "에이전트들이 서로 절반씩 회피 책임을 지는 다중 에이전트 충돌 회피 (van den Berg et al., 2008).",
        "en": "Multi-agent collision avoidance where each agent takes half the responsibility to turn (van den Berg et al., 2008).",
    },
    "potential field": {
        "display": "Potential Field",
        "ko": "목표 인력·장애물 척력으로 경로를 생성하는 고전 네비게이션.",
        "en": "Classical navigation using attractive-goal and repulsive-obstacle fields.",
    },
    "feedback motion": {
        "display": "Feedback Motion Planning",
        "ko": "상태에 대한 피드백 제어 정책 자체를 계획하는 접근 (LQR-trees 등).",
        "en": "Planning closed-loop feedback policies rather than open-loop trajectories (e.g. LQR-trees).",
    },
    "lqr-trees": {
        "display": "LQR-Trees",
        "ko": "LQR 기반 분기를 이어 붙여 넓은 안정 영역을 덮는 피드백 계획 기법 (Tedrake).",
        "en": "A feedback-planning method that tiles large stable regions using LQR funnels (Tedrake).",
    },
    "optimal control": {
        "display": "Optimal Control",
        "ko": "목적 함수를 최소화하는 제어 입력을 찾는 제어 이론 분야.",
        "en": "Control theory branch concerned with minimizing a cost over control inputs.",
    },
    "admittance control": {
        "display": "Admittance Control",
        "ko": "외력을 측정해 위치·속도 명령을 생성하는 부드러운 접촉 제어.",
        "en": "Mapping measured force to position/velocity commands for compliant contact.",
    },
    "impedance control": {
        "display": "Impedance Control",
        "ko": "위치 오차에 대한 가상 스프링·댐퍼 관계로 힘을 생성하는 상호작용 제어.",
        "en": "Shaping the force response to position error as a virtual spring-damper.",
    },
    "compliance": {
        "display": "Compliance",
        "ko": "외란이나 접촉에 유연하게 반응하는 기계적·제어적 특성.",
        "en": "The mechanical or control property of yielding softly to disturbance or contact.",
    },
    "operational space": {
        "display": "Operational Space",
        "ko": "관절 공간이 아닌 작업 공간(엔드 이펙터)에서 직접 정의하는 제어 프레임워크 (Khatib).",
        "en": "A control framework defined directly in end-effector task space rather than joint space (Khatib).",
    },
    "adaptive control": {
        "display": "Adaptive Control",
        "ko": "시스템 파라미터를 온라인으로 추정·조정하는 제어.",
        "en": "Control that estimates and adjusts system parameters online.",
    },
    "model predictive": {
        "display": "Model Predictive (MPC)",
        "ko": "매 스텝 호라이즌 최적화를 수행하는 예측 제어.",
        "en": "A predictive control paradigm solving an online horizon optimization at each step.",
    },

    # --- Manipulation ---
    "manipulation": {
        "display": "Manipulation",
        "ko": "로봇이 물체를 잡고 움직이는 전반적 연구 영역.",
        "en": "The broad area of robots grasping and moving objects.",
    },
    "grasping": {
        "display": "Grasping",
        "ko": "물체를 안정적으로 잡는 자세·힘을 결정하는 문제.",
        "en": "The problem of determining stable grasp poses and forces.",
    },
    "grasp planning": {
        "display": "Grasp Planning",
        "ko": "파지점과 접근 궤적을 알고리즘적으로 설계하는 문제.",
        "en": "Algorithmic design of grasp points and approach trajectories.",
    },
    "dexterous": {
        "display": "Dexterous Manipulation",
        "ko": "다지 손으로 물체를 손 안에서 재배치하거나 조작하는 고급 매니퓰레이션.",
        "en": "Advanced in-hand reorientation or reposing with a multi-fingered hand.",
    },
    "tactile": {
        "display": "Tactile Sensing",
        "ko": "접촉면의 힘 분포·텍스처를 감지하는 촉각 센싱.",
        "en": "Sensing force distribution and surface properties through contact.",
    },
    "force control": {
        "display": "Force Control",
        "ko": "접촉 힘을 직접 목표로 제어하는 방식.",
        "en": "Control that targets contact force directly rather than position.",
    },
    "teleoperation": {
        "display": "Teleoperation",
        "ko": "원격에서 로봇을 조종하는 분야.",
        "en": "Remote operation of a robot by a human at a distance.",
    },
    "bilateral teleoperation": {
        "display": "Bilateral Teleoperation",
        "ko": "힘 피드백까지 쌍방으로 흐르는 원격 조작.",
        "en": "Teleoperation with bidirectional force feedback between master and slave.",
    },
    "haptic": {
        "display": "Haptic",
        "ko": "촉각 피드백 인터페이스 및 상호작용.",
        "en": "Touch-based feedback interfaces and interaction.",
    },
    "fcl": {
        "display": "FCL",
        "ko": "Flexible Collision Library — MoveIt 등에서 쓰이는 충돌 검사 라이브러리 (Manocha 연구실).",
        "en": "Flexible Collision Library — a widely used collision-checking library (Manocha lab).",
    },
    "collision detection": {
        "display": "Collision Detection",
        "ko": "강체·모델 간 충돌 여부/최근접 거리를 계산하는 기하 연산.",
        "en": "Geometric test for whether or how close two bodies are to contact.",
    },

    # --- Legged / aerial ---
    "quadruped": {
        "display": "Quadruped",
        "ko": "4족 보행 로봇.",
        "en": "Four-legged robots.",
    },
    "humanoid": {
        "display": "Humanoid",
        "ko": "인간형 이족 보행 로봇.",
        "en": "Human-shaped bipedal robots.",
    },
    "biped": {
        "display": "Biped",
        "ko": "2족 보행 로봇 일반.",
        "en": "Two-legged walking robots in general.",
    },
    "locomotion": {
        "display": "Locomotion",
        "ko": "걷기·달리기 등 이동 자체에 대한 연구.",
        "en": "The study of walking, running, and other modes of robot movement.",
    },
    "legged": {
        "display": "Legged Robots",
        "ko": "다리로 이동하는 로봇 계열 전반.",
        "en": "The broad family of robots that move with legs.",
    },
    "central pattern": {
        "display": "Central Pattern Generator (CPG)",
        "ko": "주기적 이동 리듬을 만드는 생체모방 신경 회로.",
        "en": "A biologically inspired neural circuit that produces rhythmic motion.",
    },
    "cheetah": {
        "display": "MIT Cheetah",
        "ko": "MIT Sangbae Kim 랩의 고속 4족 로봇 시리즈.",
        "en": "High-speed quadruped line from Sangbae Kim's group at MIT.",
    },
    "mit cheetah": {
        "display": "MIT Cheetah",
        "ko": "MIT의 대표 고속 4족 로봇 플랫폼.",
        "en": "MIT's flagship high-speed quadruped platform.",
    },
    "hubo": {
        "display": "HUBO",
        "ko": "KAIST 오준호 교수팀의 휴머노이드 플랫폼 (DARPA DRC 우승).",
        "en": "KAIST humanoid platform from Jun-Ho Oh's group (DARPA DRC winner).",
    },
    "biped walking": {
        "display": "Biped Walking",
        "ko": "2족 보행 생성·안정성 문제.",
        "en": "The problem of generating and stabilizing bipedal walking.",
    },
    "vertical surfaces": {
        "display": "Vertical Surfaces (Climbing)",
        "ko": "수직 벽 등반 로봇 — Stickybot 계열의 주제.",
        "en": "Vertical-surface climbing robots — a line represented by Stickybot and relatives.",
    },
    "uav": {
        "display": "UAV",
        "ko": "Unmanned Aerial Vehicle — 무인 항공기.",
        "en": "Unmanned Aerial Vehicle — the broad category of aerial robots.",
    },
    "quadrotor": {
        "display": "Quadrotor",
        "ko": "4개 로터로 구성된 가장 일반적인 형태의 UAV.",
        "en": "The four-rotor configuration, by far the most common UAV form factor.",
    },
    "drone racing": {
        "display": "Drone Racing",
        "ko": "관문(gate)을 통과하는 고속 자율 드론 경주 — 극한 비행 제어 연구 영역.",
        "en": "High-speed autonomous flight through gates — a testbed for agile control.",
    },
    "agile flight": {
        "display": "Agile Flight",
        "ko": "빠르고 민첩한 UAV 비행 — 시간 최적 제어와 인식 통합이 핵심.",
        "en": "Fast and agile UAV flight — centered on time-optimal control and tight perception integration.",
    },
    "aerial manipulation": {
        "display": "Aerial Manipulation",
        "ko": "비행 중인 UAV가 팔로 물체를 조작하는 영역.",
        "en": "UAVs manipulating objects while airborne, typically with an attached arm.",
    },
    "multi-rotor": {
        "display": "Multi-Rotor",
        "ko": "복수 로터 UAV 일반 — 쿼드로터·헥사로터 등.",
        "en": "Multi-rotor UAVs in general — quad, hex, and so on.",
    },
    "omnidirectional": {
        "display": "Omnidirectional Vision",
        "ko": "360° 시야 카메라 — Scaramuzza 초기 연구 주제.",
        "en": "360° field-of-view cameras — Scaramuzza's early research focus.",
    },

    # --- Learning ---
    "reinforcement learning": {
        "display": "Reinforcement Learning (RL)",
        "ko": "환경과 상호작용하며 보상을 극대화하는 정책을 학습.",
        "en": "Learning a policy that maximizes reward through interaction with an environment.",
    },
    "imitation learning": {
        "display": "Imitation Learning",
        "ko": "전문가 시연을 모사해 정책을 학습.",
        "en": "Learning a policy by mimicking expert demonstrations.",
    },
    "apprenticeship learning": {
        "display": "Apprenticeship Learning",
        "ko": "전문가 시연에서 보상 함수를 역으로 추정 후 모방 (Abbeel & Ng, 2004).",
        "en": "Inverse-reward learning from demonstrations, then imitation (Abbeel & Ng, 2004).",
    },
    "learning from demonstration": {
        "display": "Learning from Demonstration (LfD)",
        "ko": "시연 데이터를 기반으로 스킬을 학습하는 접근 일반.",
        "en": "The general approach of learning skills from demonstration data.",
    },
    "maml": {
        "display": "MAML",
        "ko": "Model-Agnostic Meta-Learning — 몇 스텝으로 새 태스크에 빠르게 적응하는 메타학습 (Finn et al., 2017).",
        "en": "Model-Agnostic Meta-Learning — meta-learn fast adaptation to new tasks (Finn et al., 2017).",
    },
    "self-supervised": {
        "display": "Self-Supervised Learning",
        "ko": "수동 라벨 없이 데이터 자체로부터 감독 신호를 만드는 학습.",
        "en": "Learning where the supervision signal comes from the data itself, without manual labels.",
    },
    "deep reinforcement": {
        "display": "Deep Reinforcement Learning",
        "ko": "심층 신경망 정책·가치함수 기반 RL.",
        "en": "Reinforcement learning with deep neural policies/value functions.",
    },
    "diffusion policy": {
        "display": "Diffusion Policy",
        "ko": "확산 모델로 행동 분포를 표현하는 최신 로봇 정책 표현.",
        "en": "A modern robot policy representation using diffusion models over action sequences.",
    },
    "vision-language-action": {
        "display": "Vision-Language-Action",
        "ko": "시각·언어·행동을 하나의 foundation 모델로 통합 — RT-2 등.",
        "en": "Unified foundation models over vision, language, and action — RT-2 and friends.",
    },
    "open x-embodiment": {
        "display": "Open X-Embodiment",
        "ko": "여러 로봇 플랫폼에 걸친 대규모 공유 로봇 학습 데이터셋.",
        "en": "A large-scale cross-platform shared robot learning dataset.",
    },
    "policy learning": {
        "display": "Policy Learning",
        "ko": "제어 정책 자체를 학습하는 접근 일반.",
        "en": "The general approach of learning the control policy itself.",
    },
    "differentiable simulation": {
        "display": "Differentiable Simulation",
        "ko": "물리 시뮬레이터를 미분해 그래디언트로 정책/파라미터 최적화.",
        "en": "Physics simulators whose outputs can be differentiated through for gradient-based optimization.",
    },

    # --- Soft / bio / medical ---
    "soft robot": {
        "display": "Soft Robot",
        "ko": "유연한 재질로 된 연성 로봇.",
        "en": "Robots built from compliant, deformable materials.",
    },
    "origami": {
        "display": "Origami Robot",
        "ko": "접는 구조를 이용한 전개형·변형형 로봇.",
        "en": "Robots that deploy or transform using folded-structure principles.",
    },
    "pneumatic": {
        "display": "Pneumatic",
        "ko": "공압을 동력원으로 쓰는 액추에이터.",
        "en": "Actuators driven by air pressure.",
    },
    "tendon-driven": {
        "display": "Tendon-Driven",
        "ko": "케이블·힘줄로 관절을 구동하는 기구.",
        "en": "Mechanisms actuated via cables pulling on joints.",
    },
    "exoskeleton": {
        "display": "Exoskeleton",
        "ko": "신체 외부에 착용해 힘을 보조하는 외골격 장치.",
        "en": "Wearable external frames that augment human force.",
    },
    "exosuit": {
        "display": "Exosuit",
        "ko": "부드러운 직물 기반의 착용형 보조 장치.",
        "en": "Soft, textile-based wearable assistive devices.",
    },
    "continuum robot": {
        "display": "Continuum Robot",
        "ko": "불연속 관절이 아닌 연속적 휘어짐으로 움직이는 로봇 — 수술 분야 표준.",
        "en": "Robots that bend continuously instead of using discrete joints — standard in surgical settings.",
    },
    "concentric tube": {
        "display": "Concentric Tube Robot",
        "ko": "동심 튜브가 서로에 대해 회전/병진하며 곡률을 만드는 수술 로봇 (Webster, Dupont).",
        "en": "Surgical continuum robots built from concentric telescoping tubes (Webster, Dupont).",
    },
    "surgical robot": {
        "display": "Surgical Robot",
        "ko": "수술을 수행·보조하는 의료 로봇.",
        "en": "Robots that perform or assist surgical procedures.",
    },
    "endovascular": {
        "display": "Endovascular Robotics",
        "ko": "혈관 내에서 도관·가이드와이어를 조작하는 수술 로봇 영역.",
        "en": "Robotics for manipulating catheters and guidewires inside blood vessels.",
    },
    "catheter": {
        "display": "Catheter",
        "ko": "혈관·체강에 삽입하는 유연 관 — 연속체/수술 로봇의 주요 대상.",
        "en": "A flexible tube inserted into vessels or cavities — a core artifact of surgical continuum robotics.",
    },
    "gecko": {
        "display": "Gecko Adhesion",
        "ko": "게코 도마뱀 발의 van der Waals 흡착 원리 모방.",
        "en": "Robots mimicking the van-der-Waals adhesion of gecko feet.",
    },
    "biomimetic": {
        "display": "Biomimetic",
        "ko": "생물학적 메커니즘을 모방한 설계.",
        "en": "Design patterns inspired by biological mechanisms.",
    },

    # --- Kinematics / dynamics ---
    "kinematics": {
        "display": "Kinematics",
        "ko": "힘을 고려하지 않은 로봇의 위치·속도 관계.",
        "en": "The study of robot motion without considering forces.",
    },
    "inverse kinematics": {
        "display": "Inverse Kinematics",
        "ko": "목표 엔드 이펙터 자세로부터 관절 각도를 역계산.",
        "en": "Computing joint angles from a desired end-effector pose.",
    },
    "forward kinematics": {
        "display": "Forward Kinematics",
        "ko": "관절 각도에서 엔드 이펙터 위치를 계산.",
        "en": "Computing end-effector pose from given joint angles.",
    },
    "redundant manipulator": {
        "display": "Redundant Manipulator",
        "ko": "작업 자유도보다 관절 자유도가 많은 매니퓰레이터 — 널 공간 활용이 핵심.",
        "en": "Manipulator whose joint DoF exceeds task DoF — null-space utilization is the point.",
    },
    "screw theory": {
        "display": "Screw Theory",
        "ko": "강체 운동을 스크류(회전+이동)로 기술하는 이론 — Frank Park의 *Modern Robotics* 기반.",
        "en": "Describing rigid-body motion as screws (rotation + translation) — the backbone of Park's *Modern Robotics*.",
    },
    "jacobian": {
        "display": "Jacobian",
        "ko": "관절 속도와 엔드 이펙터 속도를 연결하는 선형 변환.",
        "en": "Linear map between joint-space velocities and end-effector velocities.",
    },
    "contact-rich": {
        "display": "Contact-Rich Manipulation",
        "ko": "다수의 접촉이 발생하는 정밀 조작 — 식기, 도구 사용 등.",
        "en": "Manipulation with many simultaneous contacts — tool use, assembly, etc.",
    },

    # --- Specific domains ---
    "hull inspection": {
        "display": "Hull Inspection",
        "ko": "수중 선체 검사 — 수중 로봇의 대표 응용.",
        "en": "Underwater inspection of ship hulls — a flagship application of underwater robotics.",
    },
    "ship hull": {
        "display": "Ship Hull",
        "ko": "선체 구조물 — 수중 검사의 주된 대상체.",
        "en": "The ship hull structure, the typical target of underwater inspection tasks.",
    },
    "underwater": {
        "display": "Underwater Robotics",
        "ko": "수중 로봇 — ROV/AUV 기반 탐사·검사·조작.",
        "en": "Underwater robotics — exploration, inspection, and manipulation via ROVs/AUVs.",
    },
    "auv": {
        "display": "AUV",
        "ko": "Autonomous Underwater Vehicle — 자율 수중 로봇.",
        "en": "Autonomous Underwater Vehicle.",
    },
    "rov": {
        "display": "ROV",
        "ko": "Remotely Operated Vehicle — 유선 원격 조종 수중 로봇.",
        "en": "Remotely Operated (underwater) Vehicle, tethered to a surface operator.",
    },
    "crop weed": {
        "display": "Crop vs. Weed Classification",
        "ko": "작물과 잡초를 구분하는 정밀농업 인식 문제.",
        "en": "Distinguishing crops from weeds — a precision-agriculture perception task.",
    },
    "precision farming": {
        "display": "Precision Farming",
        "ko": "필지 내 위치별 맞춤 관리를 수행하는 농업 자동화.",
        "en": "Site-specific, data-driven agriculture — the target of many UAV/ground-robot efforts.",
    },
    "precision agriculture": {
        "display": "Precision Agriculture",
        "ko": "데이터·로봇 기반 맞춤형 농작업.",
        "en": "Data- and robot-driven site-specific agriculture.",
    },
    "autonomous driving": {
        "display": "Autonomous Driving",
        "ko": "자율 주행 — 인지·계획·제어가 결합된 대규모 응용 분야.",
        "en": "Self-driving — a large-scale integration of perception, planning, and control.",
    },
    "mobile robot": {
        "display": "Mobile Robot",
        "ko": "바퀴·트랙 등으로 이동하는 지상 로봇.",
        "en": "Ground-based wheeled or tracked robots.",
    },
    "swarm": {
        "display": "Swarm Robotics",
        "ko": "단순 로봇 다수가 분산 상호작용으로 전체 행동을 창발하는 연구.",
        "en": "Emergent behavior from many simple robots interacting locally.",
    },
    "multi-robot": {
        "display": "Multi-Robot Systems",
        "ko": "복수 로봇의 협업·조정을 다루는 분야.",
        "en": "Coordination and cooperation among multiple robots.",
    },
    "navigation": {
        "display": "Navigation",
        "ko": "로봇이 환경에서 경로를 계획·실행하는 문제.",
        "en": "The problem of a robot planning and following a path through an environment.",
    },
    "outdoor navigation": {
        "display": "Outdoor Navigation",
        "ko": "비정형 야외 지형에서의 경로·지형 이해·주행 제어.",
        "en": "Path planning and terrain-aware driving in unstructured outdoor environments.",
    },
    "traversability": {
        "display": "Traversability",
        "ko": "지형을 통과 가능한지/얼마나 어려운지를 평가.",
        "en": "Estimating whether and how easily terrain can be traversed.",
    },
    "social navigation": {
        "display": "Social Navigation",
        "ko": "사람들 사이에서 자연스럽게 움직이는 로봇 네비게이션.",
        "en": "Robot navigation that respects human social norms.",
    },
    "magnetic": {
        "display": "Magnetic Manipulation",
        "ko": "외부 자기장으로 소형 장치를 원격 조작 — 마이크로 로보틱스.",
        "en": "Remotely actuating small devices with external magnetic fields — a micro-robotics core.",
    },

    # --- Acronyms / conventions ---
    "imu": {
        "display": "IMU",
        "ko": "관성 측정 장치 — 가속도계·자이로 기반 센서.",
        "en": "Inertial Measurement Unit — an accelerometer + gyroscope package.",
    },
    "ekf": {
        "display": "EKF",
        "ko": "Extended Kalman Filter — 비선형계에 쓰는 칼만 필터.",
        "en": "Extended Kalman Filter — Kalman filtering linearized for non-linear systems.",
    },
    "isam": {
        "display": "iSAM",
        "ko": "Incremental Smoothing and Mapping — 온라인 factor-graph SLAM (Kaess).",
        "en": "Incremental Smoothing and Mapping — online factor-graph SLAM (Kaess).",
    },
    "gtsam": {
        "display": "GTSAM",
        "ko": "Georgia Tech Smoothing and Mapping — factor graph 라이브러리 (Dellaert).",
        "en": "Georgia Tech Smoothing and Mapping — the factor-graph optimization library from Dellaert.",
    },
    "6-dof": {
        "display": "6-DoF",
        "ko": "3차원 공간에서의 위치 3 + 자세 3 = 6 자유도.",
        "en": "Six degrees of freedom — position (3) plus orientation (3) in 3D space.",
    },
    "variable stiffness": {
        "display": "Variable Stiffness",
        "ko": "상황에 따라 강성을 조절하는 액추에이터·그리퍼 (Bicchi 연구실의 대표 주제).",
        "en": "Actuators/grippers whose stiffness can be tuned at runtime (a flagship topic of Bicchi's group).",
    },
    "compliantly actuated": {
        "display": "Compliantly Actuated",
        "ko": "관절에 의도적인 유연성을 넣어 안전·효율을 높인 액추에이터.",
        "en": "Actuators with designed-in compliance for safer, more efficient interaction.",
    },
    "gastrointestinal": {
        "display": "Gastrointestinal Robotics",
        "ko": "소화기관 내 진단·치료용 소형·캡슐 로봇 (Menciassi 등).",
        "en": "Miniature and capsule robotics for the GI tract (Menciassi and colleagues).",
    },

    # --- EAP / soft actuators / specific materials ---
    "electro-active": {
        "display": "Electroactive Polymer (EAP)",
        "ko": "전기 자극에 반응해 형상이 변하는 고분자 — 인공근육·소프트 액추에이터의 대표 재료군.",
        "en": "Polymers that change shape in response to electric fields — a key material family for artificial muscles and soft actuators.",
    },
    "electroactive": {
        "display": "Electroactive Polymer (EAP)",
        "ko": "전기 자극에 반응해 형상이 변하는 고분자 — 인공근육·소프트 액추에이터의 대표 재료군.",
        "en": "Polymers that change shape in response to electric fields — a key material family for artificial muscles and soft actuators.",
    },
    "dielectric elastomer": {
        "display": "Dielectric Elastomer Actuator",
        "ko": "탄성 유전체에 고전압을 걸어 늘어남·수축을 유도하는 EAP 계열 액추에이터.",
        "en": "Elastomer-sandwich actuators that deform under high-voltage electric fields — a major EAP class.",
    },
    "hydrogel": {
        "display": "Hydrogel Actuator",
        "ko": "물을 머금는 고분자 겔 — 자극에 따라 팽윤/수축하는 소프트 액추에이터 재료.",
        "en": "Water-swollen polymer gels that shrink/swell in response to stimuli — a common soft-actuator material.",
    },
    "gel": {
        "display": "Gel Actuator",
        "ko": "팽윤·수축 가능한 겔 재료 기반 액추에이터 — EAP·하이드로겔 계열을 포함.",
        "en": "Actuators built from swellable/responsive gels — overlapping the EAP and hydrogel families.",
    },
    "sma": {
        "display": "Shape Memory Alloy (SMA)",
        "ko": "열을 가하면 원래 형상으로 복원되는 합금 — 소형·고출력 소프트 액추에이터에 쓰임.",
        "en": "Alloys that recover a memorized shape when heated — compact, high-force soft actuators.",
    },
    "shape memory": {
        "display": "Shape Memory",
        "ko": "가열·자극으로 기억된 형태로 되돌아가는 재료 거동 (SMA, SMP 등).",
        "en": "Material behavior where a memorized shape is recovered upon thermal or other stimulation (SMA, SMP).",
    },
    "mckibben": {
        "display": "McKibben Artificial Muscle",
        "ko": "공압으로 수축하는 섬유 직조형 인공 근육.",
        "en": "Braided pneumatic artificial muscles that contract when pressurized.",
    },
    "pneumatic artificial muscle": {
        "display": "Pneumatic Artificial Muscle",
        "ko": "공압 인공 근육 — McKibben 구조가 대표적.",
        "en": "Pneumatically actuated artificial muscle — the McKibben design is canonical.",
    },
    "hasel": {
        "display": "HASEL Actuator",
        "ko": "정전기+유체를 결합한 새로운 소프트 액추에이터 계열 (Keplinger et al.).",
        "en": "Hydraulically Amplified Self-healing Electrostatic actuators — a recent soft-actuator class (Keplinger et al.).",
    },
    "jamming": {
        "display": "Jamming",
        "ko": "진공으로 과립을 고체처럼 굳혀 강성을 만드는 소프트 로봇 원리.",
        "en": "Using vacuum-induced granular jamming to generate tunable stiffness in soft robots.",
    },
    "granular": {
        "display": "Granular Media",
        "ko": "모래·과립 등 이산 매질에서의 이동·상호작용 로보틱스.",
        "en": "Robotics in granular media — sand, grains, and other discrete media.",
    },
    "electroadhesion": {
        "display": "Electroadhesion",
        "ko": "정전 인력으로 표면에 들러붙는 원리 — 클라이밍·그리퍼에 응용.",
        "en": "Electrostatic adhesion to surfaces — applied in climbing robots and compliant grippers.",
    },
    "caudal fin": {
        "display": "Caudal Fin Propulsion",
        "ko": "어류 꼬리 지느러미를 모방한 추진 — 수중 바이오미메틱 로봇.",
        "en": "Fish-tail-inspired propulsion — a standard biomimetic underwater-robot approach.",
    },
    "fin propulsion": {
        "display": "Fin Propulsion",
        "ko": "지느러미형 추진 — 생체모방 수중/공중 로봇.",
        "en": "Fin-style propulsion — biomimetic underwater and aerial robots.",
    },
    "flexural": {
        "display": "Flexural Mechanism",
        "ko": "재료의 휨 변형으로 동작하는 기구 — 소프트 그리퍼·관절에 사용.",
        "en": "Mechanisms built on material flexure rather than rigid joints — common in soft grippers and compliant joints.",
    },
    "under-actuated": {
        "display": "Underactuated Hand/Robot",
        "ko": "자유도보다 적은 액추에이터로 구동되는 시스템 — 단순한 제어로 복잡한 파지 가능.",
        "en": "Systems with fewer actuators than DoF — enabling complex grasping with simple control.",
    },
    "underactuated": {
        "display": "Underactuated",
        "ko": "액추에이터 수가 자유도보다 적은 시스템 — 패시브 다이나믹스 활용.",
        "en": "Systems with fewer actuators than DoF — a design using passive dynamics.",
    },
    "compliant mechanism": {
        "display": "Compliant Mechanism",
        "ko": "관절 대신 탄성 변형으로 기능하는 기구 — 정밀·소형 로봇에 쓰임.",
        "en": "Mechanisms functioning through elastic deformation rather than joints — standard in precision and small robots.",
    },
    "deployable": {
        "display": "Deployable Structure",
        "ko": "접혔다가 펴지는 전개형 구조 — origami 로봇의 핵심.",
        "en": "Structures that unfold from compact form — the essence of origami-style robots.",
    },

    # --- More SLAM / state estimation / VIO ---
    "loam": {
        "display": "LOAM",
        "ko": "LiDAR Odometry and Mapping — 실시간 저정밀·고빈도 추정 + 저빈도·고정밀 매핑 분리 (Ji Zhang, 2014).",
        "en": "LiDAR Odometry and Mapping — dual-rate real-time LiDAR SLAM (Ji Zhang, 2014).",
    },
    "lsd-slam": {
        "display": "LSD-SLAM",
        "ko": "Large-Scale Direct Monocular SLAM — 직접법 기반 반조밀 VSLAM (Engel, 2014).",
        "en": "Large-Scale Direct Monocular SLAM — direct-method semi-dense VSLAM (Engel, 2014).",
    },
    "dso": {
        "display": "DSO",
        "ko": "Direct Sparse Odometry — 키프레임 기반 직접법 VO (Engel et al., 2016).",
        "en": "Direct Sparse Odometry — keyframe-based direct visual odometry (Engel et al., 2016).",
    },
    "msckf": {
        "display": "MSCKF",
        "ko": "Multi-State Constraint Kalman Filter — 효율적 visual-inertial 필터 (Roumeliotis, 2007).",
        "en": "Multi-State Constraint Kalman Filter — an efficient visual-inertial filter (Roumeliotis, 2007).",
    },
    "vins-mono": {
        "display": "VINS-Mono",
        "ko": "단안 시각-관성 SLAM 오픈소스 (Shen group, 2018).",
        "en": "Monocular visual-inertial SLAM open-source system (Shen group, 2018).",
    },
    "vins": {
        "display": "VINS",
        "ko": "Visual-Inertial Navigation System — 카메라+IMU 상태 추정 시스템 일반.",
        "en": "Visual-Inertial Navigation System — the general class of camera+IMU estimators.",
    },
    "event camera": {
        "display": "Event Camera",
        "ko": "픽셀별 밝기 변화만 비동기로 출력하는 바이오 모방 센서 — 저지연·고동적범위.",
        "en": "A bio-inspired sensor that emits asynchronous per-pixel brightness-change events — low-latency, high-dynamic-range.",
    },
    "neural implicit": {
        "display": "Neural Implicit Map",
        "ko": "좌표→속성 함수를 신경망으로 표현하는 맵 (NeRF 계열).",
        "en": "Maps represented as neural networks mapping coordinates to properties (NeRF-style).",
    },
    "shine-mapping": {
        "display": "SHINE-Mapping",
        "ko": "Stachniss 그룹의 계층적 신경 implicit LiDAR 매핑.",
        "en": "Stachniss group's hierarchical neural-implicit LiDAR mapping.",
    },
    "pin-slam": {
        "display": "PIN-SLAM",
        "ko": "Point-based Implicit Neural SLAM — 뉴럴 필드 기반 SLAM (Stachniss group).",
        "en": "Point-based Implicit Neural SLAM — a neural-field SLAM system (Stachniss group).",
    },
    "rangenet": {
        "display": "RangeNet",
        "ko": "LiDAR range 이미지 위의 CNN 기반 시맨틱 분할 네트워크.",
        "en": "CNN-based semantic segmentation over LiDAR range images.",
    },
    "active slam": {
        "display": "Active SLAM",
        "ko": "불확실성을 줄이기 위한 탐사·경로를 스스로 결정하는 SLAM.",
        "en": "SLAM that plans its own exploration to reduce uncertainty.",
    },
    "suma": {
        "display": "SuMa",
        "ko": "Surfel-based Mapping — 서펠 기반 LiDAR SLAM (Stachniss group).",
        "en": "Surfel-based Mapping — surfel-based LiDAR SLAM (Stachniss group).",
    },
    "lidar inertial": {
        "display": "LiDAR-Inertial",
        "ko": "LiDAR+IMU 센서 퓨전 상태 추정.",
        "en": "LiDAR + IMU sensor-fusion state estimation.",
    },

    # --- Legged locomotion specifics ---
    "zmp": {
        "display": "Zero Moment Point (ZMP)",
        "ko": "발바닥 지지 영역 안에서 반력 합의 수직축이 지나는 점 — 이족보행 안정성 기준.",
        "en": "The point where net ground reaction torques vanish — a classical stability criterion for biped walking.",
    },
    "zero moment point": {
        "display": "Zero Moment Point (ZMP)",
        "ko": "이족보행 안정성의 고전 기준점.",
        "en": "Classical biped stability criterion.",
    },
    "capture point": {
        "display": "Capture Point",
        "ko": "한 걸음만 내디뎌 정지할 수 있는 지점 — 이족 보행 안정화 지표.",
        "en": "A point where a single step suffices to stop — a biped stabilization target.",
    },
    "inverted pendulum": {
        "display": "Linear Inverted Pendulum (LIP)",
        "ko": "보행 CoM 동역학을 근사하는 선형 역진자 모델.",
        "en": "A linear inverted-pendulum abstraction used to model walking CoM dynamics.",
    },
    "slip model": {
        "display": "SLIP Model",
        "ko": "Spring-Loaded Inverted Pendulum — 다리를 스프링으로 추상화한 러닝 동역학 모델.",
        "en": "Spring-Loaded Inverted Pendulum — a spring-leg abstraction for running dynamics.",
    },
    "whole-body control": {
        "display": "Whole-Body Control",
        "ko": "모든 관절·접촉을 통합해 우선순위 작업을 풀어내는 휴머노이드 제어.",
        "en": "Unified control over all joints and contacts via prioritized task stacks, standard for humanoids.",
    },
    "raibert": {
        "display": "Raibert Controller",
        "ko": "Marc Raibert의 다리 로봇 균형·보행 제어 고전 프레임워크.",
        "en": "Marc Raibert's classical leg-robot balance/gait controller.",
    },
    "passive dynamic": {
        "display": "Passive Dynamic Walking",
        "ko": "구동 없이 중력만으로 내리막을 걷는 수동 보행 — Tedrake 초기 연구 주제.",
        "en": "Walking down an incline with no actuation — a key topic in Tedrake's early work.",
    },
    "rough terrain": {
        "display": "Rough Terrain Locomotion",
        "ko": "고르지 않은 지형에서의 다리 보행 연구.",
        "en": "Legged locomotion over uneven terrain.",
    },

    # --- Manipulation/planning specifics ---
    "task and motion": {
        "display": "Task and Motion Planning (TAMP)",
        "ko": "상위 작업 계획과 하위 모션 계획을 결합한 긴 호라이즌 로봇 계획.",
        "en": "Joint reasoning over task-level symbolic planning and motion planning for long-horizon tasks.",
    },
    "tamp": {
        "display": "Task and Motion Planning (TAMP)",
        "ko": "기호 작업 계획 + 모션 계획을 통합한 긴 호라이즌 계획.",
        "en": "Joint symbolic + motion planning for long-horizon tasks.",
    },
    "deformable object": {
        "display": "Deformable Object Manipulation",
        "ko": "천·끈·연체 등 형태가 변하는 물체의 조작.",
        "en": "Manipulation of cloth, rope, and other shape-changing objects.",
    },
    "cloth": {
        "display": "Cloth Manipulation",
        "ko": "천·의류 등 2D 유연 물체의 조작.",
        "en": "Manipulation of cloth, garments, and other 2D deformables.",
    },
    "peg-in-hole": {
        "display": "Peg-in-Hole",
        "ko": "핀을 구멍에 삽입하는 정밀 조립 벤치마크 문제.",
        "en": "Inserting a peg into a hole — a canonical precision-assembly benchmark.",
    },
    "assembly": {
        "display": "Robotic Assembly",
        "ko": "부품을 조립하는 로봇 작업 — 정밀·접촉 제어가 핵심.",
        "en": "Robotic assembly tasks — contact-aware precision control is central.",
    },
    "parallel mechanism": {
        "display": "Parallel Mechanism",
        "ko": "복수의 체인이 말단을 공유하는 기구 — Stewart·Delta 등.",
        "en": "Mechanisms with multiple chains sharing an end-effector — Stewart, Delta, and kin.",
    },
    "stewart": {
        "display": "Stewart Platform",
        "ko": "6자유도 병렬 기구 — 비행 시뮬레이터·정밀 모션 스테이지의 표준.",
        "en": "A 6-DoF parallel mechanism — standard for flight simulators and precision motion stages.",
    },
    "delta robot": {
        "display": "Delta Robot",
        "ko": "고속 픽앤플레이스용 3자유도 병렬 기구.",
        "en": "A 3-DoF parallel robot used for high-speed pick-and-place.",
    },
    "cable-driven": {
        "display": "Cable-Driven Parallel Robot",
        "ko": "와이어·케이블로 말단을 구동하는 병렬 기구 — 대공간 작업에 강점.",
        "en": "Parallel mechanisms actuated by cables — strong for large workspaces.",
    },
    "spherical": {
        "display": "Spherical Mechanism",
        "ko": "모든 링크 축이 한 점을 지나는 기구 — 방향 제어에 유리.",
        "en": "Mechanisms with all link axes intersecting at a point — favored for orientation control.",
    },
    "eclipse": {
        "display": "Eclipse-II Parallel Machine",
        "ko": "SNU Frank Park 연구실의 6자유도 병렬 공작 기계 연구.",
        "en": "A 6-DoF parallel machining platform line from Frank Park's SNU lab.",
    },
    "singularity": {
        "display": "Kinematic Singularity",
        "ko": "자코비안이 rank 손실되는 특이 자세 — 제어가 무너지는 지점.",
        "en": "A configuration where the Jacobian loses rank and control degenerates.",
    },

    # --- Learning specifics ---
    "behavior cloning": {
        "display": "Behavior Cloning (BC)",
        "ko": "시연 데이터로 (상태→행동) 매핑을 지도학습하는 가장 단순한 모방 학습.",
        "en": "Supervised learning of state→action from demonstrations — the simplest form of imitation learning.",
    },
    "guided policy search": {
        "display": "Guided Policy Search",
        "ko": "국소 최적 제어로 가이드한 샘플로 전역 정책을 학습하는 기법 (Levine).",
        "en": "Training a global policy from trajectories generated by local optimal controllers (Levine).",
    },
    "sim-to-real": {
        "display": "Sim-to-Real Transfer",
        "ko": "시뮬레이터에서 학습한 정책을 실기에 이식 — 랜덤화·적응이 핵심.",
        "en": "Transferring a policy learned in simulation to the real robot — randomization and adaptation are key.",
    },
    "sim2real": {
        "display": "Sim-to-Real",
        "ko": "시뮬레이션↔실기 전이 일반.",
        "en": "Simulation-to-real transfer in general.",
    },
    "domain randomization": {
        "display": "Domain Randomization",
        "ko": "시뮬레이션 파라미터를 랜덤화해 sim-to-real을 쉽게 만드는 기법.",
        "en": "Randomizing simulation parameters to ease sim-to-real transfer.",
    },
    "world model": {
        "display": "World Model",
        "ko": "환경의 동역학을 학습된 모델로 내재화해 행동을 계획하는 접근.",
        "en": "Internalizing environment dynamics in a learned model, then planning against it.",
    },
    "offline rl": {
        "display": "Offline Reinforcement Learning",
        "ko": "수집된 데이터만으로 새 환경 상호작용 없이 정책을 학습하는 RL.",
        "en": "Reinforcement learning from a fixed dataset with no new interaction.",
    },
    "meta-learning": {
        "display": "Meta-Learning",
        "ko": "새 태스크에 빠르게 적응하도록 '학습하는 방법'을 학습.",
        "en": "Learning to learn — fast adaptation to new tasks.",
    },
    "foundation model": {
        "display": "Foundation Model",
        "ko": "대규모 사전학습된 범용 모델 — VLA·세계 모델 등의 토대.",
        "en": "A large, broadly pre-trained general-purpose model — the base for VLA, world models, etc.",
    },
    "curriculum": {
        "display": "Curriculum Learning",
        "ko": "쉬운 태스크부터 점진적으로 어렵게 학습하는 전략.",
        "en": "Training with tasks arranged in increasing difficulty.",
    },

    # --- Medical / surgical specifics ---
    "minimally invasive": {
        "display": "Minimally Invasive Surgery (MIS)",
        "ko": "작은 절개로 수행하는 수술 — 수술 로봇의 주 응용.",
        "en": "Surgery through small incisions — the main target domain for surgical robots.",
    },
    "image-guided": {
        "display": "Image-Guided Surgery",
        "ko": "수술 중 영상(CT/초음파 등)으로 보조되는 로봇 수술.",
        "en": "Robot surgery guided by intraoperative imaging (CT, ultrasound, etc.).",
    },
    "microbot": {
        "display": "Microbot",
        "ko": "mm·μm 크기의 초소형 로봇 — 체내 치료·표적 약물 전달 등.",
        "en": "Millimeter/micrometer-scale robots — targeted delivery, in-body therapy.",
    },
    "capsule": {
        "display": "Capsule Robot",
        "ko": "삼킬 수 있는 형태의 체내 진단·치료 로봇.",
        "en": "Swallowable capsule-form robots for in-body diagnosis and therapy.",
    },

    # --- Aerial specifics ---
    "minimum snap": {
        "display": "Minimum Snap Trajectory",
        "ko": "가속도의 2차 미분(snap)을 최소화하는 부드러운 쿼드로터 궤적 (Mellinger & Kumar, 2011).",
        "en": "Smooth quadrotor trajectories minimizing the fourth derivative of position (Mellinger & Kumar, 2011).",
    },
    "differential flatness": {
        "display": "Differential Flatness",
        "ko": "일부 출력으로 전체 상태/입력을 대수적으로 표현 — 쿼드로터 궤적 생성에 핵심.",
        "en": "A property letting full state/inputs be written in terms of selected outputs — central to quadrotor trajectory generation.",
    },
    "time-optimal": {
        "display": "Time-Optimal Control",
        "ko": "주어진 제약 안에서 최단 시간 이동 — 드론 레이싱의 이론적 토대.",
        "en": "Fastest feasible motion under constraints — the backbone of drone racing control.",
    },
    "informative path": {
        "display": "Informative Path Planning",
        "ko": "정보 수집량을 최대화하는 경로 계획 — 탐사·매핑에 중요.",
        "en": "Planning paths that maximize information gain — key to exploration and mapping.",
    },

    # --- HRI / navigation extras ---
    "proxemics": {
        "display": "Proxemics",
        "ko": "대인 거리·공간 사용 연구 — 사회적 로봇의 네비게이션에 활용.",
        "en": "The study of human spatial-distance norms — applied to socially-aware robot navigation.",
    },
    "crowd simulation": {
        "display": "Crowd Simulation",
        "ko": "다수 보행자 움직임을 수학적으로 시뮬레이션 — 네비게이션 벤치마크.",
        "en": "Mathematical simulation of many pedestrians — a benchmark for navigation.",
    },
    "pedestrian prediction": {
        "display": "Pedestrian Prediction",
        "ko": "보행자의 미래 궤적을 예측해 안전한 경로 생성.",
        "en": "Forecasting pedestrian trajectories for safer navigation.",
    },
}


_ORDERED_KEYS = sorted(GLOSSARY.keys(), key=lambda s: -len(s))  # longer first for matching


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\- ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def lookup_phrases(phrases: Iterable[str], lang: str, max_entries: int = 4) -> list[dict]:
    """Return [{term, gloss}] for unique glossary keys found in the given phrases.

    Matching uses whole-word boundaries (padding with spaces) so 'underwater'
    does not match 'underwriter' or random substrings. Longest key wins in
    the sense that when a shorter key's tokens are fully contained in a
    previously-matched longer key, we drop the shorter one.
    """
    if not phrases:
        return []
    found_keys: list[str] = []
    for raw in phrases:
        norm = _norm(raw)
        if not norm:
            continue
        padded = f" {norm} "
        for key in _ORDERED_KEYS:
            if key in found_keys:
                continue
            # Whole-word: require a space on each side inside the padded phrase
            if f" {key} " in padded:
                key_tokens = set(key.split())
                already = any(
                    key_tokens.issubset(set(fk.split())) and fk != key
                    for fk in found_keys
                )
                if already:
                    continue
                found_keys.append(key)
                break
    out = []
    for k in found_keys[:max_entries]:
        entry = GLOSSARY[k]
        out.append({
            "term": entry["display"],
            "gloss": entry[lang],
        })
    return out
