-- Top window gap: 5 px. Other outer gaps: 10 px.
hl.config({ general = { gaps_out = { top = 5, right = 10, bottom = 10, left = 10 } }, animations = { enabled = true } })
-- Workspace transitions last 850 ms, including swipe completion.
hl.animation({ leaf = "workspaces", enabled = true, speed = 8.5, bezier = "easeOutQuint", style = "slide" })
