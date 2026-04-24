"""Extract distinctive multi-word phrases from paper titles.

Purpose: replace the broad OpenAlex `concepts` (Computer science, AI, CV)
with the researcher's own domain language per 5-year window — e.g.
"visual slam", "hull inspection", "radar odometry", "soft gripper".

Workflow:
  1. Build a global IDF over every title in the atlas (one title = one doc).
  2. Per window, compute TF × IDF for 1/2/3-grams of each title.
  3. Pick top-k phrases, deduped by token-overlap with higher-scored ones.

This is not a classifier — it is a ranker that surfaces what makes THIS
set of titles unusual compared to the rest of the corpus.
"""
from __future__ import annotations

import math
import re
from collections import Counter

# English stopwords + robotics boilerplate that carries no domain signal.
_STOP = frozenset({
    # pure English
    "a","an","the","and","or","but","in","on","at","to","from","for","of","with",
    "by","is","are","was","were","be","been","being","have","has","had","do","does",
    "did","this","that","these","those","it","its","he","she","they","we","you","i",
    "our","their","his","her","as","into","out","up","down","over","under","about",
    "against","between","through","during","before","after","above","below","not",
    "also","only","such","than","then","too","very","can","could","should","would",
    "may","might","must","so","if","while","when","where","what","which","who",
    # paper/venue/discourse
    "paper","papers","letter","article","proceedings","conference","workshop",
    "chapter","abstract","introduction","conclusion","discussion","experiment",
    "experiments","experimental","related","work","section","figure","table",
    # generic verbs/adjectives
    "based","using","via","toward","towards","novel","new","efficient","fast",
    "accurate","robust","online","offline","real","time","realtime","real-time",
    "simple","complex","general","specific","effective","enhanced","improved",
    "advanced","initial","final","good","better","best","high","low","recent",
    "current","various","several","multiple","general-purpose","purpose",
    # study language
    "study","studies","investigation","evaluation","implementation","framework",
    "frameworks","methodology","methodologies","method","methods","approach",
    "approaches","algorithm","algorithms","technique","techniques","strategy",
    "strategies","procedure","solution","solutions","scheme","model","models",
    "modeling","modelling","analysis","analytic","analyses","design","designs",
    "designing","designed","case","cases","results","result","findings","finding",
    # overused robotics words (alone they carry no sub-field signal)
    "robot","robots","robotic","robotics","system","systems","application",
    "applications","applied","toward","direction","directions",
    # numerals / position
    "one","two","three","four","five","six","seven","eight","nine","ten",
    "first","second","third","fourth","last","next","part","section",
    # bare verbs
    "use","using","used","provide","provides","provided","show","shows","showed",
    "shown","present","presents","presented","propose","proposes","proposed",
    "introduce","introduces","introduced","discuss","discusses","discussed",
    "investigate","investigates","investigated","consider","considers","considered",
    "describe","describes","described","develop","develops","developed",
    "implement","implements","implemented","enable","enables","enabled",
    "demonstrate","demonstrates","demonstrated","apply","applies","achieve",
    "achieves","achieved","obtain","obtains","obtained","ensure","ensures",
    "ensuring","provide","compare","compares","compared","evaluate","evaluates",
    "evaluated","test","tests","tested","testing",
    # conjunctions / helpers
    "also","further","furthermore","moreover","however","therefore","thus",
    "hence","meanwhile","either","neither","both","all","any","some","each",
    "every","more","most","other","others","another","same","different",
})

# Short tokens to drop unless whitelisted (e.g. "3d", "ai")
_SHORT_ALLOW = frozenset({
    "3d","2d","4d","6d","ai","ml","rl","cv","ik","fk","se3","so3","pid","mpc",
    "ekf","icp","slam","lidar","uav","ugv","auv","auvs","uavs","rov","rovs",
    "imu","gps","rgb","nerf","bev","llm","vlm","mdp","pomdp","pose","map","6dof",
})

