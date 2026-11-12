import os
import re
import time

import docker
import requests
from flask import Flask, jsonify, send_from_directory

NETWORK = os.environ.get("DOCKER_NETWORK", "sparkpoc_net")
PROJECT = os.environ.get("COMPOSE_PROJECT", "sparkpoc")
MASTER_URL = os.environ.get("SPARK_MASTER_UI", "http://spark-master:8080")
LOCAL_NODE = os.environ.get("LOCAL_NODE_NAME", "host")
NODE_NAMES = dict(p.split("=", 1) for p in os.environ.get("NODE_NAMES", "").split(",") if "=" in p)

app = Flask(__name__, static_folder="static")
client = docker.from_env()

ROLES = {
    "spark-master": "spark-master",
    "spark-worker": "spark-worker",
    "cassandra": "cassandra",
    "neo4j": "neo4j",
    "jupyterhub": "hub",
    "openldap": "ldap",
    "nfs": "nfs",
    "wan-gw": "tunnel",
    "wan-ws": "tunnel",
    "dashboard": "dashboard",
}


def role_of(name, labels):
    service = labels.get("com.docker.compose.service")
    if service in ROLES:
        return ROLES[service]
    if name.startswith("sparkpoc-user-"):
        return "notebook"
    return "other"


def container_nodes():
    nodes, env_of = {}, {}
    for c in client.containers.list(all=True):
        nets = c.attrs["NetworkSettings"]["Networks"]
        if NETWORK not in nets:
            continue
        labels = c.labels
        if "com.docker.compose.container-number" not in labels:
            labels = {k: v for k, v in labels.items() if not k.startswith("com.docker.compose.")}
        service = labels.get("com.docker.compose.service") or c.name
        health = c.attrs["State"].get("Health", {}).get("Status")
        status = c.status if not health or c.status != "running" else (
            "running" if health == "healthy" else health)
        nodes[service if labels.get("com.docker.compose.service") else c.name] = {
            "id": service if labels.get("com.docker.compose.service") else c.name,
            "label": service,
            "kind": role_of(c.name, labels),
            "status": status,
            "host": LOCAL_NODE,
            "ip": nets[NETWORK].get("IPAddress"),
            "image": c.attrs["Config"]["Image"],
            "depends_on": [d.split(":")[0] for d in labels.get("com.docker.compose.depends_on", "").split(",") if d],
        }
        env_of[nodes[service if labels.get("com.docker.compose.service") else c.name]["id"]] = c.attrs["Config"].get("Env") or []
    return nodes, env_of


def spark_state():
    try:
        return requests.get(f"{MASTER_URL}/json/", timeout=2).json()
    except Exception:
        return None


def build_graph():
    nodes, env_of = container_nodes()
    edges = []

    def edge(src, dst, kind):
        if src in nodes and dst in nodes:
            edges.append({"source": src, "target": dst, "kind": kind})

    for n in list(nodes.values()):
        for dep in n["depends_on"]:
            edge(n["id"], dep, "depends_on")
        if n["kind"] == "notebook":
            edge("jupyterhub", n["id"], "spawns")
            edge(n["id"], "spark-master", "spark")
            env = dict(e.split("=", 1) for e in env_of[n["id"]] if "=" in e)
            if env.get("CASSANDRA_HOST"):
                edge(n["id"], env["CASSANDRA_HOST"], "data")
            m = re.match(r"\w+://([^:/]+)", env.get("NEO4J_URI", ""))
            if m:
                edge(n["id"], m.group(1), "data")

    spark = spark_state()
    master_up = bool(spark) and spark.get("status") == "ALIVE"
    if "spark-master" in nodes:
        nodes["spark-master"]["spark"] = (
            {"status": spark["status"], "apps": len(spark["activeapps"]),
             "cores": spark["cores"], "coresused": spark["coresused"]} if spark else None)

    by_ip = {n["ip"]: n["id"] for n in nodes.values() if n.get("ip")}
    for w in (spark or {}).get("workers", []):
        if w["state"] == "DEAD":
            continue
        wid = by_ip.get(w["host"])
        if wid is None:
            wid = "worker@" + w["host"]
            nodes[wid] = {
                "id": wid, "label": "spark-worker", "kind": "spark-worker",
                "host": NODE_NAMES.get(w["host"], w["host"]), "ip": w["host"],
                "image": "", "depends_on": [],
            }
            edge_target = "wan-gw"
            edge(wid, edge_target, "tunnel")
        nodes[wid]["status"] = "running" if w["state"] == "ALIVE" else w["state"].lower()
        nodes[wid]["spark"] = {"state": w["state"], "cores": w["cores"],
                               "coresused": w["coresused"], "memory": w["memory"],
                               "memoryused": w["memoryused"]}
        edge(wid, "spark-master", "registered")

    return {"time": time.time(), "master_alive": master_up,
            "nodes": list(nodes.values()), "edges": edges}


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/graph")
def graph():
    try:
        return jsonify(build_graph())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/")
def index():
    return send_from_directory("static", "index.html")
