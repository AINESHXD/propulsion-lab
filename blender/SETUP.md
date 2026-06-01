# Blender MCP — setup

Lets Claude drive Blender (create/modify scenes, export glTF) over an MCP
connection. Two halves: a **Python MCP server** (already installed) and a
**Blender add-on** (`addon.py` in this folder) that opens a socket inside Blender.

## What's already done (by Claude)

- Installed the server: `pip install --user blender-mcp` → **blender-mcp 1.5.6**
  (console script at
  `C:\Users\Ainesh Das\AppData\Roaming\Python\Python313\Scripts\blender-mcp.exe`).
- Registered the MCP server **`blender`** at **local scope** (private to this
  machine, not committed) in `~/.claude.json` under the `Downloads` project.
  A backup was saved to `~/.claude.json.bak`.
- Downloaded the matching Blender add-on to `blender/addon.py`.

## What you need to do

1. **Install Blender** (3.0+, 4.x recommended) from <https://www.blender.org/download/>.
   It isn't currently installed on this machine.

2. **Install the add-on in Blender**
   - Blender → **Edit ▸ Preferences ▸ Add-ons ▸ Install…**
   - Select `…\PropulsionLab_DASLABS\propulsion_lab\blender\addon.py`
   - Tick **Interface: Blender MCP** to enable it.

3. **Start the bridge inside Blender**
   - In the 3D viewport press **N** to open the sidebar → **BlenderMCP** tab.
   - (Leave the Poly Haven / Hyper3D / Sketchfab asset options **off** unless you
     want them — see the security note below.)
   - Click **Connect to MCP server** (it listens on port **9876**).

4. **Reload Claude Code** so it picks up the new MCP server, then run **`/mcp`**.
   You should see `blender` listed as connected. If it shows "failed" while
   Blender is closed, that's expected — it connects once Blender is running and
   step 3 is done.

## Security note (read before using)

`blender-mcp` exposes an `execute_blender_code` tool — it runs **arbitrary Python
inside Blender**. That is what makes it powerful and also risky:
- **Save your .blend file before running operations.** Complex/edge-case
  commands can occasionally corrupt or destroy unsaved work.
- The third-party asset integrations (Poly Haven, Hyper3D Rodin, Sketchfab) reach
  out to external services — keep them disabled unless you intend to use them.
- The server is local-scope and only listens to this machine.

## How this helps PropulsionLab

Once connected, Claude can build/modify the jet-engine geometry in Blender and
**export glTF** straight into `app/static/` so the Three.js viewer
(`viewer3d.html`) can load a high-fidelity model instead of fully procedural
geometry. Ask for that workflow when you're ready.

## Uninstall

- Remove the `blender` entry from `~/.claude.json` (or restore `~/.claude.json.bak`).
- `pip uninstall blender-mcp`
- Disable/remove the add-on in Blender's preferences.
