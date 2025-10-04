# Block Dude Revival

A modern, browser-friendly remake of the classic TI-83 Block Dude puzzle platformer. The project uses a React + TypeScript front-end (Vite) alongside the existing Flask sandbox.

## Features

- Three handcrafted levels inspired by Block Dude.
- Keyboard-first controls with accessible status messaging.
- Simple puzzle mechanics: move, climb, pick up, and drop blocks to reach the exit door.
- Responsive pixel-art inspired styling using modern CSS.

## Getting started

### Front-end (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

The development server runs on [http://localhost:5173/](http://localhost:5173/) by default.

To build a production bundle:

```bash
npm run build
```

### Flask sandbox (optional)

The repository also contains exploratory Flask files unrelated to the game prototype. They can be run separately if needed:

```bash
python app.py
```

## SEO checklist

- Suggested title: `Block Dude Revival | Retro Puzzle Platformer`
- Meta description (already in `index.html`): `Play a modern browser remake of the classic TI-83 Block Dude puzzle platformer. Move crates, climb walls, and reach the exit across handcrafted levels.`
- Provide canonical URL via `<link rel="canonical" href="http://localhost:5173/" />` (update when deploying).
- Add an internal link from any landing page or blog post to `/` with anchor text like “Play Block Dude Revival”.
- Include descriptive alt text in future marketing imagery (e.g., `alt="Screenshot of Block Dude Revival level with stacked crates"`).
- Consider adding FAQPage JSON-LD when publishing documentation or walkthroughs.

## Notes

- No secrets are committed; environment variables are not required for the front-end demo.
- If you deploy publicly, configure a CDN or static hosting for the Vite build output for performance.
- The game logic runs entirely on the client; add rate limiting only if you later introduce networked features or leaderboards.
