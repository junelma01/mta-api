import os
import time
import gzip
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

def fetch_minutes(stop_id, routes):
    feed_urls = list(set(FEEDS[r] for r in routes if r in FEEDS))
    now = time.time()
    minutes = []

    for url in feed_urls:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"Feed fetch error for {url}: {e}")
            continue

        try:
            # Decompress if gzipped
            content = resp.content
            if content[:2] == b'\x1f\x8b':
                content = gzip.decompress(content)

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(content)
        except Exception as e:
            print(f"Protobuf parse error: {e}")
            continue

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

@app.route("/")
def index():
    return jsonify({"status": "ok", "stops": list(STOP_ROUTES.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
