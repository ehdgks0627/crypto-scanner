import json

from apps.jobs.services import serialize_dt


def build_cbom_document(snapshot):
    assets = list(snapshot.assets.select_related("target").prefetch_related("risk_scores").order_by("id"))
    dependencies = list(snapshot.asset_dependencies.select_related("source_asset", "target_asset").order_by("source_asset__bom_ref", "target_asset__bom_ref"))
    return {
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
            "properties": _metadata_properties(snapshot, assets),
        },
        "components": [_component(asset) for asset in assets],
        "dependencies": _dependency_rows(assets, dependencies),
    }


def _metadata_properties(snapshot, assets):
    properties = [
        {"name": "internal:snapshot_id", "value": str(snapshot.id)},
    ]
    if snapshot.scan_job_id:
        properties.append({"name": "internal:scan_job_id", "value": str(snapshot.scan_job_id)})
    targets = sorted({f"{asset.target.host}:{asset.target.port}" for asset in assets if asset.target})
    if targets:
        properties.append({"name": "internal:targets", "value": json.dumps(targets)})
    return properties


def _component(asset):
    risk_score = asset.risk_scores.order_by("-id").first()
    properties = [
        {"name": "internal:target_id", "value": str(asset.target_id)} if asset.target_id else None,
        {"name": "internal:algorithm_family", "value": asset.algorithm_family} if asset.algorithm_family else None,
        {"name": "internal:quantum_vulnerable", "value": str(_is_quantum_vulnerable(asset)).lower()},
    ]
    if risk_score:
        properties.extend(
            [
                {"name": "risk.tier", "value": risk_score.tier},
                {"name": "risk.score", "value": str(round(risk_score.score))},
            ]
        )
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
