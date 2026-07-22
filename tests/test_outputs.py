"""Verifier for the MLflow advisory pipeline build task.

The graded artifact is the shipped CMake project: the verifier re-runs the
build from a clean tree with no extra flags and checks the report the built
pipeline produces.
"""

import hashlib
import json
import os
import pathlib
import subprocess
import tempfile

import jsonschema
import pytest

PIPELINE = "/app/pipeline"
OUT_JSON = "/app/out/risk-report.json"
SCHEMA_JSON = "/app/schema/risk-report.schema.json"
DOCS_DIR = "/app/docs/pages"
MIRROR_DIR = "/var/lib/osv"
TOOLS = ("extract", "advise", "score")

PRISTINE = {
    "/app/pipeline/src/advise.c": "a098879e4b09b04319901218a3168445b71e6f51e7bb6576839782e13fc58e14",
    "/app/pipeline/src/common.c": "1c1db4d823854ca0cbd7664a793ec767f7f003eb02198c9ad5c92fde5fa34021",
    "/app/pipeline/src/common.h": "a13a7c651a8a89c8bfde1fa6cf548847be74027a3d9fdc742e1b4837e442a31a",
    "/app/pipeline/src/cvss.c": "f2a1a87dc74bfdd7e0eac4de63b816a578833f57470880f2382a97085c3050fd",
    "/app/pipeline/src/cvss.h": "2669676a854aa191f1ec2e1196a210b0df6dfcfd583477f503daa99b04314570",
    "/app/pipeline/src/extract.c": "796e45d89db9fe5d2cdd798d570143ba5136a612371dc27c188dbd5daadb7e02",
    "/app/pipeline/src/fold.h": "7e89ff821002d6ff3c8a3fbb4148257af23caeb21e4b9acc4ed993f3aa61e78f",
    "/app/pipeline/src/fold_alias.c": "7e6e050d9b316210262f8248135fb35f9aba723a4a3a42e4d583a345d97a4616",
    "/app/pipeline/src/fold_none.c": "19cd4fb9236de35f4b508f6037e897433cb32173a805b6bc5fd3f95008d3a691",
    "/app/pipeline/src/order.h": "ac430d825c0fcd7822c399294fba8c343a799bc1f768aa13bbc55e564d5b7b8b",
    "/app/pipeline/src/order_name.c": "43a67967d1514f3f20ce8a2c4a5f3768c077947dd4a7482bb8fb259c96c42a7c",
    "/app/pipeline/src/order_weighted.c": "d3c9393d78a96517c1f9fe92e529f0415fb08466ff1792a1d6c202e2e32b6992",
    "/app/pipeline/src/pinsel.h": "fbaa6ca3cf8111462576db15d76a22f855e415eb3db3d6b06cc5643da4ae9061",
    "/app/pipeline/src/pinsel_floor.c": "6f1dbff96190430b24275de25cf0dee03a07aac2c770393938d701454dd68879",
    "/app/pipeline/src/pinsel_latest.c": "6e51efbe7a91fa582692d8a2b2605ee035063d8b744344751730f56779c79f44",
    "/app/pipeline/src/report_row.h": "b7511d0049ef579a00983c79fdb4d23ac1771262a008cef2553a870303aa6c0c",
    "/app/pipeline/src/score.c": "a6225e7b1e1e3daed903a1ec045c3e2cf6d298a3a728cedba9a32da8b14938b1",
    "/app/pipeline/src/sevagg.h": "f33fd18a8f15b0c3f1c5ac9f8c8823c7797f4f2ca1ea026c80e26906fc4a1692",
    "/app/pipeline/src/sevagg_curated.c": "2714aa51aec2b08403701fef63ad64e0e4182c02225e11ecd5378133d3c0d9dc",
    "/app/pipeline/src/sevagg_max.c": "5d6a457d21c1002d744e242cf3f52551cbb7fc5b5c391636b200cfc91b15b673",
    "/app/pipeline/src/severity_table.h": "a79a61f5c88f09e10464902a31bfe01bc410b468e663a6b8e69f0388a539c5b3",
    "/app/pipeline/src/vercmp.c": "fe686a5d294d96979f60974e2280587094115746ea1fbe0edf0030ffa9d19ac0",
    "/app/pipeline/src/vercmp.h": "32c6d38cc500eb562c91b2684d8d3d80e4aa964527776ccd4d9d9c4eaff125a9",
    "/app/pipeline/src/compat/vercmp.h": "f4d8c4c1e53955f0924156e81cf9b5d8e632f91f8bf3781a3248ab2dc0439ad0",
    "/app/pipeline/vendor/qjson/qjson.c": "1dd94fa1e19a8a3edd5bea9090d75606241c9a0c9b22e4a387fec6330ddc88fd",
    "/app/pipeline/vendor/qjson/qjson.h": "4990299921a72cd5b2cd7ee33003f0e178fd8295427677b903b61637fc9f79b6",
    "/app/pipeline/tools/mkscore.c": "d2e874a42bf1a628bea182ed659f7624a2ab1ae8cb9d1caae64a6dbe695d8d11",
    "/app/pipeline/config/severity.map": "d10b5093a04646e17f1ed4da21073b14a46095aa4cbb4964f3b63bfcc9c4c539",
    "/app/docs/pages/artifact-store.md": "2f33427a4f504114922713eab4c8b89b633ddd6fbdfad393a4859c294ed8df0e",
    "/app/docs/pages/auth.md": "5143da006eb23bf1219f579b0398b680530272f8e37e41e4934715a0b328dcf1",
    "/app/docs/pages/model-serving.md": "b1714bf2757bbdbb41e6cadacfe4c075380285984d2350815b85d1a56f5db0ee",
    "/app/docs/pages/projects.md": "8b35f5a103c1701ec21ca278c5b8f7dbdc680d7213acd2afdbeed2158905a5a0",
    "/app/docs/pages/recipes.md": "1d2ea5290c7118f92898536259609a8f12e5aa2cb92899bf6da664ecf154d32f",
    "/app/docs/pages/scoring-container.md": "23ff91ec6a1e2fa0c984ae65dc2f35c79160d34270c0d3cf3c1b096247ea2f3c",
    "/app/docs/pages/tracking-server.md": "c5396e601c919b320beda884ca34c44ee0fd6b41ffad5d71707bc9610a289a81",
    "/app/docs/samples/smoke.md": "3f31282a3797a6212c4666f6eb10f26fddbb71a40929d01ac5bce886e904da09",
    "/var/lib/osv/GHSA-4f7p-27jc-3c36.json": "f960ade3f2d717e0896bfea29cc74af2ae6056b93335496a624b90692fc06e20",
    "/var/lib/osv/GHSA-58q9-vppv-3g6c.json": "47c9b7982975f1e742d9acca203f521b648cf01709f7ffac45d36b23ca9c194b",
    "/var/lib/osv/GHSA-6wvq-7f3h-6xmm.json": "a7532118253358e65fc01fe20f9af639e297eb5b5509208187d128ad8796e0b0",
    "/var/lib/osv/GHSA-7p9q-hrqf-2f2x.json": "290df5db68367a27fc6f84848680aa35b4a81bf1050eb092aaf0b429c0656cd2",
    "/var/lib/osv/GHSA-83mx-6h29-mm94.json": "075c542a3e025e1de4fd657a7d1f73b1eea3af138f8d2f8eba932005979e8701",
    "/var/lib/osv/GHSA-9m4x-9fex-h9qh.json": "ed16103026475d9036535b69cdbaf53b8d2df4ca481f3034ec7af95e5c9bcd1b",
    "/var/lib/osv/GHSA-cvw4-9r7p-vqqm.json": "d0bcb369d0006ab334b72ed5b56f70bfb1a9aa689883b9d849bf30368170ddef",
    "/var/lib/osv/GHSA-fm37-qk4q-8x9g.json": "e2519cc0fec62bb1f8ab2abbaae22227827ebf1d62dd83021d58c3308ad39f1f",
    "/var/lib/osv/GHSA-h5c8-rqwp-cp95.json": "7974cdc7411b8bbc4959a32e8b5a37af65f64d203540a39cdc547a294dbca34f",
    "/var/lib/osv/GHSA-hrfv-mqp8-q5rw.json": "e8863a62d5541a8bb9f333847f2c38a103e5277c220dd1ef30f830408ecba248",
    "/var/lib/osv/GHSA-p3v6-c6cx-hrgq.json": "144769750452e71e40a5b932c11aa7fc9fe8bc946a3d0bb81ee3a1e48b69011a",
    "/var/lib/osv/GHSA-w2rc-8xqm-9q5v.json": "d12638d89dc594c3bfb344915cddc7cd08cc09d875ccdd4b81e543fe2c742029",
    "/var/lib/osv/GHSA-x4qr-wcfg-2p9v.json": "2ad0c57b780000eaca8ee57700df1e3ed3cd08f008b67ca97bbc4c094d752cef",
    "/var/lib/osv/PYSEC-2025-0983.json": "476940211987a10465560e6d2d3dd3ef83735d11fe9fb5f6739a8184b5e436d6",
    "/var/lib/osv/PYSEC-2025-1104.json": "fde910d55391e80721e5db146f7b207136a4710aac97babc2665b2e020ef2ab1",
    "/var/lib/osv/PYSEC-2025-1121.json": "80321abf09ab8a873eef14405661688f0a2ae22d54f1a784121dfd2c8fa69e2d",
    "/var/lib/osv/PYSEC-2026-0219.json": "4df3e142a95c256f2af2d982ea74c075d0736c2305ef71424ed5e83f19e3e690",
    "/app/report/model-risk-report.md": "8f94817dd04db540ddfb4e4cf834965f17b6fc87d981a80ccac8b74aefd3de71",
    "/app/schema/risk-report.schema.json": "c1b566234eb4df9f4ff0bf8580691e763fa3b26c7627d46240e9f6911009dfbe"
}

