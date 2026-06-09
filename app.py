import os
import time
import gzip
from flask import Flask, jsonify
from google.transit import gtfs_realtime_pb2
import requests

app = Flask(__name__)

# Single combined feed for ALL subway lines — no API key needed
COMBINED_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

STOP_ROUTES = {
    "Q504S": ["Q"],
    "621S":  ["4", "5"],
}

HEADERS = {
    "Accept-Encoding": "identity",
}

def fetch_minutes(stop_id, routes):
    now = time.time()
    minutes = []

    try:
        resp = requests.get(COMBINED_FEED, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        print(f"Feed status={resp.status_code} bytes={len(resp.content)}")
    except Exception as e:
        print(f"Feed fetch error: {e}")
        return []

    try:
        content = resp.content
        if content[:2] == b'\x1f\x8b':
            print("Decompressing gzip...")
            content = gzip.decompress(content)

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)
        print(f"Parsed OK — {len(feed.entity)} entities")
    except Exception as e:
        print(f"Protobuf parse error: {e}")
        return []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        route = entity.trip_update.trip.route_id
        if route not in routes:
            continue
        for stu in entity.trip_update.stop_time_update:
            if stu.stop_id == stop_id:
                t = 0
                if stu.arrival.time:
                    t = stu.arrival.time
                elif stu.departure.time:
                    t = stu.departure.time
                if t and t > now:
                    m = int((t - now) / 60)
                    if 0 <= m <= 60:
                        minutes.append(m)

    minutes.sort()
    return minutes[:3]

@app.route("/<stop_id>")
def arrivals(stop_id):
    routes = STOP_ROUTES.get(stop_id)
    if not routes:
        return jsonify({"error": "Unknown stop"}), 404
    try:
        mins = fetch_minutes(stop_id, routes)
        return jsonify({"stop": stop_id, "minutes": mins})
    except Exception as e:
        print(f"Error fetching {stop_id}: {e}")
        return jsonify({"stop": stop_id, "minutes": [], "error": str(e)}), 200

@app.route("/debug/<stop_id>")
def debug(stop_id):
    routes = STOP_ROUTES.get(stop_id, [])
    try:
        resp = requests.get(COMBINED_FEED, timeout=10, headers=HEADERS)
        content = resp.content
        if content[:2] == b'\x1f\x8b':
            content = gzip.decompress(content)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)
        matching = []
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id == stop_id:
                    matching.append({
                        "route": entity.trip_update.trip.route_id,
                        "arrival": stu.arrival.time,
                        "departure": stu.departure.time,
                    })
        return jsonify({
            "status": resp.status_code,
            "bytes": len(resp.content),
            "entities": len(feed.entity),
            "matches": matching[:10],
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/")
def index():
    return jsonify({"status": "ok", "stops": list(STOP_ROUTES.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
