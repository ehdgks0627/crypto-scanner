import json

from apps.jobs.services import serialize_dt
from apps.snapshots.migration_plan import recommend_for_risk_score, snapshot_migration_plan_items


def build_cbom_document(snapshot):
    assets = list(snapshot.assets.select_related("target").prefetch_related("risk_scores").order_by("id"))
    dependencies = list(
        snapshot.asset_dependencies.select_related("source_asset", "target_asset").order_by(
            "source_asset__bom_ref",
            "target_asset__bom_ref",
        )
    )
    migration_plan = snapshot_migration_plan_items(snapshot)
    migration_by_asset_id = {item["asset_id"]: item for item in migration_plan}
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": snapshot.serial_number,
        "version": 1,
        "metadata": {
            "timestamp": serialize_dt(snapshot.created_at),
            "component": {
                "type": "application",
                "name": "PQC Risk Assessment System",
                "version": "0.1.0",
            },
            "properties": _metadata_properties(snapshot, assets, migration_plan),
        },
        "components": [build_cbom_component(asset, migration_by_asset_id.get(asset.id)) for asset in assets],
        "dependencies": _dependency_rows(assets, dependencies),
    }
    annotations = _migration_plan_annotations(snapshot, assets, migration_plan)
    if annotations:
        document["annotations"] = annotations
    return document


def _metadata_properties(snapshot, assets, migration_plan):
    properties = [
        {"name": "internal:snapshot_id", "value": str(snapshot.id)},
    ]
    if snapshot.scan_job_id:
        properties.append({"name": "internal:scan_job_id", "value": str(snapshot.scan_job_id)})
    targets = sorted({f"{asset.target.host}:{asset.target.port}" for asset in assets if asset.target})
    if targets:
        properties.append({"name": "internal:targets", "value": json.dumps(targets)})
    if migration_plan:
        properties.extend(
            [
                {"name": "migration_plan.attached", "value": "true"},
                {"name": "migration_plan.item_count", "value": str(len(migration_plan))},
            ]
        )
    return properties


def build_enriched_asset_component(asset):
    risk_score = asset.risk_scores.order_by("-id").first()
    migration_plan_item = recommend_for_risk_score(risk_score) if risk_score else None
    return build_cbom_component(asset, migration_plan_item)


def build_cbom_component(asset, migration_plan_item=None):
    risk_score = asset.risk_scores.order_by("-id").first()
    properties = [
        {"name": "internal:target_id", "value": str(asset.target_id)} if asset.target_id else None,
        {"name": "internal:algorithm_family", "value": asset.algorithm_family} if asset.algorithm_family else None,
        {"name": "internal:quantum_vulnerable", "value": str(_is_quantum_vulnerable(asset)).lower()},
    ]
    properties.extend(_asset_metadata_properties(asset))
    properties.extend(_target_context_properties(asset))
    if risk_score:
        properties.extend(
            [
                {"name": "risk.tier", "value": risk_score.tier},
                {"name": "risk.score", "value": str(round(risk_score.score))},
            ]
        )
    if migration_plan_item:
        properties.extend(_migration_plan_component_properties(migration_plan_item))
    return {
        "type": _component_type(asset),
        "bom-ref": asset.bom_ref,
        "name": asset.name,
        "cryptoProperties": {
            "assetType": asset.asset_type,
            "algorithm": asset.algorithm,
            "algorithmFamily": asset.algorithm_family,
        },
        "properties": [property_item for property_item in properties if property_item],
    }


def _migration_plan_component_properties(item):
    recommendation = item["recommendation"]
    return [
        {"name": "migration.asset_purpose", "value": item["asset_purpose"]},
        {"name": "migration.strategy", "value": recommendation["strategy"]},
        {"name": "migration.target_algorithm", "value": recommendation["target_algorithm"]},
        {
            "name": "migration.target_algorithm_set",
            "value": json.dumps(recommendation["target_algorithm_set"], sort_keys=True),
        },
        {
            "name": "migration.final_algorithm_set",
            "value": json.dumps(recommendation["final_algorithm_set"], sort_keys=True),
        },
        {"name": "migration.phase", "value": recommendation["phase"]},
        {"name": "migration.agility_level", "value": item["agility"]["level"]},
    ]


