-- Latin American keyboard, pointer, scrolling, and workspace gestures.
hl.config({ input = {
  kb_layout = "latam",
  kb_variant = "",
  kb_options = "compose:menu",
  sensitivity = 0.25,
  touchpad = { natural_scroll = true, clickfinger_behavior = true, scroll_factor = 0.25 },
} })
hl.gesture({ fingers = 4, direction = "horizontal", action = "workspace" })
hl.gesture({ fingers = 4, direction = "up", action = function()
  hl.dispatch(hl.dsp.exec_cmd("omarchy-shell shell toggle local.workspace-overview"))
end })
