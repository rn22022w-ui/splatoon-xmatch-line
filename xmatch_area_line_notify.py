import os, json, requests
from datetime import datetime, timedelta, timezone

SCHEDULE_URL = "https://splatoon3.ink/data/schedules.json"
STATE_FILE = "notify_x_area_1h.json"

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USER_ID = os.environ["LINE_USER_ID"]

# ルール英→日
RULE_JA = {
    "Splat Zones": "ガチエリア",
    "Tower Control": "ガチヤグラ",
    "Rainmaker": "ガチホコバトル",
    "Clam Blitz": "ガチアサリ",
}

# ステージ英→日（必要に応じて追加してOK）
STAGE_JA = {
    "Eeltail Alley": "マテガイ放水路",
    "Undertow Spillway": "ユノハナ大渓谷",
    "Hammerhead Bridge": "マサバ海峡大橋",
    "Wahoo World": "スメーシーワールド",
    "Scorch Gorge": "ナメロウ金属",
    "Lemuria Hub": "タラポートショッピングパーク",
    # ↓ここから先も増やせます（未登録は英語のまま出します）
}

AREA_RULES = {"Splat Zones", "ガチエリア"}

def push_line(text: str):
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"to": USER_ID, "messages": [{"type": "text", "text": text}]},
        timeout=10,
    )
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

def iso_to_local(iso_z: str) -> datetime:
    # Z(UTC) → ローカルタイムへ
    return datetime.fromisoformat(iso_z.replace("Z", "+00:00")).astimezone()

def to_ja_rule(rule_en: str) -> str:
    return RULE_JA.get(rule_en, rule_en)

def to_ja_stage(stage_en: str) -> str:
    return STAGE_JA.get(stage_en, stage_en)

def main():
    data = requests.get(SCHEDULE_URL, timeout=10).json()
    nodes = data["data"]["xSchedules"]["nodes"]

    # 「次のエリア枠」を選ぶ：今より後で最初に見つかるエリア
    now = datetime.now().astimezone()
    target = None

    for n in nodes:
        setting = n.get("xMatchSetting", {})
        rule = (setting.get("vsRule") or {}).get("name")
        if rule not in AREA_RULES:
            continue

        start_local = iso_to_local(n["startTime"])
        if start_local > now:
            target = n
            break

    if not target:
        # たまたま次のエリア枠が取得範囲に無い場合は何もしない
        return

    start_local = iso_to_local(target["startTime"])
    end_local = iso_to_local(target["endTime"])

    # 1時間前〜開始直前の間だけ通知（実行間隔が5分でもOK）
    notify_from = start_local - timedelta(hours=1)
    if not (notify_from <= now < start_local):
        return

    # 重複防止：この枠の通知は1回だけ
    state = load_state()
    key = target["startTime"]  # 枠の一意キー（UTCのISO）
    if state.get("notified_start") == key:
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
        f"{start_local:%m/%d %H:%M}〜{end_local:%H:%M}\n"
        f"ステージ：{stages_text}"
    )

    push_line(msg)
    state["notified_start"] = key
    save_state(state)

if __name__ == "__main__":
    main()
