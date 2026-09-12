-- ASUS backlight controls: replace Omarchy's brightnessctl helper with asusctl.
-- Keep saturation at off/high, cycling, repeat, lock-screen use, and the OSD.
hl.unbind("XF86KbdBrightnessUp")
hl.unbind("XF86KbdBrightnessDown")
hl.unbind("XF86KbdLightOnOff")
o.bind("XF86KbdBrightnessUp", "ASUS keyboard brightness up", "~/.local/bin/asus-hotkey keyboard up", { locked = true, repeating = true })
o.bind("XF86KbdBrightnessDown", "ASUS keyboard brightness down", "~/.local/bin/asus-hotkey keyboard down", { locked = true, repeating = true })
o.bind("XF86KbdLightOnOff", "ASUS keyboard backlight cycle", "~/.local/bin/asus-hotkey keyboard cycle", { locked = true })

-- ASUS Fn+F4: Aura (KEY_PROG4). Previously misbound to performance profile.
hl.unbind("XF86Launch4")
o.bind("XF86Launch4", "ASUS Aura next effect", "asusctl aura effect --next-mode", { locked = true })

-- ASUS Fn+F5: performance profile (KEY_FN_F5).
o.bind("XF86Fn_F5", "ASUS performance profile", "~/.local/bin/asus-hotkey profile", { locked = true })
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")
