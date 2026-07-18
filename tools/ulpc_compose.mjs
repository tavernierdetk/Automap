#!/usr/bin/env node
// ULPC bridge CLI — Automap side of the PixelAssetCreator integration
// (docs/explorations/ulpc-casting-integration.md).
//
//   node tools/ulpc_compose.mjs <build.json> <out_base_dir> <slug>
//
// Imports composeULPCExport from the sibling PixelAssetCreator checkout
// (override with PIXELASSET_ROOT). The build spec is ulpc.build/1.0 with
// output.mode "split_by_frame": frames land engine-named
// (<out>/ulpc_frames/Walk_front/… — the slicer's orientation folders ARE
// the engine animation contract). Prints a JSON result to stdout.
import path from "node:path";
import fs from "node:fs";
import { pathToFileURL } from "node:url";

const [buildPath, outBaseDir, slug, resultPath] = process.argv.slice(2);
if (!buildPath || !outBaseDir || !slug) {
  console.error("usage: ulpc_compose.mjs <build.json> <out_base_dir> <slug> [result.json]");
  process.exit(2);
}

const PIXELASSET_ROOT =
  process.env.PIXELASSET_ROOT ??
  path.join(process.env.HOME ?? "", "Cowork", "PixelAssetCreator");

const composerPath = path.join(
  PIXELASSET_ROOT, "packages", "sprite-compose", "dist", "ulpc.js");
if (!fs.existsSync(composerPath)) {
  console.error(
    `no built composer at ${composerPath} — run pnpm install + tsc -b ` +
    "in PixelAssetCreator (see the integration doc)");
  process.exit(2);
}

// resolveUlpcSheetDefs walks up from the composer package, so the vendor
// submodule resolves from the PixelAssetCreator checkout automatically.
const { composeULPCExport } = await import(pathToFileURL(composerPath));

const build = JSON.parse(fs.readFileSync(buildPath, "utf8"));
const result = await composeULPCExport({ build, outBaseDir, slug });
// the composer's pino logger owns stdout — the machine-readable result
// goes to a file so the caller never parses log noise
const payload = JSON.stringify({
  frames: result.frames ?? {},
  manifestPath: result.manifestPath ?? null,
  warnings: result.warnings,
}, null, 2);
if (resultPath) fs.writeFileSync(resultPath, payload);
else console.log(payload);
if ((result.warnings ?? []).length) {
  console.error(`[ulpc] ${result.warnings.length} warning(s)`);
}
