"""Record the effective installed dependency closure, including requested extras."""

from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

pending = [Requirement(line) for line in Path("requirements.txt").read_text().splitlines() if line.strip()]
seen = set()
versions = {}
while pending:
    requirement = pending.pop()
    name = canonicalize_name(requirement.name)
    key = (name, tuple(sorted(requirement.extras)))
    if key in seen:
        continue
    seen.add(key)
    installed = distribution(name)
    versions[name] = installed.version
    for raw in installed.requires or []:
        child = Requirement(raw)
        if child.marker is None or any(
            child.marker.evaluate({"extra": extra}) for extra in {"", *requirement.extras}
        ):
            pending.append(child)
Path("docs/dependencies-resolved.txt").write_text(
    "".join(f"{name}=={version}\n" for name, version in sorted(versions.items()))
)
print(f"Recorded {len(versions)} installed packages; this snapshot is platform-specific.")