# Pretty-print overrides for acronyms / styled tokens
_PRETTY = {
    "slam":"SLAM","vslam":"vSLAM","lslam":"lSLAM","orb-slam":"ORB-SLAM",
    "lidar":"LiDAR","radar":"radar","sonar":"sonar",
    "uav":"UAV","ugv":"UGV","auv":"AUV","uavs":"UAVs","ugvs":"UGVs","auvs":"AUVs",
    "rov":"ROV","rovs":"ROVs","vio":"VIO","vo":"VO",
    "imu":"IMU","gps":"GPS","rgb":"RGB","rgbd":"RGB-D","rgb-d":"RGB-D","bev":"BEV",
    "nerf":"NeRF","gaussian":"Gaussian","3d":"3D","2d":"2D","4d":"4D","6d":"6D",
    "6dof":"6-DoF","dof":"DoF",
    "icp":"ICP","ekf":"EKF","ukf":"UKF","pf":"PF","mcl":"MCL","iekf":"IEKF",
    "pid":"PID","mpc":"MPC","lqr":"LQR","rl":"RL","drl":"DRL","irl":"IRL",
    "ai":"AI","ml":"ML","cv":"CV","dl":"DL",
    "vlm":"VLM","llm":"LLM","vla":"VLA","mdp":"MDP","pomdp":"POMDP",
    "se3":"SE(3)","so3":"SO(3)","se2":"SE(2)",
    "cpg":"CPG","rnn":"RNN","cnn":"CNN","gnn":"GNN","gan":"GAN","vae":"VAE",
    "ros":"ROS","sdf":"SDF","esdf":"ESDF","tsdf":"TSDF",
    "kitti":"KITTI","coco":"COCO","mit":"MIT","cmu":"CMU","eth":"ETH",
    "epfl":"EPFL","kaist":"KAIST","snu":"SNU","tum":"TUM","darpa":"DARPA",
    "nasa":"NASA","esa":"ESA","jsk":"JSK","iros":"IROS","icra":"ICRA",
    "pr2":"PR2","hrp":"HRP","sma":"SMA","iga":"IGA",
}


def tokenize(title: str) -> list[str]:
    if not title:
        return []
    t = title.lower()
    # Normalize unicode quotes and punctuation to space
    t = re.sub(r"[^a-z0-9\-\s]", " ", t)
    raw = t.split()
    out = []
    for tok in raw:
        tok = tok.strip("-")
        if not tok:
            continue
        if tok in _STOP:
            continue
        if len(tok) < 3 and tok not in _SHORT_ALLOW:
            continue
        if tok.isdigit():
            continue
        out.append(tok)
    return out


def ngrams(tokens: list[str], ns=(1, 2, 3)) -> list[str]:
    grams = []
    for n in ns:
        for i in range(len(tokens) - n + 1):
            g = " ".join(tokens[i:i + n])
            grams.append(g)
    return grams


def build_global_idf(papers: list[dict]) -> tuple[dict[str, float], float]:
    """Return (idf_map, max_idf). Document = one paper title."""
    df = Counter()
    N = len(papers)
    for p in papers:
        tokens = tokenize(p.get("title", ""))
        if not tokens:
            continue
        seen = set(ngrams(tokens))
        for g in seen:
            df[g] += 1
    if N == 0:
        return {}, 0.0
    idf = {g: math.log(N / c) for g, c in df.items()}
    max_idf = math.log(N / 1) if df else 1.0
    return idf, max_idf


def distinctive_phrases(
    papers_in_window: list[dict],
    idf: dict[str, float],
    max_idf: float,
    top_k: int = 6,
    min_tf: int = 1,
) -> list[str]:
    if not papers_in_window:
        return []
    tf = Counter()
    for p in papers_in_window:
        tokens = tokenize(p.get("title", ""))
        for g in ngrams(tokens):
            tf[g] += 1
    if not tf:
        return []
    length_bonus = {1: 0.8, 2: 1.5, 3: 1.8}
    scored = []
    for g, c in tf.items():
        if c < min_tf:
            continue
        ng_len = g.count(" ") + 1
        # Require at least one non-short token for 1-grams to avoid "3d" alone
        if ng_len == 1 and len(g) < 5 and g not in _SHORT_ALLOW:
            continue
        score = c * idf.get(g, max_idf) * length_bonus.get(ng_len, 1.0)
        scored.append((g, score, c))
    scored.sort(key=lambda x: -x[1])

    # Dedup by Jaccard token overlap — drop near-duplicates of earlier picks.
    picked_phrases: list[str] = []
    for g, s, c in scored:
        toks = set(g.split())
        too_similar = False
        for pp in picked_phrases:
            pp_toks = set(pp.split())
            union = toks | pp_toks
            if not union:
                continue
            jacc = len(toks & pp_toks) / len(union)
            if jacc >= 0.5:
                too_similar = True
                break
        if too_similar:
            continue
        picked_phrases.append(g)
        if len(picked_phrases) >= top_k:
            break
    return picked_phrases


def prettify(phrase: str) -> str:
    tokens = phrase.split()
    out = []
    for t in tokens:
        low = t.lower()
        if low in _PRETTY:
            out.append(_PRETTY[low])
        elif low.isupper() or (len(low) <= 4 and low in _SHORT_ALLOW):
            out.append(low.upper())
        elif "-" in t:
            out.append("-".join(_PRETTY.get(p, p.capitalize()) for p in t.split("-")))
        else:
            out.append(t.capitalize())
    return " ".join(out)