EXPECTED = {
    "schema_version": "4",
    "packages": [
        {
            "name": "pyarrow",
            "assessed_version": "14.0.0",
            "pages_referenced": 2,
            "advisory_count": 1,
            "max_severity": 9.6,
            "risk_score": 10.0,
            "advisories": [
                "GHSA-6wvq-7f3h-6xmm"
            ]
        },
        {
            "name": "gunicorn",
            "assessed_version": "20.1.0",
            "pages_referenced": 2,
            "advisory_count": 2,
            "max_severity": 8.6,
            "risk_score": 9.4,
            "advisories": [
                "GHSA-p3v6-c6cx-hrgq",
                "PYSEC-2026-0219"
            ]
        },
        {
            "name": "mlflow",
            "assessed_version": "2.9.2",
            "pages_referenced": 4,
            "advisory_count": 2,
            "max_severity": 7.5,
            "risk_score": 8.7,
            "advisories": [
                "PYSEC-2025-1104",
                "PYSEC-2025-1121"
            ]
        },
        {
            "name": "waitress",
            "assessed_version": "2.1.2",
            "pages_referenced": 2,
            "advisory_count": 2,
            "max_severity": 7.5,
            "risk_score": 8.3,
            "advisories": [
                "GHSA-4f7p-27jc-3c36",
                "GHSA-9m4x-9fex-h9qh"
            ]
        },
        {
            "name": "jinja2",
            "assessed_version": "3.1.2",
            "pages_referenced": 1,
            "advisory_count": 1,
            "max_severity": 8.1,
            "risk_score": 8.3,
            "advisories": [
                "GHSA-h5c8-rqwp-cp95"
            ]
        },
        {
            "name": "flask",
            "assessed_version": "2.2.5",
            "pages_referenced": 1,
            "advisory_count": 1,
            "max_severity": 5.4,
            "risk_score": 5.6,
            "advisories": [
                "GHSA-hrfv-mqp8-q5rw"
            ]
        }
    ]
}


