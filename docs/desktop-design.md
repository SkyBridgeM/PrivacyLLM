# Desktop design specification

Reference: desktop-concept.png. Primary screen: local text redaction workspace.

- Cool gray 184px sidebar, white workspace, graphite text, teal #167469 actions.
- System Chinese typography; 24px page titles, 16px section titles, 13–14px controls.
- Three workspace columns: original text, redacted text, 280px entity inspector.
- Fine #e1e5e9 borders, 8px radii, minimal shadows. No external fonts or assets.
- Navigation: 脱敏工作台、恢复文本、业务词典、设置与模型。
- Main copy: 脱敏工作台 / 识别、复核，再安全地发送给 AI。 / 使用示例。
- Original editor + mode selector + identify action; output + copy/export; review + details + generate action.
- Secondary pages use the same typography, fields and panels. Model lifecycle states are necessary additions.
- Functional deviations from concept: all selected checkboxes correctly reflect output; source preview supports interactive highlighting; explicit error/empty/loading states; model lifecycle and custom rule editor.
- Native title bar is supplied by macOS, not rendered twice inside the frontend.
- At narrow widths, editors stack and inspector remains accessible. No rasterized UI.
