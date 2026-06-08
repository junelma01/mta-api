import os
import time
from flask import Flask, jsonify
from google.transit import gtfs_realtime_pb2
import requests

app = Flask(__name__)

FEEDS = {
    "Q": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "N": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "R": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "W": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "4": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-456",
    "5": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-456",
    "6": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-456",
}

STOP_ROUTES = {
    "Q504S": ["Q"],
    "621S":  ["4", "5"],
}

def get_feed_url(routes):
    for r in routes:
        if r in FEEDS:
            return FEEDS[r]
    return None

def fetch_minutes(stop_id, routes):
    url = get_feed_url(routes)
    if not url:
        return []

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"Feed fetch error: {e}")
        return []

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)

    now = time.time()
    minutes = []

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
                    if 0 <= m <= 60:
                        minutes.append(m)

    minutes.sort()
    return minutes[:3]

@app.route("/<stop_id>")
def arrivals(stop_id):
    routes = STOP_ROUTES.get(stop_id)
    if not routes:
        return jsonify({"error": "Unknown stop"}), 404
    mins = fetch_minutes(stop_id, routes)
    return jsonify({"stop": stop_id, "minutes": mins})

@app.route("/")
def index():
    return jsonify({"status": "ok", "stops": list(STOP_ROUTES.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
