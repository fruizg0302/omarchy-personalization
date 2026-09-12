-- Load after asus-bindings.lua. Replace native Aura cycling with Keyboard Glow.
hl.unbind("XF86Launch4")
hl.unbind("SHIFT + XF86Launch4")
o.bind("XF86Launch4", "Keyboard lighting next effect", "~/.local/bin/glow mode next", { locked = true })
o.bind("SHIFT + XF86Launch4", "Keyboard lighting previous effect", "~/.local/bin/glow mode prev", { locked = true })

-- Only a boolean activity event leaves the compositor, at most every 300 ms.
local glow_typing = false
hl.on("input.keyboard.key", function(_, _, state)
  if state == 1 or state == 2 then glow_typing = true end
end)
local glow_timer = hl.timer(function()
  if glow_typing then
    glow_typing = false
    hl.dispatch(hl.dsp.event("keyboard-glow,typing"))
  end
end, { timeout = 300, type = "repeat" })
glow_timer:set_enabled(true)
