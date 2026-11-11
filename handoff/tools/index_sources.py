"""Index live C ownership and frozen evidence from the handoff tree."""
import csv
import re
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "handoff"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return p.read_text(encoding="utf-8-sig")


def write(name, header, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def drive_targets():
    targets = {}
    for name, body in re.findall(r"add_(?:library|executable)\(([\w]+)([^)]*)\)", read(ROOT / "CMakeLists.txt")):
        for source in re.findall(r"[\w/.]+\.c\b", body):
            targets.setdefault(source, []).append(name)
    return targets


FAMILIES = {
    "app": ("桌面宿主", "UI / 设备 / 预设 / take 交互"),
    "cli": ("离线命令", "命令行导出或探针"),
    "drive": ("驾驶状态与动力学", "工况、换挡、启停、动力与离合"),
    "core": ("合成 DSP", "声层、时钟、渲染或 DSP 状态"),
    "profiles": ("参数表", "可替换的工程配方或参数接口"),
    "session": ("录制协议", "控制事件、参数指纹与录制结构"),
    "spatial": ("空间与声源对象", "对象、传播、布局"),
    "io": ("文件与渲染", "文件编解码、回放、离线导出"),
}
CORE_ROLES = {
    "engine": "实例生命周期、控制更新、逐样本渲染接口",
    "orchestrator": "将工况映射为各声层的独立包络",
    "clocks": "曲轴时钟与导入 DNA 时钟",
    "dna": "旧版 .dna 与低阶排气 OSC",
    "pad": "机体低频 PAD",
    "nvh": "空气、风噪、路噪等辅助声源",
    "acoustics": "IR 与机体返回",
    "high_orders": "排气高阶延伸",
    "exhaust_spectrum": "排气低高阶共享包络",
    "events": "启动、收油、换挡等瞬态",
    "excitation": "已点火与拖转压力激励",
    "mechanical": "机械与进气生成",
    "mechanical_modal": "随曲轴触发的机械共振",
    "modal": "阻尼共振器",
    "firing_source": "可选逐次压力声源",
    "pressure_texture": "可选压力纹理",
    "structure_texture": "可选结构纹理",
    "response_shape": "可选响应整形",
    "event_color": "可选逐次主排气染色",
    "character": "可选燃烧与机械色彩"
}
LIB_ROLES = {
    "profile": "解析和验证独立音色 profile",
    "voice": "初始化、更新控制与块／逐样本生成",
    "texture": "相关统计幅度变化",
    "oscillator": "固定相位振荡器",
    "cloud": "低频随机正交 OSC"
}
HOST_ROLES = {
    "ui": "原生监听控件与生命周期",
    "audio": "原生缓冲与设备线程",
    "render": "监听渲染及独奏混音",
    "bank": "模型目录与切换",
    "smoke": "设备与 UI 运行验证",
    "probe": "离线探针",
    "checks": "源级契约检查"
}


def code_rows():
    targets = drive_targets()
    for directory in ("src","tests","modules","experiments","tools","handoff/launcher"):
        for p in sorted((ROOT/directory).rglob("*")):
            if p.suffix not in (".c",".h") or not p.is_file() or "python_deps" in p.parts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            group = p.relative_to(ROOT).parts[1]
            owner = " / ".join(targets.get(rel, targets.get(str(Path(rel).with_suffix(".c")).replace("\\","/"), [])))
            if directory == "src":
                layer, role = FAMILIES[group]
                owner = owner or ("VehicleSoundLab" if group == "app" else "vsl_core")
                if group == "core":
                    role = CORE_ROLES.get(p.stem, role)
            elif directory == "tests":
                layer, role = "驾驶回归", "根 CMake 的 CTest 源码"
            elif directory == "modules":
                layer = "独立 Sound DNA" if group == "sound_dna" else "独立低频 V2"
                owner, role = group, LIB_ROLES[p.stem]
            elif group in ("sustain_monitor_v3","sustain_monitor_v4"):
                layer, role = "独立监听宿主", HOST_ROLES.get(p.stem, "监听接口")
                owner = "VslSoundDna" if group.endswith("3") else "VslLowRumble"
                if p.stem in ("render","probe","checks"):
                    owner += "_" + p.stem
            elif directory == "experiments":
                layer, owner, role = "历史 C 实验", group, "独立实验源码，入口见所在目录"
            elif directory == "tools":
                layer, owner, role = "分析与诊断", owner or group, "离线测量与验证，不在实时链"
            else:
                layer, owner, role = "交接总入口", "VslSystem", "选择子系统、设置工作目录、检查路径"
            yield rel, layer, owner, role, digest(p)


REVIEW = {
    "low_rumble_v2": "V2 听评未通过：像风声／低频噪声，缺发动机感。",
    "sound_dna_v1": "固定相位消减颤动并保住质感；单一 V10 情境，另有合成复用验证。",
    "detail_low_v1": "相位修正有效；三音低频有嗡鸣、不够厚。",
    "sustain_osc_v1": "固定情境持续声方向获认可。",
    "sustain_monitor_v1": "有限变调可接受；约70%以上细节持续颤动。",
    "osc_quality_v2": "细节保留版明显改善；实录参考正常。",
    "osc_quality_v1": "短窗联合拟合未改善主要低质感。",
    "detail_osc_v1": "原生监听一致；变调与时间同步变化，有限范围可接受。",
    "reference_osc_v2": "旧64声线获选；50%高频偏好是暂定，原始劣质感仍在。",
    "v0.20.0": "功能通过；用户指出该轮听感偏电子、像锯齿波。",
    "v0.15.0": "驾驶录制回退基线。",
    "v0.11.0": "相较当轮旧版更连贯、更接近目标。"
}


def stage_rows():
    for m in sorted((ROOT/"baselines").glob("*/manifest.json"),
                    key=lambda p: (not p.parent.name.startswith("v0."), [int(x) for x in p.parent.name[1:].split(".")] if p.parent.name.startswith("v0.") else [p.parent.name])):
        doc = json.loads(read(m))
        files = [r["path"] for r in doc["files"]]
        name = m.parent.name
        prefix = f"baselines/{name}/"
        notes = [prefix+p for p in files if p.startswith("research/") and p.endswith(".md")]
        proofs = [prefix+p for p in files if p.endswith(".log") or
                  (p.endswith(".json") and re.search(r"audit|proof|checks|metrics|validation|verification|smoke|acceptance|summary", p.rsplit("/",1)[-1], re.I))]
        if not notes:
            notes = [prefix+p for p in files if p.endswith("README.md")]
        yield (name, prefix+m.name, len(files), digest(m), doc.get("status",""),
               REVIEW.get(name,""), " | ".join(notes), " | ".join(proofs))


if __name__ == "__main__":
    write("C文件索引.csv", ("文件","模块","构建归属","职责","SHA-256"), code_rows())
    if any((ROOT/"baselines").glob("*/manifest.json")):
        write("阶段索引.csv", ("版本","冻结清单","文件数","清单SHA-256","冻结时状态","后续听评","报告路径","验证路径"), stage_rows())

