            // Apps-only scrolling: compensate for the slower global touchpad setting.
            WheelHandler {
              target: null
              enabled: root.activeMenu === "apps" && !root.dmenuActive
              acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
              onWheel: function(event) {
                var delta = event.pixelDelta.y !== 0
                  ? event.pixelDelta.y
                  : event.angleDelta.y / 120 * Qt.styleHints.wheelScrollLines * root.rowHeightForDetail("")
                var minimum = resultList.originY
                var maximum = minimum + Math.max(0, resultList.contentHeight - resultList.height)
                resultList.cancelFlick()
                resultList.contentY = Math.max(minimum, Math.min(maximum, resultList.contentY - delta * 2))
                event.accepted = true
              }
            }
