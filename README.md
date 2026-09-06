<p align="center">
  <img src="./assets/terminal.svg" alt="kieran@machine:~$ whoami — offsec · systems · embedded · ai" />
</p>

<p align="center">
  <img src="./assets/divider.svg" alt="" />
</p>

### `~$ whoami`

Computer science at **Franciscan University of Steubenville**, class of 2029.
Offensive security, low level systems, random hardware hacking and the occasional
reverse engineering project.

Most of what's below started with something on my desk annoying me. A Windows PC
with no network, next to a Quest 3 that had WiFi and was already plugged into it.
A disk that kept filling up while Finder, `df` and `du` each gave a different number.
A degree planner that would tell me a course existed and not much else.

The offsec side mostly shows up here as not trusting the client: the FPS below does
its hit detection on the server, and the daily delivery game re-scores every run from
its replay rather than believing the time the browser reports.

### `~$ ps aux | grep building`

| project | what it does | stack |
| :--- | :--- | :--- |
| **[backquest](https://github.com/KieranK07/backquest)** | Gives an internet-less Windows PC internet through a Quest 3's WiFi, over the USB-C cable it was already charging on. gnirehtet with the roles swapped. | Rust · wintun · adb |
| **[loupe](https://github.com/KieranK07/loupe)** | macOS disk-usage visualizer. Walks two million files in six seconds on a hand-written parallel `getattrlistbulk` reader, then names exactly which caches it will trash and what breaks if you let it. | Swift 6 · SwiftUI · C |
| **[swarf](https://github.com/KieranK07/swarf)** | Falling-sand sim on the GPU, 4096×2048 cells at 240 Hz. Margolus block automaton, so mass is conserved exactly and two grains can never fight over a cell. | Rust · wgpu · WGSL |
| **[claudeyes](https://github.com/KieranK07/claudeyes)** | Screen perception for a coding agent. Predicts the change each action should cause, subtracts it from what actually changed, and only wakes the agent for the leftover. | Swift · Python · MCP |
| **[Nexus](https://github.com/KieranK07/Nexus)** | Self-hosted single-user life dashboard: passkey login, Gmail, calendar, net worth, smart home, a PTY in the browser. About 15k lines. | Go · React · WebAuthn |
| **[notables](https://github.com/KieranK07/notables)** | Records a lecture on the Mac, transcribes it with whisper large-v3 on a Windows GPU over Tailscale, and has Claude file the note into a Markdown vault. Nobody touches anything. | Swift · Node · whisper |
| **[class-royale](https://github.com/KieranK07/class-royale)** | Degree planner for my university, built on the scraped catalog plus your own transcript. No server of mine ever holds a student's login; a small browser extension does the one privileged fetch. | Next.js · TypeScript |
| **[roomba-controller](https://github.com/KieranK07/roomba-controller)** | Drives a Roomba 690 over its serial Open Interface, about 2 ms from keypress to wheels, plus a parametric OpenSCAD mount for the Jetson that is supposed to go on top next. | Python · OpenSCAD |
| **[authoritative-fps](https://github.com/KieranK07/authoritative-fps)** | Browser multiplayer FPS where the client only ever sends input. A 60 Hz server owns movement, collision and occlusion-checked hit registration. | Node · Socket.io · Three.js |
| **[doordle](https://github.com/KieranK07/doordle)** | Daily delivery-racing game, one shared route a day, re-scored server-side by replaying the deterministic sim. Live at [doordle.chadnerd.lol](https://doordle.chadnerd.lol). | TypeScript · Three.js · Cloudflare |

### `~$ cat contact`

[chadnerd.lol](https://chadnerd.lol)

<p align="center">
  <img src="https://raw.githubusercontent.com/KieranK07/KieranK07/output/snake.svg" alt="contribution snake" />
</p>
