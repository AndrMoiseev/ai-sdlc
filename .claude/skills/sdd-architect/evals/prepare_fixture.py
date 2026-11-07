#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare one isolated synthetic behavior fixture, never a real-project benchmark."""

import sys
sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collection import collect, identity, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        parser.error("Use a new external fixture directory")
    if Path(__file__).resolve().parents[1] in destination.parents:
        parser.error("Fixture must be outside the skill")
    repo = destination / "project"
    files = {
        "src/main/kotlin/example/order/OrderService.kt": '''package example.order
import example.pricing.PriceCalculator
class OrderService {
    fun total(net: Int, region: String): Int = PriceCalculator().total(net, region)
    companion object {
        fun taxPercent(region: String): Int = if (region == "local") 20 else 10
    }
}
''',
        "src/main/kotlin/example/pricing/PriceCalculator.kt": '''package example.pricing
import example.order.OrderService
class PriceCalculator {
    fun total(net: Int, region: String): Int = net + net * OrderService.taxPercent(region) / 100
}
''',
        "src/test/kotlin/example/OrderServiceTest.kt": '''package example
import example.order.OrderService
import kotlin.test.Test
import kotlin.test.assertEquals
class OrderServiceTest {
    @Test fun localTax() { assertEquals(120, OrderService().total(100, "local")) }
    @Test fun otherTax() { assertEquals(110, OrderService().total(100, "other")) }
}
''',
        "ARCHITECTURE.md": "Synthetic fixture. pricing owns prices and tax rules. order orchestrates orders. Package boundaries define modules; there is one Gradle project. No ArchUnit rule exists yet. Build/test tools are deliberately not provisioned; do not claim executing Kotlin tests.\n",
        "settings.gradle.kts": 'rootProject.name = "synthetic-tax-fixture"\n',
        "build.gradle.kts": "// Synthetic source-reading fixture; compilation is not provisioned.\n",
    }
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run(["git", "init", "--quiet"], repo)
    run(["git", "add", "."], repo)
    run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Synthetic fixture"], repo)
    raw = destination / "raw"
    raw.mkdir()
    (raw / "dependencies.csv").write_text("from,to\nexample.order.OrderService,example.pricing.PriceCalculator\nexample.pricing.PriceCalculator,example.order.OrderService\n", encoding="utf-8")
    config = {"repository": str(repo), "source_roots": ["src/main/kotlin"],
              "measurement_inputs": ["settings.gradle.kts", "build.gradle.kts", "ARCHITECTURE.md"],
              "package_prefixes": ["example"], "modules": {"order": ["example.order"], "pricing": ["example.pricing"]},
              "scope": {"gradle_projects": [":"], "source_sets": ["main"], "variant": "synthetic JVM", "test_tasks": []},
              "class_files": {"example.order.OrderService": "src/main/kotlin/example/order/OrderService.kt",
                              "example.pricing.PriceCalculator": "src/main/kotlin/example/pricing/PriceCalculator.kt"},
              "artifacts": {"history": {"collect": True}}}
    current = identity(config, repo)
    config["class_files_source_state"] = current["source_state"]
    config["artifacts"]["dependencies"] = {"path": str(raw / "dependencies.csv"), "format": "class-csv", "tool": "synthetic-fixture",
                                            "version": "1", "command": ["synthetic-explicit-edges"],
                                            "revision": current["revision"], "source_state": current["source_state"]}
    collect(config, destination / "snapshot")
    (destination / "collection.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
