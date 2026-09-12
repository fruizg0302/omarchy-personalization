# Omarchy personalization

A macOS-inspired Omarchy desktop, tailored on an ASUS TUF A14 with an AMD Ryzen AI Max+ processor. This repository records selected customizations rather than a complete home directory.

Built against Omarchy 4.0.3 and Hyprland 0.56.2 with Lua configuration. Upstream plugin revisions are recorded in [plugins.lock.json](plugins.lock.json).

## Desktop behavior

- Pointer sensitivity `0.25`; natural touchpad scrolling with factor `0.25`.
- Latin American keyboard (`latam`) and Compose on Menu (`compose:menu`).
- Four-finger horizontal swipe changes workspaces; transitions last 850 ms.
- Four-finger swipe up opens a thumbnail overview of the current workspace. Click a window or use arrows and Enter; Escape closes it. Previews are snapshots taken when opened, with a label fallback when capture is unavailable.
- Stock Alt+Tab window cycling. Super+Tab opens OmaSwitch previews; Shift reverses direction. A compositor-side Super-release binding confirms the selection through a local IPC handler, supplementing Qt's modifier-release handling.
- Top window gap of 5 px. The dock reserves 6 px less space to bring windows closer.
- Ghostty is the preferred terminal, once its package is installed.

## Dock

The [rosakodu dock](https://github.com/rosakodu/omarchy-dock) is always visible and reserves screen space. Local patches add working glass translucency, labels above the icons, a divider before utility shortcuts, stable utility ordering, and 95% icon enlargement on hover with a 180 ms animation. Translucency is not a claim of compositor background blur.

Pinned order: Files, Ghostty, Chromium, Mail, Calendar, Notion, HEY Mail, HEY Calendar, Slack, Discord, ChatGPT, Claude, Zed, Apple Music, Apple Podcasts, YouTube, Brain.fm, Settings, Docker, WhatsApp, then Applications, Downloads, and Trash.

Mail and Calendar use Evolution; many other entries open web apps. Docker opens Omarchy's Docker TUI. The HEY Calendar URL requires checking after sign-in. Some themed icon paths depend on Yaru, AdwaitaLegacy, or Omarchy's packaged icons. Official logos are downloaded separately from [public sources](icons/sources.json); they are not redistributed here.

## Restore on an Omarchy installation

No script here automatically replaces your running desktop. First render a reviewable home-directory tree:

```bash
python3 scripts/stage.py ./stage --home "$HOME"
```

This creates `.config` and `.local` inside `stage`, refuses an existing destination, and substitutes your home path in icon references. Review the files and back up the corresponding existing configuration before copying selected files into your home directory. Keep `~/.local/bin` on `PATH`.

On a fresh setup, load the three staged `personal-*.lua` modules from the ends of the corresponding existing Hyprland files:

```lua
-- ~/.config/hypr/input.lua
dofile(os.getenv("HOME") .. "/.config/hypr/personal-input.lua")
-- ~/.config/hypr/looknfeel.lua
dofile(os.getenv("HOME") .. "/.config/hypr/personal-looknfeel.lua")
-- ~/.config/hypr/bindings.lua
dofile(os.getenv("HOME") .. "/.config/hypr/personal-bindings.lua")
```

Use each include in its named file. When migrating an already customized setup, remove duplicate gesture/binding declarations first. The input module intentionally selects LATAM: adapt this for other keyboards.

Install the external plugins from the URLs in `plugins.lock.json`. For reproducibility, use clean clones checked out at their recorded commit **before enabling them**, and place them under `~/.config/omarchy/plugins/<id>`. Do not reset an existing modified plugin checkout. Apply the patches to those clean, pinned directories:

```bash
python3 scripts/patch-plugin.py rosakodu.dock "$HOME/.config/omarchy/plugins/rosakodu.dock"
python3 scripts/patch-plugin.py piyush.omaswitch "$HOME/.config/omarchy/plugins/piyush.omaswitch"
omarchy-shell shell rescanPlugins
omarchy plugin enable rosakodu.dock
omarchy plugin enable piyush.omaswitch
omarchy plugin enable local.workspace-overview
```

Headroom and ASUS Control are optional entries in the lock file. The shell layout under `examples/` is a reference, not installed by the staging script; it includes additional independently installed plugins. Merge only entries whose plugins you have installed. Plugin updates may need patch rebasing; the patch helper refuses mismatched revisions and conflicting local changes.

Download the app icons and install desired native apps:

```bash
python3 scripts/fetch-icons.py "$HOME/.local/share/icons/dock-apps"
sudo pacman -S --needed ghostty zed evolution
omarchy default terminal ghostty
hyprctl reload
hyprctl configerrors
omarchy restart shell
```

These package commands are instructions, not proof those applications are installed. The Files and Chromium pins depend on their system desktop entries. Downloaded icon URLs may change; the downloader reports failures and leaves existing files alone.

## Apps-menu scroll speed

The Apps submenu uses an independent scroll multiplier of `2`, while browser scrolling retains the global touchpad factor `0.25`. Pixel-based wheel events are doubled; angle-based events use the Qt wheel-line preference and menu row height. Other menu pages retain their default behavior.

To restore this adjustment, run `omarchy plugin clone omarchy.menu`. In the local clone's `Menu.qml`, insert the contents of `menu/apps-scroll.qml.inc` inside `ListView { id: resultList ... }`, after `boundsBehavior` and before `section.property`. Do not modify the packaged file in `/usr/share/omarchy`. Validate the local plugin and restart the shell. The clone command routes the existing menu shortcuts to the local copy; future packaged menu updates need to be merged into the clone manually.

## Optional ASUS and GPU helpers

`optional/` is separate from the desktop staging tree. Review it for your hardware before installing.

- Copy `asus-hotkey` and `asus-profile-notify.py` to `~/.local/bin`; make the shell helper executable. Include `optional/hypr/asus-bindings.lua` after copying it to your Hyprland configuration. It uses `asusctl` and Omarchy's power-profile commands.
- Copy `asus-profile-notify.service` to `~/.config/systemd/user`, then run `systemctl --user daemon-reload` and `systemctl --user enable --now asus-profile-notify.service`. It watches the actual firmware profile and sends one notification per stable change, including firmware-handled Fn+F5 events.
- `gpu-memory` provides `status`, `8`, and `56` presets. Copy it to `~/.local/bin` and make it executable. Source the optional alias file from `~/.bashrc.local`.

The GPU helper expects the specific existing drop-in `/etc/limine-entry-tool.d/amdgpu-gtt.conf` and refuses an unfamiliar file layout. Presets change the next-boot GTT ceiling, not permanently reserved RAM. They require sudo, `limine-update`, and a reboot. They never edit `/boot/limine.conf`. These hardware settings are not applied by any desktop setup command in this repository.

## Privacy and maintenance

Only selected text files are tracked. No browser profiles, logins, emails, local hostname, home username, screenshots, model files, private source trees, shell history, or credentials are included. Existing private dotfiles remain separate. This is a reviewed snapshot, not an automatic home-directory sync.

Before publishing future changes, review `git diff --cached` and run `python3 scripts/check-public.py`. The check is a heuristic aid, not a guarantee against every kind of secret. Validate Lua changes with Hyprland and review plugin changes against the locked upstream revision.

The original customization files use the MIT license. Upstream patch context retains the MIT notices in `licenses/`; app names and logos belong to their respective owners. See [THIRD_PARTY.md](THIRD_PARTY.md).
