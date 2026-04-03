## 2025-04-03 - Accessible Names and Tooltips in PyQt6
**Learning:** Icon-only buttons (like a stop button `■`) in desktop apps built with PyQt6 are inaccessible to screen readers without explicitly set accessible names. Tooltips provide an added layer of usability for all users, particularly when highlighting keyboard shortcuts (like `Left`/`Right` arrows for navigation).
**Action:** Always use `setAccessibleName()` and `setToolTip()` for buttons, especially icon-only buttons or primary actions in desktop GUI applications.
