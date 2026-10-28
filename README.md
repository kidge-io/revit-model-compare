# Revit Model Compare

**Measure how accurately an AI- or plugin-generated MEP model reproduces a reference model.**

[繁體中文說明](README.zh-TW.md)

AI and automated tools can now build Revit models from 2D drawings. The hard part is knowing whether the result is right. Revit's built-in comparisons (ACC version compare, Navisworks Compare) match elements by ID, so they only work on two versions of the *same* file. Two independently built models share no IDs, and those tools report everything as added and deleted.

Revit Model Compare matches elements **by geometry** instead. It tells you, for every duct, pipe, cable tray and conduit run and every fitting, whether the model under test got it right, slightly off, moved, the wrong size, missing, or extra. It also produces colored side-by-side screenshots of the differences.

It is a [pyRevit](https://github.com/pyrevitlabs/pyRevit) extension with three buttons:

| Button | What it does |
|---|---|
| **Export MEP** | Exports MEP elements of the open model to CSV: ID, category, family, system, size, coordinates. Read-only. |
| **Compare Models** | Compares a reference CSV with a model-under-test CSV. Writes a summary, an issue list, full comparison tables and a screenshot list. |
| **Issue Shots** | For each issue cluster, creates a 3D view with a section box, colors the issue elements and exports a PNG. Run it in both models to get matching image pairs. |

The first real-world use compared a plugin-generated smoke-exhaust duct system against the owner's model (about 1,400 elements per model, 15 levels). It found that 100% of the reference centerlines were reproduced at the correct size. It also pinned down where the plugin went wrong: round-end diameters falling back to a family default, oval sections where rectangular ones were required, and plugin-generated families replacing the owner's standard families.

## What it reports

Segments (ducts, pipes, cable trays, conduits) are matched by both endpoints, regardless of drawing direction. Components (fittings, accessories, terminals, sprinklers, equipment) are matched by insertion point. Elements are only ever matched within the same discipline.

| Result | Meaning |
|---|---|
| Match | Same size, position within 5 mm |
| Minor offset | Same size, position within 50 mm |
| Break offset (segments) | Same centerline and size, but the run is split at a different point |
| Moved (components) | Same type within 1 m, but more than 50 mm away |
| Size / type mismatch | Position agrees, size or component type does not |
| Missing / Extra | No counterpart found |
| Non-reference family | The model under test uses a family the reference model does not use |

The tool also reports **centerline coverage**: the share of the reference model's segment length that the model under test reproduces. This number does not depend on how the runs are split, so it is the best single measure of "is the routing there".

Output files (folder `Results_<date_time>`):

- `Summary.txt`: headline numbers per discipline
- `Issues.csv`: one row per issue with both ElementIds, so you can *Select by ID* in Revit
- `Segments.csv`, `Components.csv`: every match decision
- `shots.csv`: input for **Issue Shots**

## Install

Requires [pyRevit](https://github.com/pyrevitlabs/pyRevit/releases). Developed and tested with pyRevit 7.0 on Revit 2024; other versions should work but are untested.

**Option A: pyRevit CLI**

```
pyrevit extend ui ModelCompare https://github.com/kidge-io/revit-model-compare.git
```

**Option B: manual**

1. Download this repository as a ZIP and extract it.
2. Rename the extracted folder to `ModelCompare.extension` (pyRevit only loads folders ending in `.extension`), for example `D:\pyRevitExt\ModelCompare.extension`.
3. In Revit: **pyRevit tab → pyRevit ▾ → Settings → Custom Extension Directories → Add folder**, pick the *parent* folder (`D:\pyRevitExt`), then **Save Settings and Reload**.

A **ModelCompare** tab with the three buttons appears.

## Use

1. Open the reference model (for example the owner's model) and click **Export MEP**. Then do the same in the model under test.
2. With the reference model open, click **Compare Models**. Pick the reference CSV, then the model-under-test CSV. Choose which disciplines and systems to compare, and pick an output folder.
3. Click **Issue Shots** in each model and select the `shots.csv` from step 2. Each issue cluster gets `Sxx_ref.png` and `Sxx_test.png` from the same viewpoint.

Want to try it without your own models? `examples/sample/` contains a synthetic pair with known, seeded differences. Run **Compare Models** on those two CSVs.

**Language:** the UI follows pyRevit's language setting. Chinese gives a Traditional Chinese UI; anything else gives English.

## Requirements and limits

- Both models must share the same **internal origin**. The tool does not align coordinates.
- Run **Issue Shots** on model copies. It only adds `MC_` 3D views and never edits elements, but it is good practice.
- Tolerances are fixed for now (5 mm / 50 mm / 1 m) and set in `lib/mc_compare.py`.
- Floors are assigned from the open model's level elevations when they agree with the CSV. Otherwise each element's reference level is used.
- Validated so far on one real project (ducts) and on the synthetic sample (ducts, pipes, cable trays). Please open an issue if your model behaves differently.

## Development

The comparison core (`lib/mc_compare.py`) is plain Python that runs on both IronPython 2.7 (inside Revit) and CPython 3. That means it can be tested without Revit:

```
python examples/make_sample.py
python -m unittest discover -s tests -v
```

Keep the core free of f-strings and other Python 3-only syntax.

## Support

This tool is free and MIT-licensed. If it saves you time, you can [buy me a coffee](https://www.buymeacoffee.com/YOUR_BMC_USERNAME).

Built by [KIDGE Ltd.](https://kidge.io) (Taipei). For AI-assisted BIM modeling and verification work, contact monica.lin@kidge.io.

## License

[MIT](LICENSE)