@pytest.fixture(scope="session")
def clean_build():
    """Configure and build the report target from a clean tree, no extra flags."""
    builddir = tempfile.mkdtemp(prefix="verify-build-")
    pathlib.Path("/app/out").mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(OUT_JSON)
    if out.exists():
        out.unlink()
    configure = subprocess.run(
        ["cmake", "-S", PIPELINE, "-B", builddir],
        capture_output=True, text=True, timeout=240,
    )
    build = None
    if configure.returncode == 0:
        build = subprocess.run(
            ["cmake", "--build", builddir, "--target", "report"],
            capture_output=True, text=True, timeout=240,
        )
    return {"builddir": builddir, "configure": configure, "build": build}


def test_shipped_inputs_pristine():
    """The C sources, vendored lib, docs, mirror, report and schema are unmodified."""
    for path, want in PRISTINE.items():
        p = pathlib.Path(path)
        assert p.is_file(), f"shipped file missing: {path}"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == want, f"shipped file was modified: {path}"


def test_clean_build_succeeds(clean_build):
    """cmake -S /app/pipeline -B <dir> && cmake --build <dir> --target report succeed."""
    configure = clean_build["configure"]
    assert configure.returncode == 0, (
        f"cmake configure failed:\n{configure.stdout}\n{configure.stderr}"
    )
    build = clean_build["build"]
    assert build is not None and build.returncode == 0, (
        f"cmake --build --target report failed:\n{build.stdout}\n{build.stderr}"
    )


