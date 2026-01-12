import os, json, requests
from datetime import datetime, timedelta, timezone

print("=== START notifier ===")

SCHEDULE_URL = "https://splatoon3.ink/data/schedules.json"
STATE_FILE = "notify_x_area_1h.json"

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USER_ID = os.environ["LINE_USER_ID"]

# JST固定（GitHub ActionsはUTCになりがちなので明示）
JST = timezone(timedelta(hours=9))

# ルール英→日
RULE_JA = {
    "Splat Zones": "ガチエリア",
    "Tower Control": "ガチヤグラ",
    "Rainmaker": "ガチホコバトル",
    "Clam Blitz": "ガチアサリ",
}

# ステージ英→日（必要に応じて追加OK）
STAGE_JA = {
    "Eeltail Alley": "マテガイ放水路",
    "Undertow Spillway": "ユノハナ大渓谷",
    "Hammerhead Bridge": "マサバ海峡大橋",
    "Wahoo World": "スメーシーワールド",
    "Scorch Gorge": "ナメロウ金属",
    "Lemuria Hub": "タラポートショッピングパーク",
}

AREA_RULES = {"Splat Zones"}  # API側は英語名

def push_line(text: str):
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"to": USER_ID, "messages": [{"type": "text", "text": text}]},
        timeout=20,
    )
    print("LINE push status:", r.status_code, r.text[:200])
    r.raise_for_status()

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)

def iso_to_jst(iso_z: str) -> datetime:
    # 例: "2026-01-12T06:00:00Z" -> JST datetime
    return datetime.fromisoformat(iso_z.replace("Z", "+00:00")).astimezone(JST)

def to_ja_rule(rule_en: str) -> str:
    return RULE_JA.get(rule_en, rule_en)

def to_ja_stage(stage_en: str) -> str:
    return STAGE_JA.get(stage_en, stage_en)

def main():
    data = requests.get(SCHEDULE_URL, timeout=20).json()
    nodes = data["data"]["xSchedules"]["nodes"]

    now = datetime.now(JST)
    print("now_jst:", now.isoformat())

    # 「次のエリア枠」を探す（今より後で最初に見つかるSplat Zones）
    target = None
    for n in nodes:
        setting = n.get("xMatchSetting", {})
        rule = (setting.get("vsRule") or {}).get("name")
        if rule not in AREA_RULES:
            continue

        start_jst = iso_to_jst(n["startTime"])
        if start_jst > now:
            target = n
            break

    if not target:
        print("No next X Splat Zones slot found.")
        return

    start_jst = iso_to_jst(target["startTime"])
    end_jst = iso_to_jst(target["endTime"])

    # 開始1時間前〜開始直前の間だけ通知
    notify_from = start_jst - timedelta(hours=1)

    print("start_jst:", start_jst.isoformat())
    print("end_jst:", end_jst.isoformat())
    print("notify_from:", notify_from.isoformat())
    print("in_window:", notify_from <= now < start_jst)

    if not (notify_from <= now < start_jst):
        print("Not in notify window. Skip.")
        return

    # 重複防止（同じ枠は1回だけ）
    state = load_state()
    key = target["startTime"]  # UTCのISOをキーにするとズレに強い
    if state.get("notified_start") == key:
        print("Already notified for this slot. Skip.")
        return

    setting = target["xMatchSetting"]
    rule_en = (setting.get("vsRule") or {}).get("name", "")
    rule_ja = to_ja_rule(rule_en)

    stages_en = [s.get("name", "") for s in setting.get("vsStages", [])]
    stages_ja = [to_ja_stage(s) for s in stages_en]
    stages_text = " / ".join(stages_ja)

    msg = (
        f"【スプラ3：Xマッチ {rule_ja}】\n"
        f"開始1時間前通知\n"
        f"{start_jst:%m/%d %H:%M}〜{end_jst:%H:%M}\n"
        f"ステージ：{stages_text}"
    )

    push_line(msg)
    state["notified_start"] = key
    save_state(state)
    print("Notified and saved state.")

if __name__ == "__main__":
    main()
