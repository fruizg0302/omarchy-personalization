-- OmaSwitch previews on Super+Tab; retain Omarchy's default Alt+Tab cycling.
-- Replace the default next/previous workspace shortcuts.
hl.unbind("SUPER + TAB")
hl.unbind("SUPER + SHIFT + TAB")
o.bind("SUPER + TAB", "OmaSwitch", [[omarchy-shell shell summon piyush.omaswitch '{"mode":"cycle","direction":1}']])
o.bind("SUPER + SHIFT + TAB", "OmaSwitch (reverse)", [[omarchy-shell shell summon piyush.omaswitch '{"mode":"cycle","direction":-1}']])

-- Confirm the preview on Super release, including while its overlay has focus.
for _, key in ipairs({ "SUPER_L", "SUPER_R" }) do
  o.bind(key, "Confirm OmaSwitch on Super release", "omarchy-shell personal-omaswitch confirm", {
    release = true, ignore_mods = true, locked = true, non_consuming = true,
  })
end
