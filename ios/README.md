# YardHarvest iOS

Modern SwiftUI companion app for community-garden organizers and members,
built on the **lime / Onest** design system that matches yardharvest.app.
Targets iOS 17+, written in Swift with strict concurrency in mind.

## Design language

| Token | Value | Role |
|---|---|---|
| Ink | `#22242a` | Primary text, dark CTAs |
| Lime | `#e3ff8f` | Single accent — buttons, highlights, badges |
| Canvas | `#ffffff` | Background |
| Surface | `#f2f3f3` | Subtle panels |
| Border | `#e5e6e6` | Hairlines |
| Muted | `#6b6e76` | Secondary text |
| Forest | `#1b4d3e` | Sunflower logo backdrop (preserved) |

Buttons follow `.yh-btn-dark` / `.yh-btn-ghost` / `.yh-btn-lime` from the web
side. Highlights use lime as a marker swatch. Cards are white on the canvas
with 1px borders and 12–16pt radii.

## Architecture

- **SwiftUI**, iOS 17+. No UIKit except the camera wrapper.
- **@Observable** state (Auth, GardenStore, BadgeStore).
- **`URLSession` + `async/await`**, actor-isolated client with auto JWT refresh.
- **Keychain** for tokens. Biometric session re-entry when available.
- **App Intents** for "Log Harvest" — Siri + Shortcuts entry point.
- **Skeleton loaders**, sensory feedback, animated symbol effects throughout.
- Hits the live Render backend at `https://www.yardharvest.app`.

## Build

```bash
brew install xcodegen      # or use the bundled /tmp/xcodegen/bin/xcodegen
cd ios
xcodegen
open YardHarvest.xcodeproj
```

Pick an iOS 17+ simulator, hit ⌘R.

## Project layout

```
ios/
├── project.yml
├── README.md
└── YardHarvest/
    ├── Info.plist
    ├── YardHarvestApp.swift          # @main
    ├── ContentView.swift             # Auth gate
    ├── Brand/                        # Design system (tokens + components)
    ├── Core/                         # AppEnvironment, APIClient, stores
    ├── API/                          # Endpoint extensions
    ├── Models/                       # Codable types
    ├── Features/                     # Per-screen folders
    ├── Intents/                      # App Intents (Siri / Shortcuts)
    ├── Widgets/                      # Home-screen widget(s)
    └── Resources/                    # Asset catalog
```
