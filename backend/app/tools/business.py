"""S6 订单 / S7 物流 / S8 账号 / S9 跨工单 / S10 产品知识 / S11 批次投诉。"""
import re
from datetime import timedelta

from ..config import thresholds
from ..repo import Repo, parse_time
from . import image as imgtool

TRANSIT_ANOMALY = re.compile(r"破损|破|压|湿|挤|异常|加固")


def logistics(repo: Repo, ticket: dict, order: dict) -> dict:
    lg = repo.logistics.get(order["order_id"]) if order else None
    if not lg:
        return {"found": False}
    signed = parse_time(lg.get("signed_at"))
    created = parse_time(ticket["created_at"])
    anomalies = [e for e in lg["events"] if TRANSIT_ANOMALY.search(e["desc"])]
    return {
        "found": True, "carrier": lg["carrier"], "route": lg["route"], "signed_at": lg.get("signed_at"),
        "days_after_sign": round((created - signed).total_seconds() / 86400, 1) if signed else None,
        "anomalies": anomalies, "events": lg["events"],
    }


def account(repo: Repo, account_id: str, ref_time: str) -> dict:
    a = repo.accounts.get(account_id)
    if not a:
        return {"found": False}
    th = thresholds()["account"]
    refunds = a["refunds_90d"]
    ratio = a["refund_only_90d"] / refunds if refunds else 0.0
    years = round((parse_time(ref_time) - parse_time(a["register_at"])).days / 365, 1)
    return {
        "found": True, **a, "refund_only_ratio": round(ratio, 2), "account_years": years,
        "high_refund": refunds >= th["refunds_90d_flag"] or (refunds >= 2 and ratio >= th["refund_only_ratio_flag"]),
        "loyal": a["vip_level"] >= 3 and years >= 2 and refunds <= 1,
    }


def _images(repo: Repo, ticket: dict) -> dict[str, bytes]:
    out = {}
    for n in ticket["images"]:
        p = repo.image_path(n)
        if p.exists():
            out[n] = p.read_bytes()
    return out


def _ngrams(s: str, n: int = 3) -> set[str]:
    s = re.sub(r"\s|[，。！？,.!?]", "", s)
    return {s[i : i + n] for i in range(max(len(s) - n + 1, 1))}


def cross_ticket(repo: Repo, ticket: dict, images: dict[str, bytes]) -> dict:
    th = thresholds()["dup"]
    size = th["phash_size"]
    mine = {n: imgtool.phash_bytes(b, size) for n, b in images.items()}
    image_hits, text_hits = [], []
    my_grams = _ngrams(ticket.get("description", ""))
    for other in repo.other_tickets(ticket["ticket_id"]):
        for on, ob in _images(repo, other).items():
            oh = imgtool.phash_bytes(ob, size)
            for n, h in mine.items():
                dist = h - oh
                if dist <= th["near_max_dist"]:
                    image_hits.append({
                        "image": n, "other_ticket": other["ticket_id"], "other_image": on,
                        "other_account": other["account_id"], "same_account": other["account_id"] == ticket["account_id"],
                        "distance": int(dist), "exact": dist <= th["exact_max_dist"], "other_created_at": other["created_at"],
                    })
        og = _ngrams(other.get("description", ""))
        sim = len(my_grams & og) / len(my_grams | og) if my_grams and og else 0.0
        if sim >= th["text_sim_medium"] and other["account_id"] != ticket["account_id"]:
            text_hits.append({"other_ticket": other["ticket_id"], "similarity": round(sim, 2), "text": other["description"]})
    return {"indexed": len(repo.tickets), "image_hits": image_hits, "text_hits": text_hits}


def batch_cluster(repo: Repo, ticket: dict, order: dict, issue: str) -> dict:
    th = thresholds()["batch"]
    created = parse_time(ticket["created_at"])
    since = created - timedelta(days=th["window_days"])
    hits = []
    for t in repo.credible_history():
        if t["ticket_id"] == ticket["ticket_id"]:
            continue
        o = repo.order(t["order_id"])
        tc = parse_time(t["created_at"])
        t_issue = repo.results.get(t["ticket_id"], {}).get("issue_type") or t.get("issue_type")
        if o and o["sku_id"] == order["sku_id"] and o["batch_no"] == order["batch_no"] and t_issue == issue and since <= tc <= created:
            hits.append({"ticket_id": t["ticket_id"], "created_at": t["created_at"]})
    return {"sku_id": order["sku_id"], "batch_no": order["batch_no"], "window_days": th["window_days"],
            "credible_same_issue": len(hits), "tickets": hits}
