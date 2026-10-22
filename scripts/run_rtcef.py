#!/usr/bin/env python3
"""Bounded author-service integration with controlled adaptation signals.

The injected scores exercise control flow; they are NOT measured concept drift.
All five author services, Kafka, Py4J, retraining, optimisation and model swaps
run as real processes. Children are terminated on success, failure or interrupt.
"""
import argparse
import configparser
import hashlib
import json
import os
import platform
import random
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from check_sources import ROOT, check

AUTHOR = ROOT / "upstream/rtcef"
sys.path.insert(0, str(AUTHOR))
import utilities
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError
from py4j.java_gateway import JavaGateway, GatewayParameters


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(path, count, seed, start=100000):
    schema = json.loads((AUTHOR / "schemas/schemas_maritime/input_stream-value.avsc").read_text())
    rng = random.Random(seed)
    records = []
    high = False
    for i in range(count):
        high = rng.random() < (0.8 if high else 0.25)
        record = {f["name"]: ("" if f["type"] == "string" else 0) for f in schema["fields"]}
        record.update(timestamp=start + 600 * (i + 1), mmsi="synthetic-vessel", speed=15.0 if high else 2.0,
                      lon=-4.7, lat=48.1, trh=0.0, cog=0.0,
                      next_timestamp=start + 600 * (i + 2), critical_bitstring="00000000")
        records.append(record)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
    return records


