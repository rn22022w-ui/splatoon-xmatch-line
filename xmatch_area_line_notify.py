import os, json, requests
from datetime import datetime, timedelta, timezone

print("=== START notifier ===")

SCHEDULE_URL = "https://splatoon3.ink/data/schedules.json"
STATE_FILE = "notify_x_area_1h.json"

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
USER_ID = os.environ["LINE_USER_ID"]

# JST固定
JST = timezone(timedelta(hours=9))

RULE_JA = {
    "Splat Zones": "ガチエリア",
    "Tower Control": "ガチヤグラ",
    "Rainmaker": "ガチホコバトル",
    "Clam Blitz": "ガチアサリ",
}

STAGE_JA = {
    "Eeltail Alley": "マテガイ放水路",
    "Undertow Spillway": "ユノハナ大渓谷",
    "Hammerhead Bridge": "マサバ海峡大橋",
    "Wahoo World": "スメーシーワールド",
    "Scorch Gorge": "ナメロウ金属",
    "Lemuria Hub": "タラポートショッピングパーク",
    "Flounder Heights": "ヒラメが丘団地",
    "Inkblot Art Academy": "アンチョビットゲームズ",
    "Mincemeat Metalworks": "ナメロウ金属",
    "Museum d'Alfonsino": "キンメダイ美術館",
    "Crableg Capital": "ザトウマーケット",
    "Urchin Underpass": "デカライン高架下",
    "MakoMart": "マテガイ放水路",
    "Robo ROM-en": "コンブトラック",
    "Hagglefish Market": "ザトウマーケット",
    "Shipshape Cargo Co.": "マンタマリア号",
    "Bluefin Depot": "ネギトロ炭鉱",
    "Barnacle & Dime": "タチウオパーキング",
    "Mahi-Mahi Resort": "マヒマヒリゾート＆スパ",
    "Sturgeon Shipyard": "チョウザメ造船",
    "Humpback Pump Track": "Bバスパーク",
}


AREA_RULES = {"Splat Zones"}

def push_line(text: str):
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json={"to": USER_ID, "messages": [{"type": "text", "text": text}]},
        timeout=20,
    )
    print("LINE push status:", r.status_code)
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
    return datetime.fromisoformat(iso_z.replace("Z", "+00:00")).astimezone(JST)

def main():
    now = datetime.now(JST)
    print("now_jst:", now.isoformat())

    data = requests.get(SCHEDULE_URL, timeout=20).json()
    nodes = data["data"]["xSchedules"]["nodes"]

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
        print("No next area slot")
        return

    start_jst = iso_to_jst(target["startTime"])
    end_jst = iso_to_jst(target["endTime"])
    notify_from = start_jst - timedelta(hours=1)

    print("start_jst:", start_jst.isoformat())
    print("notify_from:", notify_from.isoformat())

    if not (notify_from <= now < start_jst):
        print("Not in notify window")
        return

    # ===== 重複防止（ここが重要）=====
    state = load_state()
    key = target["startTime"]  # 枠ごとの一意キー

    if state.get("notified_start") == key:
        print("Already notified -> skip")
        return
    # =================================

    setting = target["xMatchSetting"]
    rule_ja = RULE_JA.get((setting.get("vsRule") or {}).get("name", ""), "エリア")

    stages_ja = [
        STAGE_JA.get(s.get("name", ""), s.get("name", ""))
        for s in setting.get("vsStages", [])
    ]

    msg = (
        f"【スプラ3：Xマッチ {rule_ja}】\n"
        f"開始1時間前\n"
        f"{start_jst:%m/%d %H:%M}〜{end_jst:%H:%M}\n"
        f"ステージ：{' / '.join(stages_ja)}"
    )

    push_line(msg)

    state["notified_start"] = key
    save_state(state)
    print("Saved state:", state)

if __name__ == "__main__":
    main()
