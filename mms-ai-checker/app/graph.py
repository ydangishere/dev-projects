"""Module 1 graph retrieval: deterministic evidence graph, optional Neo4j backend.

Graph relationships represent server-side facts and Rule Engine findings only.
No document contents, extracted names, account numbers, or raw questions are
stored in Neo4j. The local graph is always available without external services.
"""

import hashlib
import hmac
from collections import defaultdict


def build_snapshot(application, documents, findings, rules):
    """Build a provenance graph from an authorized application snapshot."""
    nodes = []
    edges = []

    def node(key, kind, label):
        nodes.append({"key": key, "kind": kind, "label": label})

    def link(source, relation, target):
        edges.append({"source": source, "relation": relation, "target": target})

    node("application", "application", "application")
    node("policy", "policy", str(rules["policy_id"]))
    for rule in sorted(set(rules["rules"].values())):
        node(f"rule:{rule}", "rule", rule)
        link(f"rule:{rule}", "POLICY_SOURCE", "policy")

    required = list(rules["required_documents"])
    for kind in required:
        node(f"kind:{kind}", "document_type", kind)
        link("application", "REQUIRES", f"kind:{kind}")

    by_id = {}
    for document in documents:
        document_id = document["id"]
        by_id[document_id] = document
        doc_key = f"document:{document_id}"
        node(doc_key, "document", document["kind"])
        link("application", "HAS_DOCUMENT", doc_key)
        link(doc_key, "OF_KIND", f"kind:{document['kind']}")

    missing_kinds = iter(kind for kind in required if kind not in {
        doc["kind"] for doc in documents
    })
    for finding in findings:
        fkey = f"finding:{finding.id}"
        node(fkey, "finding", finding.code)
        link("application", "HAS_FINDING", fkey)
        link(fkey, "RULE", f"rule:{finding.rule}")
        if finding.document_id and finding.document_id in by_id:
            link(fkey, "DOCUMENT_EVIDENCE", f"document:{finding.document_id}")
            link(f"document:{finding.document_id}", "HAS_FINDING", fkey)
        elif finding.code == "missing_document":
            # Rule Engine emits missing-document findings in required-document order.
            missing_kind = next(missing_kinds, None)
            if missing_kind:
                link(fkey, "MISSING_TYPE", f"kind:{missing_kind}")
                link(f"kind:{missing_kind}", "MISSING_FINDING", fkey)

    return {"nodes": nodes, "edges": edges}


def graph_evidence(snapshot, documents, findings):
    """Read graph paths linking findings, required document types and rules."""
    relations = defaultdict(set)
    for edge in snapshot["edges"]:
        relations[edge["source"]].add((edge["relation"], edge["target"]))
    by_id = {doc["id"]: doc for doc in documents}
    evidence = []
    for finding in findings:
        fkey = f"finding:{finding.id}"
        neighbors = relations[fkey]
        rule = f"rule:{finding.rule}"
        if ("HAS_FINDING", fkey) not in relations["application"]:
            continue
        if ("RULE", rule) not in neighbors or (
            "POLICY_SOURCE", "policy"
        ) not in relations[rule]:
            continue
        row = {
            "finding_id": finding.id,
            "finding_code": finding.code,
            "rule": finding.rule,
            "path": ["application", fkey, rule, "policy"],
            "document_kind": None,
            "document_id": None,
            "document_verification": None,
            "missing_required_kind": None,
        }
        document = by_id.get(finding.document_id)
        if document and (
            "DOCUMENT_EVIDENCE", f"document:{finding.document_id}"
        ) in neighbors and (
            "HAS_FINDING", fkey
        ) in relations[f"document:{finding.document_id}"]:
            row["document_kind"] = document["kind"]
            row["document_id"] = document["id"]
            row["document_verification"] = document["verification"]
            row["path"].insert(1, f"document:{document['id']}")
        else:
            missing = sorted(
                target.removeprefix("kind:")
                for relation, target in neighbors
                if relation == "MISSING_TYPE"
                and ("REQUIRES", target) in relations["application"]
                and ("MISSING_FINDING", fkey) in relations[target]
            )
            if missing:
                row["missing_required_kind"] = missing[0]
                row["path"].insert(1, f"kind:{missing[0]}")
        evidence.append(row)
    return evidence


