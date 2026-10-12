# MR.Softie: notes for Claude

## Working with Blender through MCP (read before any execute_blender_code call)

On 2026-10-11 a session hung on a single `execute_blender_code` call and ran down Jay's usage limit before he stopped it by hand. The Blender MCP server runs every call on Blender's main thread with no time limit on synchronous code. If code defines `check_is_finished`, the call can wait up to 60 minutes. Rules:

- **Keep every call short.** One small job per call, finished in a few seconds. Never loop over many screen states, files or frames in one call; split into separate calls.
- **Cap loops and time.** Any loop gets a hard iteration cap and a wall-clock check (`if time.time() - t0 > 15: break`) and returns what it has.
- **No `check_is_finished`.** Don't use deferred completion. Its timeout is an hour.
- **Nothing blocking on the main thread.** No renders, bakes, simulations, `bpy.ops.render.*`, `wm.redraw_timer`, modal or interactive operators, file browsers, `input()`, `time.sleep()` waits, or waiting on a redraw. Renders and bakes go through `blender --background` from a shell, or Jay runs them himself.
- **Screenshots:** use the MCP screenshot tools one at a time. Don't capture screen states from inside `execute_blender_code`.
- **One slow call means stop.** If a call doesn't return promptly, make one lightweight check (a window screenshot). If Blender is unresponsive or the call is still hanging, stop and report. Never retry the same call or loop.
- **Prefer headless.** Verify changes with `python tests/test_headless.py` (needs `pip install bpy`) instead of driving Jay's open Blender session.

## Project

- Add-on source is in `mr_softie/`. Version lives in `mr_softie/blender_manifest.toml`; each release is one commit titled `X.Y.0: summary`.
- Jay's installed copy is in `%APPDATA%\Blender Foundation\Blender\5.2\extensions\https\mr_softie` (from the `download/` repo feed). Don't edit it directly.
