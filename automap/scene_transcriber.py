"""SceneCreator's transcriber: an authored Godot 2D scene -> level@2 document.

The reverse projection (and the S5 re-absorb seed): parses a .tscn's text
form and lifts the original game's backdrop-scene vocabulary into the level
contract — background sprite, SceneSpawn markers, TeleportArea2D volumes
(scene-file/uid targets remapped to LEVEL IDS), StaticBody2D walls,
player and NPC placements. Anything it does not understand lands in the
`skipped` report instead of silently vanishing — fidelity means knowing what
was left behind (Auregate's dead arrow spawner, script-less orphan actors).

Pure text parsing, no Godot needed; deterministic; the JeuZoeMila scenes
round-trip against the hand transcriptions as the component's proof.
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADER = re.compile(r"^\[(gd_scene|ext_resource|sub_resource|node|connection)\s*(.*?)\]\s*$")
_ATTR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s\]]+)')
_VEC2 = re.compile(r"Vector2\(\s*([-\d.e+]+)\s*,\s*([-\d.e+]+)\s*\)")


def _unquote(v: str) -> str:
    return v[1:-1] if v.startswith('"') and v.endswith('"') else v


def parse_tscn(text: str) -> dict:
    """.tscn text -> {ext_resources, sub_resources, nodes} (order preserved)."""
    ext: dict[str, dict] = {}
    sub: dict[str, dict] = {}
    nodes: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        m = _HEADER.match(line.strip())
        if m:
            kind, attr_text = m.group(1), m.group(2)
            attrs = {k: _unquote(v) for k, v in _ATTR.findall(attr_text)}
            if kind == "ext_resource":
                ext[attrs.get("id", "")] = attrs
                current = None
            elif kind == "sub_resource":
                current = {"_kind": "sub", "type": attrs.get("type", ""), "props": {}}
                sub[attrs.get("id", "")] = current
            elif kind == "node":
                current = {"_kind": "node", "name": attrs.get("name", ""),
                           "type": attrs.get("type", ""),
                           "parent": attrs.get("parent"), "props": {}}
                nodes.append(current)
            else:
                current = None
            continue
        if current is None or "=" not in line:
            continue
        key, _, val = line.partition("=")
        current["props"][key.strip()] = val.strip()
    return {"ext": ext, "sub": sub, "nodes": nodes}


def _vec2(raw: str | None, default=(0.0, 0.0)) -> list[float]:
    if raw:
        m = _VEC2.search(raw)
        if m:
            return [float(m.group(1)), float(m.group(2))]
    return list(default)


def _resolve(raw: str | None, table: dict) -> dict | None:
    """ExtResource("x")/SubResource("x") -> the referenced entry."""
    if not raw:
        return None
    m = re.search(r'(?:Ext|Sub)Resource\("([^"]+)"\)', raw)
    return table.get(m.group(1)) if m else None


def _script_base(node: dict, ext: dict) -> str:
    ref = _resolve(node["props"].get("script"), ext)
    return Path(ref["path"]).name if ref and "path" in ref else ""


def _node_path(node: dict, by_path: dict) -> str:
    p = node.get("parent")
    if p in (None, ""):
        return "."
    return node["name"] if p == "." else f"{p}/{node['name']}"


def build_uid_map(*scene_dirs: Path) -> dict[str, str]:
    """uid://... -> level id, from the original scene files' headers."""
    uid_map: dict[str, str] = {}
    for d in scene_dirs:
        for f in d.rglob("*.tscn"):
            head = f.read_text(errors="ignore").splitlines()[0] if f.exists() else ""
            m = re.search(r'uid="(uid://[a-z0-9]+)"', head)
            if m:
                uid_map[m.group(1)] = f.stem
    return uid_map


