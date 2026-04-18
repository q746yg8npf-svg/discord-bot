import json
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "schulden.json")


def _load() -> dict:
    if not os.path.exists(DB_FILE):
        return {"schulden": [], "transaktionen": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def schuld_hinzufuegen(schuldner_id, schuldner_name, glaeubiger_id, glaeubiger_name, betrag, beschreibung):
    data = _load()
    eintrag = {
        "id": len(data["transaktionen"]) + 1,
        "schuldner_id": schuldner_id,
        "schuldner_name": schuldner_name,
        "glaeubiger_id": glaeubiger_id,
        "glaeubiger_name": glaeubiger_name,
        "betrag": round(betrag, 2),
        "beschreibung": beschreibung,
        "datum": datetime.now().isoformat(),
        "bezahlt": False,
        "bezahlt_datum": None,
    }
    data["transaktionen"].append(eintrag)
    _save(data)
    return eintrag


def schuld_bezahlen(transaktion_id, bezahler_id):
    data = _load()
    for t in data["transaktionen"]:
        if t["id"] == transaktion_id:
            if t["schuldner_id"] != bezahler_id:
                return None
            t["bezahlt"] = True
            t["bezahlt_datum"] = datetime.now().isoformat()
            _save(data)
            return t
    return None


def alle_schulden_bezahlen(schuldner_id, glaeubiger_id):
    data = _load()
    count = 0
    for t in data["transaktionen"]:
        if t["schuldner_id"] == schuldner_id and t["glaeubiger_id"] == glaeubiger_id and not t["bezahlt"]:
            t["bezahlt"] = True
            t["bezahlt_datum"] = datetime.now().isoformat()
            count += 1
    _save(data)
    return count


def schulden_auflisten(user_id):
    data = _load()
    offene_schulden = [t for t in data["transaktionen"] if t["schuldner_id"] == user_id and not t["bezahlt"]]
    offene_forderungen = [t for t in data["transaktionen"] if t["glaeubiger_id"] == user_id and not t["bezahlt"]]
    return offene_schulden, offene_forderungen


def server_schulden_auflisten():
    data = _load()
    return [t for t in data["transaktionen"] if not t["bezahlt"]]


def stats_berechnen(user_id):
    data = _load()
    t = data["transaktionen"]
    total_schulden = sum(x["betrag"] for x in t if x["schuldner_id"] == user_id and not x["bezahlt"])
    total_forderungen = sum(x["betrag"] for x in t if x["glaeubiger_id"] == user_id and not x["bezahlt"])
    bezahlt_als_schuldner = sum(x["betrag"] for x in t if x["schuldner_id"] == user_id and x["bezahlt"])
    bezahlt_als_glaeubiger = sum(x["betrag"] for x in t if x["glaeubiger_id"] == user_id and x["bezahlt"])
    anzahl_offen = sum(1 for x in t if x["schuldner_id"] == user_id and not x["bezahlt"])
    anzahl_forderungen_offen = sum(1 for x in t if x["glaeubiger_id"] == user_id and not x["bezahlt"])
    schuldner_stats = {}
    for x in t:
        if x["glaeubiger_id"] == user_id and not x["bezahlt"]:
            schuldner_stats[x["schuldner_name"]] = round(schuldner_stats.get(x["schuldner_name"], 0) + x["betrag"], 2)
    glaeubiger_stats = {}
    for x in t:
        if x["schuldner_id"] == user_id and not x["bezahlt"]:
            glaeubiger_stats[x["glaeubiger_name"]] = round(glaeubiger_stats.get(x["glaeubiger_name"], 0) + x["betrag"], 2)
    return {
        "total_schulden": round(total_schulden, 2),
        "total_forderungen": round(total_forderungen, 2),
        "bezahlt_als_schuldner": round(bezahlt_als_schuldner, 2),
        "bezahlt_als_glaeubiger": round(bezahlt_als_glaeubiger, 2),
        "anzahl_offen": anzahl_offen,
        "anzahl_forderungen_offen": anzahl_forderungen_offen,
        "schuldner_stats": schuldner_stats,
        "glaeubiger_stats": glaeubiger_stats,
        "netto": round(total_forderungen - total_schulden, 2),
    }


def verlauf_abrufen(user_id, limit=10):
    data = _load()
    verlauf = [t for t in data["transaktionen"] if t["schuldner_id"] == user_id or t["glaeubiger_id"] == user_id]
    verlauf.sort(key=lambda x: x["datum"], reverse=True)
    return verlauf[:limit]


def rangliste():
    data = _load()
    nettos = {}
    for t in data["transaktionen"]:
        if not t["bezahlt"]:
            sid, gid = t["schuldner_id"], t["glaeubiger_id"]
            if sid not in nettos:
                nettos[sid] = {"name": t["schuldner_name"], "netto": 0.0}
            if gid not in nettos:
                nettos[gid] = {"name": t["glaeubiger_name"], "netto": 0.0}
            nettos[sid]["netto"] -= t["betrag"]
            nettos[gid]["netto"] += t["betrag"]
    result = [{"id": uid, **v} for uid, v in nettos.items()]
    result.sort(key=lambda x: x["netto"], reverse=True)
    return result