def test_tools_built(clean_build):
    """The build leaves extract, advise and score executables under <builddir>/bin."""
    for tool in TOOLS:
        exe = pathlib.Path(clean_build["builddir"]) / "bin" / tool
        assert exe.is_file(), f"missing built tool: {exe}"
        assert os.access(exe, os.X_OK), f"tool not executable: {exe}"


def test_report_validates_against_schema(clean_build):
    """The build writes /app/out/risk-report.json and it validates against the shipped schema."""
    assert pathlib.Path(OUT_JSON).is_file(), f"report not written: {OUT_JSON}"
    with open(OUT_JSON) as f:
        report = json.load(f)
    with open(SCHEMA_JSON) as f:
        schema = json.load(f)
    jsonschema.validate(report, schema)


def test_report_matches_methodology(clean_build):
    """The report equals the revision 4 result: membership, values, ordering, advisory ids."""
    assert pathlib.Path(OUT_JSON).is_file(), f"report not written: {OUT_JSON}"
    with open(OUT_JSON) as f:
        report = json.load(f)
    assert report == EXPECTED, (
        f"report content does not match the revision 4 methodology:\n"
        f"got: {json.dumps(report, indent=1)}"
    )


def test_built_tools_reproduce_report(clean_build):
    """Running the built tools directly on the shipped inputs regenerates the same report."""
    bindir = pathlib.Path(clean_build["builddir"]) / "bin"
    for tool in TOOLS:
        assert (bindir / tool).is_file(), f"missing built tool: {bindir / tool}"
    tmp = tempfile.mkdtemp(prefix="verify-run-")
    steps = [
        [str(bindir / "extract"), DOCS_DIR, f"{tmp}/packages.tsv"],
        [str(bindir / "advise"), f"{tmp}/packages.tsv", MIRROR_DIR,
         f"{tmp}/matches.json"],
        [str(bindir / "score"), f"{tmp}/matches.json", f"{tmp}/report.json"],
    ]
    for cmd in steps:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, f"{cmd[0]} failed: {proc.stderr}"
    with open(f"{tmp}/report.json") as f:
        rerun = json.load(f)
    assert rerun == EXPECTED, "pipeline rerun does not reproduce the report"
