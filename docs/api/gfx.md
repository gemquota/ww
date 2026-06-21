# Mascot TUI

Terminal mascot with 8 animation states: SLEEP, WAKING, WAITING, WALKING, SCANNING, THINKING, CONFUSED, SUCCESS, GLITCH.

## Usage
```python
from src.gfx.mascot_tui import Mascot
m = Mascot()
m.on_event('THINKING')
# ... work ...
m.on_event('SUCCESS')
m.shutdown()
```