def transcribe(scene_path: Path, uid_map: dict[str, str],
               level_id: str | None = None,
               dialogues_dir: Path | None = None) -> tuple[dict, list[str]]:
    """One authored scene -> (level@2 doc, skipped-node report).

    `dialogues_dir`: when a `<slug>_intro` dialogue document exists there, NPC
    placements get wired to it (the slug->conversation convention).
    """
    parsed = parse_tscn(scene_path.read_text())
    ext, sub, nodes = parsed["ext"], parsed["sub"], parsed["nodes"]
    by_path = {_node_path(n, {}): n for n in nodes}
    lid = level_id or scene_path.stem
    doc: dict = {"id": lid, "name": lid.replace("_", " ").title(), "spawns": []}
    skipped: list[str] = []

    def shape_of(parent_path: str) -> tuple[list[float], list[float]] | None:
        """First CollisionShape2D child -> (pos incl. parent offset, size)."""
        for n in nodes:
            if n["type"] == "CollisionShape2D" and n.get("parent") == parent_path:
                res = _resolve(n["props"].get("shape"), sub)
                if res and res["type"] == "RectangleShape2D":
                    size = _vec2(res["props"].get("size"), (32.0, 32.0))
                    parent = by_path.get(parent_path, {"props": {}})
                    base = _vec2(parent["props"].get("position"))
                    off = _vec2(n["props"].get("position"))
                    return [base[0] + off[0], base[1] + off[1]], size
        return None

    for n in nodes:
        path = _node_path(n, by_path)
        base = _script_base(n, ext)
        pos = _vec2(n["props"].get("position"))
        if n["type"] == "Sprite2D" and "background" not in doc:
            tex = _resolve(n["props"].get("texture"), ext)
            if tex and "path" in tex:
                doc["background"] = {"file": Path(tex["path"]).name, "pos": pos,
                                     "scale": _vec2(n["props"].get("scale"), (1, 1))}
            else:
                skipped.append(f"{path}: Sprite2D without texture")
        elif base == "SceneSpawn.gd":
            tag = _unquote(n["props"].get("tag", '"default"')) or "default"
            doc["spawns"].append({"tag": tag, "pos": pos})
        elif base == "TeleportArea2D.gd":
            target_raw = _unquote(n["props"].get("target_scene_path", '""'))
            target = uid_map.get(target_raw, Path(target_raw).stem if target_raw else "")
            rect = shape_of(path)
            if target and rect:
                t = {"target_level": target, "rect": {"pos": rect[0], "size": rect[1]}}
                tag = _unquote(n["props"].get("target_spawn_tag", '""'))
                if tag:
                    t["target_spawn_tag"] = tag
                doc.setdefault("teleports", []).append(t)
            else:
                skipped.append(f"{path}: teleport missing target or shape")
        elif base == "OverworldPlayer.gd":
            doc["player"] = {"pos": pos}
            slug = _unquote(n["props"].get("creature_slug", '""'))
            if slug:
                doc["player"]["slug"] = slug
        elif base == "OverworldNPC.gd":
            npc = {"slug": _unquote(n["props"].get("creature_slug", '""')), "pos": pos}
            if dialogues_dir is not None and \
                    (dialogues_dir / f"{npc['slug']}_intro.json").exists():
                npc["dialogue"] = f"{npc['slug']}_intro"
            doc.setdefault("npcs", []).append(npc)
        elif n["type"] == "StaticBody2D":
            rect = shape_of(path)
            if rect:
                doc.setdefault("collision_rects", []).append(
                    {"pos": rect[0], "size": rect[1]})
            else:
                skipped.append(f"{path}: StaticBody2D without rectangle shape")
        elif n["type"] in ("Node2D", "Area2D", "CharacterBody2D", "Timer", "") \
                and path != "." and base == "" \
                and not any(x.get("parent") == path for x in nodes):
            if n["props"].get("script") == "null" or n["type"] == "":
                skipped.append(f"{path}: script-less orphan node")
            elif n["type"] == "Timer":
                skipped.append(f"{path}: timer (embedded logic not transcribable)")

    if not doc["spawns"]:
        # the scene authored no arrival point at all — synthesize one, loudly
        fallback = doc.get("player", {}).get("pos") \
                or doc.get("background", {}).get("pos") or [512.0, 512.0]
        doc["spawns"].append({"tag": "default", "pos": fallback})
        skipped.append("no spawn authored — default synthesized")
    return doc, skipped