def configuration(run_dir, initial):
    conf = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    conf.read(AUTHOR / "configs/port/conf_0.ini")
    conf["default"]["projectpath"] = str(AUTHOR)
    conf["default"]["pattern_file"] = str(run_dir / "pattern.sre")
    conf["default"]["declaration_file"] = str(run_dir / "declarations.sre")
    for service in ("engine", "observer", "collector", "factory", "optimiser"):
        conf[service]["executionlog"] = str(run_dir / f"{service}.execution.log")
    replacements = {
        "engine": {"model.wayebjar": str(ROOT / "artifacts/rtcef-wayeb.jar"),
                   "model.param.initial_model": str(initial), "model.param.confidence_threshold": "0.6",
                   "model.param.reporting_dt": "120000", "model.param.start_time": "100000"},
        "collector": {"bucketsize": "30000", "bucketsnumber": "20", "k": "2",
                      "storagepath": str(run_dir / "collected") + "/"},
        "factory": {"assembleddatasetspath": str(run_dir / "assembled") + "/",
                    "savedmodelspath": str(run_dir / "models")},
        "optimiser": {"hyper.confidence.min": "0.3", "hyper.confidence.max": "0.9",
                      "hyper.order.min": "1", "hyper.order.max": "2",
                      "hyper.pmin.min": "0.001", "hyper.pmin.max": "0.01",
                      "hyper.gamma.min": "0.001", "hyper.gamma.max": "0.01",
                      "init.model.param.confidence": "0.6", "init.model.param.order": "2",
                      "init.model.param.pmin": "0.001", "init.model.param.gamma": "0.001",
                      "ninitbench": "2", "ntotalevals": "3", "keepnevals": "-1", "reuse": "false",
                      "optimisationlogs": str(run_dir / "optimisation") + "/",
                      "optimisationsamples": str(run_dir / "optimisation") + "/",
                      "optimisationmodels": str(run_dir / "optimisation") + "/"},
        "observer": {"k": "3", "slopethreshold": "-0.05", "lowscorethreshold": "0.1", "recenttrainthreshold": "3"},
    }
    for section, values in replacements.items():
        conf[section].update(values)
    conf["optimiser"].pop("initialmodel", None)
    # Keep injected control signals separate from real engine scores.
    conf["observer.topics"]["input.modelscores"] = "controlled_scores"
    conf["observer.topics.schemas"]["input.modelscores"] = str(AUTHOR / "schemas/schemas_maritime/model_runtime_scores")
    path = run_dir / "rtcef.ini"
    with path.open("w") as out:
        conf.write(out)
    return conf, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sources = check()
    for port in (9092, 9093, 25333, 25334, 25335, 25336):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} is already in use; this bounded run requires isolated ports")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (args.output or ROOT / "runs" / f"rtcef-{stamp}").resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ("collected", "assembled", "models", "optimisation"):
        (run_dir / name).mkdir()
    (run_dir / "pattern.sre").write_text(";(SpeedBetween(10.0,30.0),SpeedBetween(10.0,30.0)){order:0}{partitionBy:mmsi}\n")
    (run_dir / "declarations.sre").write_text("~(SpeedBetween(0.0,10.0),SpeedBetween(10.0,30.0),IsEventTypePredicate(RESET))\n")
    train, test = run_dir / "train.jsonl", run_dir / "test.jsonl"
    generate(train, 1000, 20261022)
    generate(test, 400, 20261023)
    stream_path = run_dir / "stream.jsonl"
    stream = generate(stream_path, 960, 20261024)
    initial = run_dir / "initial.spst"
    conf, config_path = configuration(run_dir, initial)
    java = os.environ["WAYEB_JAVA"]
    kafka = ROOT / ".tools/kafka_2.13-3.4.0"
    children, handles, clients, messages = [], [], [], []
    report = {"status": "failed", "scope": "bounded author-service integration with injected control scores, not a concept-drift accuracy benchmark"}

    def spawn(name, command):
        handle = (run_dir / f"{name}.log").open("w")
        handles.append(handle)
        child = subprocess.Popen(command, cwd=run_dir, env=os.environ.copy(), stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        children.append((name, child))
        return child

    def healthy():
        for name, child in children:
            if child.poll() is not None:
                raise RuntimeError(f"{name} exited with {child.returncode}; inspect {run_dir / (name + '.log')}")

    def wait_port(port):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            healthy()
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    return
            time.sleep(0.2)
        raise TimeoutError(f"Port {port} did not open")

    try:
        broker_config = run_dir / "broker.properties"
        broker_config.write_text("\n".join([
            "process.roles=broker,controller", "node.id=1", "controller.quorum.voters=1@127.0.0.1:9093",
            "listeners=PLAINTEXT://127.0.0.1:9092,CONTROLLER://127.0.0.1:9093",
            "advertised.listeners=PLAINTEXT://127.0.0.1:9092", "controller.listener.names=CONTROLLER",
            "listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT",
            "inter.broker.listener.name=PLAINTEXT", f"log.dirs={run_dir / 'kafka-data'}",
            "offsets.topic.replication.factor=1", "transaction.state.log.replication.factor=1",
            "transaction.state.log.min.isr=1", "group.initial.rebalance.delay.ms=0", "auto.create.topics.enable=false",
        ]) + "\n")
        classpath = str(kafka / "libs/*")
        subprocess.run([java, "-cp", classpath, "kafka.tools.StorageTool", "format", "-t", "MkU3OEVBNTcwNTJENDM2Qk", "-c", str(broker_config)], check=True, cwd=run_dir, stdout=subprocess.DEVNULL)
        spawn("kafka", [java, "-Xmx512m", "-Dkafka.logs.dir=" + str(run_dir / "kafka-logs"), "-Dlog4j.configuration=file:" + str(kafka / "config/log4j.properties"), "-cp", classpath, "kafka.Kafka", str(broker_config)])
        wait_port(9092)
        # A listening broker socket can precede controller election readiness.
        deadline = time.monotonic() + 60
        while True:
            healthy()
            try:
                admin = KafkaAdminClient(bootstrap_servers="127.0.0.1:9092", api_version=(2, 6, 0), request_timeout_ms=30000)
                break
            except KafkaError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        topic_schemas = {v: AUTHOR / conf["kafka.recordSchemas"]["schema." + k.split(".", 1)[1]] for k, v in conf["kafka.topics"].items()}
        topic_schemas["controlled_scores"] = AUTHOR / "schemas/schemas_maritime/model_runtime_scores"
        admin.create_topics([NewTopic(t, 1, 1) for t in topic_schemas])
        admin.close()
        print("Kafka ready", flush=True)
        jar = ROOT / "artifacts/rtcef-wayeb.jar"
        java_command = [java, "-Xmx1g", "-Dlogback.configurationFile=" + str(ROOT / "configs/logback.xml"), "-jar", str(jar)]
        spawn("factory-gateway", [*java_command, "server"])
        wait_port(25334)
        # This gateway's JVM is owned by the run and stopped below; suppress
        # remote finalizer calls after JVM shutdown.
        gateway = JavaGateway(gateway_parameters=GatewayParameters(port=25334, auto_convert=True, enable_memory_management=False))
        objective = list(gateway.entry_point.trainAndSave(str(train), str(run_dir / "pattern.sre"), str(run_dir / "declarations.sre"), str(initial), "maritimejson", -1.0, -1.0, 2, 0.001, 0.001, "nt"))
        heldout = list(gateway.entry_point.loadAndTest(str(test), str(initial), "maritimejson", -1.0, -1.0, 0.6))
        assert objective == [2.0] and sum(heldout) > 0 and initial.stat().st_size > 0
        gateway.close()
        print("Author Py4J training and held-out evaluation passed", flush=True)
        spawn("engine-gateway", [*java_command, "service", "--pythonPort", "25335", "--javaPort", "25336"])
        wait_port(25336)
        monitor = KafkaConsumer(*topic_schemas, bootstrap_servers="localhost:9092", group_id="deployment-validation", auto_offset_reset="earliest", enable_auto_commit=False)
        clients.append(monitor)
        for service in ("collector", "factory", "optimiser", "observer", "engine"):
            spawn(service, [sys.executable, "-u", str(ROOT / "scripts/rtcef_service.py"), "-s", service, "-c", str(config_path)])

        def producer(topic):
            prefix = str(topic_schemas[topic])
            client = KafkaProducer(bootstrap_servers="localhost:9092", key_serializer=utilities.avro_serializer(prefix + "-key.avsc"), value_serializer=utilities.avro_serializer(prefix + "-value.avsc"))
            clients.append(client)
            return client

        input_producer, score_producer = producer("input_stream"), producer("controlled_scores")

        def send_chunk(start, stop):
            for row in stream[start:stop]:
                input_producer.send("input_stream", key={"timestamp": row["timestamp"], "mmsi": row["mmsi"]}, value=row)
            input_producer.flush(timeout=30)

        decoders = {t: utilities.avro_deserializer(str(p) + "-value.avsc") for t, p in topic_schemas.items()}

        def wait_for(topic, condition, seconds=180):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                healthy()
                for batches in monitor.poll(timeout_ms=500).values():
                    for record in batches:
                        messages.append({"topic": record.topic, "offset": record.offset, "value": decoders[record.topic](record.value)})
                for message in messages:
                    if message["topic"] == topic and condition(message["value"]):
                        return message["value"]
            raise TimeoutError(f"No expected record on {topic}; inspect service logs in {run_dir}")

        def control_score(value):
            metrics = json.dumps({"mcc": value})
            row = {"timestamp": 172000, "model_version": -1, "creation_method": "integration-control", "batch_metrics": metrics, "runtime_metrics": metrics}
            score_producer.send("controlled_scores", key={"timestamp": row["timestamp"]}, value=row).get(timeout=30)

        send_chunk(0, 240)
        # A bucket holds 51 records (600s spacing, strict >30000s boundary).
        # Wait for every complete bucket in this chunk before triggering a
        # control action, so process scheduling cannot choose a different data window.
        wait_for("assembled_datasets", lambda row: row["version"] == 3)
        retrain_input = run_dir / "retrain-input.jsonl"
        shutil.copyfile(run_dir / "assembled/assembled_dataset_version_3", retrain_input)
        print("Author collector and factory assembled a streaming dataset", flush=True)
        control_score(0.9)
        control_score(0.7)
        retrained = wait_for("model_versions", lambda row: row["creation_method"] == "retrain")
        wait_for("engine_sync", lambda row: row["type"] == "play" and row["model_id"] == retrained["id"])
        send_chunk(240, 480)
        wait_for("model_runtime_scores", lambda row: row["model_version"] == retrained["id"])
        wait_for("assembled_datasets", lambda row: row["version"] == 8)
        optimisation_input = run_dir / "optimisation-input.jsonl"
        shutil.copyfile(run_dir / "assembled/assembled_dataset_version_8", optimisation_input)
        print("Observer-triggered retraining and engine model swap passed", flush=True)
        control_score(0.05)
        optimised = wait_for("model_versions", lambda row: row["creation_method"] == "optimisation")
        wait_for("engine_sync", lambda row: row["type"] == "play" and row["model_id"] == optimised["id"])
        send_chunk(480, 720)
        wait_for("model_runtime_scores", lambda row: row["model_version"] == optimised["id"])
        print("Bayesian optimisation and second engine model swap passed", flush=True)
        candidate_reports = [m["value"] for m in messages if m["topic"] == "factory_reports" and m["value"]["metrics"]]
        assert len(candidate_reports) == 3, candidate_reports
        report.update(status="passed", created_at_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
                      platform=platform.platform(), sources=sources["repositories"],
                      heldout_counts=dict(zip(("tp", "tn", "fp", "fn"), heldout)),
                      inputs={p.name: digest(p) for p in (train, test, stream_path, retrain_input, optimisation_input)},
                      seeds={"train": 20261022, "test": 20261023, "stream": 20261024},
                      training_events=1000, heldout_events=400, streaming_events_sent=720,
                      retrained_model_id=retrained["id"], optimised_model_id=optimised["id"],
                      controlled_scores=[0.9, 0.7, 0.05], optimisation_evaluations=3,
                      adaptation_dataset_versions={"retrain": 3, "optimisation": 8},
                      optimised_parameters=json.loads(optimised["model_params"]),
                      optimisation_candidates=[{"params": json.loads(r["params_dict"]), "metrics": json.loads(r["metrics"])} for r in candidate_reports],
                      services=[name for name, _ in children], jar_sha256=digest(jar),
                      configuration_sha256=digest(config_path), kafka_python=__import__("kafka").__version__,
                      python_requirements_sha256=digest(ROOT / "configs/requirements-rtcef.lock.txt"),
                      limitations=["Adaptation signals are injected, not measured concept drift.",
                                   "The author factory's optimisation path evaluates on its assembled training data; its train/test splitting is commented out upstream.",
                                   "The independent 400-event held-out evaluation above is a separate deployment check.",
                                   "Forward progress and observed model swaps do not prove the paper's lossless adaptation theorem or reproduce its benchmarks."])
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        for client in clients:
            try:
                client.close(timeout=2) if isinstance(client, KafkaProducer) else client.close()
            except Exception:
                pass
        for _, child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for _, child in reversed(children):
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for handle in handles:
            handle.close()
        (run_dir / "messages.json").write_text(json.dumps(messages, indent=2) + "\n")
        report["all_children_stopped"] = all(child.poll() is not None for _, child in children)
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(run_dir), "retrained_model_id": report["retrained_model_id"], "optimised_model_id": report["optimised_model_id"]}, indent=2))


if __name__ == "__main__":
    main()