def _migration_plan_annotations(snapshot, assets, migration_plan):
    if not migration_plan:
        return []
    assets_by_id = {asset.id: asset for asset in assets}
    items = [_migration_plan_attachment_item(item, assets_by_id.get(item["asset_id"])) for item in migration_plan]
    subjects = [item["bom_ref"] for item in items if item["bom_ref"]]
    return [
        {
            "bom-ref": f"migration-plan:snapshot:{snapshot.id}",
            "subjects": subjects,
            "annotator": {
                "component": {
                    "type": "application",
                    "name": "PQC Risk Assessment System",
                    "version": "0.1.0",
                }
            },
            "timestamp": serialize_dt(snapshot.created_at),
            "text": "PQC migration plan generated from snapshot risk scores.",
            "properties": [
                {"name": "attachment.type", "value": "pqc_migration_plan"},
                {"name": "attachment.format", "value": "application/json"},
                {"name": "migration_plan.item_count", "value": str(len(items))},
                {"name": "migration_plan.items", "value": json.dumps(items, sort_keys=True)},
            ],
        }
    ]


def _migration_plan_attachment_item(item, asset):
    recommendation = item["recommendation"]
    current = item["current"]
    agility = item["agility"]
    return {
        "asset_id": item["asset_id"],
        "bom_ref": asset.bom_ref if asset else None,
        "asset_name": item["asset_name"],
        "asset_type": item["asset_type"],
        "asset_purpose": item["asset_purpose"],
        "risk_score": item["risk_score"],
        "tier": item["tier"],
        "current_algorithm": current["algorithm"],
        "quantum_vulnerable": current["quantum_vulnerable"],
        "strategy": recommendation["strategy"],
        "target_algorithm": recommendation["target_algorithm"],
        "target_algorithm_set": recommendation["target_algorithm_set"],
        "final_algorithm_set": recommendation["final_algorithm_set"],
        "phase": recommendation["phase"],
        "blockers": recommendation["blockers"],
        "validation": recommendation["validation"],
        "agility_level": agility["level"],
        "agility_score": agility["score"],
    }


def _dependency_rows(assets, dependencies):
    by_source = {}
    for dependency in dependencies:
        by_source.setdefault(dependency.source_asset.bom_ref, []).append(dependency.target_asset.bom_ref)
    return [
        {"ref": asset.bom_ref, "dependsOn": sorted(set(by_source[asset.bom_ref]))}
        for asset in assets
        if asset.bom_ref in by_source
    ]


def _component_type(asset):
    return "crypto-asset" if asset.asset_class == "crypto" else asset.asset_class


def _is_quantum_vulnerable(asset):
    return asset.algorithm_family in {"RSA", "DSA", "ECDSA", "ECDH", "DH"}


def _asset_metadata_properties(asset):
    metadata = asset.metadata or {}
    safe_keys = {
        "scanner": "evidence.scanner",
        "type": "evidence.type",
        "path": "evidence.path",
        "fingerprint_sha256": "evidence.fingerprint_sha256",
        "key_size_bits": "crypto.key_size_bits",
        "in_use": "evidence.in_use",
        "dormant": "evidence.dormant",
        "referenced_by": "evidence.referenced_by",
        "source_scanners": "evidence.source_scanners",
        "source_paths": "evidence.source_paths",
        "source_bom_refs": "evidence.source_bom_refs",
        "merged": "evidence.merged",
        "minimum_tls_version": "crypto.minimum_tls_version",
        "format": "crypto.format",
    }
    properties = []
    for key, name in safe_keys.items():
        if key not in metadata or metadata[key] is None:
            continue
        value = metadata[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True)
        else:
            value = str(value).lower() if isinstance(value, bool) else str(value)
        properties.append({"name": name, "value": value})
    return properties


def _target_context_properties(asset):
    if not asset.target or not isinstance(asset.target.context, dict):
        return []
    context = asset.target.context
    properties = []
    for key in ("service_role", "sensitivity", "criticality", "exposure", "lifespan_years"):
        value = context.get(key)
        if value is not None:
            properties.append({"name": f"context.{key}", "value": str(value)})
    inference = context.get("homepage_inference")
    if isinstance(inference, dict):
        for key in ("source", "method", "url", "title", "description", "signals", "confidence"):
            value = inference.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = json.dumps(value, sort_keys=True)
            properties.append({"name": f"context.homepage.{key}", "value": str(value)})
    return properties
