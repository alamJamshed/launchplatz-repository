# LaunchPlatz Frontend Design System

A standalone React, TypeScript, and Vite component library and gallery. It contains presentation components only; it does not call the Django API.

## Development

```bash
npm install
npm run dev
```

Open the URL printed by Vite. Other useful commands:

```bash
npm run lint
npm run typecheck
npm run build
npm run preview
```

## Reuse

Import components from `src/components` and the design tokens from `src/styles/design-system.css`. Components receive data, events, and state through props, so application code can connect them to any API later.
