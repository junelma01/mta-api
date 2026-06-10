import os
import time
import gzip
from flask import Flask, jsonify
from google.transit import gtfs_realtime_pb2
import requests
from datetime import datetime, timezone

app = Flask(__name__)

FEEDS = {
    "Q": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "4": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "5": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
}

STOP_ROUTES = {
    "Q04S": ["Q"],
    "621S":  ["4"],
}

HEADERS = {"Accept-Encoding": "identity"}

def parse_feed(url):
    resp = requests.get(url, timeout=10, headers=HEADERS)
    resp.raise_for_status()
    content = resp.content
    if content[:2] == b'\x1f\x8b':
        content = gzip.decompress(content)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    print(f"Fetched {url} — {len(feed.entity)} entities")
    return feed

def fetch_minutes(stop_id, routes):
    now = datetime.now(timezone.utc).timestamp()
    minutes = []
    feed_urls = list(set(FEEDS[r] for r in routes if r in FEEDS))
    for url in feed_urls:
        try:
            feed = parse_feed(url)
        except Exception as e:
            print(f"Feed error {url}: {e}")
            continue
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            route = entity.trip_update.trip.route_id
            if route not in routes:
                continue
            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id == stop_id:
                    t = stu.arrival.time or stu.departure.time
                    if t and t > now:
                        m = int((t - now) / 60)
                        if 0 < m <= 60:
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

@app.route("/stops/<route_id>")
def stops(route_id):
    url = FEEDS.get(route_id)
    if not url:
        return jsonify({"error": "Unknown route"})
    try:
        feed = parse_feed(url)
        stop_ids = set()
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            if entity.trip_update.trip.route_id != route_id:
                continue
            for stu in entity.trip_update.stop_time_update:
                stop_ids.add(stu.stop_id)
        return jsonify({"route": route_id, "stops": sorted(stop_ids)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/")
def index():
    return jsonify({"status": "ok", "stops": list(STOP_ROUTES.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