def merge_and_rerank(sections, graph_rows, findings):
    """Prioritize rules supported by graph findings; never omit policy sections."""
    severities = {finding.id: finding.severity for finding in findings}
    scores = defaultdict(int)
    for row in graph_rows:
        scores[row["rule"]] += 3 if severities.get(row["finding_id"]) == "blocker" else 2
    enriched = [
        {**section, "graph_score": scores[section["rule"]]}
        for section in sections
    ]
    return sorted(
        enriched,
        key=lambda item: (
            -item["graph_score"],
            -item["score"],
            item["rule"],
        ),
    )


class Neo4jGraph:
    """Optional authorized snapshot materialization and graph-edge retrieval.

    Persist only HMAC-pseudonymized graph node keys, fixed codes and relations.
    Both the write and read occur in a single transaction for consistency.
    """

    def __init__(self, uri, username, password, secret, database="neo4j"):
        if not uri or not username or not password or len(secret) < 32:
            raise ValueError("Neo4j requires URI, username, password and GRAPH_HMAC_KEY >=32 characters")
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("Install the optional requirements-graph.txt") from exc
        self.secret = secret.encode("utf-8")
        self.database = database
        self.driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=3,
            connection_acquisition_timeout=3,
            max_transaction_retry_time=2,
        )

    def _token(self, value):
        return hmac.new(self.secret, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def retrieve_edges(self, tenant, application_id, snapshot):
        scope = self._token(f"{tenant}\0{application_id}")
        keys = {
            node["key"]: self._token(f"{scope}\0{node['key']}")
            for node in snapshot["nodes"]
        }
        nodes = [
            {"token": keys[node["key"]], "kind": node["kind"], "label": node["label"]}
            for node in snapshot["nodes"]
        ]
        links = [
            {
                "source": keys[edge["source"]],
                "relation": edge["relation"],
                "target": keys[edge["target"]],
            }
            for edge in snapshot["edges"]
        ]

        def write_and_query(tx):
            tx.run(
                "MATCH (n:MMSGraphNode {scope: $scope}) DETACH DELETE n",
                scope=scope,
            ).consume()
            tx.run(
                "UNWIND $nodes AS item "
                "CREATE (n:MMSGraphNode {scope: $scope, token: item.token, "
                "kind: item.kind, label: item.label})",
                scope=scope,
                nodes=nodes,
            ).consume()
            tx.run(
                "UNWIND $links AS item "
                "MATCH (a:MMSGraphNode {scope: $scope, token: item.source}) "
                "MATCH (b:MMSGraphNode {scope: $scope, token: item.target}) "
                "CREATE (a)-[:MMS_LINK {kind: item.relation}]->(b)",
                scope=scope,
                links=links,
            ).consume()
            return [
                (record["source"], record["relation"], record["target"])
                for record in tx.run(
                    "MATCH (a:MMSGraphNode {scope: $scope})-[r:MMS_LINK]->"
                    "(b:MMSGraphNode {scope: $scope}) "
                    "RETURN a.token AS source, r.kind AS relation, b.token AS target",
                    scope=scope,
                )
            ]

        with self.driver.session(database=self.database) as session:
            observed = session.execute_write(write_and_query)

        reverse = {value: key for key, value in keys.items()}
        if len(observed) != len(links):
            raise RuntimeError("Neo4j returned an incomplete graph snapshot")
        actual = {
            (reverse.get(a), relation, reverse.get(b))
            for a, relation, b in observed
        }
        expected = {
            (edge["source"], edge["relation"], edge["target"])
            for edge in snapshot["edges"]
        }
        if actual != expected:
            raise RuntimeError("Neo4j graph snapshot does not match authorized facts")
        return [
            {"source": source, "relation": relation, "target": target}
            for source, relation, target in sorted(actual)
        ]

    def close(self):
        self.driver.close()


def retrieve_module1(application, documents, findings, rules, sections, backend=None):
    """Return graph rows and graph-assisted section order; fail safely to local graph."""
    snapshot = build_snapshot(application, documents, findings, rules)
    source = "local"
    status = None
    if backend is not None:
        try:
            edges = backend.retrieve_edges(application["tenant"], application["id"], snapshot)
            snapshot["edges"] = edges
            source = "neo4j"
        except Exception:
            # Graph is advisory. Never lose Rule Engine findings on a DB outage.
            status = "neo4j_unavailable_local_fallback"
    rows = graph_evidence(snapshot, documents, findings)
    sections = merge_and_rerank(sections, rows, findings)
    return {"backend": source, "evidence": rows}, sections, status
